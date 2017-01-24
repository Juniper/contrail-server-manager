#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_manager.py
   Author : Abhay Joshi
   Description : This file contains code that provides REST api interface to
                 configure, get and manage configurations for servers which
                 are part of the contrail cluster of nodes, interacting
                 together to provide a scalable virtual network system.
"""
import os
import glob
import sys
import re
import datetime
import json
import argparse
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import subprocess
import bottle
from bottle import route, run, request, abort
import ConfigParser
import paramiko
import base64
import shutil
import string
import tarfile
from urlparse import urlparse, parse_qs
from time import gmtime, strftime, localtime
import pdb
import server_mgr_db
import ast
import uuid
import traceback
import platform
from netaddr import *
import copy
import distutils.core
from server_mgr_defaults import *
from server_mgr_err import *
from server_mgr_status import *
from server_mgr_db import ServerMgrDb as db
from server_mgr_certs import ServerMgrCerts
from server_mgr_utils import *
from server_mgr_ssh_client import ServerMgrSSHClient
from server_mgr_issu import *
from generate_dhcp_template import *
sys.path.append(os.path.join(os.path.dirname(__file__), 'ansible'))
from sm_ansible_utils import send_REST_request
from sm_ansible_utils import _container_img_keys
from sm_ansible_utils import _valid_roles
from server_mgr_docker import SM_Docker

try:
    from server_mgr_cobbler import ServerMgrCobbler as ServerMgrCobbler
except ImportError:
    pass
try:
    from server_mgr_mon_base_plugin import ServerMgrMonBasePlugin
except ImportError:
    pass
from server_mgr_puppet import ServerMgrPuppet as ServerMgrPuppet
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_validations import ServerMgrValidations as ServerMgrValidations
import json
import pycurl
import xmltodict
from StringIO import StringIO
import requests
import tempfile
from contrail_defaults import *

from gevent import monkey
monkey.patch_all()
import gevent
from gevent.queue import Queue

bottle.BaseRequest.MEMFILE_MAX = 2 * 102400

_WEB_HOST = '127.0.0.1'
_WEB_PORT = 9001
_ANSIBLE_PROVISION_START_ENDPOINT = 'start_provision'
_ANSIBLE_PROVISION_ENDPOINT = 'run_playbook'
_ANSIBLE_SRVR_PORT = 9003
_DEF_CFG_DB = 'cluster_server_mgr.db'
_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_SERVER_TAGS_FILE = 'tags.ini'
_DEF_HTML_ROOT_DIR = '/var/www/html/'
_DEF_COBBLER = 'True'
_DEF_MONITORING = 'True'
_DEF_COBBLER_IP = '127.0.0.1'
_DEF_COBBLER_PORT = None
_DEF_COBBLER_USERNAME = 'cobbler'
_DEF_COBBLER_PASSWORD = 'cobbler'
_DEF_IPMI_USERNAME = 'ADMIN'
_DEF_IPMI_PASSWORD = 'ADMIN'
_DEF_IPMI_TYPE = 'ipmilan'
_DEF_IPMI_INTERFACE = None
_DEF_PUPPET_DIR = '/etc/puppet/'
_DEF_COLLECTORS_IP = "['127.0.0.1:8086']"
_DEF_INTROSPECT_PORT = 8107
_DEF_SANDESH_LOG_LEVEL = 'SYS_INFO'
_DEF_ROLE_SEQUENCE_DEF_FILE = _DEF_SMGR_BASE_DIR + 'role_sequence.json'
_CONTRAIL_CENTOS_REPO = 'contrail-centos-repo'
_CONTRAIL_REDHAT_REPO = 'contrail-redhat-repo'
_DEF_SMGR_PROVISION_LOGS_DIR = '/var/log/contrail-server-manager/provision/'
_DEF_PUPPET_AGENT_RETRY_COUNT = 10
_DEF_PUPPET_AGENT_RETRY_POLL_INTERVAL = 20
# Temporary variable added to disable use of new puppet framework. This should be removed/enabled
# only after the new puppet framework has been fully tested. Value is set to TRUE for now, remove
# this variable and it's use when enabling new puppet framework.
_ENABLE_NEW_PUPPET_FRAMEWORK = True
_ERR_INVALID_CONTRAIL_PKG = 'Invalid contrail package. Please specify a valid package'

@bottle.error(403)
def error_403(err):
    return err.body
# end error_403


@bottle.error(404)
def error_404(err):
    return err.body
# end error_404


@bottle.error(409)
def error_409(err):
    return err.body
# end error_409


@bottle.error(500)
def error_500(err):
    return err.body
# end error_500


@bottle.error(503)
def error_503(err):
    return err.body
# end error_503

class VncServerManager():
    '''
    This is the main class that makes use of bottle package to provide rest
    interface for the server manager. This class serves rest APIs and then
    processes cluster, server and nodes classes in accordance with information
    provided in the REST calls.
    '''
    _smgr_log = None
    _smgr_trans_log = None
    _tags_list = ['tag1', 'tag2', 'tag3', 'tag4',
                  'tag5', 'tag6', 'tag7']
    _image_list = ["centos", "fedora", "ubuntu", "redhat",
                   "contrail-ubuntu-package", "contrail-centos-package",
                   "contrail-storage-ubuntu-package",
                   "esxi5.5", "esxi5.1", "contrail-container-ubuntu"]
    _iso_types = ["centos", "redhat", "ubuntu", "fedora", "esxi5.1", "esxi5.5"]

    # Add here for each container that is built
    _contrail_container_list = ["contrail-container-ubuntu"]
    _package_types = ["contrail-ubuntu-package", "contrail-centos-package",
                      "contrail-storage-ubuntu-package",
                      "contrail-container-ubuntu"]
    _image_category_list = ["image", "package", "container"]
    _control_roles = ['global_controller', 'loadbalancer', 'database',
            'openstack', 'config', 'control', 'collector', 'webui']
    _role_sequence = [(['haproxy'], 'p'),
                      (['loadbalancer'], 'p'),
                      (['database'], 'p'), (['openstack'], 'p'),
                      (['config'], 'p'), (['control'], 'p'), (['global_controller'], 'p'),
                      (['collector'], 'p'), (['webui'], 'p')]
    _role_step_sequence_ha = [(['keepalived'], 'p'), (['haproxy'], 'p'),
                      (['loadbalancer'], 'p'),
                      (['database'], 'p'), (['openstack'], 'p'),
                      (['pre_exec_vnc_galera'], 's'),
                      (['post_exec_vnc_galera'], 's'),
                      (['config'], 'p'), (['control'], 'p'), (['global_controller'], 'p'),
                      (['collector'], 'p'), (['webui'], 'p')]

    _role_step_sequence_contrail_ha = [(['keepalived'], 'p'), (['haproxy'], 'p'),
                      (['loadbalancer'], 'p'),
                      (['database'], 'p'), (['openstack'], 'p'),
                      (['config'], 'p'), (['control'], 'p'), (['global_controller'], 'p'),
                      (['collector'], 'p'), (['webui'], 'p')]

    #_role_sequence = [(['database', 'openstack', 'config', 'control', 'collector', 'webui'], 'p')]
    #_role_sequence = [(['database', 'openstack', 'config', 'control', 'collector', 'webui'], 's')]
    _compute_roles = ['compute', 'tsn', 'toragent','storage-compute', 'storage-master']
    _roles = _control_roles + _compute_roles
    _control_step_roles = ['global_controller', 'loadbalancer', 'database', 'openstack', 'config', 'control', 'collector', 'webui']
    _compute_step_roles = ['compute', 'tsn', 'toragent','storage-compute', 'storage-master']
    _openstack_steps = ['pre_exec_vnc_galera', 'post_exec_vnc_galera', 'keepalived', 'haproxy']
    _role_steps = _control_roles + _openstack_steps + _compute_roles
    _control_step_roles = ['global_controller', 'loadbalancer', 'database', 'openstack', 'config', 'control', 'collector', 'webui']
    _compute_step_roles = ['compute', 'storage-compute', 'storage-master']
    _step_roles = _control_step_roles + _compute_step_roles
    _tags_dict = {}
    _rev_tags_dict = {}
    _monitoring_base_plugin_obj = None
    _monitoring_config_set = False
    _inventory_config_set = False
    _monitoring_gevent_thread_obj = None
    # dict to hold cfg defaults
    _cfg_defaults_dict = {}
    #dict to hold code defaults
    _code_defaults_dict = {}
    _smgr_config = None
    _dhcp_host_key_list = ["host_fqdn","ip_address","mac_address","host_name"]
    _dhcp_subnet_key_list = ["subnet_address","subnet_mask","subnet_gateway","subnet_domain",
        "search_domains_list","dns_server_list","default_lease_time", "max_lease_time"]
    _server_mask_list = ["password"]
    _cluster_mask_list = ["parameters.password",
                          "parameters.keystone_password",
                          "parameters.keystone_admin_token",
                          "parameters.mysql_root_password",
                          "parameters.mysql_service_password",
                          "parameters.heat_encryption_key",
                          #New Params
                          "parameters.provision.openstack.keystone.admin_password",
                          "parameters.provision.openstack.keystone.admin_token",
                          "parameters.provision.openstack.mysql.root_password",
                          "parameters.provision.openstack.mysql.service_password",
                          "parameters.provision.openstack.glance.password",
                          "parameters.provision.openstack.cinder.password",
                          "parameters.provision.openstack.swift.password",
                          "parameters.provision.openstack.nova.password",
                          "parameters.provision.openstack.horizon.password",
                          "parameters.provision.openstack.neutron.password",
                          "parameters.provision.openstack.heat.password",
                          "parameters.provision.openstack.heat.encryption_key",
                          "parameters.provision.openstack.ceilometer.password",
                          "parameters.provision.openstack.ceilometer.mongo",
                         ]
    #fileds here except match_keys, obj_name and primary_key should
    #match with the db columns

    def _is_cobbler_enabled(self, cobbler):
        if cobbler.lower() == 'true':
            return True
        else:
            return False

    def _is_monitoring_enabled(self, monitoring):
        if monitoring.lower() == 'true':
            return True
        else:
            return False

    def _do_puppet_kick(self, host_ip):
        msg = "Puppet kick trigered for %s" % (host_ip)
        self._smgr_log.log(self._smgr_log.INFO, msg)

        try:
            rc = subprocess.check_call(
                    ["puppet", "kick", "--host", host_ip])
            # Log, return error if return code is non-null - TBD Abhay
        except subprocess.CalledProcessError as e:
            msg = ("put_image: error %d when executing"
                       "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)

    def merge_dict(self, d1, d2):
        for k,v2 in d2.items():
            v1 = d1.get(k) # returns None if v1 has no value for this key
            if ( isinstance(v1, dict) and
                 isinstance(v2, dict) ):
                self.merge_dict(v1, v2)
            elif v1:
                #do nothing, Retain value
                msg = "%s already present in dict d1," \
                    "Retaining value %s against %s" % (k, v1, v2)
                self._smgr_log.log(self._smgr_log.INFO, msg)
            else:
                #do nothing, Retain value
                msg = "adding %s:%s" % (k, v1)
                self._smgr_log.log(self._smgr_log.INFO, msg)
                d1[k] = copy.deepcopy(v2)

    def _cfg_parse_defaults(self, cfg_def_objs):
        defaults_dict = {}
        cur_dict = defaults_dict
        for k,v in cfg_def_objs.items():
            d_dict = v
            cur_dict = defaults_dict
            if k in cur_dict:
                cur_dict_l1 = cur_dict[k]
                continue
            else:
                new_dict = {}
                cur_dict[k] = new_dict
                previous_dict_l1 = cur_dict
                cur_dict_l1 = new_dict
            for k,v in d_dict.items():
                cur_dict = cur_dict_l1
                dict_key_list = k.split(".")
                for x in dict_key_list:
                    if x in cur_dict:
                        cur_dict = cur_dict[x]
                        continue
                    else:
                        new_dict = {}
                        cur_dict[x] = new_dict
                        previous_dict = cur_dict
                        cur_dict = new_dict
                previous_dict[x] = v

        return defaults_dict

    def _prepare_code_defaults(self):
        code_defaults_dict = {}
        obj_list = {"server" : server_fields, "cluster": cluster_fields,
            "image": image_fields, "dhcp_host": dhcp_host_fields, "dhcp_subnet": dhcp_subnet_fields}
        for obj_name, obj in obj_list.items():
            obj_cpy = obj.copy()
            pop_items = ["match_keys", "obj_name", "primary_keys"]
            obj_cpy.pop("match_keys")
            obj_cpy.pop("obj_name")
            obj_cpy.pop("primary_keys")
            parameters = eval(obj_cpy.get("parameters", {}))
            obj_cpy["parameters"] = parameters
            code_defaults_dict[obj_name] = obj_cpy
        return code_defaults_dict

    def __init__(self, args_str=None):
        self._args = None
        #Create an instance of logger
        try:
            self._smgr_log = ServerMgrlogger()
        except:
            print "Error Creating logger object"

        self._smgr_log.log(self._smgr_log.INFO, "Starting Server Manager")


        #Create an instance of Transaction logger
        try:
            self._smgr_trans_log = ServerMgrTlog()
        except:
            print "Error Creating Transaction logger object"

        try:
            self._smgr_validations = ServerMgrValidations()
        except:
            print "Error Creating ServerMgrValidations object"

        if not args_str:
            args_str = sys.argv[1:]
        self._parse_args(args_str)
        self._cfg_obj_defaults = self._read_smgr_object_defaults(self._smgr_config)
        self._cfg_defaults_dict = self._cfg_parse_defaults(self._cfg_obj_defaults)
        self._code_defaults_dict = self._prepare_code_defaults()
        self._docker_cli = SM_Docker()

        # Reads the tags.ini file to get tags mapping (if it exists)
        if os.path.isfile(self._args.server_manager_base_dir + _SERVER_TAGS_FILE):
            tags_config = ConfigParser.SafeConfigParser()
            tags_config.read(self._args.server_manager_base_dir + _SERVER_TAGS_FILE)
            tags_config_dict = dict(tags_config.items("TAGS"))
            for key, value in tags_config_dict.iteritems():
                if key not in self._tags_list:
                    self._smgr_log.log(
                        self._smgr_log.ERROR,
                        "Invalid tag %s in tags ini file"
                        %(key))
                    exit()
                if value:
                    self._tags_dict[key] = value
                    self._rev_tags_dict[value] = key
        # end if os.path.isfile()

        # Connect to the cluster-servers database
        try:
            self._serverDb = db(
                self._args.server_manager_base_dir+self._args.database_name)
        except:
            self._smgr_log.log(self._smgr_log.ERROR,
                     "Error Connecting to Server Database %s"
                    % (self._args.server_manager_base_dir+self._args.database_name))
            exit()

        # Add server tags to the DB
        try:
            self._serverDb.add_server_tags(self._tags_dict)
        except:
            self._smgr_log.log(
                self._smgr_log.ERROR,
                "Error adding server tags to server manager DB")
            exit()

        # Create an instance of cobbler interface class and connect to it.
        try:
            self._smgr_cobbler = None
            if self._is_cobbler_enabled(self._args.cobbler):
                self._smgr_cobbler = ServerMgrCobbler(self._args.server_manager_base_dir,
                                 self._args.cobbler_ip_address,
                                 self._args.cobbler_port,
                                 self._args.cobbler_username,
                                 self._args.cobbler_password)
            # Copy contrail centos/redhat repo to cobber repos, so that target
            # systems can install and run puppet agent from kickstart.
            if self._smgr_cobbler:
                self._smgr_cobbler._init_create_repo(
                    _CONTRAIL_CENTOS_REPO, self._args.server_manager_base_dir)
                self._smgr_cobbler._init_create_repo(
                    _CONTRAIL_REDHAT_REPO, self._args.server_manager_base_dir)
        except Exception as e:
            print "Error connecting to cobbler, please check username and password in config file."
            self._smgr_log.log(self._smgr_log.ERROR,
                     "Error connecting to cobbler: %s" % (repr(e)))
            exit()

        # Create an instance of puppet interface class.
        try:
            # TBD - Puppet parameters to be added.
            self._smgr_puppet = ServerMgrPuppet(self._args.server_manager_base_dir,
                                                self._args.puppet_dir)
        except:
            self._smgr_log.log(self._smgr_log.ERROR, "Error creating instance of puppet object")
            exit()

        # Start gevent thread for reimage task.
        self._reimage_queue = Queue()
        gevent.spawn(self._reimage_server_cobbler)

        try:
            # needed for testing...
            status_thread_config = {}
            status_thread_config['listen_ip'] = self._args.listen_ip_addr
            status_thread_config['listen_port'] = '9002'
            status_thread_config['base_obj'] = self._monitoring_base_plugin_obj
            status_thread_config['smgr_puppet'] = self._smgr_puppet
            status_thread_config['smgr_main'] = self
            status_thread = ServerMgrStatusThread(
                            None, "Status-Thread", status_thread_config)
            # Make the thread as daemon
            status_thread.daemon = True
            status_thread.start()
        except:
            self._smgr_log.log(self._smgr_log.ERROR,
                     "Error starting the status thread")
            exit()

        # Generate SM Certs
        self._smgr_certs = ServerMgrCerts()
        sm_private_key, sm_cert = self._smgr_certs.create_sm_ca_cert()

        # Read the JSON file, validate for correctness and add the entries to
        # our DB.
        if self._args.server_list is not None:
            try:
                server_file = open(self._args.server_list, 'r')
                json_data = server_file.read()
                server_file.close()
            except IOError:
                self._smgr_log.log(self._smgr_log.ERROR,
                    "Error reading initial config file %s") \
                    % (self._args.server_list)
                exit()
            try:
                self.config_data = json.loads(json_data)
                self._smgr_log.log(self._smgr_log.DEBUG,
                    "Server list is %s" % self.config_data)

            except Exception as e:
                print repr(e)
                self._smgr_log.log(self._smgr_log.ERROR,
                    "Initial config file %s format error. "
                    "File should be in JSON format") \
                    % (self._args.server_list)
                exit()
            # Validate the config for sematic correctness.
            self._validate_config(self.config_data)
            # Store the initial configuration in our DB
            try:
                self._create_server_manager_config(self.config_data)
            except Exception as e:
                print repr(e)
                self._smgr_log.log(self._smgr_log.ERROR,
                    "Error adding initial config to SM Db. "
                    "The following config data couldn't be added:\n%s") \
                    % (self.config_data)
        self._monitoring_base_plugin_obj.initialize_features(sm_args=self._args, serverdb=self._serverDb)
        #Create and copy the ssh keys in the target servers if they are not already present
        #This will cover the upgrade case where none of the servers may have the key in it
        gevent.spawn(self._monitoring_base_plugin_obj.setup_keys, self._serverDb)

        #Generate the DHCP template for the SM host only such that cobbler works correctly
        self._using_dhcp_management = False
        self._dhcp_template_obj = DHCPTemplateGenerator(self._serverDb)
        dhcp_hosts = self._serverDb.get_dhcp_host()
        dhcp_subnets = self._serverDb.get_dhcp_subnet()
        if len(dhcp_hosts) > 1 and len(dhcp_subnets):
            self._using_dhcp_management = True

        self._base_url = "http://%s:%s" % (self._args.listen_ip_addr,
                                           self._args.listen_port)
        self._pipe_start_app = bottle.app()

        # All bottle routes to be defined here...
        # REST calls for GET methods (Get Info about existing records)
        bottle.route('/all', 'GET', self.get_server_mgr_config)
        bottle.route('/cluster', 'GET', self.get_cluster)
        bottle.route('/server', 'GET', self.get_server)
        bottle.route('/image', 'GET', self.get_image)
        bottle.route('/status', 'GET', self.get_status)
        bottle.route('/server_status', 'GET', self.get_server_status)
        bottle.route('/provision_status', 'GET', self.get_provision_status)
        bottle.route('/chassis-id', 'GET', self.get_server_chassis_id)
        bottle.route('/tag', 'GET', self.get_server_tags)
        bottle.route('/log', 'GET', self.get_server_logs)
        bottle.route('/columns', 'GET', self.get_table_columns)
        bottle.route('/dhcp_subnet', 'GET', self.get_dhcp_subnet)
        bottle.route('/dhcp_host', 'GET', self.get_dhcp_host)
        bottle.route('/MonitorConf', 'GET', self._server_monitoring_obj.get_mon_conf_details)
        bottle.route('/MonitorInfo', 'GET', self._server_monitoring_obj.get_monitoring_info)
        bottle.route('/MonitorInfoSummary', 'GET', self._server_monitoring_obj.get_monitoring_info_summary)
        bottle.route('/InventoryConf', 'GET', self._server_inventory_obj.get_inv_conf_details)
        bottle.route('/InventoryInfo', 'GET', self._server_inventory_obj.get_inventory_info)
        bottle.route('/defaults', 'GET', self.get_defaults)

        #bottle.route('/logs/<filepath:path>', 'GET', self.get_defaults)
        @route('/logs/<filename:re:.*>')
        def callback(filename):
            colorinfo = ['<tr style = "background-color:skyblue">','<tr>'] #CSS to color alternate rows
            show_hidden = False
            serve_path = "/var/log/contrail-server-manager/provision"
            i=1  #To alternate background color
            path = serve_path + filename
            html = '''<html>
            <head><title>Listing</title>
            <style>

            </style>
            </head>
            <body><a href = '..'>Previous Folder</a><br><hr>
            <table border=0>'''
            cwd = os.getcwd()
            if(os.path.isfile(path)):
                if(os.path.split(path)[-1][0]=='.' and show_hidden==False): #Allow accessing hidden files?
                    return "404! Not found."
                bottle.response.set_header('Content-Type', 'text/plain')
                with open(serve_path+ filename) as f:  # <-- you'll need the correct path here, possibly including "articles"
                    stat_art = f.read()
                return stat_art   #serve a file
            else:
                try:
                    os.chdir(path)
                    files = filter(os.path.isfile, glob.glob("*"))
                    dirs = filter(os.path.isdir, glob.glob("*"))
                    objs = files + dirs
                    objs.sort(key=lambda x: os.path.getmtime(x))
                    for x in objs:
                        if x==os.path.split(__file__)[-1] or (x[0]=='.' and show_hidden==False):  #Show hidden files?
                            continue
                        scheme = bottle.request.urlparts[0]	#get the scheme of the requested url
                        host = bottle.request.urlparts[1]	#get the hostname of the requested url
                        if i==0:    #alternate rows are colored
                            i+=1
                        else:
                            i=0
                        #just html formatting :D
                        file_mod_time = time.strftime('%a, %d %b %Y %H:%M:%S +0000"', time.gmtime(os.path.getmtime(x)))
                        html = html+colorinfo[i]+"<td><a href = '"+scheme+"://"+host+"/logs/"+filename+"/"+x+"'>"+x+"</a></td><td>" + file_mod_time +"</td></tr>"
                except Exception as e:  #Actually an error accessing the file or switching to the directory
                    html = "404! Not found."
                finally:
                    os.chdir(cwd)
            os.chdir(cwd)
            return html+"</table><hr><br><br></body></html>" #Append the remaining html code


        # REST calls for PUT methods (Create New Records)
        bottle.route('/all', 'PUT', self.create_server_mgr_config)
        bottle.route('/image/upload', 'PUT', self.upload_image)
        bottle.route('/status', 'PUT', self.put_status)

        #smgr_add
        bottle.route('/server', 'PUT', self.put_server)
        bottle.route('/image', 'PUT', self.put_image)
        bottle.route('/cluster', 'PUT', self.put_cluster)
        bottle.route('/tag', 'PUT', self.put_server_tags)
        bottle.route('/dhcp_subnet', 'PUT', self.put_dhcp_subnet)
        bottle.route('/dhcp_host', 'PUT', self.put_dhcp_host)

        # REST calls for DELETE methods (Remove records)
        bottle.route('/cluster', 'DELETE', self.delete_cluster)
        bottle.route('/server', 'DELETE', self.delete_server)
        bottle.route('/image', 'DELETE', self.delete_image)
        bottle.route('/dhcp_subnet', 'DELETE', self.delete_dhcp_subnet)
        bottle.route('/dhcp_host', 'DELETE', self.delete_dhcp_host)

        # REST calls for POST methods
        if self._smgr_cobbler:
            bottle.route('/server/reimage', 'POST', self.reimage_server)
            bottle.route('/server/restart', 'POST', self.restart_server)
            bottle.route('/dhcp_event', 'POST', self.process_dhcp_event)
        bottle.route('/server/provision', 'POST', self.provision_server)
        bottle.route('/interface_created', 'POST', self.interface_created)
        bottle.route('/run_inventory', 'POST', self._server_inventory_obj.run_inventory)

    def get_pipe_start_app(self):
        return self._pipe_start_app
    # end get_pipe_start_app

    def get_server_ip(self):
        return self._args.listen_ip_addr
    # end get_server_ip

    def get_server_port(self):
        return self._args.listen_port
    # end get_server_port

    # REST API call to get sever manager config - configuration of all
    # clusters & all servers is returned.
    def get_server_mgr_config(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server_mgr_config")
        config = {}
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Check if request arguments has detail parameter
            detail = ("detail" in query_args)
            config['cluster'] = self._serverDb.get_cluster(detail=detail)
            config['server'] = self._serverDb.get_server(detail=detail)
            config['image'] = self._serverDb.get_image(detail=detail)
            # always call get_server_tags with detail=True
            config['tag'] = self._serverDb.get_server_tags(detail=True)
            config['dhcp_host'] = self._serverDb.get_dhcp_host()
            config['dhcp_subnet'] = self._serverDb.get_dhcp_subnet()
        except Exception as e:
            #self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_ALL,
                                     #False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR, None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_CFG_ALL)
        self._smgr_log.log(self._smgr_log.DEBUG, "Config returned: %s" % (config))
        return config
    # end get_server_mgr_config

    def get_table_columns(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_table_columns")
        query_args = parse_qs(urlparse(request.url).query,
                              keep_blank_values=True)
        table_name = query_args.get('table', None)
        if not table_name:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_TABLE_COLUMNS,
                                     False)
            resp_msg = self.form_operartion_data('table not present', ERR_GENERAL_ERROR, None)
            abort(404, resp_msg)
        table_columns = self._serverDb.get_table_columns(table_name[0])
        self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.GET_SMGR_CFG_TABLE_COLUMNS)
        self._smgr_log.log(self._smgr_log.DEBUG, "Db returned columns for %s: %s" % (table_name[0], table_columns))
        return table_columns
    # end get_table_columns

    # REST API call to get sever manager config - configuration of all
    # CLUSTERs, with all servers and roles is returned. This call
    # provides all the configuration as in get_server_mgr_config() call
    # above. This call additionally provides a way of getting all the
    # configuration for a particular cluster.
    def get_cluster(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_cluster")
        try:
            ret_data = self.validate_smgr_request("CLUSTER", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                select_clause = ret_data["select"]
                match_dict = {}
                if match_key:
                    match_dict[match_key] = match_value
                detail = ret_data["detail"]
                entity = self._serverDb.get_cluster(
                    match_dict, detail=detail,
                    field_list=select_clause)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_CLUSTER,
                                     False)

            resp_msg = self.form_operartion_data(e.msg, ERR_IMG_TYPE_INVALID,
                                                                    None)
            abort(404, resp_msg)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_CLUSTER,
                                     False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR, None)
            abort(404, resp_msg)
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_CLUSTER,
                                     False)
        self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.GET_SMGR_CFG_CLUSTER)
        for x in entity:
            if x.get("parameters", None) is not None:
                x['parameters'] = eval(x['parameters'])
            self.hide_passwords(x, self._cluster_mask_list)
        return {"cluster": entity}
    # end get_cluster

    def get_server_logs(self):
        try:
            query_args = parse_qs(bottle.request.query_string,
                                    keep_blank_values=True)
            if not query_args:
                self._smgr_log.log(self._smgr_log.ERROR,
                        "required parameter --server_id missing")
                resp_msg = self.form_operartion_data(
                        "Usage: server-manager show logs --server_id <id> [--file <log_file_on_server>]", ERR_GENERAL_ERROR,
                    None)
                return resp_msg
            else:
                sid = query_args.get('id', None)
                fname = query_args.get('file', None)
                remote_dir = '/var/log/contrail/'

                server = self._serverDb.get_server(
                    {"id" : sid[0]}, detail=True)
                ssh_client = self.create_ssh_connection(server[0]['ip_address'],
                    'root', server[0]['password'])
                sftp_client = ssh_client.open_sftp()

                logs = []
                dict_name = None
                if fname == None:
                    # Return list of log files in the /var/log/contrail directory
                    # logs.append("\nList of log files on server %s:\n" % sid[0])
                    for filename in sftp_client.listdir(remote_dir):
                        logs.append(filename)
                    dict_name = "log files"
                else:
                    # Retrun content of speciied log file
                    remote_file = remote_dir + fname[0]
                    remote_fd = sftp_client.open(remote_file)
                    dict_name = fname[0]
                    try:
                        for line in remote_fd:
                            logs.append(line)
                    finally:
                        remote_fd.close()

                sftp_client.close()
                return {dict_name: logs}

        except Exception as e:
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                    None)
            abort(404, resp_msg)

    # REST API call to get list of server tags. The tags are read from
    # .ini file and stored in DB. There is also a copy maintained in a
    # dictionary. Since all these are synced up, we return info from
    # dictionaty variable itself.
    def get_server_tags(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server_tags")
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                    keep_blank_values=True)
            tag_dict = self._tags_dict.copy()
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_TAG,
                                     False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.GET_SMGR_CFG_TAG)

        return tag_dict
    # end get_server_tags

    def validate_smgr_entity(self, type, entity):
        obj_list = entity.get(type, None)
        if obj_list is None:
           msg = "%s data not available in JSON" % \
                        type
           self.log_and_raise_exception(msg)

    def validate_smgr_get(self, validation_data, request, data=None):
        ret_data = {}
        ret_data['status'] = 1
        query_args = parse_qs(urlparse(request.url).query,
                                    keep_blank_values=True)
        detail = ("detail" in query_args)
        query_args.get("detail", None)

	query_args.pop("show_pass", None)

        match_key = None
        match_value = None
        select_clause = self.get_select_clause(query_args)
        if ((detail == True and len(query_args) == 1) or\
                (detail == False and len(query_args) == 0) or\
                (detail == False and len(query_args) == 1 and select_clause)):
            ret_data["status"] = 0
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_value
            ret_data["detail"] = detail
        elif len(query_args) >= 1:
            match_keys_str = validation_data['match_keys']
            match_keys = eval(match_keys_str)
            match_values = []
            matches = self.validate_smgr_keys(query_args, match_keys)
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "match key returned: %s" % (matches))
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "select keys: %s" %(select_clause))
            match_key, match_values = matches.popitem()
            #TODO, Do we need this ?
            # Append "discovered" as one of the values, though
            # its not part of server table fields.
            match_keys.append("discovered")
            if (match_key not in match_keys):
                raise ServerMgrException("Match Key not present", ERR_MATCH_KEY_NOT_PRESENT)
            if match_values == None or match_values[0] == '':
                raise ServerMgrException("Match Value not Specified",
                                                                ERR_MATCH_VALUE_NOT_PRESENT)
            ret_data["status"] = 0
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_values[0]
            ret_data["detail"] = detail
        # end elif
        ret_data['select'] = select_clause
        return ret_data

    def validate_smgr_put(self, validation_data, request, data=None,
                                                        modify = False):
        ret_data = {}
        ret_data['status'] = 1
        try:
            json_data = json.load(request.body)
        except ValueError as e :
            msg = "Invalid JSON data : %s " % e
            self.log_and_raise_exception(msg)
        entity = request.json
        #check if json data is present
        if (not entity):
            msg = "No JSON data specified"
            self.log_and_raise_exception(msg)
        #Check if object is present
        obj_name = validation_data['obj_name']
        objs = entity.get(obj_name)
        if len(objs) == 0:
            msg = ("No %s data specified") % \
                    (obj_name)
            self.log_and_raise_exception(msg)
        #check if primary_keys are present
        primary_keys_str = validation_data['primary_keys']
        primary_keys = eval(primary_keys_str)
        for primary_key in primary_keys:
            if primary_key not in data:
                msg =  ("Primary Key %s not present") % (primary_key)
                self.log_and_raise_exception(msg)
        #Parse for the JSON to find allowable fields
        remove_list = []

        #new default code
        if modify == False:
            #pick the object defaults
            obj_defaults = self._cfg_defaults_dict[obj_name]
            obj_code_defaults = self._code_defaults_dict[obj_name]
            #call the merge
            self.merge_dict(data, obj_defaults)
            self.merge_dict(data, obj_code_defaults)

        obj_params_str = obj_name + "_params"
        for k, v in data.iteritems():
            #If json data name is not present in list of
            #allowable fields silently ignore them.

            if k not in validation_data:
#                data.pop(k, None)
                remove_list.append(k)
                msg =  ("Value %s is not an option") % (k)
                self._smgr_log.log(self._smgr_log.ERROR,
                                   msg)
            if v == '""':
                data[k] = ''
        for item in remove_list:
            data.pop(item, None)

        if 'parameters' in data and obj_name == 'cluster':
            if 'provision' not in data['parameters']:
                msg =  ("Old Parameters format is no longer supported for cluster parameters. Please use the new format")
                self._smgr_log.log(self._smgr_log.ERROR,msg)
                self.log_and_raise_exception(msg)

        if 'roles' in data:
            if 'storage-compute' in data['roles'] and 'compute' not in data['roles']:
                msg = "role 'storage-compute' needs role 'compute' in provision file"
                raise ServerMgrException(msg, ERR_OPR_ERROR)
            elif 'storage-master' in data['roles'] and 'openstack' not in data['roles']:
                msg = "role 'storage-master' needs role 'openstack' in provision file"
                raise ServerMgrException(msg, ERR_OPR_ERROR)

            if 'toragent' in data['roles'] and 'compute' not in data['roles']:
                msg = "role 'toragent' needs role 'compute' in provision file"
                raise ServerMgrException(msg, ERR_OPR_ERROR)

            if 'tsn' in data['roles'] and 'compute' not in data['roles']:
                msg = "role 'tsn' needs role 'compute' in provision file"
                raise ServerMgrException(msg, ERR_OPR_ERROR)

        return ret_data

    def validate_smgr_delete(self, validation_data, request, data = None):

        ret_data = {}
        ret_data['status'] = 1

        match_keys_str = validation_data['match_keys']
        match_keys = eval(match_keys_str)
        query_args = parse_qs(urlparse(request.url).query,
                              keep_blank_values=True)

        # Get the query argument.
        force = ("force" in query_args)
        query_args.pop("force", None)
        matches = self.validate_smgr_keys(query_args, match_keys)
        match_key, match_values = matches.popitem()

        ret_data["status"] = 0
        ret_data["match_key"] = match_key
        ret_data["match_value"] = match_values[0]
        ret_data["force"] = force
        return ret_data

    def validate_non_openstack_cluster(self, cluster_id):
        cluster = self._serverDb.get_cluster(
                {"id" : cluster_id},
                detail=True)[0]
        cluster_params = eval(cluster['parameters'])
        if 'provision' in cluster_params and 'openstack' in cluster_params['provision']:
            cluster_openstack_prov_params = cluster_params['provision']
            cluster_openstack_params = cluster_openstack_prov_params['openstack']
        else:
            msg = "Cluster with only Openstack role is supported only with new cluster params format with Openstack section\n"
            self.log_and_raise_exception(msg)
        configured_external_openstack_ip = cluster_openstack_params.get("external_openstack_ip", None)
        configured_nova_params = cluster_openstack_params.get("nova", None)
        if configured_nova_params:
            configured_nova_rabbit_servers = configured_nova_params.get("rabbit_hosts", None)
        else:
            configured_nova_rabbit_servers = None
        if configured_external_openstack_ip and configured_nova_rabbit_servers:
            pass
        else:
            msg = "In a Cluster with no Openstack role, you need to configure both openstack::keystone::ip and openstack::nova::rabbit_hosts to point to an external Openstack\n"
            self.log_and_raise_exception(msg)

    def validate_openstack_only_cluster(self, cluster_id):
        cluster = self._serverDb.get_cluster(
                {"id" : cluster_id},
                detail=True)[0]
        cluster_params = eval(cluster['parameters'])
        if 'provision' in cluster_params and 'openstack' in cluster_params['provision']:
            cluster_openstack_prov_params = cluster_params['provision']
            cluster_openstack_params = cluster_openstack_prov_params['openstack']
        else:
            msg = "Cluster with only Openstack role is supported only with new cluster params format with Openstack section\n"
            self.log_and_raise_exception(msg)

        openstack_manage_amqp_check = cluster_openstack_params.get("openstack_manage_amqp", None)
        if openstack_manage_amqp_check:
            pass
        else:
            msg = "In a Cluster with only Openstack role defined, you need to configure openstack::openstack_manage_amqp = true\n"
            self.log_and_raise_exception(msg)

    def _validate_roles(self, cluster_id, pkg_id):
        # get list of all servers in this cluster
        servers = self._serverDb.get_server(
            {'cluster_id': cluster_id}, detail=True)
        if self.get_package_category(pkg_id) == 'container':
            # Validation happens in sm_ansible_playbook.py
            return 0

        role_list = [
                "database", "openstack", "config",
                "control", "collector", "webui", "compute"]
        roles_set = set(role_list)
        # adding role here got the role in hieradata yaml file
        optional_role_list = ["storage-compute", "storage-master", "tsn", "toragent", "loadbalancer", "global_controller"]
        optional_role_set = set(optional_role_list)

        cluster_role_list = []
        for server in servers:
            if 'roles' in server and server['roles']:
                role_list = eval(server['roles'])
            else:
                role_list = []
            duplicate_roles = self.list_duplicates(role_list)
            if len(duplicate_roles):
                msg = "Duplicate Roles '%s' present" % \
                        ", ".join(str(e) for e in duplicate_roles)
                self.log_and_raise_exception(msg)
            cluster_role_list.extend(role_list)

        cluster_unique_roles = set(cluster_role_list)

        unknown_roles = cluster_unique_roles.difference(roles_set)
        unknown_roles.difference_update(optional_role_set)

        if len(unknown_roles):
            msg = "Unknown Roles: %s" % \
            ", ".join(str(e) for e in unknown_roles)
            self.log_and_raise_exception(msg)

        return 0

    def list_duplicates(self, seq):
        seen = set()
        seen_add = seen.add
        # adds all elements it doesn't know yet to seen and all other to
        # seen_twice
        seen_twice = set( x for x in seq if x in seen or seen_add(x) )
        # turn the set into a list (as requested)
        return list( seen_twice )

    def get_package_category(self, package_image_id):
        packages = self._serverDb.get_image(
            {"id": package_image_id}, detail=True)
        if not packages:
            msg = "no package %s found" % (package_image_id)
            raise ServerMgrException(msg)
        return packages[0]['category']

    def validate_smgr_provision(self, validation_data, request, data=None, issu_flag = False):
        ret_data = {}
        ret_data['status'] = 1
        if not issu_flag:
            entity = request.json
        else:
            entity = request
        package_image_id = entity.get("package_image_id", '')
        if package_image_id:
            self.get_package_image(package_image_id)
        #if package_image_id is None:
        #    msg = "No contrail package specified for provisioning"
        #    raise ServerMgrException(msg)
        req_provision_params = entity.get("provision_parameters", None)
        # if req_provision_params are specified, check contents for
        # validity, store the info in DB and proceed with the
        # provisioning step.
        if req_provision_params is not None:
            role_list = [
                "database", "openstack", "config",
                "control", "collector", "webui", "compute", "zookeeper",
                "storage-compute", "storage-master", "tsn", "toragent", "loadbalancer", "global_controller"]
            roles = req_provision_params.get("roles", None)
            if roles is None:
                msg = "No provisioning roles specified"
                self.log_and_raise_exception(msg)
            if (type(roles) != type({})):
                msg = "Invalid roles definition"
                self.log_and_raise_exception(msg)
            prov_servers = {}
            for key, value in roles.iteritems():
                if key not in role_list:
                    msg = "invalid role %s in provision file" %(
                            key)
                    self.log_and_raise_exception(msg)
                if type(value) != type ([]):
                    msg = "role %s needs to have server list" %(
                        key)
                    self.log_and_raise_exception(msg)
                for server in value:
                    if server not in prov_servers:
                        prov_servers[server] = [key]
                    else:
                        prov_servers[server].append(key)
                # end for server
            # end for key
            cluster_id = None
            servers = []
            for key in prov_servers:
                server = self._serverDb.get_server(
                    {"id" : key}, detail=True)
                if server:
                    server = server[0]
                servers.append(server)
                if ((cluster_id != None) and
                    (server['cluster_id'] != cluster_id)):
                    msg = "all servers must belong to same cluster"
                    self.log_and_raise_exception(msg)
                cluster_id = server['cluster_id']
            # end for
            ret_data["cluster_id"] = cluster_id
            #Modify the roles
            for key, value in prov_servers.iteritems():
                new_server = {
                    'id' : key,
                    'roles' : value }
                self._serverDb.modify_server(new_server)
            # end for
            if len(servers) == 0:
                msg = "No servers found"
                self.log_and_raise_exception(msg)
            ret_data["status"] = 0
            ret_data["servers"] = servers
            ret_data["package_image_id"] = package_image_id
        else:
            matches = self.validate_smgr_keys(entity)
            match_key, match_value = matches.popitem()
#            match_value = match_values[0]
            # end else
            match_dict = {}
            if match_key == "tag":
                match_dict = self._process_server_tags(match_value)
            elif match_key:
                match_dict[match_key] = match_value
            servers = self._serverDb.get_server(
                match_dict, detail=True)
            if len(servers) == 0:
                msg = "No servers found for %s" % \
                            (match_value)
                self.log_and_raise_exception(msg)
            cluster_id = servers[0]['cluster_id']
            if not cluster_id:
                msg =  ("No Cluster associated with server %s") % (match_value)
                self.log_and_raise_exception(msg)
            self._validate_roles(cluster_id, package_image_id)
            ret_data["status"] = 0
            ret_data["servers"] = servers
            ret_data["cluster_id"] = cluster_id
            ret_data["package_image_id"] = package_image_id
            if (self.get_package_category(package_image_id) == 'container'):
                ret_data["category"] = "container";
                ret_data["server_packages"] = \
                        self.get_container_packages(servers, package_image_id)
                compute_img_id = entity.get("compute_image_id", None)
                if compute_img_id != None:
                    ret_data["compute_image_id"] = compute_img_id
            else:
                ret_data['server_packages'] = \
                        self.get_server_packages(servers, package_image_id)
        return ret_data
    # end validate_smgr_provision

    def validate_smgr_reboot(self, validation_data, request , data=None):
        ret_data = {}
        ret_data['status'] = 1

        entity = request.json
        # Get parameter to check if netboot should be enabled.
        net_boot = entity.get("net_boot", None)
        if ((not net_boot) or
            (net_boot not in ["y","Y","1"])):
            net_boot = False
        else:
            net_boot = True
        matches = self.validate_smgr_keys(entity)
        match_key, match_value = matches.popitem()

        ret_data['status'] = 0
        ret_data['match_key'] = match_key
        ret_data['match_value'] = match_value
        ret_data['net_boot'] = net_boot
        return ret_data
        # end else

    def validate_smgr_reimage(self, validation_data, request , data=None):

        ret_data = {}
        ret_data['status'] = 1
        entity = request.json
        # Get parameter to check server(s) are to be rebooted
        # following reimage configuration in cobbler. Default is yes.
        do_reboot = True
        no_reboot = entity.get("no_reboot", None)
        if ((no_reboot) and
            (no_reboot in ["y","Y","1"])):
            do_reboot = False

        # Get image version parameter
        base_image_id = entity.get("base_image_id", None)
        package_image_id = entity.get("package_image_id", '')

        matches = self.validate_smgr_keys(entity)
        match_key, match_value = matches.popitem()

        ret_data['status'] = 0
        ret_data['match_key'] = match_key
        ret_data['match_value'] = match_value
        ret_data['base_image_id'] = base_image_id
        ret_data['package_image_id'] = package_image_id
        ret_data['do_reboot'] = do_reboot
        return ret_data
    # end validate_smgr_reimage

    def get_select_clause(self, entity):
        select_clause = select = None
        if entity:
            select = entity.get("select", None)
        if select:
            return select[0].split(',')
        return select_clause
    # end get_select_clause

    def validate_smgr_keys(self, entity,
                   keys = ["id", "mac_address","tag","cluster_id", "where",
                           "host_fqdn","subnet_address"]):
        found = False
        for key in keys:
	    if key in entity:
	        found = True
	        match_key = key
	        match_value = entity[key]
        if found == False:
	    msg = "Match key not present"
	    self.log_and_raise_exception(msg)
        return {match_key: match_value}
    # end validate_smgr_keys


    def validate_smgr_request(self, type, oper, request, data = None, modify =
                              False):
        self._smgr_log.log(self._smgr_log.DEBUG, "validate_smgr_request")
        ret_data = {}
        ret_data['status'] = 1
        if type == "SERVER":
            validation_data = server_fields
        elif type == "CLUSTER":
            validation_data = cluster_fields
        elif type == "IMAGE":
            validation_data = image_fields
        elif type == "DHCP_SUBNET":
            validation_data = dhcp_subnet_fields
        elif type == "DHCP_HOST":
            validation_data = dhcp_host_fields
        else:
            validation_data = None

        if oper == "GET":
            ret_val_data = self.validate_smgr_get(validation_data, request, data)
        elif oper == "PUT":
            ret_val_data = self.validate_smgr_put(validation_data, request, data, modify)
        elif oper == "DELETE":
            ret_val_data = self.validate_smgr_delete(validation_data, request, data)
        elif oper == "PROVISION":
            ret_val_data = self.validate_smgr_provision(validation_data, request, data)
        elif oper == "REBOOT":
            ret_val_data = self.validate_smgr_reboot(validation_data, request, data)
        elif oper == "REIMAGE":
            ret_val_data = self.validate_smgr_reimage(validation_data, request, data)

        #self._smgr_log.log(self._smgr_log.DEBUG, "ret_val_data returned: %s" % (ret_val_data))

	return ret_val_data
    # This function converts the string of tags received in REST call and make
    # a dictionary of tag keys that can be passed to match servers from DB.
    # The match_value (tags received are in form tag1=value,tag2=value etc.
    # This function maps the tag name to tag number and value and makes
    # a dictionary of those.
    def _process_server_tags(self, match_value):
        if not match_value:
            return {}
        match_dict = {}
        tag_list = match_value.split(',')
        for x in tag_list:
            tag = x.strip().split('=')
            if tag[0] in self._rev_tags_dict:
                match_dict[self._rev_tags_dict[tag[0]]] = tag[1]
            else:
                msg = ("Unknown tag %s specified" %(
                    tag[0]))
                self.log_and_raise_exception(msg)
            # end else
        return match_dict
    # end _process_server_tags

    # This function gets storage_chassis_id of all servers configured in
    # the server-manager. If chassis_id is not configured, it returns "[]"
    # empty array. This api helps SM-UI to get all chassis-id configured
    # in the system abd let admin select any of existing chassis-id or
    # provide a new one.
    def get_server_chassis_id(self):
        try:
            servers = self._serverDb.get_server(None, detail=True)
            all_chassis_id_set = set()
            for server in servers:
                server_parameters = server.get('parameters', "{}")
                if not server_parameters:
                    server_parameters = "{}"
                server_params = eval(server_parameters)
                storage_chassis_id = server_params.get('storage_chassis_id', "")
                # if no chassis_id is configured, just move-on. we are here to
                # collect chassis-id only
                if storage_chassis_id and storage_chassis_id != "":
                    all_chassis_id_set.add(storage_chassis_id)

        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)

        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR, None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER)
        # Convert some of the fields in server entry to match what is accepted for put

        return {"chassis_id": list(all_chassis_id_set)}

    # End get_server_chassis_id

    # This call returns status information about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server_status(self):
        ret_data = None
        try:
            ret_data = self.validate_smgr_request("SERVER", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                select_clause = ret_data["select"]
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value
                detail = False
                if not select_clause:
                    select_clause = ["id", "mac_address", "ip_address", "status"]
                servers = self._serverDb.get_server(
                    match_dict, detail=detail, field_list=select_clause)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER)
        # Convert some of the fields in server entry to match what is accepted for put
        return {"server": servers}
    # end get_server_status


    # This call returns information about the status of currently provisioned servers. If no server/cluster
    # is provided, or if cluster/server is not being currently provisioned, then error is returned
    # configuration is returned.
    def get_provision_status(self):
        ret_data = None
        provision_server_status = []
        try:
            ret_data = self.validate_smgr_request("SERVER", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                select_clause = ret_data["select"]
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value
                detail = ret_data["detail"]
                if not select_clause:
                    select_clause = ["id", "host_name", "cluster_id", "status"]
                servers = self._serverDb.get_server(
                    match_dict, field_list=select_clause)
                if not len(servers):
                    msg =  ("There are no servers for which provision info can be displayed.")
                    self.log_and_raise_exception(msg)
                cluster_id = servers[0]['cluster_id']
                cluster_dict_detail = self._serverDb.get_cluster(
                    {"id": cluster_id}, detail=True)[0]
                provision_role_sequence = cluster_dict_detail['provision_role_sequence']
                provision_role_sequence = eval(provision_role_sequence)
                provision_steps = provision_role_sequence.get('steps', [])
                provision_step_tuple_list = []
                for provision_step_tuple in provision_steps:
                    for step_tuple in provision_step_tuple:
                        provision_step_tuple_list.append(step_tuple)
                provision_complete = provision_role_sequence.get('completed', [])
                server_role_mapping = {}
                for idx, server_role_steps_tuple in enumerate(provision_step_tuple_list):
                    server_id, role_to_do = server_role_steps_tuple
                    if str(server_id) not in server_role_mapping:
                        server_role_mapping[str(server_id)] = {}
                    server_role_dict = server_role_mapping[str(server_id)]
                    server_role_dict[str(role_to_do)] = {}
                    if idx > 0:
                        previous_server_id, previous_role_to_do = provision_step_tuple_list[idx-1]
                        server_role_dict[str(role_to_do)]["previous_server"] = str(previous_server_id)
                        server_role_dict[str(role_to_do)]["previous_role"] = str(previous_role_to_do)

                for server_role_completed_tuple in provision_complete:
                    server_id, role_completed, time_completed = server_role_completed_tuple
                    if str(server_id) not in server_role_mapping:
                        server_role_mapping[str(server_id)] = {}
                    server_role_dict = server_role_mapping[str(server_id)]
                    server_role_dict[str(role_completed)] = {}
                    server_role_dict[str(role_completed)]["end_time"] = time_completed

                for server in servers:
                    if server['status'] in ['server_added','server_discovered','reimage_started','restart_issued', 'reimage_started']:
                        msg =  ("Server with Id %s is currently not under provision." % (server['id']))
                        self.log_and_raise_exception(msg)
                    provision_server_dict = {"id": str(server['host_name']), "cluster_id": str(server['cluster_id']),
                        "provisioned_roles": [], "role_being_provisioned": None, "roles_pending_provision": []}
                    if str(server['host_name']) in server_role_mapping:
                        server_role_dict = server_role_mapping[str(server['host_name'])]
                        for role in server_role_dict.keys():
                            if "end_time" in server_role_dict[role]:
                                provision_server_dict["provisioned_roles"].append(str(role))
                            elif str(server['status']) == str(role+"_started"):
                                provision_server_dict["role_being_provisioned"] = str(role)
                            else:
                                provision_server_dict["roles_pending_provision"].append(str(role))
                        if len(provision_server_dict["roles_pending_provision"]) and (provision_server_dict["role_being_provisioned"] == None):
                            next_role_dict = server_role_dict[str(provision_server_dict["roles_pending_provision"][0])]
                            if "previous_role" in next_role_dict and "previous_server" in next_role_dict:
                                provision_server_dict["role_being_provisioned"] = "Waiting for role " + str(next_role_dict["previous_role"]) + \
                                " to complete on node " + str(next_role_dict["previous_server"])
                        provision_server_status.append(provision_server_dict)

        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER)
        # Convert some of the fields in server entry to match what is accepted for put
        return {"servers": provision_server_status}
    # end get_provision_status

    # This call returns inf rmation about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server(self):
        ret_data = None
        servers = []
        try:
            ret_data = self.validate_smgr_request("SERVER", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                select_clause = ret_data["select"]
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value
                detail = ret_data["detail"]
                servers = self._serverDb.get_server(
                    match_dict, detail=detail, field_list=select_clause)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER)


        # Convert some of the fields in server entry to match what is accepted for put
        for x in servers:
            if x.get("parameters", None) is not None:
                x['parameters'] = eval(x['parameters'])

            if x.get("roles", None) is not None:
                x['roles'] = eval(x['roles'])
            if x.get("intf_control", None) is not None:
                x['control_data_network'] = eval(x['intf_control'])
                x.pop('intf_control', None)
            if x.get("intf_bond", None) is not None:
                x['bond_interface'] = eval(x['intf_bond'])
                x.pop('intf_bond', None)
            if x.get("network", None):
                x['network'] = eval(x['network'])
            if x.get("contrail", None):
                x['contrail'] = eval(x['contrail'])
            if x.get("top_of_rack", None):
                x['top_of_rack'] = eval(x['top_of_rack'])

            #Hide the passwords
            self.hide_passwords(x, self._server_mask_list)
            if detail:
                #Temp workarounf for UI, UI doesnt like None
                if x.get("roles", None) is None:
                    x['roles'] = []
                if x.get("parameters", None) is None:
                    x['parameters'] = {}

                x['tag'] = {}
                for i in range(1, len(self._tags_list)+1):
                    tag = "tag" + str(i)
                    if x[tag]:
                        x['tag'][self._tags_dict[tag]] = x.pop(tag, None)
                    else:
                        x.pop(tag, None)
                for blocked_field in server_blocked_fields:
                    x.pop(blocked_field, None)
        return {"server": servers}
    # end get_server

    def get_servers_for_tag(self, tags):
        '''returns servers matching tags, tags format tag1=xxx,tag2=xxx'''
        try:
            match_value = tags
            match_dict = self._process_server_tags(match_value)
            servers = self._serverDb.get_server(
                             match_dict, detail=True)
        except ServerMgrException as e:
            self.log_and_raise_exception(e)
        return servers
    # end get_servers_for_tag

    def _get_client_ip_addr(self):
        client_ip = bottle.request.environ.get('REMOTE_ADDR')
        return client_ip

    def hide_passwords(self, x, hide_list):
        #Leaving behind this code,
        #So that if we decide to hide based on Client-IP address
        client_ip = self._get_client_ip_addr()
        query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
        # Check if request arguments has show_pass parameter
        show_pass = ("show_pass" in query_args)

        if show_pass == True:
           return
        for item in hide_list:
           object_item = x
           element_list = item.split('.')
           for element in element_list:
              if element in object_item:
                 if type(object_item[element]) != dict:
                     #strip the item
                     object_item[element] = "*****"
                 else:
                     object_item = object_item[element]
        return

    #API Call to list DHCP Hosts
    def get_dhcp_subnet(self):
        try:
            ret_data = self.validate_smgr_request("DHCP_SUBNET", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                if match_key:
                    match_dict[match_key] = match_value
            dhcp_subnets = self._serverDb.get_dhcp_subnet(match_dict)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE)
        return {"dhcp_subnet": dhcp_subnets}
    # end get_dhcp_subnet

    #API Call to list DHCP Hosts
    def get_dhcp_host(self):
        try:
            ret_data = self.validate_smgr_request("DHCP_HOST", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                if match_key:
                    match_dict[match_key] = match_value
            dhcp_hosts = self._serverDb.get_dhcp_host(match_dict)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE)
        return {"dhcp_host": dhcp_hosts}
    # end get_dhcp_host

    # API Call to list images
    def get_image(self):
        try:
            ret_data = self.validate_smgr_request("IMAGE", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                select_clause = ret_data["select"]
                match_dict = {}
                if match_key:
                    match_dict[match_key] = match_value
                detail = ret_data["detail"]
            images = self._serverDb.get_image(match_dict,
                                              detail=detail,
                                              field_list=select_clause)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE)
        for image in images:
            if image.get("parameters", None) is not None:
                image['parameters'] = eval(image['parameters'])
        return {"image": images}
    # end get_image

    def get_obj(self, resp):
        try:
            data = json.loads(resp)
            return data
        except ValueError:
            return ''
    #end def get_obj

    def put_status(self):
        query_args = parse_qs(urlparse(bottle.request.url).query,
                                      keep_blank_values=True)
        match_key, match_value = query_args.popitem()
        if ((match_key not in (
                            "server_id", "mac_address", "cluster_id", "ip_address")) or
                            (len(match_value) != 1)):
                self._smgr_log.log(self._smgr_log.ERROR, "Invalid Query data")
                abort(404, "Invalid Query arguments")
        if match_value[0] == '':
            abort(404, "Match value not present")
        server_id = match_value[0]
        body = bottle.request.body.read()
        server_data = {}
        server_data['id'] = server_id
        server_data['server_status'] = body
        try:
            resp = self.get_obj(body)
            if str(resp) == 'reimage completed' or str(resp) == 'reimage start':
                message = server_id + ' ' + str(resp) + strftime(" (%Y-%m-%d %H:%M:%S)", localtime())
                self.send_status_mail(server_id, message, message)
            servers = self._serverDb.put_status(
                            server_data)
        except Exception as e:
            self.log_trace()
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding to db %s" % repr(e))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                        None)
            abort(404, resp_msg)


    def get_status(self):
        match_key = match_value = None
        match_dict = None
        if 'id' in bottle.request.query:
            server_id = bottle.request.query['id']
            match_key = 'id'
            match_value = server_id
            match_dict[match_key] = match_value

        servers = self._serverDb.get_status(
                    match_dict, detail=True)

        if servers:
            return servers[0]
        else:
            return None

    #Common function to get the version of tgz(for both CentOs and Ubuntu), rpm
    #and debian Contrail packages. It also gets the version of the Contrail storage package
    def get_contrail_package_version(self, image_type, image_id, image_path,file_type):
        sm = ServerMgrUtil()
        if file_type and 'gzip compressed data' in file_type:
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
            if image_type == 'contrail-storage-ubuntu-package':
                tmp_img_path = 'ls '+ mirror + '/contrail-storage_*'
            else:
                tmp_img_path = 'ls '+ mirror + '/contrail-setup*'
            tmp_pkg = subprocess.check_output(tmp_img_path, shell=True)
        else:
            tmp_pkg = image_path
        version = sm.get_package_version(tmp_pkg.strip('\n'), image_type)
        return version.strip('\n')

    def diff_string(self, str1, str2):
        import difflib
        str1 = re.sub(' +', ' ', str1)
        str2 = re.sub(' +', ' ', str2)
        str1=str1.splitlines(True)
        str2=str2.splitlines(True)

        diff=difflib.ndiff(str1, str2)
        return ''.join(diff)

    def put_container_image(self, entity, image):
        new_containers = {}
        image_id       = image.get("id", None)
        image_type     = image.get("type", None)
        image_params   = image.get("parameters", {})
        #TODO: should be possible to specify version per container
        # inside the parameters
        image_version  = image.get("version", None)
        image_category = image.get("category", None)

        msg = "Image(s) specified refers to external registry. Make \
                        sure the following image(s) exist(s): "
        external_image = False
        local_image    = False
        for container in image_params.get("containers", None):
            cpath = container.get("container_path", None)
            role  = container.get("role", None)

            if cpath == None or not os.path.exists(cpath):
                external_image = True
                if cpath == None:
                    container_name = self._args.docker_insecure_registries + \
                             '/' + image_id + '-' + role + ':' +     \
                             image_version
                else:
                    container_name = cpath
                msg = msg + container_name + " "
            else:
                local_image = True

        if external_image == True and local_image == False:
            resp_msg = self.form_operartion_data(msg, 0, entity)

        for idx, container in enumerate(image_params.get("containers", None)):
            cpath = container.get("container_path", None)
            role  = container.get("role", None)
            if cpath == None or not os.path.exists(cpath):
                if cpath == None:
                    container_name = self._args.docker_insecure_registries + \
                             '/' + image_id + '-' + role + ':' +     \
                             image_version
                elif not os.path.exists(cpath):
                    container_name = cpath

                container["container_image"] = container_name
                continue

            container_name = self._args.docker_insecure_registries + \
                             '/' + image_id + '-' + role + ':' +     \
                             image_version

            self._smgr_log.log(self._smgr_log.INFO,
                "Loading container image %s ..." % container_name)
            [status, new_image] = self._docker_cli.load_containers(cpath)
            if status == False or new_image == None:
                if status == False:
                    self._smgr_log.log(self._smgr_log.ERROR,
                        "Loading container failed for %s" % cpath)
                    print("Loading container failed for %s" % cpath)
                    msg = "Loading container failed for %s" % (cpath)
                    raise ServerMgrException(msg, ERR_OPR_ERROR)
                    resp_msg = self.form_operartion_data(msg, 0, entity)
                    return resp_msg
                else:
                    # The load image did not result in any new image
                    continue

            role = container.get("role", None)
            repo = self._args.docker_insecure_registries + \
                                     '/' + image_id + '-' + role
            self._docker_cli.tag_containers(new_image['Id'], repo,
                                            image_version)
            self._smgr_log.log(self._smgr_log.INFO,
                            "Pushing container image %s ..." % container_name)
            if self._docker_cli.push_containers(container_name) == False:
                self._smgr_log.log(self._smgr_log.ERROR,
                    "Pushing container failed for %s" % container_name)
                msg = "Pushing container failed for %s" % (container_name)
                #raise ServerMgrException(msg, ERR_OPR_ERROR)
                resp_msg = self.form_operartion_data(msg, 0, entity)
                return resp_msg

            self._smgr_log.log(self._smgr_log.INFO,
                            "Pushed container image %s ..." % container_name)
            image_params["containers"][idx]["container_image"] = container_name
            image_params["containers"][idx]["docker_image_id"] = new_image["Id"]
        #for container ...

        if external_image == False:
            msg = "Image add/Modify success"
            resp_msg = self.form_operartion_data(msg, 0, entity)
            self._smgr_log.log(self._smgr_log.INFO, msg)
        else:
            msg = "Image add/Modify success. " + msg
            self._smgr_log.log(self._smgr_log.INFO, msg)

        image_data = {
            'id': image_id,
            'version': image_version,
            'type': image_type,
            'category' : image_category,
            'parameters' : image_params
        }
        self._serverDb.add_image(image_data)
        return resp_msg

    def put_image(self):
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("image", entity)
            images = entity.get("image", None)
            for image in images:
                #use macros for obj type
                if self._serverDb.check_obj(
                    "image", {"id" : image['id']},
                    raise_exception=False):
                    raise ServerMgrException("image modification is not " \
                           "allowed, delete and add it.", ERR_OPR_ERROR)
                else:
                    self.validate_smgr_request("IMAGE", "PUT", bottle.request,
                                                image)
                    image_id = image.get("id", None)
                    image_version = image.get("version", None)
                    # Get Image type
                    image_type = image.get("type", None)
                    image_path = image.get("path", None)
                    image_category = image.get("category", None)
                    image_params = image.get("parameters", {})
                    if (image_type in self._contrail_container_list):
                        for container in image_params.get("containers", None):
                            role  = container.get("role", None)
                            if role not in _valid_roles:
                                self._smgr_log.log(self._smgr_log.ERROR,
                                        "Invalid role in image json: %s" % role)
                                msg = "Invalid role in image json: %s" % role
                                raise ServerMgrException(msg, ERR_OPR_ERROR)
                                resp_msg = self.form_operartion_data(msg, 0, entity)
                                return resp_msg

                        gevent.spawn(self.put_container_image, entity, image)
                        msg = \
                        "Image add/Modify happening in the background. "\
                        "Check /var/log/contrail-server-manager/debug.log "\
                        "for progress"
                        resp_msg = self.form_operartion_data(msg, 0, entity)
                        return resp_msg

                    if (not image_id) or (not image_path):
                        self._smgr_log.log(self._smgr_log.ERROR,
                                     "image id or location not specified")
                        raise ServerMgrException("image id or location \
                                 not specified", ERR_OPR_ERROR)
                    if (image_type not in self._image_list):
                        msg = "image type not specified or invalid for image %s" %(
                                    image_id)
                        self._smgr_log.log(self._smgr_log.ERROR, msg)
                        raise ServerMgrException(msg, ERR_OPR_ERROR)
                    if (not image_category):
                        if image_type in self._iso_types:
                            image_category = "image"
                        if image_type in self._package_types:
                            image_category = "package"
                    if (image_category not in self._image_category_list):
                        msg = "image category (%s) is not supported" % \
                                                (image_category)
                        self._smgr_log.log(self._smgr_log.ERROR, msg)
                        raise ServerMgrException(msg, ERR_OPR_ERROR)
                    if not os.path.exists(image_path):
                        msg = "image not found at %s" % \
                                                (image_path)
                        raise ServerMgrException(msg, ERR_OPR_ERROR)
                    #Get the file type
                    cmd = 'file %s'%image_path
                    output = subprocess.check_output(cmd, shell=True)
                    if ((image_type == "contrail-centos-package") or
                        (image_type == "contrail-ubuntu-package") ):
                        if not self.validate_package_id(image_id):
                            msg =  ("Id given %s,Id can contain only lowercase alpha-numeric characters including '_'." % (image_id))
                            self.log_and_raise_exception(msg)

                        puppet_manifest_version, sequence_provisioning_available, puppet_version  = self._create_repo(
                            image_id, image_type, image_version, image_path)
                        image_params['puppet_manifest_version'] = \
                            puppet_manifest_version
                        image_params['sequence_provisioning_available'] = sequence_provisioning_available
                        if puppet_version not in image_params:
                            image_params['puppet_version'] = puppet_version
                        #Get the contrail package version
                        version = self.get_contrail_package_version(image_type, image_id, image_path,output)
                        image_params['version'] = version.split('~')[0]
                        #find sku of package (juno/kilo/liberty)
                        package_sku = self.find_package_sku(image_id, image_type)
                        image_params['sku'] = package_sku
                    elif image_type == "contrail-storage-ubuntu-package":
                        self._create_repo(
                            image_id, image_type, image_version, image_path)
                        version = self.get_contrail_package_version(image_type, image_id, image_path,output)
                        image_params['version'] = version.split('~')[0]
                    else:
                        image_kickstart = image_params.get('kickstart', '')
                        image_kickseed = image_params.get('kickseed', '')
                        kickstart_dest = kickseed_dest = ''
                        if image_kickstart:
                            if not os.path.exists(image_kickstart):
                                raise ServerMgrException("kickstart not found at %s" % \
                                                             (image_kickstart), ERR_OPR_ERROR)
                            kickstart_dest = self._args.html_root_dir + \
                                "contrail/images/" + image_id + ".ks"
                            subprocess.check_call(["cp", "-f", image_kickstart,
                                                  kickstart_dest])
                        if image_kickseed:
                            if not os.path.exists(image_kickseed):
                                raise ServerMgrException("kickseed not found at %s" % \
                                                         (image_kickseed), ERR_OPR_ERROR)
                            kickseed_dest = self._args.html_root_dir + \
                                "contrail/images/" + image_id + ".seed"
                            subprocess.check_call(["cp", "-f", image_kickseed,
                                                  kickseed_dest])
                        image_params['kickstart'], image_params['kickseed'] = \
                                    self._add_image_to_cobbler(image_id, image_type,
                                    image_version, image_path,
                                    kickstart_dest, kickseed_dest)
                    image_data = {
                        'id': image_id,
                        'version': image_version,
                        'type': image_type,
                        'path': image_path,
                        'category' : image_category,
                        'parameters' : image_params}
                    self._serverDb.add_image(image_data)
        except subprocess.CalledProcessError as e:
            msg = ("put_image: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            self._smgr_trans_log.log(
                bottle.request,
                self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)

        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_IMAGE)
        msg = "Image add/Modify success"
        resp_msg = self.form_operartion_data(msg, 0, entity)
        return resp_msg

    def put_cluster(self):
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("cluster", entity)
            cluster = entity.get('cluster', None)
            for cur_cluster in cluster:
                #use macros for obj type
                if self._serverDb.check_obj(
                    "cluster", {"id" : cur_cluster['id']},
                    raise_exception=False):
                    #TODO Handle uuid here
                    self.validate_smgr_request("CLUSTER", "PUT", bottle.request,
                                                cur_cluster, True)
                    self._serverDb.modify_cluster(cur_cluster)
                else:
                    self.validate_smgr_request("CLUSTER", "PUT", bottle.request,
                                                cur_cluster)
                    str_uuid = str(uuid.uuid4())
                    storage_fsid = str(uuid.uuid4())
                    storage_virsh_uuid = str(uuid.uuid4())
                    cur_cluster["parameters"].update({"uuid": str_uuid})
                    cur_cluster["parameters"].update({"storage_fsid": storage_fsid})
                    cur_cluster["parameters"].update({"storage_virsh_uuid": storage_virsh_uuid})
                    cur_cluster["provision_role_sequence"] = {}
                    cur_cluster["provision_role_sequence"]["steps"] = []
                    cur_cluster["provision_role_sequence"]["completed"] = []
                    self._smgr_log.log(self._smgr_log.INFO, "Cluster Data %s" % cur_cluster)
                    self.generate_passwords(cur_cluster.get("parameters", {}))
                    self._serverDb.add_cluster(cur_cluster)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER,
                                False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER,
                                False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER)
        msg = "Cluster Add/Modify Success"
        resp_msg = self.form_operartion_data(msg, 0, entity)
        return resp_msg

    # Function to validate values of tag field, if present, in received
    # server json object.
    def validate_server_mgr_tags(self, server):
        tags = server.get("tag", None)
        if tags is None:
            return
        for key in tags.iterkeys():
            if key not in self._rev_tags_dict:
                msg = "Invalid tag %s in server entry" %(
                    key)
                self.log_and_raise_exception(msg)
    # end validate_server_mgr_tags

    def plug_mgmt_intf_details(self, server):
        if 'network' in server and server['network']:
            intf_dict = self.get_interfaces(server)
            network_dict = server['network']
            mgmt_intf_name = network_dict['management_interface']
            mgmt_intf_obj = intf_dict[mgmt_intf_name]

            server['mac_address'] = mgmt_intf_obj['mac_address']
            server['ip_address'] = mgmt_intf_obj['ip']
            server['subnet_mask'] = mgmt_intf_obj['mask']
            server['gateway'] = mgmt_intf_obj['d_gw']
            if 'parameters' in server:
                server_parameters = server['parameters']
            else:
                server_parameters = {}
            server_parameters['interface_name'] = mgmt_intf_name
            server['parameters'] = server_parameters
            dhcp = mgmt_intf_obj.get('dhcp', False)
            if not dhcp  and mgmt_intf_obj['d_gw'] is None:
                raise ServerMgrException("For managment interface configured as static default gateway has to be specified", ERR_OPR_ERROR)
        else:
            print 'check'
            # check if old details are there else throw error

    def put_dhcp_host(self):
        entity = bottle.request.json
        if (not entity):
            msg = 'Host FQDN not specified'
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        try:
            self.validate_smgr_entity("dhcp_host", entity)
            dhcp_hosts = entity.get("dhcp_host", None)
            for dhcp_host in dhcp_hosts:
                for key in dhcp_host:
                    dhcp_host[str(key)] = dhcp_host.pop(key)
                db_dhcp_hosts = self._serverDb.get_dhcp_host(
                    {"host_fqdn" : str(dhcp_host['host_fqdn'])})
                if db_dhcp_hosts:
                    self.validate_smgr_request("DHCP_HOST", "PUT", bottle.request,
                                               dhcp_host, True)
                    self._serverDb.modify_dhcp_host(dhcp_host)
                else:
                    self.validate_smgr_request("DHCP_HOST", "PUT", bottle.request,
                                               dhcp_host)
                    dhcp_host.pop('parameters')
                    if set(self._dhcp_host_key_list) == set(dhcp_host.keys()):
                        self._serverDb.add_dhcp_host(dhcp_host)
                    else:
                        msg = "Keys missing from the config sent: " + str(list(set(self._dhcp_host_key_list)-set(dhcp_host.keys()))) + "\n"
                        self.log_and_raise_exception(msg)
            stanza = self._dhcp_template_obj.generate_dhcp_template()
            self._using_dhcp_management = True
            # Sync the above information
            if self._smgr_cobbler:
                self._smgr_cobbler.sync()
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.PUT_SMGR_CFG_SERVER)
        msg = "DHCP host add/Modify Success"
        resp_msg = self.form_operartion_data(msg, 0, entity)
        return resp_msg

    def put_dhcp_subnet(self):
        entity = bottle.request.json
        if (not entity):
            msg = 'Subnet Address not specified'
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        try:
            self.validate_smgr_entity("dhcp_subnet", entity)
            dhcp_subnets = entity.get("dhcp_subnet", None)
            for dhcp_subnet in dhcp_subnets:
                for key in dhcp_subnet:
                    if not isinstance(dhcp_subnet[key],list):
                        dhcp_subnet[str(key)] = str(dhcp_subnet.pop(key))
                    else:
                        dhcp_subnet[str(key)] = [str(n) for n in dhcp_subnet.pop(key)]
                    if key in ['dns_server_list','search_domains_list'] and isinstance(dhcp_subnet[str(key)],basestring):
                        dhcp_subnet[str(key)] = [dhcp_subnet[str(key)]]
                db_dhcp_subnets = self._serverDb.get_server(
                    {"id" : dhcp_subnet['subnet_address']}, None, True)
                if db_dhcp_subnets:
                    self.validate_smgr_request("DHCP_SUBNET", "PUT", bottle.request,
                                               dhcp_subnet, True)
                    self._serverDb.modify_dhcp_subnet(dhcp_subnet)
                else:
                    self.validate_smgr_request("DHCP_SUBNET", "PUT", bottle.request,
                                               dhcp_subnet)
                    dhcp_subnet.pop('parameters')
                    if set(self._dhcp_subnet_key_list) == set(dhcp_subnet.keys()):
                        result = self._serverDb.add_dhcp_subnet(dhcp_subnet)
                        if result:
                           self.log_and_raise_exception(result)
                    else:
                        msg = "Keys missing from the config sent: " + str(set(self._dhcp_subnet_key_list)) + " " + str(set(dhcp_subnet.keys())) + "\n"
                        self.log_and_raise_exception(msg)
            stanza = self._dhcp_template_obj.generate_dhcp_template()
            self._using_dhcp_management = True
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.PUT_SMGR_CFG_SERVER)
        msg = "DHCP subnet add/Modify Success"
        resp_msg = self.form_operartion_data(msg, 0, entity)
        return resp_msg

    def put_server(self):
        entity = bottle.request.json
        if (not entity):
            msg = 'Server MAC or server_id not specified'
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        try:
            self.validate_smgr_entity("server", entity)
            servers = entity.get("server", None)
            new_servers = []
            for server in servers:
                self.plug_mgmt_intf_details(server)
                self.validate_server_mgr_tags(server)
                # Add server_added status and discovered after validation
                db_servers = self._serverDb.get_server(
                    {"id" : server['id']},
                    None, True)
                if not db_servers:
                    db_servers = self._serverDb.get_server(
                        {"mac_address" : server['mac_address']},
                        None, True)
                if db_servers:
                    #TODO - Revisit this logic
                    # Do we need mac to be primary MAC
                    server_fields['primary_keys'] = "['id']"
                    self.validate_smgr_request("SERVER", "PUT", bottle.request,
                                               server, True)
                    status = db_servers[0]['status']
                    if not status or status == "server_discovered":
                        server['status'] = "server_added"
                        server['discovered'] = "false"
                    self._serverDb.modify_server(server)
                    server_fields['primary_keys'] = "['id', 'mac_address']"
                else:
                    new_servers.append(server)
                    self.validate_smgr_request("SERVER", "PUT",
                                               bottle.request, server)
                    server['status'] = "server_added"
                    server['discovered'] = "false"
                    self._serverDb.add_server(server)
                    # Trigger to collect monitoring info

            # End of for
            if len(new_servers):
                gevent.spawn(self._monitoring_base_plugin_obj.setup_keys, None, new_servers)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.PUT_SMGR_CFG_SERVER)
        msg = "Server add/Modify Success"
        resp_msg = self.form_operartion_data(msg, 0, entity)
        return resp_msg

    # Function to change tags used for grouping together servers.
    def put_server_tags(self):
        entity = bottle.request.json
        if (not entity):
            msg = 'no tags specified'
            resp_msg = self.form_operartion_data(msg, ERR_MATCH_KEY_NOT_PRESENT, None)
            abort(404, resp_msg)

        try:
            for key in entity.iterkeys():
                if key not in self._tags_list:
                    msg = ("Invalid tag %s "
                           "specified" %(key))
                    self.log_and_raise_exception(msg)

            for key, value in entity.iteritems():
                current_value = self._tags_dict.get(key, None)
                # if tag is defined, then check if new tag name is
                # different from old one.
                if (current_value and
                    (value != current_value)):
                    servers = self._serverDb.get_server(
                        {}, {key : ''}, detail=False)
                    if servers:
                            msg = (
                                "Cannot modify tag name "
                                "for %s, used in server table" %(key))
                            self.log_and_raise_exception(msg)

            for key, value in entity.iteritems():
                if value:
                    self._tags_dict[key] = value
                    self._rev_tags_dict[value] = key
                else:
                    current_value = self._tags_dict.pop(key, None)
                    self._rev_tags_dict.pop(current_value, None)
            # Now write to ini file
            tags_config = ConfigParser.SafeConfigParser()
            tags_config.add_section('TAGS')
            for key, value in self._tags_dict.iteritems():
                tags_config.set('TAGS', key, value)
            with open(
                self._args.server_manager_base_dir + _SERVER_TAGS_FILE, 'wb') as configfile:
                tags_config.write(configfile)
            # Also write the tags to DB
            self._serverDb.add_server_tags(self._tags_dict)
        except ServerMgrException as e:
            self._smgr_trans_log.log(
                bottle.request, self._smgr_trans_log.PUT_SMGR_CFG_TAG, False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_TAG, False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.PUT_SMGR_CFG_TAG)
        msg = "Tags add/Modify Success"
        resp_msg = self.form_operartion_data(msg, 0, self._tags_dict)
        return resp_msg
    # end put_server_tags

    def form_operartion_data(self, msg, ret_code, data):
        return_data = {}
        return_data['return_code'] = ret_code
        return_data['return_msg'] = msg
        return_data['return_data'] = data

        return_data_str = print_rest_response(return_data)

        return return_data_str

    def validate_package_id(self, package_id):
        #ID shouldn't have only apha-numerice and "_"
        #id can be none or empty, if server is discovered
        id_valid = True
        is_id_allowed = []
        if package_id is not None and  package_id != "":
            is_id_allowed = re.findall('^[a-z0-9_]+$', package_id)
        if len(is_id_allowed) == 0:
            return False
        return True

    # API Call to add image file to server manager (file is copied at
    # <default_base_path>/images/filename.iso and distro, profile
    # created in cobbler. This is similar to function above (add_image),
    # but this call actually upload ISO image from client to the server.
    def upload_image(self):
        image_id = bottle.request.forms.id
        image_version = bottle.request.forms.version
        image_type = bottle.request.forms.type
        image_category = bottle.request.forms.category
        msg = ""
        if (image_type not in self._image_list):
            msg = "Invalid Image type for %s" % (image_id)
            resp_msg = self.form_operartion_data(msg, ERR_IMG_TYPE_INVALID, None)
            abort(404, resp_msg)

        if (not image_category):
            if image_type in self._iso_types:
                image_category = "image"
            if image_type in self._package_types:
                image_category = "package"
        if (image_category not in self._image_category_list):
            msg = "image category (%s) is not supported" % (image_category)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)

        db_images = self._serverDb.get_image(
            {'id' : image_id}, detail=False)
        if db_images:
            msg = "image %s already exists" %(image_id)
            resp_msg = self.form_operartion_data(msg, ERR_IMG_EXISTS, None)
            abort(404, resp_msg)

        file_obj = bottle.request.files.get('file', None)
        if file_obj is None:
            msg = "image file is not specified"
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        file_name = file_obj.filename
        extn = os.path.splitext(file_name)[1]
        dest = self._args.server_manager_base_dir + 'images/' + \
            image_id + extn
        try:
            if file_obj.file:
                with open(dest, 'w') as open_file:
                    open_file.write(file_obj.file.read())
            image_params = {}
            cmd = 'file %s'%dest
            output = subprocess.check_output(cmd, shell=True)
            if ((image_type == "contrail-centos-package") or
                (image_type == "contrail-ubuntu-package")):
                if not self.validate_package_id(image_id):
                    msg =  ("Id given %s, Id can contain only lowercase alpha-numeric characters including '_'." % (image_id))
                    self.log_and_raise_exception(msg)

                puppet_manifest_version, sequence_provisioning_available, puppet_version = self._create_repo(
                    image_id, image_type, image_version, dest)
                image_params['puppet_manifest_version'] = \
                    puppet_manifest_version
                image_params['sequence_provisioning_available'] = sequence_provisioning_available
                if puppet_version not in image_params:
                    image_params['puppet_version'] = puppet_version
                version = self.get_contrail_package_version(image_type, image_id, dest, output)
                image_params['version'] = version.split('~')[0]
                package_sku = self.find_package_sku(image_id, image_type)
                image_params['sku'] = package_sku
            elif image_type == "contrail-storage-ubuntu-package":
                self._create_repo(
                    image_id, image_type, image_version, dest)
                version = self.get_contrail_package_version(image_type, image_id, dest, output)
                image_params['version'] = version.split('~')[0]
            else:
                kickstart_obj = bottle.request.files.get('kickstart', None)
                kickstart_dest = kickseed_dest = ''
                if kickstart_obj:
                    kickstart_dest = self._args.html_root_dir + \
                        "contrail/images/" + image_id + ".ks"
                    if kickstart_obj.file:
                        with open(kickstart_dest, 'w') as open_file:
                            open_file.write(kickstart_obj.file.read())
                kickseed_obj = bottle.request.files.get('kickseed', None)
                if kickseed_obj:
                    kickseed_dest = self._args.html_root_dir + \
                        "contrail/images/" + image_id + ".seed"
                    if kickseed_obj.file:
                        with open(kickseed_dest, 'w') as open_file:
                            open_file.write(kickseed_obj.file.read())
                image_params['kickstart'], image_params['kickseed'] = \
                self._add_image_to_cobbler(image_id, image_type,
                                           image_version, dest,
                                           kickstart_dest, kickseed_dest)
            image_data = {
                'id': image_id,
                'version': image_version,
                'type': image_type,
                'path': dest,
                'category' : image_category,
                'parameters' : image_params}
            self._serverDb.add_image(image_data)
            # Removing the package/image from /etc/contrail_smgr/images/ after it has been added
            os.remove(dest)
        except subprocess.CalledProcessError as e:
            msg = ("upload_image: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            self._smgr_trans_log.log(
                bottle.request,
                self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            resp_msg = self.form_operartion_data(msg, ERR_GENERAL_ERROR,
                                                                    repr(e))
            abort(404, resp_msg)
        #TODO use the below method to return a JSON for all operations commands
        #with status, Move the codes and msg to a seprate file
        msg = "Image Uploaded"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg
    # End of upload_image


    #menthod to add status code and msg for json to be returned.
    def _add_return_status(self, entity, code, msg):
        status = {}
        status['code'] = code
        status['message'] = msg
        entity['status'] = status
        return entity

    #End of _add_return_status

    # The below function takes the tgz path for puppet modules in the repo
    # being added, checks if that version of modules is already added to
    # puppet and adds it if not already added.
    def _add_puppet_modules(self, puppet_modules_tgz, image_id):
        tmpdirname = tempfile.mkdtemp()
        try:
            # change dir to the temp dir created
            cwd = os.getcwd()
            os.chdir(tmpdirname)
            if not os.path.exists(puppet_modules_tgz):
                raise ServerMgrException(_ERR_INVALID_CONTRAIL_PKG, ERR_OPR_ERROR)
            # Copy the tgz to tempdir
            cmd = ("cp -f %s ." %(puppet_modules_tgz))
            subprocess.check_call(cmd, shell=True)
            # untar the puppet modules tgz file
            cmd = ("tar xvzf contrail-puppet-manifest.tgz > /dev/null")
            subprocess.check_call(cmd, shell=True)

            sequence_provisioning_available = \
                os.path.isfile('sequence_provisioning_available')

            # Get puppet manifests version (stored in version file along with manifests)
            puppet_version = 0.0
            if os.path.isfile('version'):
                data = ''
                with open('version', 'r') as versionfile:
                    data=versionfile.read().replace('\n', '')
                # end with
                try:
                    puppet_version = float(data)
                except:
                    puppet_version = 0.0
                # end except
            # end with

            # If the untarred file list has environment directory, copy it's
            # contents to /etc/puppet/environments. This is where the new
            # restructured contrail puppet labs modules are going to be
            # maintained. The old logic is being maintained for safety till
            # the new refactored code is well tested and confirmed to be working.
            # not environment directory can't contain "-". replace with "_".
            version = image_id
            environment_dir = "contrail/environment"
            if os.path.isdir(environment_dir):
                if _ENABLE_NEW_PUPPET_FRAMEWORK:
                    cmd = ("/bin/rm -rf /etc/puppet/environments/"+ image_id.replace('-','_'))
                    subprocess.check_call(cmd, shell=True)
                    # distutils keeps a cache of all paths created. Need to
                    # clear this to re add a path that might have been
                    # previously deleted
                    distutils.dir_util._path_created = {}
                    distutils.dir_util.copy_tree(environment_dir,
                        "/etc/puppet/environments/" + image_id.replace('-','_'))
                distutils.dir_util.remove_tree(environment_dir)
                os.chdir(cwd)
                return version, sequence_provisioning_available, puppet_version
            # end if os.path.isdir
            # Below code is for old versions of contrail (pre-2.0) and old puppet modules.
            # Create modules directory if it does not exist.
            target_dir = "/etc/puppet/environments/contrail_" + version + \
                "/modules/contrail_" + version
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            if not os.path.isdir("/etc/puppet/modules/inifile"):
                os.makedirs("/etc/puppet/modules/inifile")
            if not os.path.isdir("/etc/puppet/modules/ceph"):
                os.makedirs("/etc/puppet/modules/ceph")
            if not os.path.isdir("/etc/puppet/modules/stdlib"):
                os.makedirs("/etc/puppet/modules/stdlib")
            # This contrail puppet modules version does not exist. Add it.
            cmd = ("cp -rf ./contrail/* " + target_dir)
            subprocess.check_call(cmd, shell=True)
            if os.path.isdir("./inifile"):
                cmd = ("cp -rf ./inifile/* " + "/etc/puppet/modules/inifile")
                subprocess.check_call(cmd, shell=True)
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "directory inifile not in source tar ball - not copied")
            if os.path.isdir("./ceph"):
                cmd = ("cp -rf ./ceph/* " + "/etc/puppet/modules/ceph")
                subprocess.check_call(cmd, shell=True)
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "directory ceph not in source tar ball - not copied")
            if os.path.isdir("./stdlib"):
                cmd = ("cp -rf ./stdlib/* " + "/etc/puppet/modules/stdlib")
                subprocess.check_call(cmd, shell=True)
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "directory stdlib not in source tar ball - not copied")
            # Replace the class names in .pp files to have the version number
            # of this contrail modules.
            filelist = target_dir + "/manifests/*.pp"
            cmd = ("sed -i \"s/__\$version__/contrail_%s/g\" %s" %(
                    version, filelist))
            subprocess.check_call(cmd, shell=True)

            cmd = ("sed -i \"s/__\$VERSION__/Contrail_%s/g\" %s" %(
                    version, filelist))
            subprocess.check_call(cmd, shell=True)
            os.chdir(cwd)
            return version, sequence_provisioning_available, puppet_version
        except subprocess.CalledProcessError as e:
            shutil.rmtree(tmpdirname) # delete directory
            msg = ("add_puppet_modules: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        finally:
            try:
                os.chdir(cwd)
                shutil.rmtree(tmpdirname) # delete directory
            except OSError, e:
                if e.errno != 2: # code 2 - no such file or directory
                    raise
    # end _add_puppet_modules

    # Create yum repo for "centos" and "fedora" packages.
    # repo created includes the wrapper package too.
    def _create_yum_repo(
        self, image_id, image_type, image_version, dest):
        puppet_manifest_version = ""
        try:
            cmd = 'file %s'%dest
            output = subprocess.check_output(cmd, shell=True)
            # create a repo-dir where we will create the repo
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
            cmd = "/bin/rm -fr %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = "mkdir -p %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.check_call(cmd, shell=True)
            if output and 'gzip compressed data' in output:
                cmd = ("tar xvzf $(ls *.tgz) > /dev/null")
                subprocess.check_call(cmd, shell=True)
                cmd = (
                    "rpm2cpio $(ls contrail-puppet*) | cpio -ivd ./opt/contrail/puppet/contrail-puppet-manifest.tgz > /dev/null")
                subprocess.check_call(cmd, shell=True)
            elif output and 'RPM' in output:
                # Extract .tgz of contrail puppet manifest files
                cmd = (
                    "rpm2cpio %s | cpio -ivd ./opt/contrail/puppet/"
                    "contrail-puppet-manifest.tgz > /dev/null" %(dest))
                subprocess.check_call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            puppet_modules_tgz_path = mirror + \
                "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version, sequence_provisioning_available, puppet_version  = self._add_puppet_modules(
                puppet_modules_tgz_path, image_id)
            if output and 'RPM' in output:
                # Extract .tgz of other packages from the repo
                cmd = (
                    "rpm2cpio %s | cpio -ivd ./opt/contrail/contrail_packages/"
                    "contrail_rpms.tgz > /dev/null" %(dest))
                subprocess.check_call(cmd, shell=True)
                cmd = ("mv ./opt/contrail/contrail_packages/contrail_rpms.tgz .")
                subprocess.call(cmd, shell=True)
            cmd = ("rm -rf opt")
            subprocess.check_call(cmd, shell=True)
            if output and 'RPM' in output:
                # untar tgz to get all packages
                cmd = ("tar xvzf contrail_rpms.tgz > /dev/null")
                subprocess.check_call(cmd, shell=True)
                # remove the tgz file itself, not needed any more
                cmd = ("rm -f contrail_rpms.tgz")
                subprocess.check_call(cmd, shell=True)
            # build repo using createrepo
            cmd = ("createrepo . > /dev/null")
            subprocess.check_call(cmd, shell=True)
            # change directory back to original
            os.chdir(cwd)
            # cobbler add repo
            self._smgr_cobbler.create_repo(
                image_id, mirror)
            return puppet_manifest_version, sequence_provisioning_available, puppet_version
        except subprocess.CalledProcessError as e:
            msg = ("create_yum_repo: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        except Exception as e:
            raise(e)
    # end _create_yum_repo

    # Create DPDK repo
    def _create_dpdk_repo(self, mirror):
        dpdk_depends_pkg_list = glob.glob('%s/dpdk-depends*.deb' % mirror)

        if len(dpdk_depends_pkg_list) :
            self._smgr_log.log(self._smgr_log.INFO, "Creating DPDK repo")
            cmd = ("/bin/rm -fr  %s/dpdk_depends" % mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = ("mkdir -p %s/dpdk_depends" % mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = ("cp -v -a %s %s/dpdk_depends/" % ( dpdk_depends_pkg_list[0], mirror))
            subprocess.check_call(cmd, shell=True)
            cmd = (
                "dpkg -x %s/dpdk_depends/dpdk*.deb %s/dpdk_depends > /dev/null" %(mirror, mirror ))
            subprocess.check_call(cmd, shell=True)
            cmd = ("cp -R -v -a /opt/contrail/server_manager/reprepro/dpdk_depends_conf %s/dpdk_depends/conf" % mirror)
            subprocess.check_call(cmd, shell=True)

            cmd = ("reprepro includedeb contrail-dpdk-depends %s/dpdk_depends/opt/contrail/contrail_install_repo_dpdk/*.deb" % mirror)
            dpdk_repo_dir = "%s/dpdk_depends" % (mirror)
            subprocess.check_call(cmd, cwd= dpdk_repo_dir, shell=True)
        else:
            self._smgr_log.log(self._smgr_log.INFO, "Not creating DPDK repo")

        return

    # Create debian repo
    # Create debian repo for "debian" packages.
    # repo created includes the wrapper package too.
    def _create_deb_repo(
        self, image_id, image_type, image_version, dest):
        puppet_manifest_version = ""
        tgz_image = False
        try:
            # create a repo-dir where we will create the repo
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
            cmd = "/bin/rm -fr %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = "mkdir -p %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.check_call(cmd, shell=True)
            # Extract .tgz of other packages from the repo
            cmd = 'file %s'%dest
            output = subprocess.check_output(cmd, shell=True)
            #If the package is tgz or debian extract it appropriately
            if output:
                if 'Debian binary package' in output:
                    cmd = (
                        "dpkg -x %s . > /dev/null" %(dest))
                elif 'gzip compressed data' in output:
                    cmd = ("tar xvzf %s > /dev/null" %(dest))
                    tgz_image = True
            subprocess.check_call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            #If tgz, then extract the debian package within the tgz and get the puppet manifest tgz
            if tgz_image:
                tmpdirname = tempfile.mkdtemp()
                if not glob.glob('contrail-puppet_*.deb'):
                    raise ServerMgrException(_ERR_INVALID_CONTRAIL_PKG, ERR_OPR_ERROR)
                cmd = ("dpkg-deb -x $(ls contrail-puppet_*.deb) %s" %(tmpdirname))
                subprocess.check_call(cmd, shell=True)
                puppet_modules_tgz_path = tmpdirname + "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            else:
                puppet_modules_tgz_path = mirror + \
                    "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version, sequence_provisioning_available, puppet_version  = self._add_puppet_modules(
                puppet_modules_tgz_path, image_id)
            # check if its a new version where repo pinning changes are brought in
            if tgz_image:
                archive = tarfile.open(puppet_modules_tgz_path, 'r')
            else:
                archive = tarfile.open('./opt/contrail/puppet/contrail-puppet-manifest.tgz', 'r')
            if './contrail/environment/modules/contrail/files/contrail_repo_preferences' in archive.getnames():
                repo_pinning = True
            else:
                repo_pinning = False
            if not tgz_image:
                cmd = ("mv ./opt/contrail/contrail_packages/contrail_debs.tgz .")
                subprocess.check_call(cmd, shell=True)
                cmd = ("rm -rf opt")
                subprocess.check_call(cmd, shell=True)
                # untar tgz to get all packages
                cmd = ("tar xvzf contrail_debs.tgz > /dev/null")
                subprocess.check_call(cmd, shell=True)
                # remove the tgz file itself, not needed any more
                cmd = ("rm -f contrail_debs.tgz")
                subprocess.check_call(cmd, shell=True)
            # build repo using dpkg-scanpackages or reprepro based on repo pinning availability
            if repo_pinning:
                cmd = ("cp -v -a /opt/contrail/server_manager/reprepro/conf %s/" % mirror)
                subprocess.check_call(cmd, shell=True)
                cmd = ("reprepro includedeb contrail %s/*.deb" % mirror)
                subprocess.check_call(cmd, shell=True)
                #create dpdk-depends repo
                self._create_dpdk_repo(mirror)
            else:
                cmd = ("dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz")
                subprocess.check_call(cmd, shell=True)
            #delete the tmpdirectory created for extracting puppet debian file
            if 'gzip compressed data' in output:
                shutil.rmtree(tmpdirname)
            # change directory back to original
            os.chdir(cwd)
            # cobbler add repo
            # TBD - This is working for "centos" only at the moment,
            # will need to revisit and make it work for ubuntu - Abhay
            # self._smgr_cobbler.create_repo(
            #     image_id, mirror)
            return puppet_manifest_version, sequence_provisioning_available, puppet_version
        except subprocess.CalledProcessError as e:
            msg = ("create_deb_repo: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        except Exception as e:
            raise(e)
    # end _create_deb_repo

    # Create storage debian repo
    # Create storage debian repo for "debian" packages.
    # repo created includes the wrapper package too.
    def _create_storage_deb_repo(
        self, image_id, image_type, image_version, dest):
        try:
            # create a repo-dir where we will create the repo
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
            cmd = "/bin/rm -fr %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = "mkdir -p %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = 'file %s'%dest
            output = subprocess.check_output(cmd, shell=True)
            #Check if the package is a tgz or deb and get its version
            if output and 'gzip compressed data' in output:
                cmd = ("tar xvzf %s > /dev/null" %(dest))
            elif 'Debian binary package' in output:
                # Extract .tgz of other packages from the repo
                cmd = (
                    "dpkg -x %s . > /dev/null" %(dest))
            subprocess.check_call(cmd, shell=True)
            if 'Debian binary package' in output:
                cmd = ("mv ./opt/contrail/contrail_packages/contrail_storage_debs.tgz .")
                subprocess.check_call(cmd, shell=True)
            #Since CentOS is new but default repopinning will be enabled for it
            # check if its a new version where repo pinning changes are brought in
            if os.path.isfile('./opt/contrail/contrail_packages/.repo_pinning') or (output and 'gzip compressed data' in output):
                repo_pinning = True
            else:
                repo_pinning = False
            if 'Debian binary package' in output:
                cmd = ("rm -rf opt")
                subprocess.check_call(cmd, shell=True)
                # untar tgz to get all packages
                cmd = ("tar xvzf contrail_storage_debs.tgz > /dev/null")
                subprocess.check_call(cmd, shell=True)
                # remove the tgz file itself, not needed any more
                cmd = ("rm -f contrail_storage_debs.tgz")
                subprocess.check_call(cmd, shell=True)

            # if repo pinning is enabled use reprepo to create the repo
            if repo_pinning:
                cmd = ("cp -v -a /opt/contrail/server_manager/reprepro/conf %s/" % mirror)
                subprocess.check_call(cmd, shell=True)
                cmd = ("reprepro includedeb contrail %s/*.deb" % mirror)
                subprocess.check_call(cmd, shell=True)
            else:
                cmd = (
                    "dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz")
                subprocess.check_call(cmd, shell=True)

            # change directory back to original
            os.chdir(cwd)
            # cobbler add repo
            # TBD - This is working for "centos" only at the moment,
            # will need to revisit and make it work for ubuntu - Abhay
            # self._smgr_cobbler.create_repo(
            #     image_id, mirror)
        except subprocess.CalledProcessError as e:
            msg = ("create_storage_deb_repo: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        except Exception as e:
            raise(e)
    # end _create_storage_deb_repo


    # Given a package, create repo for it on cobbler. The repo created is
    # modified to include the wrapper package too (!!). This is needed as
    # setup.sh and other scripts needed on target can be easily installed.
    def _create_repo(
        self, image_id, image_type, image_version, dest):
        puppet_manifest_version = ""
        puppet_version = 0.0
        sequence_provisioning_available = False
        try:
            if (image_type == "contrail-centos-package"):
                puppet_manifest_version, sequence_provisioning_available, puppet_version  = self._create_yum_repo(
                    image_id, image_type, image_version, dest)
            elif (image_type == "contrail-ubuntu-package"):
                puppet_manifest_version, sequence_provisioning_available, puppet_version  = self._create_deb_repo(
                    image_id, image_type, image_version, dest)
            elif (image_type == "contrail-storage-ubuntu-package"):
                self._create_storage_deb_repo(
                    image_id, image_type, image_version, dest)

            else:
                pass
            return puppet_manifest_version, sequence_provisioning_available, puppet_version
        except Exception as e:
            raise(e)
    # end _create_repo

    # Copy to Cobbler as a distro and profile.
    # Distro related stuff. Check if distro for given ISO exists already.
    # The convention we will follow is that distro name is same as ISO
    # file name, without .iso extension. The iso is copied to a directory
    # with the same name under html root directory/contrail/images.
    # e.g. if iso is xyz.iso, we mount this iso under
    # /var/www/html/contrail/images. The distro name is XYZ, the profile
    # name is XYZ-P.
    def _add_image_to_cobbler(self, image_id, image_type,
                              image_version, dest,
                              kickstart='', kickseed=''):
        # Mount the ISO
        distro_name = image_id
        copy_path = self._args.html_root_dir + \
            'contrail/images/' + distro_name

        try:
            ks_file = kseed_file = ''
            if kickstart:
                ks_file = kickstart
            if kickseed:
                kseed_file = kickseed
            if ((image_type == "fedora") or (image_type == "centos")
                or (image_type == "redhat")):
                kernel_file = "/isolinux/vmlinuz"
                initrd_file = "/isolinux/initrd.img"
                if not ks_file:
                    ks_file = self._args.html_root_dir + \
                        "kickstarts/contrail-centos.ks"
                    kickstart = ks_file
                kernel_options = ''
                ks_meta = ''
            elif ((image_type == "esxi5.1") or
                  (image_type == "esxi5.5")):
                kernel_file = "/mboot.c32"
                initrd_file = "/imgpayld.tgz"
                if not ks_file:
                    ks_file = self._args.html_root_dir + \
                        "kickstarts/contrail-esxi.ks"
                    kickstart = ks_file
                kernel_options = ''
                ks_meta = 'ks_file=%s' %(ks_file)
            elif (image_type == "ubuntu"):
                kernel_file = "/install/netboot/ubuntu-installer/amd64/linux"
                initrd_file = (
                    "/install/netboot/ubuntu-installer/amd64/initrd.gz")
                if not ks_file:
                    ubuntu_ks_file = 'kickstarts/contrail-ubuntu_trusty.ks'
                    kickstart = self._args.html_root_dir + ubuntu_ks_file
                else:
                    ubuntu_ks_file = 'contrail/images/' + ks_file.split('/').pop()
                if not kseed_file:
                    ks_file = self._args.html_root_dir + \
                        "kickstarts/contrail-ubuntu_trusty.seed"
                    kickseed = ks_file
                else:
                    ks_file = kseed_file
                kernel_options = (
                    "lang=english console-setup/layoutcode=us locale=en_US "
                    "auto=true console-setup/ask_detect=false "
                    "priority=critical interface=auto "
                    "console-keymaps-at/keymap=us "
                    "ks=http://%s/%s ") % (
                    self._args.listen_ip_addr, ubuntu_ks_file)
                ks_meta = ''
            else:
                #TODO Raise an exception here
                self._smgr_log.log(self._smgr_log.ERROR, "Invalid image type")
                msg = "invalid image type"
                raise ServerMgrException(msg)

            self._mount_and_copy_iso(dest, copy_path, distro_name,
                                     kernel_file, initrd_file, image_type)
            # Setup distro information in cobbler
            self._smgr_cobbler.create_distro(
                distro_name, image_type,
                copy_path, kernel_file, initrd_file,
                self._args.listen_ip_addr)

            # Setup profile information in cobbler
            profile_name = distro_name
            self._smgr_cobbler.create_profile(
                profile_name, distro_name, image_type,
                ks_file, kernel_options, ks_meta)

            # Sync the above information
            self._smgr_cobbler.sync()
            return kickstart, kickseed
        except ServerMgrException as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding image to cobbler %s" % repr(e))
            raise
        except Exception as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding image to cobbler %s" % repr(e))
            raise ServerMgrException(repr(e))
    # End of _add_image_to_cobbler

    # API call to delete a cluster from server manager config. Along with
    # cluster, all servers in that cluster and associated roles are also
    # deleted.
    def delete_cluster(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_cluster")
        try:
            ret_data = self.validate_smgr_request("CLUSTER", "DELETE",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                if match_key:
                    match_dict[match_key] = match_value
                self._serverDb.delete_cluster(match_dict)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Error while deleting cluster %s" % (repr(e)))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER)
        msg = "CLUSTER deleted"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg

    # end delete_cluster

    # API call to delete a server from the configuration.
    def delete_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_server")
        try:
            ret_data = self.validate_smgr_request("SERVER", "DELETE",
                                                         bottle.request)

            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value

            servers = self._serverDb.get_server(
                match_dict, detail= True)
            self._serverDb.delete_server(match_dict)
            # delete the system entries from cobbler
            for server in servers:
                if server['id'] and self._smgr_cobbler:
                    self._smgr_cobbler.delete_system(server['host_name'])
            # Sync the above information
            if self._smgr_cobbler:
                self._smgr_cobbler.sync()
            # Inventory Delete Info Trigger
            gevent.spawn(self._server_inventory_obj.handle_inventory_trigger, "delete", servers)
            self._smgr_certs.delete_server_cert(server)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Unable to delete server, %s" % (repr(e)))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER)
        msg = "Server deleted"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg
    # end delete_server

    # API call to delete a dhcp subnet from the configuration.
    def delete_dhcp_subnet(self):
        try:
            ret_data = self.validate_smgr_request("DHCP_SUBNET", "DELETE",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                match_dict[match_key] = match_value

            self._serverDb.delete_dhcp_subnet(match_dict)
            self._dhcp_template_obj.generate_dhcp_template()
            # Sync the above information
            if self._smgr_cobbler:
                self._smgr_cobbler.sync()
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Unable to delete DHCP Subnet, %s" % (repr(e)))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                       None)
            abort(404, resp_msg)
        #self._smgr_trans_log.log(bottle.request,
        #                        self._smgr_trans_log.DELETE_SMGR_CFG_SERVER)
        msg = "DHCP Subnet deleted"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg
    # end delete_dhcp_subnet

    # API call to delete a dhcp host from the configuration.
    def delete_dhcp_host(self):
        try:
            ret_data = self.validate_smgr_request("DHCP_HOST", "DELETE",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                match_dict = {}
                match_dict[match_key] = match_value

            self._serverDb.delete_dhcp_host(match_dict)
            self._dhcp_template_obj.generate_dhcp_template()
            # Sync the above information
            if self._smgr_cobbler:
                self._smgr_cobbler.sync()
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Unable to delete DHCP Host, %s" % (repr(e)))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                       None)
            abort(404, resp_msg)
        #self._smgr_trans_log.log(bottle.request,
        #                        self._smgr_trans_log.DELETE_SMGR_CFG_SERVER)
        msg = "DHCP Host deleted"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg
    # end delete_dhcp_host

    # API Call to delete an image
    def delete_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_image")
        try:
            ret_data = self.validate_smgr_request("IMAGE", "DELETE",
                                                  bottle.request)
            if ret_data["status"] == 0:
                image_dict = {}
                image_dict[ret_data["match_key"]] = ret_data["match_value"]
            else:
                msg = "Validation failed"
                self.log_and_raise_exception(msg)
            images = self._serverDb.get_image(image_dict, detail=True)
            if not images:
                msg = "Image %s doesn't exist" % (image_dict)
                self.log_and_raise_exception(msg)
                self._smgr_log.log(self._smgr_log.ERROR,
                        msg)
            image = images[0]
            image_id = image['id']
            if (image['type'] in self._contrail_container_list):
                image_params   = image.get("parameters", {})
                for container in (eval(image_params)).get("containers", None):
                    if "docker_image_id" in container.keys():
                        print "removing %s" % container["docker_image_id"]
                        self._docker_cli.remove_containers(container["docker_image_id"])
                self._serverDb.delete_image(image_dict)
                msg = "Image Deleted"
                resp_msg = self.form_operartion_data(msg, 0, None)
                return resp_msg

            package = os.path.basename(image['path'])
            if ((image['type'] == 'contrail-ubuntu-package') or
                (image['type'] == 'contrail-centos-package') or
                (image['type'] == 'contrail-storage-ubuntu-package')):
                if package.endswith('.tgz'):
                    extn = '.tgz'
                else:
                    extn = '.deb'
                ext_dir = {
                    "contrail-ubuntu-package" : extn,
                    "contrail-centos-package": ".rpm",
                    "contrail-storage-ubuntu-package": ".deb"}
                if os.path.isfile(self._args.server_manager_base_dir + 'images/' + image_id + ext_dir[image['type']]):
                    os.remove(self._args.server_manager_base_dir + 'images/' +
                              image_id + ext_dir[image['type']])

                # remove repo dir
                shutil.rmtree(
                    self._args.html_root_dir + "contrail/repo/" +
                    image_id, True)
                # remove puppet modules
                # new contrail packages manifests dir
                puppet_manifest_dir = "/etc/puppet/environments/" + image_id.replace('-', '_')
                if os.path.isdir(puppet_manifest_dir):
                    shutil.rmtree(
                        puppet_manifest_dir, True
                    )
                # old contrail packages manifests dir
                puppet_manifest_old_dir = "/etc/puppet/environments/contrail_" + image_id
                if os.path.isdir(puppet_manifest_old_dir):
                    shutil.rmtree(
                        puppet_manifest_old_dir, True
                    )
                # delete repo from cobbler
                if self._smgr_cobbler:
                    self._smgr_cobbler.delete_repo(image_id)
            else:
                if self._smgr_cobbler:
                    # delete corresponding distro from cobbler
                    self._smgr_cobbler.delete_distro(image_id)
                    # Sync the above information
                    self._smgr_cobbler.sync()
                # remove the file
                if os.path.isfile(self._args.server_manager_base_dir + 'images/' + image_id + '.iso'):
                        os.remove(self._args.server_manager_base_dir + 'images/' +
                                  image_id + '.iso')
                # Remove the tree copied under cobbler.
                dir_path = self._args.html_root_dir + \
                    'contrail/images/' + image_id
                shutil.rmtree(dir_path, True)
                ks_path = self._args.html_root_dir + \
                    'contrail/images/' + image_id + '.ks'
                if os.path.exists(ks_path):
                    os.remove(ks_path)
                kseed_path = self._args.html_root_dir + \
                    'contrail/images/' + image_id + '.seed'
                if os.path.exists(kseed_path):
                    os.remove(kseed_path)
            # remove the entry from DB
            self._serverDb.delete_image(image_dict)
        except ServerMgrException as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                "Unable to delete image, %s" % (repr(e)))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                    self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE)
        msg = "Image Deleted"
        resp_msg = self.form_operartion_data(msg, 0, None)
        return resp_msg

    # End of delete_image

    # API to create the server manager configuration DB from provided JSON
    # file.
    def create_server_mgr_config(self):
        entity = bottle.request.json
        if not entity:
            msg =  "No JSON config file specified"
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)

        # Validate the config for sematic correctness.
        self._validate_config(entity)
        # Store the initial configuration in our DB
        try:
            self._create_server_manager_config(entity)
        except Exception as e:
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        return entity
    # end create_server_mgr_config

    # API to process DHCP event from cobbler. This event notifies of a server
    # getting or releasing dynamic IP from cobbler DHCP.
    def process_dhcp_event(self):
        action = bottle.request.query.action
        entity = bottle.request.json
        try:
            self._serverDb.server_discovery(action, entity)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_SERVER,
                                     False)
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                           self._smgr_trans_log.PUT_SMGR_CFG_SERVER)
        return entity
    # end process_dhcp_event

    def log_and_raise_exception(self, msg, err_code = ERR_OPR_ERROR):
         self._smgr_log.log(self._smgr_log.ERROR, msg)
         raise ServerMgrException(msg, err_code)

    def get_package_image(self, package_image_id):
        package_image = {}
        if not package_image_id:
            return package_image_id, package_image
        packages = self._serverDb.get_image(
            {"id": package_image_id}, detail=True)
        if not packages:
            msg = "No package %s found" % (package_image_id)
            raise ServerMgrException(msg)
        if packages[0]['category'] and packages[0]['category'] != 'package' and packages[0]['category'] != 'container':
            msg = "Target Package Category is not package, it is %s" % (packages[0]['category'])
            raise ServerMgrException(msg)
        if packages[0]['type'] not in self._package_types:
            msg = "%s is not a package" % (package_image_id)
            raise ServerMgrException(msg)
        return package_image_id, packages[0]
    # end get_package_image

    def get_base_image(self, base_image_id):
        base_image = {}
        if not base_image_id:
            return base_image_id, base_image
        images = self._serverDb.get_image(
            {"id": base_image_id}, detail=True)
        if not images:
            msg = "No Image %s found" % (base_image_id)
            raise ServerMgrException(msg, ERR_IMG_NOT_FOUND)
        if images[0]['category'] and images[0]['category'] != 'image':
            msg = "Target Image Category is not image, it is %s" % (images[0]['category'])
            raise ServerMgrException(msg, ERR_IMG_CATEGORY_ERROR)
        if images[0]['type'] not in self._iso_types:
            msg = "Image %s is not an iso" % (base_image_id)
            raise ServerMgrException(msg, ERR_IMG_TYPE_INVALID)
        return base_image_id, images[0]
    # end get_base_image

    def get_interfaces(self, server):
        #Fetch network realted data and push to reimage
        if 'network' in server and server['network']:
            network_dict = server['network']
            if isinstance(network_dict, basestring):
                network_dict = eval(network_dict)
            if not network_dict:
                return None
            mgmt_intf = network_dict['management_interface']
            interface_list = network_dict["interfaces"]
            return_intf_dict = {}
            for intf in interface_list:
                intf_dict = {}
                name = intf['name']
                ip_addr = intf.get('ip_address', None)
                if ip_addr is None:
                    continue
                ip = IPNetwork(ip_addr)
                intf_dict['ip'] = str(ip.ip)
                intf_dict['d_gw'] = intf.get('default_gateway', None)
                intf_dict['dhcp'] = intf.get('dhcp', None)
                intf_dict['type'] = intf.get('type', None)
                intf_dict['bond_opts'] = intf.get('bond_options', None)
                intf_dict['mem_intfs'] = intf.get('member_interfaces', None)
                intf_dict['mac_address'] = intf.get('mac_address', None)
                intf_dict['mask'] = str(ip.netmask)

                return_intf_dict[name] = intf_dict
            return return_intf_dict
        return None

    def create_vm(self, server):
        vm_params = server['vm_parameters']
        cpus = vm_params.get('cpus', 4)
        memory = vm_params.get('memory', 8192)
        disksize = vm_params.get('disksize', '80G')
        physical_host = vm_params.get('physical_host_ip')
        networks_str = vm_params['network']
        nics = ''
        networks = eval(networks_str)
        for intf in networks['interfaces']:
            mac = intf['mac_address']
            bridge = intf['physical_host_bridge']
            uplink = intf['physical_host_uplink']
            nics = nics + " %s,%s,%s" %(mac, bridge, uplink)
        name = server['server_id']
        username = vm_params.get('physical_host_username', 'root')
        password = vm_params.get('physical_host_password', 'c0ntrail123')
        count = 1
        cmd = "python /opt/contrail/server_manager/create_vm.py"
        cmd = cmd + " -c %d -m %d -s %s" %(cpus, memory, physical_host)
        cmd = cmd + " -d %s -nics %s" %(disksize, nics)
        cmd = cmd + " -H %s -U %s -P %s" %(name, username, password)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,\
                                stderr= subprocess.PIPE, shell = True)
        o, e = proc.communicate()
        if o:
            self._smgr_log.log(self._smgr_log.INFO, \
                               "issued CREATE VM commands:\n%s" %o)
        if e:
            self._smgr_log.log(self._smgr_log.ERROR, \
                               "issued CREATE VM commands:\n%s" %e)
            cmd = "python /opt/contrail/server_manager/create_vm.py"
            cmd = cmd + " -H %s -U %s -P % -D" %(name, username, password)
            subprocess.call(cmd, shell =True)
            self.log_and_raise_exception(e)
    # end create_vm

    # This call returns information about a provided server.
    # If no server if provided, information about all the servers
    # in server manager configuration is returned.
    def reimage_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "reimage_server")
        try:
            ret_data = self.validate_smgr_request("SERVER", "REIMAGE", bottle.request)
            if ret_data['status'] == 0:
                base_image_id = ret_data['base_image_id']
                package_image_id = ret_data['package_image_id']
                match_key = ret_data['match_key']
                match_value = ret_data['match_value']
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value
                do_reboot = ret_data['do_reboot']

            reboot_server_list = []
            reimage_server_list = []
            base_image = {}
            if base_image_id:
                base_image_id, base_image = self.get_base_image(base_image_id)
            servers = self._serverDb.get_server(match_dict, detail=True)
            if len(servers) == 0:
                msg = "No Servers found for %s" % (match_value)
                self.log_and_raise_exception(msg)
            reimage_status = {}
            reimage_status['return_code'] = 0
            reimage_status['server'] = []

            # Get all the DHCP IPs under the control of Cobbler
            valid_dhcp_ip_list = self.get_dhcp_ips()

            for server in servers:
                cluster = None
                server_parameters = eval(server['parameters'])
                # build all parameters needed for re-imaging
                if server['cluster_id']:
                    cluster = self._serverDb.get_cluster(
                        {"id" : server['cluster_id']},
                        detail=True)
                cluster_parameters = {}
                if cluster and cluster[0]['parameters']:
                    cluster_parameters = eval(cluster[0]['parameters'])

                if 'ip_address' in server and server['ip_address'] and self._using_dhcp_management:
                    if str(server['ip_address']) not in valid_dhcp_ip_list:
                        msg = "The server with id %s cannot be reimaged. \
                               There is no cobbler DHCP configuration for the ip address of this server \
                               : %s" % (server['id'], server['ip_address'])
                        raise ServerMgrException(msg)

                image = base_image
                if not image:
                    base_image_id = server.get('base_image_id', '')
                    if not base_image_id and cluster:
                        base_image_id = cluster[0].get('base_image_id', '')
                    image_id, image = self.get_base_image(base_image_id)
                if not image:
                    msg = "No valid image id found for server %s" % (server['id'])
                    raise ServerMgrException(msg)
                password = subnet_mask = gateway = domain = None
                server_id = server['id']


                #Move this to a function and return a single error
                if 'password' in server and server['password']:
                    password = server['password']
                elif 'password' in cluster_parameters and cluster_parameters['password']:
                    password = cluster_parameters['password']
                else:
                    server['password'] = ''

                if 'subnet_mask' in server and server['subnet_mask']:
                    subnet_mask = server['subnet_mask']
                elif 'subnet_mask' in cluster_parameters and cluster_parameters['subnet_mask']:
                    subnet_mask = cluster_parameters['subnet_mask']
                else:
                    msg = "Missing prefix/mask for " + server_id
                    server['subnet_mask'] = ''

                if 'gateway' in server and server['gateway']:
                    gateway = server['gateway']
                elif 'gateway' in cluster_parameters and cluster_parameters['gateway']:
                    gateway = cluster_parameters['gateway']
                else:
                    msg = "Missing gateway for " + server_id
                    server['gateway'] = ''

                if 'domain' in server and server['domain']:
                    domain = server['domain']
                elif 'domain' in cluster_parameters and cluster_parameters['domain']:
                    domain = cluster_parameters['domain']
                else:
                    msg = "Missing domain for " + server_id
                    server['domain'] = ''

                if 'ip_address' in server and server['ip_address']:
                    ip = server['ip_address']
                else:
                    msg = "Missing ip for " + server_id
                    server['ip_address'] = ''



                reimage_parameters = {}
                if ((image['type'] == 'esxi5.1') or
                    (image['type'] == 'esxi5.5')):
                    reimage_parameters['server_license'] = server_parameters.get(
                        'server_license', '')
                    reimage_parameters['esx_nicname'] = server_parameters.get(
                        'esx_nicname', 'vmnic0')
                reimage_parameters['server_id'] = server['id']
                reimage_parameters['server_host_name'] = server['host_name']
                reimage_parameters['server_ip'] = server['ip_address']
                reimage_parameters['server_mac'] = server['mac_address']
                reimage_parameters['server_password'] = self._encrypt_password(
                    password)
                reimage_parameters['server_mask'] = subnet_mask
                reimage_parameters['server_gateway'] = gateway
                reimage_parameters['server_domain'] = domain
                if 'interface_name' not in server_parameters:
                    msg = "Missing interface name for " + server_id
                    self.log_and_raise_exception(msg)
                if 'ipmi_address' in server and server['ipmi_address'] == None:
                    msg = "Missing ipmi address for " + server_id
                    server['ipmi_address'] = ''
                reimage_parameters['server_ifname'] = server_parameters['interface_name']
                reimage_parameters['ipmi_type'] = server.get('ipmi_type')
                if not reimage_parameters['ipmi_type']:
                    reimage_parameters['ipmi_type'] = self._args.ipmi_type
                reimage_parameters['ipmi_username'] = server.get('ipmi_username')
                if not reimage_parameters['ipmi_username']:
                    reimage_parameters['ipmi_username'] = self._args.ipmi_username
                reimage_parameters['ipmi_password'] = server.get('ipmi_password')
                if not reimage_parameters['ipmi_password']:
                    reimage_parameters['ipmi_password'] = self._args.ipmi_password
                reimage_parameters['ipmi_interface'] = server.get('ipmi_interface')
                if not reimage_parameters['ipmi_interface']:
                    reimage_parameters['ipmi_interface'] = self._args.ipmi_interface
                reimage_parameters['ipmi_address'] = server.get(
                    'ipmi_address', '')
                reimage_parameters['partition'] = server_parameters.get('partition', '')
                reimage_parameters['vm_parameters'] = server_parameters.get('vm_parameters', None)
                if reimage_parameters['vm_parameters']:
                    reimage_parameters['vm_parameters']['network'] = \
                                                    server.get('network', None)

                execute_script = self.build_server_cfg(server)
                host_name = server['host_name']

                #network
                if execute_script:
                    reimage_parameters['config_file'] = \
                                "http://%s/contrail/config_file/%s.sh" % \
                                (self._args.listen_ip_addr, host_name)

                _mandatory_reimage_params = {"server_password": "password",
                            "server_domain":"domain", "server_ifname" :"interface_name"}

                msg = ''
                for k,v in _mandatory_reimage_params.items():
                    if k not in reimage_parameters or \
                        reimage_parameters[k] == '' or \
                        reimage_parameters[k] == None:
                        msg += "%s " % v
                if msg != '':
                    err_msg = "Fields %s not present" % msg
                    self.log_and_raise_exception(err_msg)
                reimage_server_entry = {'image' : image,
                                        'package_image_id' : package_image_id,
                                        'reimage_parameters' : reimage_parameters}
                reimage_server_list.append(reimage_server_entry)

                # Build list of servers to be rebooted.
                reboot_server = {
                    'id' : server['id'],
                    'host_name' : server['host_name'],
                    'domain' : domain,
                    'ip' : server.get("ip_address", ""),
                    'password' : password,
                    'ipmi_address' : server.get('ipmi_address',"") }
                reboot_server_list.append(
                    reboot_server)
                server_status = {}
                server_status['id'] = server['id']
                server_status['base_image'] =  image['id']
                reimage_status['server'].append(server_status)
            # end for server in servers

            # Add the request to reimage_queue
            reimage_item = ('reimage',reimage_server_list, reboot_server_list, do_reboot)
            self._reimage_queue.put_nowait(reimage_item)
            self._smgr_log.log(self._smgr_log.DEBUG, "reimage queued. Number of servers reimaged is %d:" %len(reimage_server_list))
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
            reimage_status['return_code'] = e.ret_code
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE,
                                     False)
            print 'Exception error is: %s' % e
            resp_msg = self.form_operartion_data("Error in re-imaging server",
                                                 ERR_GENERAL_ERROR,
                                                 None)
            abort(404, resp_msg)
            reimage_status['return_code'] = ERR_GENERAL_ERROR
        reimage_status['return_message'] = "server(s) reimage queued"
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE)

        return reimage_status
    # end reimage_server

    def get_member_interfaces(self, network_dict, member_intfs):
        new_member_list = []
        if not member_intfs:
            return new_member_list
        interface_list = network_dict["interfaces"]
        for intf in interface_list:
            name = intf.get('name', '')
            if name and name in member_intfs:
                mac_address = intf.get('mac_address', '').lower()
                if mac_address:
                    new_member_list.append(mac_address)
                else:
                    new_member_list.append(name)
        return new_member_list

    # end get_member_interfaces

    def build_server_cfg(self, server):
        #Fetch network realted data and push to reimage
        execute_script = False
        network = server.get('network', "{}")
        if network and eval(network):
            network_dict = eval(network)
            mgmt_intf = network_dict['management_interface']
            interface_list = network_dict["interfaces"]
            device_str = "#!/bin/bash\n"
            for intf in interface_list:
                name = intf['name']
                intf_name = name
                ip_addr = intf.get('ip_address', None)
                if ip_addr is None:
                    continue
                ip = IPNetwork(ip_addr)
                d_gw = intf.get('default_gateway', None)
                dhcp = intf.get('dhcp', None)
                mtu = intf.get('mtu', '')
                vlan = intf.get('vlan','')

                if mtu:
                    mtu = '--mtu %s' %mtu

                if vlan:
                    vlan = '--vlan %s' %vlan
                else:
                    vlan = ''

                type = intf.get('type', None)
                #form string
                if type and type.lower() == 'bond':
                    bond_opts = intf.get('bond_options', {})
                    member_intfs = self.get_member_interfaces(network_dict,
                                                              intf.get('member_interfaces', []))
                    if dhcp:
                        device_str+= ("python /root/interface_setup.py \
--device %s --members %s --bond-opts \"%s\" --dhcp %s\n") % \
                        (name, " ".join(member_intfs), json.dumps(bond_opts), vlan)
                    #If bond interface is the management interface you need to set the gateway
                    elif ((mgmt_intf == name) and d_gw):
                        device_str+= ("python /root/interface_setup.py \
--device %s --members %s --bond-opts \"%s\" --ip %s --gw %s %s\n") % \
                        (name, " ".join(member_intfs), json.dumps(bond_opts), ip_addr, d_gw, vlan)
                    else:
                        device_str+= ("python /root/interface_setup.py \
--device %s --members %s --bond-opts \"%s\" --ip %s %s\n") % \
                        (name, " ".join(member_intfs), json.dumps(bond_opts), ip_addr, vlan)
                    execute_script = True
                else:
                    #Take the mac_address as the name as the interface may be renamed after reboot
                    if 'mac_address' in intf:
                        name = intf['mac_address'].lower()
                    if dhcp:
                        device_str+= ("python /root/interface_setup.py --device %s --dhcp %s\n") %(name, vlan)
                    else:
                        #For static managment interface pass the default gateway
                        if (mgmt_intf == intf_name) and d_gw:
                            device_str+= ("python /root/interface_setup.py --device %s --ip %s --gw %s %s\n") % \
                               (name, ip_addr, d_gw, vlan)
                        else:
                            device_str+= ("python /root/interface_setup.py --device %s --ip %s %s\n") % \
                               (name, ip_addr, vlan)
                execute_script = True
            # Build route configuration and add it
            route_str = self.build_route_cfg(server)
            if route_str:
                device_str+= route_str
                execute_script = True
            sh_file_name = "/var/www/html/contrail/config_file/%s.sh" % (server['id'])
            rm_filename = "rm /etc/init.d/%s.sh" %(server['id'])
            f = open(sh_file_name, "w")
            f.write(device_str)
            f.write(rm_filename)
            f.close()
        return execute_script

    def build_route_cfg(self, server):
        routes = []
        ipaddr=""
        netmask=""
        gateway=""
        device=""
        if not server:
            return routes
        network = eval(server.get('network', '{}'))
        routes = network.get('routes', [])
        routes_str = ''
        for route in routes:
            ipaddr += '%s ' % route.get('network', '')
            netmask += '%s ' % route.get('netmask', '')
            gateway += '%s ' % route.get('gateway', '')
            device += '%s ' % route.get('interface', '')
            if not ipaddr or not netmask or not gateway or not device:
                continue
        routes_str+= ("python /root/staticroute_setup.py --device %s --network %s --netmask %s --gw %s\n") % \
                          (device, ipaddr, netmask, gateway)
        return routes_str


    # This function runs on a separate gevent thread and processes requests for reimage.
    def _reimage_server_cobbler(self):
        self._smgr_log.log(self._smgr_log.DEBUG,
                           "started reimage_server_cobbler greenlet")
        server = {}
        # Since this runs on a separate greenlet, create its own cobbler
        # connection, so that it does not interfere with main thread.
        cobbler_server = None
        if self._is_cobbler_enabled(self._args.cobbler):
            cobbler_server = ServerMgrCobbler(
                self._args.server_manager_base_dir,
                self._args.cobbler_ip_address,
                self._args.cobbler_port,
                self._args.cobbler_username,
                self._args.cobbler_password)
        while True:
            try:
                reimage_item = self._reimage_queue.get()
                optype = reimage_item[0]
                if optype == 'reimage':
                    reimage_server_list = reimage_item[1]
                    reboot_server_list = reimage_item[2]
                    do_reboot = reimage_item[3]
                    if reimage_server_list:
                        for server in reimage_server_list:
                            self._do_reimage_server(
                                server['image'],
                                server['package_image_id'],
                                server['reimage_parameters'],
                                cobbler_server)
                            self._smgr_log.log(self._smgr_log.DEBUG, "reimage processed from queue")
                    if do_reboot and reboot_server_list:
                        status_msg = self._power_cycle_servers(
                            reboot_server_list, cobbler_server, True)
                    cobbler_server.sync()
                if optype == 'provision':
                    provision_server_list  = reimage_item[1]
                    if provision_server_list:
                        cluster_id = reimage_item[2]
                        role_sequence = reimage_item[3]
                        for server in provision_server_list:
                            self._do_provision_server(server['provision_params'], server['server'],
                                    server['cluster'], server['cluster_servers'],
                                    server['package'], server['serverDb'])
                            self._smgr_log.log(self._smgr_log.DEBUG, "provision processed from queue")
                        # Update cluster with role_sequence and apply sequence first step
                        # If no role_sequence present, just update cluster with it.
                        self.update_cluster_provision(cluster_id, role_sequence)
                if optype == 'issu':
                    if not self.issu_obj:
                        entity = {}
                        entity['opcode'] = reimage_item[0]
                        entity['old_cluster'] = reimage_item[1]
                        entity['new_cluster'] = reimage_item[2]
                        entity['new_image'] = reimage_item[3]
                        entity['compute_tag'] = reimage_item[4]
                        self.issu_obj = SmgrIssuClass(self, entity)
                    self.issu_obj._do_issu()
                if optype == "issu_finalize":
                    entity = {}
                    entity['opcode'] = reimage_item[0]
                    entity['old_cluster'] = reimage_item[1]
                    entity['new_cluster'] = reimage_item[2]
                    self.issu_obj = SmgrIssuClass(self, entity)
                    self.issu_obj._do_finalize_issu()
                if optype == "issu_rollback":
                    entity = {}
                    entity['opcode'] = reimage_item[0]
                    entity['old_cluster'] = reimage_item[1]
                    entity['new_cluster'] = reimage_item[2]
                    entity['old_image'] = reimage_item[3]
                    entity['compute_tag'] = reimage_item[4]
                    entity['server_id'] = reimage_item[5]
                    self.issu_obj = SmgrIssuClass(self, entity)
                    self.issu_obj._do_rollback_compute()
                gevent.sleep(0)
            except Exception as e:
                self._smgr_log.log(
                    self._smgr_log.DEBUG,
                    "reimage_server_cobbler failed: " + str(e))
                pass
            # end try
        #end while
    # end _reimage_server_cobbler

    # API call to power-cycle the server (IMPI Interface)
    def restart_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "restart_server")
        net_boot = None
        match_key = None
        match_value = None
        try:
            ret_data = self.validate_smgr_request("SERVER", "REBOOT", bottle.request)
            if ret_data['status'] == 0:
                do_net_boot = ret_data['net_boot']
                match_key = ret_data['match_key']
                match_value = ret_data['match_value']
                match_dict = {}
                if match_key == "tag":
                    match_dict = self._process_server_tags(match_value)
                elif match_key:
                    match_dict[match_key] = match_value
            reboot_server_list = []
            # if the key is server_id, server_table server key is 'id'
            servers = self._serverDb.get_server(match_dict, detail=True)
            if len(servers) == 0:
                msg = "No Servers found for match %s" % \
                    (match_value)
                self.log_and_raise_exception(msg)
            for server in servers:
                cluster = None
                #if its None,It gets the CLUSTER list
                if server['cluster_id']:
                    cluster = self._serverDb.get_cluster(
                        {"id" : server['cluster_id']},
                        detail=True)
                cluster_parameters = {}
                if cluster and cluster[0]['parameters']:
                    cluster_parameters = eval(cluster[0]['parameters'])

                server_id = server['id']
                if 'password' in server:
                    password = server['password']
                elif 'password' in cluster_parameters:
                    password = cluster_parameters['password']
                else:
                    msg = "Missing password for " + server_id
                    self.log_and_raise_exception(msg)

                if 'domain' in server and server['domain']:
                    domain = server['domain']
                elif 'domain' in cluster_parameters and cluster_parameters['domain']:
                    domain = cluster_parameters['domain']
                else:
                    msg = "Missing Domain for " + server_id
                    self.log_and_raise_exception(msg)

                # Build list of servers to be rebooted.
                reboot_server = {
                    'id' : server['id'],
                    'host_name' : server['host_name'],
                    'domain' : domain,
                    'ip' : server.get("ip_address", ""),
                    'password' : password,
                    'ipmi_address' : server.get('ipmi_address',"") }
                reboot_server_list.append(
                    reboot_server)
            # end for server in servers

            status_msg = self._power_cycle_servers(
                reboot_server_list, self._smgr_cobbler, do_net_boot)
            self._smgr_cobbler.sync()
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REBOOT,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REBOOT,
                                     False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REBOOT)
        return status_msg
    # end restart_server

    # Function to get all servers in a Cluster configured for given role.
    def role_get_servers(self, cluster_servers, role_type):
        servers = []
        for server in cluster_servers:
            role_set = set(eval(server['roles']))
            if role_type in role_set:
                servers.append(server)
        return servers

    # Function to get control interface for a specified server.
    def get_control_interface(self, server):
        contrail = server.get('contrail', "")
        if contrail and eval(contrail):
            contrail_dict = eval(contrail)
            control_data_intf = contrail_dict.get('control_data_interface', "")
            interface_list = self.get_interfaces(server)
            intf_dict = {}
            control_ip = interface_list[control_data_intf] ['ip']
            control_mask = interface_list[control_data_intf] ['mask']
            control_gway = interface_list[control_data_intf].get('d_gw', "")
            ip_prefix = "%s/%s" %(control_ip, control_mask)
            ip_obj = IPNetwork(ip_prefix)
            intf_dict[control_data_intf] = {
                "ip_address" : str(ip_obj),
                "gateway" : str(control_gway)
            }
            return str(intf_dict)
        else:
            intf_control = server['intf_control']
            if intf_control is None:
                intf_control = "{}"
            return intf_control
    # end def get_control_interface

    # Function to get control interface for a specified server.
    def get_control_ip(self, server):
        control_intf = eval(self.get_control_interface(server))
        for key, value in control_intf.iteritems():
            return str(IPNetwork(value['ip_address']).ip)
        return server['ip_address']
    # end def get_control_ip

    # Function to get control gateway for a specified server.
    def get_control_gateway(self, server):
        control_intf = eval(self.get_control_interface(server))
        for key, value in control_intf.iteritems():
            if 'gateway' in value:
                if value['gateway'].isspace() or not value['gateway'] or value['gateway'] == 'None':
                    return ''
                else:
                    return str(IPNetwork(value['gateway']).ip)
        if 'gateway' in server and len(server['gateway']):
            return str(IPNetwork(server['gateway']).ip)
        else:
            return ''
    # end def get_control_gateway

    #Function to get control section for all servers
    # belonging to the same VN
    # If 'contrail' block ins present, use the new interface configuration
    #   otherwise, use the old way of configuration
    def get_control_net(self, cluster_servers):
        server_control_list = {}
        for server in cluster_servers:
            server_control_list[server['ip_address']] = self.get_control_interface(
                server)
        return server_control_list

    #Function to get list of all DHCP IPs under control of Cobbler
    def get_dhcp_ips(self):
        dhcp_ips = []
        db_dhcp_hosts = self._serverDb.get_dhcp_host()
        for host in db_dhcp_hosts:
            dhcp_ips.append(str(host['ip_address']))
        db_dhcp_subnets = self._serverDb.get_dhcp_subnet()
        for subnet in db_dhcp_subnets:
            subnet_cidr = self._serverDb.get_cidr(subnet['subnet_address'], subnet['subnet_mask'])
            subnet_ip_list = [str(x) for x in IPNetwork(str(subnet_cidr))]
            dhcp_ips+=subnet_ip_list
        return set(dhcp_ips)

    # Function to get map server name to server ip
    # accepts list of server names and returns list of
    # server ips
    def get_server_ip_list(self, server_names, servers):
        server_ips = []
        for server_name in server_names:
            for server in servers:
                if server['id'] == server_name:
                    server_ips.append(
                        server['ip_address'])
                    break
                # end if
            # end for server
        # end for server_name
        return server_ips
    # end get_server_ip_list

    def interface_created(self):
        entity = bottle.request.json
        entity["interface_created"] = "Yes"
        print "Interface Created"
        self.provision_server()

    def log_trace(self):
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if not exc_type or not exc_value or not exc_traceback:
            return
        self._smgr_log.log(self._smgr_log.ERROR, "*****TRACEBACK-START*****")
        tb_lines = traceback.format_exception(exc_type, exc_value,
                          exc_traceback)
        for tb_line in tb_lines:
            self._smgr_log.log(self._smgr_log.ERROR, tb_line)
        self._smgr_log.log(self._smgr_log.ERROR, "*****TRACEBACK-END******")

        #use below formating if needed
        '''
        print "*** format_exception:"
        print repr(traceback.format_exception(exc_type, exc_value,
                          exc_traceback))
        print "*** extract_tb:"
        print repr(traceback.extract_tb(exc_traceback))
        print "*** format_tb:"
        print repr(traceback.format_tb(exc_traceback))
        print "*** tb_lineno:", exc_traceback.tb_lineno
        '''

    def get_container_packages(self, servers, package_image_id):
        server_packages = []
        if package_image_id:
            package_image_id, package = self.get_package_image(package_image_id)
            package_type = package['type']
        for server in servers:
            server_pkg = {}
            server_pkg['server'] = server
            pkg_id = ''
            package = {}
            if not package_image_id:
                pkg_id = server['package_image_id']
                if pkg_id:
                    pkg_id, package = self.get_package_image(pkg_id)
                if not package:
                    cluster_id = server.get('cluster_id', '')
                    if not cluster_id:
                        msg = "Package not found in server %s" % (server['id'])
                        raise ServerMgrException(msg)
                    else:
                        cluster = self._serverDb.get_cluster(
                            {"id": cluster_id}, detail=True)[0]
                        pkg_id = cluster['package_image_id']
                        pkg_id, package = self.get_package_image(pkg_id)
                        if not package:
                            msg = "Package not found in server/cluster %s/%s" % \
                                (server['id'], cluster['id'])
                            raise ServerMgrException(msg)
                server_pkg['package_image_id'] = pkg_id
                server_pkg['package_type'] = package['type']
            else:
                server_pkg['package_image_id'] = package_image_id
                server_pkg['package_type'] = package_type
            server_packages.append(server_pkg)
        return server_packages
    # end get_container_packages


    def get_server_packages(self, servers, package_image_id):
        server_packages = []
        if package_image_id:
            package_image_id, package = self.get_package_image(package_image_id)
            puppet_manifest_version = \
                eval(package['parameters'])['puppet_manifest_version']
            package_type = package['type']
            sequence_provisioning_available = \
                eval(package['parameters']).get('sequence_provisioning_available', False)
        for server in servers:
            server_pkg = {}
            server_pkg['server'] = server
            pkg_id = ''
            package = {}
            if not package_image_id:
                pkg_id = server['package_image_id']
                if pkg_id:
                    pkg_id, package = self.get_package_image(pkg_id)
                if not package:
                    cluster_id = server.get('cluster_id', '')
                    if not cluster_id:
                        msg = "Package not found in server %s" % (server['id'])
                        raise ServerMgrException(msg)
                    else:
                        cluster = self._serverDb.get_cluster(
                            {"id": cluster_id}, detail=True)[0]
                        pkg_id = cluster['package_image_id']
                        pkg_id, package = self.get_package_image(pkg_id)
                        if not package:
                            msg = "Package not found in server/cluster %s/%s" % \
                                (server['id'], cluster['id'])
                            raise ServerMgrException(msg)
                server_pkg['package_image_id'] = pkg_id
                server_pkg['puppet_manifest_version'] = \
                    eval(package['parameters'])['puppet_manifest_version']
                server_pkg['package_type'] = package['type']
                server_pkg['sequence_provisioning_available'] = \
                    eval(package['parameters']).get('sequence_provisioning_available', False)
            else:
                server_pkg['package_image_id'] = package_image_id
                server_pkg['puppet_manifest_version'] = puppet_manifest_version
                server_pkg['package_type'] = package_type
                server_pkg['sequence_provisioning_available'] = sequence_provisioning_available
            server_packages.append(server_pkg)
        return server_packages
    # end get_server_packages


    # Function to decide which type of monitoring info to fetch
    def get_defaults(self):
        ret_defaults_dict = {}
        try:
            query_args = parse_qs(urlparse(request.url).query,
                                    keep_blank_values=True)
            obj = query_args.get("object", ['']) [0]
            if obj not in ["server", "cluster", "image"]:
                resp_msg = self.form_operartion_data("Unknown Object Type", ERR_OPR_ERROR,
                                                                None)
                abort(404, resp_msg)

            level = query_args.get("level", ['']) [0]
            if not level:
                ret_defaults_dict = copy.deepcopy(self._cfg_defaults_dict)
                self.merge_dict(ret_defaults_dict, self._code_defaults_dict)
                return ret_defaults_dict[obj]
            elif level == "code":
                return self._code_defaults_dict[obj]
            elif level == "config":
                return self._cfg_defaults_dict[obj]
        except Exception as e:
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)


    def update_cluster_provision(self, cluster_id, role_sequence):
        if not cluster_id or not role_sequence:
            return
        cluster_data = {"id": cluster_id, "provision_role_sequence": role_sequence}
        self._serverDb.modify_cluster(cluster_data)
        role_steps_list = []
        sequence_steps = role_sequence.get('steps', [])
        if sequence_steps:
            role_steps_list = sequence_steps[0]

        for step_tuple in role_steps_list:
            server_host_name = step_tuple[0]
            servers = self._serverDb.get_server({'host_name': server_host_name}, detail=True)
            if not servers:
              continue
            server_id = servers[0]['id']
            hiera_file = self.get_server_control_hiera_filename(server_host_name)
            self._smgr_puppet.modify_server_hiera_data(server_host_name, hiera_file, [step_tuple])

        # generate list of tuples based on hostnames
        #input = [('a', '1'), ('a', '2'), ('b', '1'), ('b', '2')]
        #output = {'a': [('a', '1'), ('a', '2')], 'b': [('b', '1'), ('b', '2')]}
        cluster_host_steps = {}
        if role_steps_list:
            cluster_host_steps = dict((key[0], []) for key in role_steps_list)
            for key in role_steps_list:
                cluster_host_steps[key[0]].append(key)

        #iterate over  following format
        # {'a': [('a', '1'), ('a', '2')], 'b': [('b', '1'), ('b', '2')]}
        for hostname in cluster_host_steps:
            hiera_file = self.get_server_control_hiera_filename(hostname)
            if not hiera_file:
                return False
            host_steps = cluster_host_steps[hostname]
            self._smgr_puppet.modify_server_hiera_data(hostname, hiera_file, host_steps )

    def get_server_control_hiera_filename(self, server_hostname, cluster=None):
        hiera_filename = ''
        servers = self._serverDb.get_server({'host_name': server_hostname}, detail=True)
        if not servers:
            return hiera_filename
        server = servers[0]
        server_domain = self.get_server_domain(server, cluster)
        hieradata_environment = self.get_hieradata_environment(server)
        if not server_domain or not hieradata_environment:
            return hiera_filename
        hiera_filename = hieradata_environment + \
            server['host_name'] + "." + \
            server_domain + "-contrail.yaml"
        return hiera_filename

    def get_server_domain(self, server, cluster=None):
        domain = ''
        domain = server['domain']
        if domain:
            return domain
        if not cluster:
            cluster_id = server['cluster_id']
            if not cluster_id:
                return domain
            clusters = self._serverDb.get_cluster(
                {"id" : cluster_id}, detail=True)
            if clusters:
                cluster = clusters[0]
                cluster_params = eval(cluster['parameters'])
                domain = cluster_params['domain']
        return domain
    # end get_server_domain

    def is_sequence_provisioning_available(self, package_id):
        available = False
        try:
            package_id, package = self.get_package_image(package_id)
            available = \
                eval(package['parameters']).get('sequence_provisioning_available', False)
        except ServerMgrException as e:
            pass
        return available

    def update_provision_started_flag(self, server_id, status):
        if status != "provision_started":
            return False
        servers = self._serverDb.get_server(
            {"id" : server_id}, detail=True)
        if not servers:
            return False
        server = servers[0]
        cluster_id = server['cluster_id']
        clusters = self._serverDb.get_cluster(
            {"id" : cluster_id}, detail=True)
        if not clusters:
            return False
        cluster = clusters[0]
        # By default, sequence provisioning is On.
        sequence_provisioning = eval(cluster['parameters']).get(
            "sequence_provisioning", True)
        provisioned_id  = server.get('provisioned_id', '')
        sequence_provisioning_available = \
            self.is_sequence_provisioning_available(provisioned_id)
        if not sequence_provisioning_available or not sequence_provisioning:
            return False
        step_tuple = (server['host_name'], status)
        hiera_file = self.get_server_control_hiera_filename(server['host_name'])
        self._smgr_puppet.modify_server_hiera_data(server['host_name'],
                                                   hiera_file, [step_tuple],
                                                   False)
        return True

    def update_provision_role_sequence(self, server_id, status):
        if not server_id or not status or '_' not in status:
            return False
        if status.split('_')[-1] != 'completed':
            return False
        state = status.replace('_completed', '')

        if not state or \
           (state not in self._role_steps and state != 'post_provision'):
            return False
        servers = self._serverDb.get_server(
            {"id" : server_id}, detail=True)
        if not servers:
            return False
        server = servers[0]
        cluster_id = server['cluster_id']
        clusters = self._serverDb.get_cluster(
            {"id" : cluster_id}, detail=True)
        if not clusters:
            return False
        cluster = clusters[0]
        # By default, sequence provisioning is On.
        sequence_provisioning = eval(cluster['parameters']).get(
            "sequence_provisioning", True)

        provisioned_id  = server.get('provisioned_id', '')
        sequence_provisioning_available = \
            self.is_sequence_provisioning_available(provisioned_id)
        if not sequence_provisioning_available or not sequence_provisioning:
            return False

        provision_role_sequence = cluster.get('provision_role_sequence', '{}')
        if not provision_role_sequence:
            return False
        provision_role_sequence = eval(provision_role_sequence)
        if not provision_role_sequence:
            return False
        steps = provision_role_sequence.get('steps', [])
        step_tuple = (server['host_name'], state)
        role_steps_list = []
        if steps:
            role_steps_list = steps[0]
        else:
            return False
        if step_tuple not in role_steps_list:
            return False

        role_steps_list.remove(step_tuple)
        time_str = strftime("%Y_%m_%d__%H_%M_%S", localtime())
        provision_role_sequence['completed'].append(step_tuple + (time_str,))
        hiera_file = self.get_server_control_hiera_filename(step_tuple[0])
        self._smgr_puppet.modify_server_hiera_data(step_tuple[0],
                                                   hiera_file, [step_tuple],
                                                   False)
        if role_steps_list:
            provision_role_sequence['steps'][0] = role_steps_list
        else:
            role_steps_list = []
            provision_role_sequence['steps'].pop(0)
            if provision_role_sequence['steps']:
                role_steps_list = provision_role_sequence['steps'][0]

            # generate list of tuples based on hostnames
            #input = [('a', '1'), ('a', '2'), ('b', '1'), ('b', '2')]
            #output = {'a': [('a', '1'), ('a', '2')], 'b': [('b', '1'), ('b', '2')]}
            cluster_host_steps = {}
            if role_steps_list:
                cluster_host_steps = dict((key[0], []) for key in role_steps_list)
                for key in role_steps_list:
                    cluster_host_steps[key[0]].append(key)

            #iterate over  following format
            # {'a': [('a', '1'), ('a', '2')], 'b': [('b', '1'), ('b', '2')]}
            for hostname in cluster_host_steps:
                hiera_file = self.get_server_control_hiera_filename(hostname)
                if not hiera_file:
                    return False
                host_steps = cluster_host_steps[hostname]
                self._smgr_puppet.modify_server_hiera_data(hostname, hiera_file, host_steps )

        cluster_data = {'id': cluster_id, 'provision_role_sequence': provision_role_sequence}
        self._serverDb.modify_cluster(cluster_data)
        return True
    # end update_provision_role_sequence

    def get_hieradata_environment(self, server):
        hiera_env = ''
        package_image_id = server['provisioned_id']
        if not package_image_id:
            return hiera_env
        environment = ''
        package_image_id, package = self.get_package_image(package_image_id)
        puppet_manifest_version = \
            eval(package['parameters'])['puppet_manifest_version']
        environment = puppet_manifest_version.replace('-','_')
        if not environment:
            return hiera_env
        hiera_env = self._smgr_puppet.puppet_directory + "environments/" + \
            environment + "/hieradata/"
        return hiera_env
    # end get_hieradata_environment

    def is_cluster_ext_lb(self, cluster):
        '''return true if loadbalancer role is defined for cluster
        else return false'''
        if not cluster:
            return False
        cluster_params = eval(cluster['parameters'])
        cluster_provision_params = cluster_params.get("provision", {})
        if cluster_provision_params:
            cluster_params_lb = cluster_provision_params.get("contrail", {})
            if cluster_params_lb.get('loadbalancer', None):
                return True
        return False

    def get_role_step_servers(self, role_servers, cluster):
        role_step_servers = {}
        if not cluster:
            return role_step_servers
        role_step_servers['pre_exec_vnc_galera'] = []
        role_step_servers['post_exec_vnc_galera'] = []
        role_step_servers['keepalived'] = []
        role_step_servers['haproxy'] = []
        openstack_ha = self.is_cluster_ha(cluster)
        contrail_ha = self.is_cluster_contrail_ha(cluster)
        ext_lb_flag = self.is_cluster_ext_lb(cluster)
        for role in self._roles:
            role_step_servers[role] = []
            for server in role_servers[role]:
                role_step_servers[role].append(server['host_name'])
                if role == 'openstack' and openstack_ha:
                    if server['host_name'] not in role_step_servers['pre_exec_vnc_galera']:
                        role_step_servers['pre_exec_vnc_galera'].append(server['host_name'])
                    if server['host_name'] not in role_step_servers['post_exec_vnc_galera']:
                        role_step_servers['post_exec_vnc_galera'].append(server['host_name'])
                    if not ext_lb_flag:
                        if server['host_name'] not in role_step_servers['keepalived']:
                            role_step_servers['keepalived'].append(server['host_name'])
                        if server['host_name'] not in role_step_servers['haproxy']:
                            role_step_servers['haproxy'].append(server['host_name'])
                if role == 'config' and (not ext_lb_flag):
                    if server['host_name'] not in role_step_servers['haproxy']:
                        role_step_servers['haproxy'].append(server['host_name'])
                    if contrail_ha:
                        if server['host_name'] not in role_step_servers['keepalived']:
                            role_step_servers['keepalived'].append(server['host_name'])
                # add loadbalancer node in keepalived and haproxy list, if one defined
                if role == 'loadbalancer':
                    if openstack_ha or contrail_ha:
                        if server['host_name'] not in role_step_servers['keepalived']:
                            role_step_servers['keepalived'].append(server['host_name'])
                        if server['host_name'] not in role_step_servers['haproxy']:
                            role_step_servers['haproxy'].append(server['host_name'])
        return role_step_servers

    def validate_role_sequence(self, role_sequence):
        return True

    def is_cluster_ha(self, cluster):
        if not cluster:
            return False
        cluster_params = eval(cluster['parameters'])
        cluster_provision_params = cluster_params.get("provision", {})
        if cluster_provision_params:
            openstack_params = cluster_provision_params.get("openstack", {})
            ha_params = openstack_params.get("ha", {})
            internal_vip = ha_params.get('internal_vip', '')
        else:
            internal_vip = cluster_params.get('internal_vip', '')
        if internal_vip:
            return True
        return False

    def is_cluster_contrail_ha(self, cluster):
        if not cluster:
            return False
        cluster_params = eval(cluster['parameters'])
        cluster_provision_params = cluster_params.get("provision", {})
        if cluster_provision_params:
            contrail_params = cluster_provision_params.get("contrail", {})
            contrail_ha_params = contrail_params.get("ha", {})
            contrail_internal_vip = contrail_ha_params.get('contrail_internal_vip', '')
        else:
            contrail_internal_vip = cluster_params.get('contrail_internal_vip', '')
        if contrail_internal_vip:
            return True
        return False

    def get_role_sequence(self, cluster):
        if not cluster:
            return []
        cluster_id = cluster['id']
        ha = self.is_cluster_ha(cluster)

        contrail_ha = self.is_cluster_contrail_ha(cluster)
        if ha:
            default_role_sequence = self._role_step_sequence_ha
        elif contrail_ha:
            default_role_sequence = self._role_step_sequence_contrail_ha
        else:
            default_role_sequence = self._role_sequence
        try:
            role_sequence_file = open(_DEF_ROLE_SEQUENCE_DEF_FILE, 'r')
            json_data = role_sequence_file.read()
            role_sequence_file.close()
        except IOError:
            self._smgr_log.log(self._smgr_log.ERROR,
                               "Error reading role sequence config file %s" \
                               % (_DEF_ROLE_SEQUENCE_DEF_FILE))
            role_sequence = default_role_sequence
            return role_sequence
        try:
            role_sequence_data = json.loads(json_data)
            cluster_role_sequence_list = role_sequence_data.get('cluster', [])
            cluster_role_sequence = []
            for cluster in cluster_role_sequence_list:
                if cluster_id == cluster.get('id', ''):
                    cluster_role_sequence = cluster['role_sequence']
                    break
            if not cluster_role_sequence:
                if ha:
                    default_sequence = role_sequence_data.get('default_ha', {})
                elif contrail_ha:
                    default_sequence = role_sequence_data.get('default_contrail_ha', {})
                else:
                    default_sequence = role_sequence_data.get('default', {})
                cluster_role_sequence = default_sequence.get('role_sequence', [])
            role_sequence = []
            for role_set_list in cluster_role_sequence:
                role_tuple = tuple(role_set_list)
                role_sequence.append(role_tuple)
            if not role_sequence:
                role_sequence = default_role_sequence
            else:
                if not self.validate_role_sequence(role_sequence):
                    role_sequence = default_role_sequence
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "Role sequence: %s" % str(role_sequence))
        except Exception as e:
            print repr(e)
            self._smgr_log.log(self._smgr_log.ERROR,
                               "Role sequence file %s File should be in JSON format" \
                               % (_DEF_ROLE_SEQUENCE_DEF_FILE))
            role_sequence = default_role_sequence
        return role_sequence

    def prepare_provision_role_sequence(self, cluster, role_servers, puppet_manifest_version):
        # Make sure this is calculated for compute image in mixed provisions
        provision_role_sequence = {}
        if not cluster or not role_servers:
            return provision_role_sequence
        if not self._smgr_puppet.is_new_provisioning(puppet_manifest_version):
            return provision_role_sequence
        if cluster['provision_role_sequence'] and eval(cluster['provision_role_sequence']):
            self._smgr_log.log(self._smgr_log.WARN,
                               "provision_role_sequence already present:%s" %(cluster['provision_role_sequence']))
        provision_role_sequence['steps'] = []
        provision_role_sequence['completed'] = []
        control_role_sequence = []
        compute_role_sequence = []
        server_compute_flag = {}
        # Get the role sequence
        role_sequence = self.get_role_sequence(cluster)
        role_step_servers = self.get_role_step_servers(role_servers, cluster)
        cluster_servers = self._serverDb.get_server(
            {"cluster_id" : cluster['id']}, detail=True)
        for role_seq in role_sequence:
            role_list = role_seq[0]
            execution = role_seq[1]
            if execution != 's' and execution != 'p':
                execution = 's'
            if execution == 'p':
                role_steps_list = []
            for server in cluster_servers:
                if execution == 's':
                    role_steps_list = []
                for role in role_list:
                    if role in self._compute_roles:
                        continue
                    for role_step_server_id in role_step_servers[role]:
                        if server['host_name'] == role_step_server_id:
                            role_steps_tuple = (server['host_name'], role)
                            role_steps_list.append(role_steps_tuple)
                            server_compute_flag[server['host_name']] = False
                            break
                if role_steps_list and execution == 's':
                    control_role_sequence.append(role_steps_list)
            if role_steps_list and execution == 'p':
                control_role_sequence.append(role_steps_list)

        role_steps_list = []
        for role in self._compute_roles:
            for role_step_server_id in role_step_servers[role]:
                role_steps_tuple = (role_step_server_id, role)
                role_steps_list.append(role_steps_tuple)
                role_steps_tuple = (role_step_server_id, "post_provision")
                if role_steps_tuple not in role_steps_list:
                    role_steps_list.append(role_steps_tuple)
                server_compute_flag[role_step_server_id] = True
        if role_steps_list:
            compute_role_sequence.append(role_steps_list)
        # Set provision_complete as last step for all the servers.
        provision_complete_control_list = []
        compute_list = []
        control_list = []
        for server_id, compute_flag in server_compute_flag.iteritems():
            if not compute_flag:
                role_steps_tuple = (server_id, "post_provision")
                control_list.append(role_steps_tuple)

        if control_list:
            provision_complete_control_list.append(control_list)

        # Create the full sequence of steps
        provision_role_sequence['steps'] = control_role_sequence + \
            provision_complete_control_list + \
            compute_role_sequence
        return provision_role_sequence

    #end prepare_provision_role_sequence

    def get_role_servers(self, cluster_id, server_packages):
        role_servers = {}
        servers = []
        if not cluster_id:
            return role_servers
        for server_pkg in server_packages:
            servers.append(server_pkg['server'])
        # build roles dictionary for this set of servers. Roles dictionary will be
        # keyed by role-id and value would be list of servers configured
        # with this role.
        for role in self._roles:
            role_servers[role] = self.role_get_servers(
                servers, role)
        return role_servers
    #end get_role_servers

    def find_package_sku(self, image_id, image_type):
        if image_type == "contrail-ubuntu-package":
            nova_api_package = self._args.html_root_dir+"contrail/repo/"+image_id + '/nova-api_*.deb'
            cmd = 'dpkg-deb -f ' + nova_api_package.encode("ascii") + ' Version'
            version = subprocess.check_output(cmd, shell=True)
        elif image_type == "contrail-centos-package":
            nova_api_package = self._args.html_root_dir+"contrail/repo/"+image_id + '/openstack-nova-api-*.rpm'
            cmd = 'ls ' + nova_api_package.encode("ascii")
            package_name = subprocess.check_output(cmd, shell=True)
            sm = ServerMgrUtil()
            version = sm.get_package_version(package_name, image_type)
        if version != '' :
            self._smgr_log.log(self._smgr_log.DEBUG, "version of nova-api : %s" %version)
            # we need to find openstack version now, sample version string
            # version='1:2015.1.2-0ubuntu2~cloud0.1contrail'

            return version
        else:
          msg = ("find_package_sku: unable to find version from package")
          raise ServerMgrException(msg, ERR_OPR_ERROR)

    def storage_get_control_network_mask(
        self, server, cluster, role_servers, cluster_servers):

        control_intf = eval(self.get_control_interface(server))
        for key, value in control_intf.iteritems():
          control_ip_prefixlen = "%s/%s" %(str(IPNetwork(value['ip_address']).network), str(IPNetwork(value['ip_address']).prefixlen))
          msg = "STORAGE: control_ip: %s => %s" %(value['ip_address'], control_ip_prefixlen)
          self._smgr_log.log(self._smgr_log.DEBUG, msg)
          return control_ip_prefixlen

        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
          subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")

        control_ip = "%s/%s" %(str(server['ip_address']), subnet_mask )
        control_ip_prefixlen = "%s/%s" %(str(IPNetwork(control_ip).network), str(IPNetwork(control_ip).prefixlen))

        return control_ip_prefixlen

    # end storage_get_control_network_mask

    def build_hostnames(self, cluster_servers):
      hostnames_root = {}
      hostnames_root['literal'] = True
      hostnames = {}
      for server in cluster_servers:
        #domain could be empty as well.
        domain = self.get_server_domain(server)
        hostname=server['host_name']
        if domain != '' :
            fqdn = hostname + "."+  domain
        else:
            fqdn = hostname

        ip_address = self.get_control_ip(server)
        hostnames[fqdn] = {}
        hostnames[fqdn]['name'] = fqdn
        alias_list = set()
        #alias_list.add(fqdn)
        alias_list.add(hostname)
        alias_list.add(hostname + "ctrl")
        hostnames[fqdn]['host_aliases'] = list(alias_list)
        hostnames[fqdn]['ip'] = ip_address

      hostnames_root['hostnames']=hostnames
      return hostnames_root

    def build_tor_ha_config(self, server, cluster, role_servers):
        tor_ha_config = {}
        tor_ha_config['literal'] = True
        domain = server.get('domain', '')
        if not domain:
            domain = (cluster.get('parameters', {})).get('domain', '')
        for toragent_server in role_servers['toragent']:
            tor_config = eval(toragent_server['top_of_rack'])
            if len(tor_config) > 0:
                tsn_ip = self.get_control_ip(toragent_server)
                node_id = toragent_server['id']
                tor_ha_config[node_id]= {}
                for switch in tor_config.get("switches", []):
                    key = switch['switch_name'] + switch['id']
                    tor_ha_config[node_id][key] = switch
                    tor_ha_config[node_id][key]['tsn_ip'] = tsn_ip
                    if ((switch.get(
                        'ovs_protocol', "")).lower() == "pssl"):
                        self._smgr_puppet.generate_tor_certs(
                            switch, server['host_name'], domain)
                # end for switch
            # end if len...
        # end for toragent_server
        return tor_ha_config
    # end build_tor_ha_config

    def build_calculated_cluster_params(
            self, server, cluster, role_servers, cluster_servers, package):
        # if parameters are already calculated, nothing to do, return.
        cluster_params = cluster.get("parameters", {})
        cluster_contrail_prov_params = (
            cluster_params.get("provision", {})).get("contrail", {})
        cluster_openstack_prov_params = (
            cluster_params.get("provision", {})).get("openstack", {})
        server_params = server.get("parameters", {})
        server_contrail_prov_params = (
            server_params.get("provision", {})).get("contrail", {})
        package_params = package.get("parameters", {})
        package_contrail_prov_params = (
            package_params.get("provision", {})).get("contrail", {})
        if 'calc_params' in cluster:
            return
        contrail_params = {}
        openstack_params = {}
        # contrail_repo_name
        if package.get('category', None) == "container":
            if package.get('compute_image_id', None):
                contrail_params['contrail_repo_name'] = [package.get('compute_image_id', '')]
            else:
                msg = "Please provide compute_image_id to do puppet provision"
                self.log_and_raise_exception(msg)
        else:
            contrail_params['contrail_repo_name'] = [package.get('id', '')]
        # contrail_repo_type (not used by 3.0 code, maintained for pre-3.0)
        contrail_params['contrail_repo_type'] = [package.get('type', '')]
        roles = eval(server.get("roles", "[]"))
        if (('storage-compute' in roles) or
            ('storage-master' in roles)):
            storage_repo = (server_contrail_prov_params.get(
                    "storage", {})).get("storage_repo_id", "")

            if not storage_repo:
              storage_repo = (cluster_contrail_prov_params.get(
                    "storage", {})).get("storage_repo_id", "")

            if storage_repo:
                contrail_params['contrail_repo_name'].append(storage_repo)
                contrail_params['contrail_repo_type'].append(
                    "contrail-ubuntu-storage-repo".encode('utf-8'))

        my_uuid = cluster_params.get(
            "uuid", str(uuid.uuid4()).encode("utf-8"))
        contrail_params['uuid'] = my_uuid
        for role, servers in role_servers.iteritems():
            role_ctl_ip = [(self.get_control_ip(x)) for x in servers]
            role_ip = [x.get("ip_address", "") for x in servers]
            role_id = [x.get("host_name", "") for x in servers]
            role_passwd = [x.get("password", "") for x in servers]
            role_user = ["root" for x in servers]

            # special case - convert role name for collector to analytics
            if (role == "collector"):
                role = "analytics"
            # Expanding special cases to allow mixed ansible/puppet provisioning
            if (role == "controller"):
                role = "config"
            if (role == "analyticsdb"):
                role = "database"
            if role != "openstack":
                contrail_params[role] = {}
                contrail_params[role][role + "_ip_list"] = role_ctl_ip
                contrail_params[role][role + "_name_list"] = role_id
                contrail_params[role][role + "_passwd_list"] = role_passwd
                contrail_params[role][role + "_user_list"] = role_user
            else:
                openstack_params[role + "_ip_list"] = role_ctl_ip
                openstack_params[role + "_name_list"] = role_id
                openstack_params[role + "_passwd_list"] = role_passwd
                openstack_params[role + "_user_list"] = role_user
                openstack_params['openstack_mgmt_ip_list'] = role_ip
        #end for
        # Build mysql_allowed_hosts list
        contrail_ha_params = cluster_contrail_prov_params.get("ha", {})
        openstack_ha_params = cluster_openstack_prov_params.get("ha", {})
        configured_external_openstack_ip = cluster_openstack_prov_params.get("external_openstack_ip", None)
        mysql_allowed_hosts = []
        internal_vip = openstack_ha_params.get("internal_vip", None)
        if internal_vip:
            mysql_allowed_hosts.append(internal_vip)
        external_vip = openstack_ha_params.get("external_vip", None)
        if external_vip:
            mysql_allowed_hosts.append(external_vip)
        contrail_internal_vip = contrail_ha_params.get("contrail_internal_vip", None)
        if contrail_internal_vip:
            mysql_allowed_hosts.append(contrail_internal_vip)
        contrail_external_vip = contrail_ha_params.get("contrail_external_vip", None)
        if contrail_external_vip:
            mysql_allowed_hosts.append(contrail_external_vip)
        os_ctl_ip_list = [(self.get_control_ip(x)) for x in role_servers["openstack"]]
        config_ctl_ip_list = [(self.get_control_ip(x)) for x in role_servers["config"]]
        os_ip_list = [x.get("ip_address", "") for x in role_servers["openstack"]]
        config_ip_list = [x.get("ip_address", "") for x in role_servers["config"]]
        mysql_allowed_hosts = list(
               set(mysql_allowed_hosts + os_ip_list + config_ip_list + os_ctl_ip_list + config_ctl_ip_list ))
        # top_of_rack related config
        contrail_params['ha'] = {
            'tor_ha_config': self.build_tor_ha_config(
                server, cluster, role_servers)
        }
        contrail_params['system'] = self.build_hostnames(cluster_servers)

        # Storage parameters..
        cluster_storage_params = cluster_contrail_prov_params.get("storage", {})
        server_storage_params = server_contrail_prov_params.get("storage", {})
        contrail_params['storage'] = {}
        total_osd = int(0)
        num_storage_hosts = int(0)
        storage_mon_host_ip_set = set()
        storage_mon_hostname_set = set()
        storage_chassis_config_set = set()
        live_migration_host = cluster_storage_params.get(
            "live_migration_host", "")
        live_migration_ip = ""
        for role_server in role_servers['storage-compute']:
            role_server_params = eval(
                role_server.get("parameters", "{}"))
            storage_params = ((
                    role_server_params.get(
                        "provision", {})).get(
                            "contrail", {})).get(
                                "storage", {})
            if (('storage_osd_disks' in storage_params) and
                (len(storage_params['storage_osd_disks']) > 0)):
                total_osd += len(storage_params['storage_osd_disks'])
                num_storage_hosts += 1
            # end if
            storage_mon_host_ip_set.add(self.get_control_ip(role_server))
            storage_mon_hostname_set.add(role_server['host_name'])
            if role_server['host_name'] == live_migration_host:
                live_migration_ip = self.get_control_ip(role_server)
            if storage_params.get('storage_chassis_id', ""):
                storage_host_chassis = (
                    role_server['host_name'] + ':' + storage_params['storage_chassis_id'])
                storage_chassis_config_set.add(storage_host_chassis)
            # end if
        # end for
        for x in role_servers['storage-master']:
            storage_mon_host_ip_set.add(self.get_control_ip(x))
            storage_mon_hostname_set.add(x['host_name'])
        # end for

        contrail_params['storage']['storage_num_osd'] = total_osd
        contrail_params['storage']['storage_num_hosts'] = num_storage_hosts
        storage_fsid = cluster_params.get(
            "storage_fsid", str(uuid.uuid4()).encode("utf-8"))
        contrail_params['storage']['storage_fsid'] = storage_fsid
        storage_virsh_uuid = cluster_params.get(
            "storage_virsh_uuid", str(uuid.uuid4()).encode("utf-8"))
        contrail_params['storage']['storage_virsh_uuid'] = storage_virsh_uuid
        contrail_params['storage']['storage_enabled'] = (len(role_servers['storage-compute']) != 0)
        contrail_params['storage']['live_migration_ip'] = live_migration_ip
        contrail_params['storage']['storage_ip_list'] = list(storage_mon_host_ip_set)
        contrail_params['storage']['storage_monitor_hosts'] = list(storage_mon_host_ip_set)
        contrail_params['storage']['storage_hostnames'] = list(storage_mon_hostname_set)
        if ('storage-master' in roles):
            contrail_params['storage']['storage_chassis_config'] = list(storage_chassis_config_set)
        control_network = self.storage_get_control_network_mask(
            server, cluster, role_servers, cluster_servers)

        msg = "STORAGE: Control_network : %s" %(control_network)
        self._smgr_log.log(self._smgr_log.DEBUG, msg)

        contrail_params['storage']['storage_cluster_network'] = control_network
        # Build openstack parameters for openstack modules
        self_ip = server.get("ip_address", "")
        openstack_ips = [x["ip_address"] for x in cluster_servers if "openstack" in eval(x.get('roles', '[]'))]
        if configured_external_openstack_ip:
            openstack_ip = configured_external_openstack_ip
            external_openstack_ip_list = []
            external_openstack_ip_list.append(openstack_ip)
            openstack_params["openstack_ip_list"] = external_openstack_ip_list
        elif self_ip in openstack_ips:
            openstack_ip = self_ip
        elif len(openstack_ips):
            openstack_ip = openstack_ips[0]
        else:
            msg = "Openstack role not defined for cluster AND External Openstack not configured in cluster parameters.\n" \
                  " The cluster needs to point to at least one Openstack node.\n"
            self.log_and_raise_exception(msg)
        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")
        net_and_mask = openstack_ip + "/" + subnet_mask
        openstack_params['network'] = {
            "api": net_and_mask,
            "external": net_and_mask,
            "management": net_and_mask,
            "data": net_and_mask,
        }
        openstack_params['controller'] = {
            "address": {
                 "api": openstack_ip,
                 "management": openstack_ip
             }
        }
        openstack_params['storage'] = {
            "address": {
                 "api": openstack_ip,
                 "management": openstack_ip
             }
        }
        # if this is issu job for my cluster and role is compute, rabbit should be from old cluster
        # neutron should be from old cluster
        issu_params = cluster_params.get("issu", {})
        server_roles = server.get('roles', [])
        if issu_params.get('issu_partner', None) and \
          (server_roles == str(['compute']))  and \
          (issu_params.get('issu_clusters_synced', "false") == "true"):
            ssh_hndl = paramiko.SSHClient()
            ssh_hndl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_hndl.connect(server['ip_address'],
                               username = server.get('username', 'root'),
                               password = server['password'])
            neutron_url = self.issu_obj.get_set_config_parameters(ssh_hndl,
                          '/etc/nova/nova.conf', 'url', section = "neutron")
            m = re.search('[0-9]+(?:\.[0-9]+){3}', neutron_url)
            neutron_ip = m.group()
            old_rabbit_server_str = self.issu_obj.get_set_config_parameters(
                                            ssh_hndl, '/etc/nova/nova.conf',
                                        'rabbit_hosts', section = "DEFAULT")
            old_rabbit_server = old_rabbit_server_str.strip()
            ssh_hndl.close()
            openstack_params['nova'] = {
                'rabbit_hosts' : old_rabbit_server,
                'neutron_ip' : neutron_ip
            }
        openstack_params['mysql'] = {
             "allowed_hosts": ['localhost', '127.0.0.1'] + mysql_allowed_hosts
        }

        contrail_params = ServerMgrUtil.convert_unicode(contrail_params)
        openstack_params = ServerMgrUtil.convert_unicode(openstack_params)
        cluster['calc_params'] = {
            "contrail": contrail_params,
            "openstack": openstack_params,
            "mysql_allowed_hosts": mysql_allowed_hosts
        }
    # end build_calculated_cluster_params

    def build_calculated_server_params(
            self, server, cluster, role_servers, package):
        # if parameters are already calculated, nothing to do, return.
        if 'calc_params' in server:
            return
        contrail_params = {}
        provisioned_id = server.get("provisioned_id", "")
        if ((provisioned_id) and
            (provisioned_id != package.get('id', ""))):
            contrail_params['contrail_upgrade'] = True
        server_control_ip = self.get_control_ip(server)
        server_control_gateway = self.get_control_gateway(server)
        contrail_params['host_ip'] = server_control_ip
        role_id = [x.get("host_name", "") for x in role_servers['openstack']]
        if len(role_id):
            contrail_params['sync_db'] = (server['host_name'] == role_id[0])
        contrail_params['host_roles'] = [ x for x in eval(server['roles']) ]
        if (server_control_ip and
           (server_control_ip != server['ip_address'])):
            contrail_params['host_non_mgmt_ip'] = server_control_ip
            contrail_params['host_non_mgmt_gateway'] = server_control_gateway
        contrail_params = ServerMgrUtil.convert_unicode(contrail_params)
        server['calc_params'] = {
            "contrail": contrail_params
        }
        return server
    # end build_calculated_server_params

    def build_calculated_package_params(
            self, server, cluster, package):
        if 'calc_params' in package:
            return
        contrail_params = {}
        package_params = package.get("parameters", {})
        compute_image_id = package.get('compute_image_id',None)
        if compute_image_id:
            compute_package = self._serverDb.get_image({"id":
                    str(compute_image_id)}, detail=True)
            if len(compute_package):
                compute_package = compute_package[0]
            else:
                msg = "Compute_image_id %s provided doesn't match a package added to SM" % (compute_image_id)
                self.log_and_raise_exception(msg)
            compute_package_params = eval(compute_package.get('parameters',{}))
            contrail_params['contrail_version'] = compute_package_params.get("version", "")
            contrail_params['package_sku'] = compute_package_params.get("sku", "")
        else:
            contrail_params['contrail_version'] = package_params.get("version", "")
            contrail_params['package_sku'] = package_params.get("sku", "")
        contrail_params = ServerMgrUtil.convert_unicode(contrail_params)
        package['calc_params'] = {
            "contrail": contrail_params
        }
    # end build_calculated_package_params

    def build_calculated_provision_params(
            self, server, cluster, role_servers, cluster_servers, package):
        # Build cluster calculated parameters
        self.build_calculated_cluster_params(
            server, cluster, role_servers, cluster_servers, package)
        # Build server calculated parameters
        self.build_calculated_server_params(
            server, cluster, role_servers, package)
        # Build package calculated parameters
        self.build_calculated_package_params(
            server, cluster, package)
    # end build_calculated_provision_params

    def prepare_provision(self, provisioning_data):
        '''returns provision role_sequence and povision_server_list
           after provision request validation'''

        role_ips = {}
        role_ids = {}
        provision_server_list = []
        provision_status = {}
        provision_status['server'] = []
        cluster_id = provisioning_data['cluster_id']
        server_packages = provisioning_data['server_packages']
        compute_image_id = provisioning_data.get('compute_image_id',None)
        #Validate the vip configurations for the cluster
        self._smgr_validations.validate_vips(cluster_id, self._serverDb)
        if compute_image_id:
            compute_package = self._serverDb.get_image({"id":
                    str(compute_image_id)}, detail=True)
            if len(compute_package):
                compute_package = compute_package[0]
            else:
                msg = "Compute_image_id %s provided doesn't match a package added to SM" % (compute_image_id)
                self.log_and_raise_exception(msg)
            package_to_use = {}
            package_to_use['puppet_manifest_version'] = \
                    eval(compute_package['parameters']).get('puppet_manifest_version','')
            package_to_use['sequence_provisioning_available'] = \
                    eval(compute_package['parameters']).get('sequence_provisioning_available', None)
        else:
            package_to_use = server_packages[0]
        puppet_manifest_version = \
            package_to_use.get('puppet_manifest_version', '')
        sequence_provisioning_available = \
            package_to_use.get('sequence_provisioning_available', False)
        role_servers = self.get_role_servers(cluster_id, server_packages)
        cluster = self._serverDb.get_cluster(
                                  {"id" : cluster_id},
                                    detail=True)[0]
        # By default, sequence provisioning is On.
        sequence_provisioning = eval(cluster['parameters']).get(
            "sequence_provisioning", True)
        if sequence_provisioning_available and sequence_provisioning:
            role_sequence = \
                self.prepare_provision_role_sequence(
                    cluster,
                    role_servers,
                    puppet_manifest_version)
        else:
            role_sequence = {}
            role_sequence['steps'] = []
            role_sequence['completed'] = []
        role_servers = {}
        for server_pkg in server_packages:
            server = server_pkg['server']
            package_image_id = server_pkg['package_image_id']
            package_image_id, package = self.get_package_image(
                                               package_image_id)
            package['compute_image_id'] = compute_image_id
            package_type = server_pkg['package_type']
            if "parameters" in package:
                package["parameters"] = eval(package["parameters"])
            if "parameters" in server:
                server["parameters"] = eval(server["parameters"])
            server_params = server.get('parameters', {})
            server_tor_config = server['top_of_rack']
            cluster = self._serverDb.get_cluster(
                {"id" : server['cluster_id']},
                detail=True)[0]
            if "parameters" in cluster:
                cluster["parameters"] = eval(cluster["parameters"])
            cluster_params = cluster.get('parameters', {})
            # Get all the servers belonging to the CLUSTER that this server
            # belongs too.
            cluster_servers = self._serverDb.get_server(
                    {"cluster_id" : server["cluster_id"]},
                    detail="True")
            # build roles dictionary for this cluster. Roles dictionary will be
            # keyed by role-id and value would be list of servers configured
            # with this role.
            if not role_servers:
                for role in self._roles:
                    role_servers[role] = self.role_get_servers(
                                              cluster_servers, role)
                    role_ips[role] = [x["ip_address"] for x in role_servers[role]]
                    role_ids[role] = [x["id"] for x in role_servers[role]]

            # If cluster has new format for providing provisioning parameters, call the new method, else follow
            # thru the below long code. The old code is kept for compatibility and can be removed once we are
            # fully on new format.
            provision_params = {}
            if "provision" in cluster_params:
                # validate ext lb params in cluster
                if role_servers.get('loadbalancer', None):
                    msg = self._smgr_validations.validate_external_lb_params(
                                                                     cluster)
                    if msg:
                        self.log_and_raise_exception(msg)
                self.build_calculated_provision_params(
                    server, cluster, role_servers, cluster_servers, package)
            else:
                try:
                    self._smgr_trans_log.log(bottle.request,
                                            self._smgr_trans_log.SMGR_PROVISION,
                                            False)
                except Exception as e:
                    pass
                resp_msg = self.form_operartion_data(
                           "Cluster "+str(cluster_id) + " uses old params format. "
                                                    "This is no longer supported. "
                          "Please switch to new params format for cluster config.",
                                               ERR_GENERAL_ERROR, provision_status)
                abort(404, resp_msg)

            # end else of "provision" in cluster_params
            provision_server_entry = \
                    {'provision_params' : copy.deepcopy(provision_params),
                     'server' : copy.deepcopy(server),
                     'cluster' : copy.deepcopy(cluster),
                     'cluster_servers' : copy.deepcopy(cluster_servers),
                     'package' : copy.deepcopy(package),
                     'serverDb' : self._serverDb}
            provision_server_list.append(provision_server_entry)
            server_status = {}
            server_status['id'] = server['id']
            server_status['package_id'] = package_image_id
            provision_status['server'].append(server_status)
            self._smgr_log.log(self._smgr_log.DEBUG,
                  "%s added in the provision server list" %server['ip_address'])
            #end of for
        return provision_server_list, role_sequence, provision_status
    # end prepare_provision

    # API call to provision server(s) as per roles/roles
    # defined for those server(s). This function creates the
    # puppet manifest file for the server and adds it to site
    # manifest file.
    def provision_server(self, issu_flag = False):
	provision_server_list = []
        package_type_list = ["contrail-ubuntu-package", "contrail-centos-package", "contrail-storage-ubuntu-package"]
        self._smgr_log.log(self._smgr_log.DEBUG, "provision_server")
        provision_status = {}
        try:
            entity = bottle.request.json
            if entity.get('opcode', '') == "issu" and not issu_flag:
                # create SmgrIssuClass instance
                self.issu_obj = SmgrIssuClass(self, entity)
                prov_status = self.issu_obj.do_issu()
                self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.SMGR_PROVISION)
                return prov_status
            if entity.get('opcode', '') == "issu_finalize":
                # create SmgrIssuClass instance
                self.issu_obj = SmgrIssuClass(self, entity)
                prov_status = self.issu_obj.do_finalize_issu()
                self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.SMGR_PROVISION)
                return prov_status
            if entity.get('opcode', '') == "issu_rollback":
                # create SmgrIssuClass instance
                # entity includes server_id or tag, new cluster, old_cluster, old_image
                self.issu_obj = SmgrIssuClass(self, entity)
                prov_status = self.issu_obj.do_rollback_compute()
                self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.SMGR_PROVISION)
                return prov_status
            if not issu_flag:
                ret_data = self.validate_smgr_request(
                                     "PROVISION", "PROVISION", bottle.request)
            else:
                # only validate provision request, no harm making this generic not just for issu
                req_json = {'cluster_id': entity['new_cluster'],
                            'package_image_id': entity['new_image']}
                ret_data = self.validate_smgr_provision(
                                     "PROVISION", req_json, issu_flag=issu_flag)
            if ret_data['status'] == 0:
                if 'category' in ret_data and ret_data['category'] == 'container':
                    server_packages = ret_data['package_image_id']
                else:
                    server_packages = ret_data['server_packages']
            else:
                msg = "Error validating request"
                self.log_and_raise_exception(msg)
            cluster_id = ret_data['cluster_id']
            provision_server_list, role_sequence, provision_status = \
                                      self.prepare_provision(ret_data)

            # Add the provision request to reimage_queue (name of queue needs to be changed,
            # earlier it was used only for reimage, now provision requests also queued there).
            provision_item = ('provision', provision_server_list,
                                        cluster_id, role_sequence)
            self._reimage_queue.put_nowait(provision_item)
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "provision queued. Number of servers " \
                               "provisioned is %d:" %len(provision_server_list))
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, ERR_IMG_NOT_FOUND,
                                                         provision_status)
            abort(404, resp_msg)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION,
                                     False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                       None)
            abort(404, resp_msg)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION)
        if issu_flag:
            msg = "New Cluster %s needed provisioning, " %entity['new_cluster']
            msg = msg + "ISSU will be triggered after provision complete."
            provision_status['ISSU'] = msg
        provision_status['return_code'] = "0"
        provision_status['return_message'] = "server(s) provision issued"
        return provision_status
    # end provision_server

    # TBD
    def cleanup(self):
        print "called cleanup"
        self._server_monitoring_obj.cleanup(self._monitoring_base_plugin_obj.monitoring_gevent_thread_obj)

    # end cleanup

    # Private Methods

    # Method to read defaults
    def _read_smgr_object_defaults(self, smgr_config_sections):

        cluster_defaults_dict = dict(smgr_config_sections.items("CLUSTER"))
        server_defaults_dict = dict(smgr_config_sections.items("SERVER"))
        image_defaults_dict = dict(smgr_config_sections.items("IMAGE"))
        dhcp_host_defaults_dict = dict(smgr_config_sections.items("DHCP_HOST"))
        dhcp_subnet_defaults_dict = dict(smgr_config_sections.items("DHCP_SUBNET"))

        obj_cfg_defaults = {}

        obj_cfg_defaults["server"] = server_defaults_dict
        obj_cfg_defaults["cluster"] = cluster_defaults_dict
        obj_cfg_defaults["image"] = image_defaults_dict
        obj_cfg_defaults["dhcp_host"] = dhcp_host_defaults_dict
        obj_cfg_defaults["dhcp_subnet"] = dhcp_subnet_defaults_dict

        return obj_cfg_defaults


    # Parse program arguments.
    def _parse_args(self, args_str):
        '''
        Eg. python vnc_server_manager.py --config_file serverMgr.cfg
                                         --listen_ip_addr 127.0.0.1
                                         --listen_port 8082
                                         --database_name cluster_server_mgr.db
                                         --server_list myClusters.json
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        serverMgrCfg = {
            'listen_ip_addr': _WEB_HOST,
            'listen_port': _WEB_PORT,
            'database_name': _DEF_CFG_DB,
            'server_manager_base_dir': _DEF_SMGR_BASE_DIR,
            'html_root_dir': _DEF_HTML_ROOT_DIR,
            'cobbler': _DEF_COBBLER,
            'monitoring': _DEF_MONITORING,
            'cobbler_ip_address': _DEF_COBBLER_IP,
            'cobbler_port': _DEF_COBBLER_PORT,
            'cobbler_username': _DEF_COBBLER_USERNAME,
            'cobbler_password': _DEF_COBBLER_PASSWORD,
            'ipmi_username': _DEF_IPMI_USERNAME,
            'ipmi_password': _DEF_IPMI_PASSWORD,
            'ipmi_type': _DEF_IPMI_TYPE,
            'ipmi_interface': _DEF_IPMI_INTERFACE,
            'puppet_dir': _DEF_PUPPET_DIR,
            'collectors': _DEF_COLLECTORS_IP,
            'http_introspect_port': _DEF_INTROSPECT_PORT,
            'sandesh_log_level': _DEF_SANDESH_LOG_LEVEL,
            'puppet_agent_retry_count': _DEF_PUPPET_AGENT_RETRY_COUNT,
            'puppet_agent_retry_poll_interval_seconds': _DEF_PUPPET_AGENT_RETRY_POLL_INTERVAL
        }

        serverMgrAnsibleCfg = {
                'ansible_srvr_ip': _WEB_HOST,
                'ansible_srvr_port': _ANSIBLE_SRVR_PORT,
                'docker_insecure_registries': _WEB_HOST + ":5100"
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        self._smgr_config = config
        try:
            for key in dict(config.items("SERVER-MANAGER")).keys():
                if key in serverMgrCfg.keys():
                    serverMgrCfg[key] = \
                            dict(config.items("SERVER-MANAGER"))[key]
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG,
                            "Configuration set for invalid parameter: %s" % key)

            # Read the ansible server ip and port
            for key in dict(config.items("ANSIBLE-SERVER")).keys():
                if key in serverMgrAnsibleCfg.keys():
                    serverMgrCfg[key] = \
                            dict(config.items("ANSIBLE-SERVER"))[key]


            self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form config file %s" % serverMgrCfg)
        except ConfigParser.NoSectionError:
            msg = "Server Manager doesn't have a configuration set."
            self.log_and_raise_exception(msg)

        self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form config file %s" % serverMgrCfg)
        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**serverMgrCfg)

        parser.add_argument(
            "-i", "--listen_ip_addr",
            help="IP address to provide service on, default %s" % (_WEB_HOST))
        parser.add_argument(
            "-p", "--listen_port",
            help="Port to provide service on, default %s" % (_WEB_PORT))
        parser.add_argument(
            "-d", "--database_name",
            help=(
                "Name where server DB is maintained, default %s"
                % (_DEF_CFG_DB)))
        parser.add_argument(
            "-l", "--server_list",
            help=(
                "Name of JSON file containing list of cluster and servers,"
                " default None"))
        self._args = parser.parse_args(remaining_argv)
        self._monitoring_base_plugin_obj = ServerMgrMonBasePlugin()
        self._server_monitoring_obj = self._monitoring_base_plugin_obj
        self._server_inventory_obj = self._monitoring_base_plugin_obj
        if self._is_monitoring_enabled(self._args.monitoring):
            self._server_monitoring_obj = \
                self._monitoring_base_plugin_obj.parse_monitoring_args(args_str, args, self._args, self._rev_tags_dict,
                                                                       self._monitoring_base_plugin_obj)
            self._server_inventory_obj = \
                self._monitoring_base_plugin_obj.parse_inventory_args(args_str, args, self._args, self._rev_tags_dict,
                                                                      self._monitoring_base_plugin_obj)
        self._args.config_file = args.config_file
    # end _parse_args

    # TBD : Any semantic rules to be added when creating configuration
    # objects would be included here. e.g. checking IP address format
    # for the server etc.
    def _validate_config(self, config_data):
        pass
    # end _validate_config

    # Private method to unmount iso after calling cobbler functions.
    def _unmount_iso(self, mount_path):
        return_code = subprocess.call(["umount", mount_path])
    # end _unmount_iso

    # Private method to mount a given iso before calling cobbler functions.
    def _mount_and_copy_iso(self, full_image_name, copy_path, distro_name,
                            kernel_file, initrd_file, image_type):
        try:
            mount_path = self._args.server_manager_base_dir + "mnt/"
            self._unmount_iso(mount_path)
            # Make directory where ISO will be mounted
            return_code = subprocess.call(["mkdir", "-p", mount_path])
            if (return_code != 0):
                return return_code
            # Mount the ISO
            return_code = subprocess.call(
                ["mount", "-o", "loop", full_image_name, mount_path])
            if (return_code != 0):
                return return_code
            #  Make directory where files from mounted ISO are copied.
            return_code = subprocess.call(["mkdir", "-p", copy_path])
            if (return_code != 0):
                return return_code
            # Copy the files from mounted ISO.
            shutil.rmtree(copy_path, True)
            shutil.copytree(mount_path, copy_path, True)
            # Temporary Bug Fix for Corrupt Packages.gz issue reported by boot loader
            # during PXE booting if using Server Manager on Ubuntu
            # Final permanent fix TBD

            if platform.dist()[0].lower() == 'ubuntu' and image_type == 'ubuntu':
                packages_dir_path = str(copy_path + "/dists/precise/restricted/binary-amd64")
                if os.path.exists(packages_dir_path):
                    cwd = os.getcwd()
                    os.chdir(packages_dir_path)
                    shutil.copyfile('Packages.gz', 'Packages_copy.gz')
                    return_code = subprocess.call(["gunzip", "Packages_copy.gz"])
                    if (return_code != 0):
                        return return_code
                    file_size = os.stat(packages_dir_path + "/Packages_copy").st_size
                    if file_size == 0:
                        shutil.move('Packages_copy', 'Packages')
                    else:
                        shutil.rmtree('Packages_copy')
                    os.chdir(cwd)
            # End Temporary Bug Fix
            # Need to change mode to kernel and initrd files to read for all.
            kernel_file_full_path = copy_path + kernel_file
            return_code = subprocess.call(
                ["chmod", "755", kernel_file_full_path])
            if (return_code != 0):
                return return_code
            initrd_file_full_path = copy_path + initrd_file
            return_code = subprocess.call(
                ["chmod", "755", initrd_file_full_path])
            if (return_code != 0):
                return return_code
            # Now unmount the ISO
            self._unmount_iso(mount_path)
        except Exception as e:
            raise e
    # end _mount_and_copy_iso

    def create_ssh_connection(self, ip, user, pw):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=user, password=pw)
            return client
        except Exception as e:
            raise e

    # Private method to reboot the server after cobbler config is setup.
    # If power address is provided and power management system is configured
    # with cobbler, that is used to power cycle the server, else if SSH
    # connectivity is available to the server, that is used to login and reboot
    # the server.
    def _power_cycle_servers(
        self, reboot_server_list,
        cobbler_server, net_boot=False):
        self._smgr_log.log(self._smgr_log.DEBUG,
                                "_power_cycle_servers")
        success_list = []
        failed_list = []
        power_reboot_list = []
        for server in reboot_server_list:
            try:
                # Enable net boot flag in cobbler for the system.
                # Also if netbooting, delete the old puppet cert. This is
                # temporary. Need # to figure out way for cobbler to do it
                # automatically TBD Abhay
                if net_boot:
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                        "Enable netboot")
                    cobbler_server.enable_system_netboot(
                        server['host_name'])
                    cmd = "puppet cert clean %s.%s" % (
                        server['host_name'], server['domain'])
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))
                    # Remove any puppet files for new framework
                    self._smgr_puppet.new_unprovision_server(
                        server['host_name'], server['domain'])
                    # Remove manifest file for this server
                    cmd = "rm -f /etc/puppet/manifests/%s.%s.pp" %(
                        server['host_name'], server['domain'])
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))
                    # Remove entry for that server from site.pp
                    cmd = "sed -i \"/%s.%s.pp/d\" /etc/puppet/manifests/site.pp" %(
                        server['host_name'], server['domain'])
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))
                    # Remove provision log for the server
                    cmd = "rm -rf " + _DEF_SMGR_PROVISION_LOGS_DIR + server['host_name'] + '.' + \
                            server['domain']
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))

                # end if
                if server['ipmi_address']:
                    power_reboot_list.append(
                        server['id'])
                else:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(
                        paramiko.AutoAddPolicy())
                    client.connect(
                        server["ip"], username='root',
                        password=server["password"])
                    stdin, stdout, stderr = client.exec_command('reboot')
                # end else
                # Update Server table to update time.
                update = {'id': server['id'],
                          'status' : 'restart_issued',
                          'last_update': strftime(
                             "%Y-%m-%d %H:%M:%S", gmtime())}
                if self._serverDb.modify_server(update):
                    success_list.append(server['id'])
                else:
                    self._smgr_log.log(self._smgr_log.ERROR,
                         "Failed re-booting for server %s, not present in the db" % \
                                           (server['id']))
                    failed_list.append(server['id'])
            except subprocess.CalledProcessError as e:
                msg = ("power_cycle_servers: error %d when executing"
                       "\"%s\"" %(e.returncode, e.cmd))
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                self._smgr_log.log(self._smgr_log.ERROR,
                                "Failed re-booting for server %s" % \
                                (server['id']))
                failed_list.append(server['id'])
            except Exception as e:
                self._smgr_log.log(self._smgr_log.ERROR,
                                            repr(e))
                self._smgr_log.log(self._smgr_log.ERROR,
                                "Failed re-booting for server %s" % \
                                (server['id']))
                failed_list.append(server['id'])
        #end for
        if power_reboot_list:
            try:
                cobbler_server.reboot_system(
                    power_reboot_list)
                status_msg = (
                    "OK : IPMI reboot operation"
                    " initiated for specified servers")
            except Exception as e:
                status_msg = ("Error : IPMI reboot operation"
                              " failed for some servers")
        else:
            status_msg = (
                "Reboot Successful for (%s),"
                "failed for (%s)" %(
                ",".join(success_list),
                ",".join(failed_list)))
        # End if power_reboot_list
        return status_msg

    # end _power_cycle_servers

    def _encrypt_password(self, server_password):
        try:
            xyz = subprocess.Popen(
                ["openssl", "passwd", "-1", "-noverify", server_password],
                stdout=subprocess.PIPE).communicate()[0]
        except:
            return None
        return xyz

    # Internal private call to upgrade server. This is called by REST
    # API update_server and upgrade_cluster
    def _do_reimage_server(self, base_image,
                           package_image_id, reimage_parameters,
                           cobbler_server):
        try:
            # Profile name is based on image name.
            profile_name = base_image['id']
            # Setup system information in cobbler
            cobbler_server.create_system(
                reimage_parameters['server_host_name'], profile_name, package_image_id,
                reimage_parameters['server_mac'], reimage_parameters['server_ip'],
                reimage_parameters['server_mask'], reimage_parameters['server_gateway'],
                reimage_parameters['server_domain'], reimage_parameters['server_ifname'],
                reimage_parameters['server_password'],
                reimage_parameters.get('server_license', ''),
                reimage_parameters.get('esx_nicname', 'vmnic0'),
                reimage_parameters.get('ipmi_type',self._args.ipmi_type),
                reimage_parameters.get('ipmi_username',self._args.ipmi_username),
                reimage_parameters.get('ipmi_password',self._args.ipmi_password),
                reimage_parameters.get('ipmi_address',''),
                base_image, self._args.listen_ip_addr,
                reimage_parameters.get('partition', ''),
                reimage_parameters.get('config_file', None),
                reimage_parameters.get('ipmi_interface',self._args.ipmi_interface))
            # if this is a VM do qemu_system to create VM the proceed
            if reimage_parameters.get('vm_parameters', None):
                self.create_vm(reimage_parameters)
        except Exception as e:
            msg = "Server %s reimaged failed" % reimage_parameters['server_id']
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            update = {
                'mac_address': reimage_parameters['server_mac'],
                'status': "reimage_failed"
            }
            self._serverDb.modify_server(update)

        # Update Server table to add image name
        update = {
            'mac_address': reimage_parameters['server_mac'],
            'reimaged_id': base_image['id'],
            'provisioned_id': ''}
        if not self._serverDb.modify_server(update):
            msg = "Server %s is not present" % reimage_parameters['server_id']
            self._smgr_log.log(self._smgr_log.ERROR, msg)
    # end _do_reimage_server

    def get_container_provision_params(self, parent):
        params     = parent.get("parameters", {})
        prov       = params.get("provision", {})
        containers = prov.get("containers", {})
        return containers

    def get_container_image_for_role(self, role, package):
        if role == 'compute':
            return None
        container_image = self._args.docker_insecure_registries + \
                           '/' + package['id'] + '-' + role + ':' + \
                           package['version']
        pparams = package['parameters']
        for x in pparams['containers']:
            if x['role'] == role:
                if "container_image" in x:
                    container_image = x['container_image']
                else:
                    # How can this possible?
                    # Only when push container failed. This is a backup
                    msg = "container_image not set for role %s. "\
                            "Using default: %s" % (role, container_image)
                    self._smgr_log.log(self._smgr_log.ERROR, msg)

        return container_image

    def set_container_image_for_role(self, params, x, package):
        img = self.get_container_image_for_role(x, package)
        if img != None:
            params[_container_img_keys[x]] = img


    def _do_ansible_provision(self, provision_parameters, server, cluster,
                              cluster_servers, package, serverDb):
        merged_params = {}
        params   = {}
        merged_params.update(self.get_container_provision_params(cluster))
        merged_params.update(self.get_container_provision_params(server))
        params["ansible_host"] = server['ip_address']
        params["ansible_user"] = "root"
        params["ansible_password"] = server['password']
        if not (len(set(eval(server['roles'])).intersection(set(_valid_roles)))):
            msg = "No ansible roles for this server, skipping to puppet provision"
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return False
        for x in eval(server['roles']):
            srvr_provision_params = server['parameters']['provision']
            container_params = srvr_provision_params['containers']
            if not x in merged_params.keys():
                msg = "Provision Error: server and cluster parameters do " +\
                      "not contain section for role %s" % x
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                update = {'id': server['id'],
                    'status' : msg,
                    'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                    'provisioned_id': package.get('id', '')}
                self._serverDb.modify_server(update)
                return False
            else:
                params[x] = merged_params[x]

        cnt = 0
        numroles = len(eval(server['roles']))
        send_REST_request(self._args.ansible_srvr_ip,
                    self._args.ansible_srvr_port,
                    _ANSIBLE_PROVISION_START_ENDPOINT, params)
        pp = []
        for x in eval(server['roles']):
            params['container_name'] = x
            self.set_container_image_for_role(params, x, package)
            params['container_image'] = self.get_container_image_for_role(x,
                                            package)
            parameters = { 'server_id': server['id'], 'parameters': params }
            pp.append(copy.deepcopy(parameters))

        time.sleep(10)
        send_REST_request(self._args.ansible_srvr_ip,
                      self._args.ansible_srvr_port,
                      _ANSIBLE_PROVISION_ENDPOINT, pp)
        update = {'id': server['id'],
                'status' : 'provision_issued',
                'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                'provisioned_id': package.get('id', '')}
        self._serverDb.modify_server(update)

        return True



    # Internal private call to provision server. This is called by REST API
    # provision_server and provision_cluster
    def _do_provision_server(
        self, provision_parameters, server,
        cluster, cluster_servers, package, serverDb):
        
        if package['category'] == 'container':
            self._do_ansible_provision(provision_parameters, server, cluster,
                                  cluster_servers, package, serverDb)
            if ('compute' in server['roles'] or 'openstack' in server['roles']) and package['compute_image_id']:
                compute_images = self._serverDb.get_image({"id":
                    str(package['compute_image_id'])}, detail=True)
                if compute_images:
                    compute_package = compute_images[0]
                    compute_package_image_id, compute_package = self.get_package_image(
                                               str(package['compute_image_id']))
                    if "parameters" in compute_package:
                        compute_package["parameters"] = eval(compute_package["parameters"])
                        compute_package["calc_params"] = package.get("calc_params",{})
                    self._do_provision_server(provision_parameters, server,
                            cluster, cluster_servers, compute_package, serverDb)
        else:
            #Start the puppet agent in the target servers
            gevent.spawn(self._monitoring_base_plugin_obj.gevent_puppet_agent_action, server, serverDb, self._args, "start")
            try:
                # Now call puppet to provision the server.
                self._smgr_puppet.provision_server(
                    provision_parameters,
                    server,
                    cluster,
                    cluster_servers,
                    package,
                    serverDb)
                self._smgr_certs.create_server_cert(server)
                # Update Server table with provisioned id
                update = {'id': server['id'],
                      'status' : 'provision_issued',
                      'last_update': strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                      'provisioned_id': package.get('id', '')}
                self._serverDb.modify_server(update)
            except subprocess.CalledProcessError as e:
                msg = ("do_provision_server: error %d when executing"
                       "\"%s\"" %(e.returncode, e.cmd))
                self._smgr_log.log(self._smgr_log.ERROR, msg)
            except Exception as e:
                raise e
    # end _do_provision_server

    def _create_server_manager_config(self, config):
        try:
            cluster_list = config.get("cluster", None)
            if cluster_list:
                for cluster in cluster_list:
                    self._serverDb.add_cluster(cluster)
            servers = config.get("servers", None)
            if servers:
                for server in servers:
                    self._serverDb.add_server(server)
        except Exception as e:
            raise e
    # end _create_server_manager_config

    #generate random string
    def random_string(self, string_length=10):
        """Returns a random string of length string_length."""
        random = str(uuid.uuid4()) # Convert UUID format to a Python string.
        random = random.upper() # Make all characters uppercase.
        random = random.replace("-","") # Remove the UUID '-'.
        return random[0:string_length] # Return the random string.

    def _plug_service_passwords(self, openstack_params, service_name, field_name,
                                                    password):
        service_dict = openstack_params.get(service_name, {})
        service_dict[field_name] = service_dict.get(field_name, password)
        openstack_params[service_name] = service_dict

    def generate_passwords(self, params):
        if params == None:
            return;

        if "provision" in params:
            #New params
            self._smgr_log.log(self._smgr_log.INFO, "generating passwords for new params")
            provision_params = params.get("provision", {})

            openstack_params = provision_params.get("openstack", {})
            provision_params["openstack"] = openstack_params
            mysql_params = openstack_params.get("mysql", {})
            openstack_params["mysql"] = mysql_params
            mysql_params["root_password"] = mysql_params.get("root_password", self.random_string(12))
            mysql_params["service_password"] = mysql_params.get("service_password", self.random_string(12))
            keystone_params = openstack_params.get("keystone", {})
            openstack_params["keystone"] = keystone_params
            keystone_params["admin_password"] = keystone_params.get("admin_password", self.random_string(12))
            keystone_params["admin_token"] = keystone_params.get("admin_token", self.random_string(12))
            #generate passwords for service
            self._plug_service_passwords(openstack_params, "glance", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "cinder", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "swift", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "nova", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "horizon", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "neutron", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "heat", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "ceilometer", "password",
                                                    keystone_params["admin_password"])
            self._plug_service_passwords(openstack_params, "ceilometer", "mongo",
                                                    keystone_params["admin_password"])
            #Do we need the below
            self._plug_service_passwords(openstack_params, "heat",
                                                    "encryption_key",
                                                    self.random_string(16))
            heat_encryption_key = openstack_params["heat"]["encryption_key"]
            if 'E' in heat_encryption_key:
                heat_encryption_key = heat_encryption_key.replace('E','D')
                openstack_params["heat"]["encryption_key"] = heat_encryption_key

# End class VncServerManager()

def print_rest_response(resp):
        if resp:
            try:
                if type(resp) is str:
                    resp_obj = json.loads(resp)
                else:
                    resp_obj = resp
                resp = json.dumps(resp_obj, sort_keys=True, indent=4)
            except ValueError:
                pass
            return resp


def main(args_str=None):
    vnc_server_mgr = VncServerManager(args_str)
    pipe_start_app = vnc_server_mgr.get_pipe_start_app()

    server_ip = vnc_server_mgr.get_server_ip()
    server_port = vnc_server_mgr.get_server_port()

    server_mgr_pid = os.getpid()
    pid_file = "/var/run/contrail-server-manager/contrail-server-manager.pid"
    dir = os.path.dirname(pid_file)
    if not os.path.exists(dir):
        os.mkdir(dir)
    f = open(pid_file, "w")
    f.write(str(server_mgr_pid))
    print "wiriting pid file"
    print "smgr pid written is %s" % server_mgr_pid
    f.close()

    try:
        bottle.run(app=pipe_start_app,server = 'gevent', host=server_ip, port=server_port)

    except Exception as e:
        # cleanup gracefully
        print 'Exception error is: %s' % e
        vnc_server_mgr.cleanup()

# End of main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    main()
# End if __name__


