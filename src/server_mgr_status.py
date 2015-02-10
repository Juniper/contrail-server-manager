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
from server_mgr_defaults import *

class ServerMgrStatusThread(threading.Thread):

    _smgr_log = None
    _status_serverDb = None
    _smgr_puppet = None


    ''' Class to run function that keeps validating the cobbler token
        periodically (every 30 minutes) on a new thread. '''
    _pipe_start_app = None
    def __init__(self, timer, server, status_thread_config):
        threading.Thread.__init__(self)
        self._status_thread_config = status_thread_config
        self._smgr_puppet = status_thread_config['smgr_puppet']

    def run(self):
        #create the logger
        try:
            self._smgr_log = ServerMgrlogger()
        except:
            print "Error Creating logger object"

        # Connect to the cluster-servers database
        try:
            self._status_serverDb = db(
                "/etc/contrail_smgr/smgr_data.db")
        except:
            self._smgr_log.log(self._smgr_log.DEBUG,
                     "Error Connecting to Server Database %s"
                    % (self._args.smgr_base_dir+self._args.db_name))
            exit()

        #set the status related handlers
        status_bottle_app = Bottle()
        status_bottle_app.route('/server_status', 'POST', self.put_server_status)
        status_bottle_app.route('/server_status', 'PUT', self.put_server_status)

        try:
            bottle.run(status_bottle_app,
                       host=self._status_thread_config['listen_ip'],
                       port=self._status_thread_config['listen_port'])
        except Exception as e:
            # cleanup gracefully
            exit()

    def put_server_status(self):
        print "put-status"
        #query_args = parse_qs(urlparse(bottle.request.url).query,
                                      #keep_blank_values=True)
        #match_key, match_value = query_args.popitem()
        server_id = request.query['server_id']
        server_state = request.query['state']
        body = request.body.read()
        server_data = {}
        server_data['id'] = server_id
        server_data['status'] = server_state
        try:
            time_str = strftime(" %Y-%m-%d %H:%M:%S", gmtime())
            message = server_id + ' ' + server_state + time_str
            self._smgr_log.log(self._smgr_log.DEBUG, "Server status Data %s" % server_data)
            servers = self._status_serverDb.modify_server(
                                                    server_data)
            if server_state == "provision_completed":
                domain = self._status_serverDb.get_server_domain(server_id)
                environment_name = 'TurningOffPuppetAgent:' + time_str
                if domain:
                    self._smgr_puppet.update_node_map_file(server_id,
                                                       domain, environment_name)
            if server_state in email_events:
                self.send_status_mail(server_id, message, message)
        except Exception as e:
#            self.log_trace()
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding to db %s" % repr(e))
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
        

