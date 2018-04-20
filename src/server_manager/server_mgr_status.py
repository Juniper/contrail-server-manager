#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_manager_status.py
   Author : Abhay Joshi
   Description : This file contains code that provides REST api interface to
                 configure, get and manage configurations for servers which
                 are part of the contrail cluster of nodes, interacting
                 together to provide a scalable virtual network system.

"""


import pdb
import bottle
from bottle import route, run, request, abort, Bottle
from urlparse import urlparse, parse_qs
import time
import threading
from server_mgr_db import ServerMgrDb as db
from time import gmtime, strftime, localtime
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from send_mail import send_mail
import requests
import json
from server_mgr_defaults import *
from server_mgr_utils import *
from paramiko import *
import os
import sys
from server_mgr_ssh_client import ServerMgrSSHClient
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import gevent
import subprocess
from server_mgr_issu import *

class ServerMgrStatusThread(threading.Thread):

    _smgr_log = None
    _status_serverDb = None
    _smgr_main = None


    ''' Class to run function that keeps validating the cobbler token
        periodically (every 30 minutes) on a new thread. '''
    _pipe_start_app = None
    def __init__(self, timer, server, status_thread_config):
        threading.Thread.__init__(self)
        self._status_thread_config = status_thread_config
        self._smgr_main = status_thread_config['smgr_main']

    def run(self):
        #create the logger
        try:
            self._smgr_log = ServerMgrlogger()
        except:
            print "Error Creating logger object"

        # Connect to the cluster-servers database
        try:
            self._status_serverDb = db(
                self._smgr_main._args.server_manager_base_dir+self._smgr_main._args.database_name)
        except:
            self._smgr_log.log(self._smgr_log.DEBUG,
                     "Error Connecting to Server Database %s"
                    % (self._smgr_main._args.server_manager_base_dir+self._smgr_main._args.database_name))
            exit()

        #set the status related handlers
        status_bottle_app = Bottle()
        status_bottle_app.route('/server_status', 'POST', self.put_server_status)
        status_bottle_app.route('/server_status', 'PUT', self.put_server_status)
        status_bottle_app.route('/ansible_status', 'PUT',
                self.put_ansible_status)

        try:
            bottle.run(status_bottle_app,
                       host=self._status_thread_config['listen_ip'],
                       port=self._status_thread_config['listen_port'])
        except Exception as e:
            # cleanup gracefully
            exit()

    def check_issu_cluster_status(self, cluster):
        servers = self._status_serverDb.get_server(
                          {"cluster_id" : cluster},
                                       detail=True)
        for server in servers:
            if 'provision_completed' not in server['status']:
                return False
        return True
    # end check_issu_cluster_status

    def put_ansible_status(self):
        server_hostname= request.query['server_id']
        server_state = request.query['state']
        server_data = {}
        smutil = ServerMgrUtil()
        try:
            result = parse_qs(request.query_string)
            ansible_status = str(result['state'][0])
            test_servers = self._status_serverDb.get_server(\
                    {"ip_address" : server_hostname}, detail=True)
            if not len(test_servers):
                time_str = strftime("%Y_%m_%d__%H_%M_%S", localtime())
                message = ansible_status + ' ' + server_hostname + ' ' + time_str
                self._smgr_log.log(self._smgr_log.DEBUG, "Server status Data %s" % message)
                return
            if "provision_failed" in ansible_status:
                cur_status = test_servers[0]['status']
                if isinstance(cur_status, unicode):
                    cur_status = cur_status.encode('ascii')
                matched = 0
                for pattern in ["started", "completed", "issued"]:
                    if pattern in cur_status:
                        matched = 1
                        cur_status = cur_status.replace(pattern, "failed")
                        break
                if matched == 0:
                    cur_status = ansible_status
            else:
                cur_status = ansible_status
            server_id = test_servers[0]['id']
            server_data['id'] = server_id
            server_data['status'] = cur_status
            time_str = strftime("%Y_%m_%d__%H_%M_%S", localtime())
            message = server_id + ' ' + server_state + ' ' + time_str
            self._smgr_log.log(self._smgr_log.DEBUG, "Server status Data %s" % message)
            servers = self._status_serverDb.modify_server( server_data)
            self._smgr_main.update_provisioned_roles(server_id, cur_status)
            # if this is issu triggered provision, re-queue issu steps here
            self._smgr_log.log(self._smgr_log.DEBUG, "######### cluster is %s ##########" %servers[0]['cluster_id'])
            server = servers[0]
            cluster_id = server['cluster_id']
            cluster_det = self._status_serverDb.get_cluster({'id': cluster_id}, detail = True)[0]
            cluster_params = eval(cluster_det['parameters'])
            issu_params = cluster_params.get("issu", {})
            if issu_params.get('issu_partner', None) and \
              self.check_issu_cluster_status(cluster_id) and \
              (issu_params.get('issu_clusters_synced', "false") == "false"):
                self._smgr_main.issu_obj = None
                old_cluster = issu_params['issu_partner']
                new_cluster = cluster_id
                new_image = issu_params['issu_image']
                compute_tag = issu_params.get('issu_compute_tag', '')
                provision_item = ('issu', old_cluster, new_cluster,
                                                     new_image, compute_tag)
                self._smgr_main._reimage_queue.put_nowait(provision_item)
                self._smgr_log.log(self._smgr_log.DEBUG, "ISSU sync job queued")
            # if this is compute being rolled back, remove vrouter mod and restart vrouter svc
            server_det = self._status_serverDb.get_server({'id': server_id}, detail = True)[0]
            server_params = eval(server_det['parameters'])
            if server_params.get("compute-rollback", None) == cluster_id:
                cmd = "service supervisor-vrouter stop && " \
                      "rmmod vrouter && " \
                      "service supervisor-vrouter start"
                ssh_handl = paramiko.SSHClient()
                ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_handl.connect(server['ip_address'],
                          username = server.get('username', 'root'),
                          password = smutil.get_password(server,self._status_serverDb))
                # for bug 1648268 collect output for the failed command
                i, o, err = ssh_handl.exec_command(cmd)
                self._smgr_log.log(self._smgr_log.DEBUG, 
                                   "ISSU-ROLLBACK: rmmod op is %s" %(
                                                           o.read()))
                self._smgr_log.log(self._smgr_log.DEBUG, 
                                   "ISSU-ROLLBACK: rmmod err is %s" %(
                                                          err.read()))
                # remove the rollback flag
                server_data = {"id": server["id"],
                               "parameters": {
                                    "compute-rollback": None
                                   }
                              }
                self._status_serverDb.modify_server(server_data)
        except Exception as e:
            #self.log_trace()
            self._smgr_log.log(self._smgr_log.ERROR,
                               "HOST: %s Error modifying server db %s" %
                               (server_hostname, repr(e)))
            abort(404, repr(e))

    def put_server_status(self):
        print "put-status"
        #query_args = parse_qs(urlparse(bottle.request.url).query,
                                      #keep_blank_values=True)
        #match_key, match_value = query_args.popitem()
        smutil = ServerMgrUtil()
        server_hostname= request.query['server_id'].lower()
        server_state = request.query['state']
        body = request.body.read()
        server_data = {}
        test_servers = self._status_serverDb.get_server({"host_name" : server_hostname}, detail=True)
        server_id = test_servers[0]['id']
        server_data['id'] = server_id
        if server_state == "post_provision_completed":
            server_data['status'] = "provision_completed"
        else:
            server_data['status'] = server_state
        try:
            time_str = strftime("%Y_%m_%d__%H_%M_%S", localtime())
            message = server_id + ' ' + server_state + ' ' + time_str
            self._smgr_log.log(self._smgr_log.DEBUG, "Server status Data %s" % message)
            servers = self._status_serverDb.modify_server( server_data)
            if server_state == "reimage_completed":
                payload = dict()
                payload["id"] = server_id
                #self._smgr_log.log(self._smgr_log.DEBUG, "Spawning Gevent for Id: %s" % payload["id"])
            if server_state == "provision_started":
                self._smgr_main.update_provision_started_flag(server_id, server_state)
            self._smgr_main.update_provision_role_sequence(server_id,
                                                           server_state)
            self._smgr_main.update_provisioned_roles(server_id, server_state)
            if server_state == "post_provision_completed":
                server_state = "provision_completed"

            if server_state == "provision_completed":
                domain = self._status_serverDb.get_server_domain(server_id)
                environment_name = 'TurningOffPuppetAgent__' + time_str
                if domain:
                    server_fqdn = server_hostname + "." + domain
                servers = self._status_serverDb.get_server({"host_name" : server_hostname}, detail=True)
                server = servers[0]
                # if this is issu triggered provision, re-queue issu steps here
                cluster_id = server['cluster_id']
                cluster_det = self._status_serverDb.get_cluster({'id': cluster_id}, detail = True)[0]
                cluster_params = eval(cluster_det['parameters'])
                issu_params = cluster_params.get("issu", {})
                if issu_params.get('issu_partner', None) and \
                  self.check_issu_cluster_status(cluster_id) and \
                  (issu_params.get('issu_clusters_synced', "false") == "false"):
                    self._smgr_main.issu_obj = None
                    old_cluster = issu_params['issu_partner']
                    new_cluster = cluster_id
                    new_image = issu_params['issu_image']
                    compute_tag = issu_params.get('issu_compute_tag', '')
                    provision_item = ('issu', old_cluster, new_cluster,
                                                             new_image, compute_tag)
                    self._smgr_main._reimage_queue.put_nowait(provision_item)
                    self._smgr_log.log(self._smgr_log.DEBUG, "ISSU sync job queued")
                # if this is compute being rolled back, remove vrouter mod and restart vrouter svc
                server_det = self._status_serverDb.get_server({'id': server_id}, detail = True)[0]
                server_params = eval(server_det['parameters'])
                if server_params.get("compute-rollback", None) == cluster_id:
                    cmd = "service supervisor-vrouter stop && " \
                          "rmmod vrouter && " \
                          "service supervisor-vrouter start"
                    ssh_handl = paramiko.SSHClient()
                    ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh_handl.connect(server['ip_address'],
                              username = server.get('username', 'root'),
                              password = smutil.get_password(server,self._status_serverDb))
                    # for bug 1648268 collect output for the failed command
                    i, o ,err = ssh_handl.exec_command(cmd)
                    self._smgr_log.log(self._smgr_log.DEBUG, 
                                       "ISSU-ROLLBACK: rmmod op is %s" %(
                                                               o.read()))
                    self._smgr_log.log(self._smgr_log.DEBUG, 
                                       "ISSU-ROLLBACK: rmmod err is %s" %(
                                                              err.read()))
                    # remove the rollback flag
                    server_data = {"id": server["id"],
                                   "parameters": {
                                        "compute-rollback": None
                                        }
                                  }
                    self._status_serverDb.modify_server(server_data)
            if server_state in email_events:
                self.send_status_mail(server_id, message, message)
        except Exception as e:
            #self.log_trace()
            self._smgr_log.log(self._smgr_log.ERROR, "HOST: %s: Error adding to db %s" % (server_id, repr(e)))
            abort(404, repr(e))

    def get_email_list(self, email):
        email_to = []
        if not email:
            return email_to
        if email.startswith('[') and email.endswith(']'):
            email_to = eval(email)
        else:
            email_to = [s.strip() for s in email.split(',')]
        return email_to
    # end get_email_list

    def send_status_mail(self, server_id, event, message):
        # Get server entry and find configured e-mail
        servers = self._status_serverDb.get_server(
            {"id" : server_id}, detail=True)
        if not servers:
            msg = "No server found with server_id " + server_id
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return -1
        server = servers[0]
        email_to = []
        if 'email' in server and server['email']:
            email_to = self.get_email_list(server['email'])
        else:
            # Get cluster entry to find configured e-mail
            if 'cluster_id' in server and server['cluster_id']:
                cluster_id = server['cluster_id']
                cluster = self._status_serverDb.get_cluster(
                    {"id" : cluster_id}, detail=True)
                if cluster and 'email' in cluster[0] and cluster[0]['email']:
                        email_to = self.get_email_list(cluster[0]['email'])
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                       "cluster or server doesn't configured for email")
                    return 0
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "server not associated with a cluster")
                return 0
        send_mail(event, message, '', email_to,
                                    self._status_thread_config['listen_ip'], '25')
        msg = "An email is sent to " + ','.join(email_to) + " with content " + message
        self._smgr_log.log(self._smgr_log.DEBUG, msg)
    # send_status_mail



