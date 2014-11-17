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
import subprocess
import json
import argparse
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import bottle
from bottle import route, run, request, abort
import ConfigParser
import paramiko
import base64
import shutil
import string
from urlparse import urlparse, parse_qs
from time import gmtime, strftime, localtime
import pdb
import server_mgr_db
import ast
import uuid
import traceback
import platform
from server_mgr_defaults import *
from server_mgr_err import *
from server_mgr_status import *
from server_mgr_db import ServerMgrDb as db
from server_mgr_cobbler import ServerMgrCobbler as ServerMgrCobbler
from server_mgr_puppet import ServerMgrPuppet as ServerMgrPuppet
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_mon_base_plugin import ServerMgrMonBasePlugin
from send_mail import send_mail
import tempfile
from contrail_defaults import *

bottle.BaseRequest.MEMFILE_MAX = 2 * 102400

_WEB_HOST = '127.0.0.1'
_WEB_PORT = 9001
_DEF_CFG_DB = 'cluster_server_mgr.db'
_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_SERVER_TAGS_FILE = _DEF_SMGR_BASE_DIR + 'tags.ini'
_DEF_HTML_ROOT_DIR = '/var/www/html/'
_DEF_COBBLER_IP = '127.0.0.1'
_DEF_COBBLER_PORT = None
_DEF_COBBLER_USERNAME = 'cobbler'
_DEF_COBBLER_PASSWORD = 'cobbler'
_DEF_IPMI_USERNAME = 'ADMIN'
_DEF_IPMI_PASSWORD = 'ADMIN'
_DEF_IPMI_TYPE = 'ipmilan'
_DEF_PUPPET_DIR = '/etc/puppet/'

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
                   "esxi5.5", "esxi5.1"]
    _iso_types = ["centos", "redhat", "ubuntu", "fedora", "esxi5.1", "esxi5.5"]
    _package_types = ["contrail-ubuntu-package", "contrail-centos-package",
                      "contrail-storage-ubuntu-package"]
    _image_category_list = ["image", "package"]
    _tags_dict = {}
    _rev_tags_dict = {}
    _dev_env_monitoring_obj = None
    _monitoring_base_plugin_obj = None
    _config_set = False
    #fileds here except match_keys, obj_name and primary_key should
    #match with the db columns


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

        self._monitoring_base_plugin_obj = ServerMgrMonBasePlugin()
        if not args_str:
            args_str = sys.argv[1:]
        self._parse_args(args_str)
        # Reads the tags.ini file to get tags mapping (if it exists)
        if os.path.isfile(_SERVER_TAGS_FILE):
            tags_config = ConfigParser.SafeConfigParser()
            tags_config.read(_SERVER_TAGS_FILE)
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
            self._smgr_cobbler = ServerMgrCobbler(self._args.server_manager_base_dir,
                                                  self._args.cobbler_ip_address,
                                                  self._args.cobbler_port,
                                                  self._args.cobbler_username,
                                                  self._args.cobbler_password)
        except:
            print "Error connecting to cobbler"
            exit()

        try:
            # needed for testing...
            status_thread_config = {}
            status_thread_config['listen_ip'] = self._args.listen_ip_addr
            status_thread_config['listen_port'] = '9002'

            status_thread = ServerMgrStatusThread(
                            None, "Status-Thread", status_thread_config)
            # Make the thread as daemon
            status_thread.daemon = True
            status_thread.start()
        except:
            self._smgr_log.log(self._smgr_log.ERROR,
                     "Error starting the status thread")
            exit()

        # Create an instance of puppet interface class.
        try:
            # TBD - Puppet parameters to be added.
            self._smgr_puppet = ServerMgrPuppet(self._args.server_manager_base_dir,
                                                self._args.puppet_dir)
        except:
            self._smgr_log.log(self._smgr_log.ERROR, "Error creating instance of puppet object")
            exit()

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

        self._dev_env_monitoring_obj.set_serverdb(self._serverDb)
        self._dev_env_monitoring_obj.set_ipmi_defaults(self._args.ipmi_username, self._args.ipmi_password)
        self._dev_env_monitoring_obj.daemon = True
        self._dev_env_monitoring_obj.start()

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
        bottle.route('/tag', 'GET', self.get_server_tags)
        bottle.route('/Monitor', 'GET', self.get_mon_details)

        # REST calls for PUT methods (Create New Records)
        bottle.route('/all', 'PUT', self.create_server_mgr_config)
        bottle.route('/image/upload', 'PUT', self.upload_image)
        bottle.route('/status', 'PUT', self.put_status)

        #smgr_add
        bottle.route('/server', 'PUT', self.put_server)
        bottle.route('/image', 'PUT', self.put_image)
        bottle.route('/cluster', 'PUT', self.put_cluster)
        bottle.route('/tag', 'PUT', self.put_server_tags)

        # REST calls for DELETE methods (Remove records)
        bottle.route('/cluster', 'DELETE', self.delete_cluster)
        bottle.route('/server', 'DELETE', self.delete_server)
        bottle.route('/image', 'DELETE', self.delete_image)

        # REST calls for POST methods
        bottle.route('/server/reimage', 'POST', self.reimage_server)
        bottle.route('/server/provision', 'POST', self.provision_server)
        bottle.route('/server/restart', 'POST', self.restart_server)
        bottle.route('/dhcp_event', 'POST', self.process_dhcp_event)
        bottle.route('/interface_created', 'POST', self.interface_created)

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
        except Exception as e:
            self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_ALL,
                                     False)
            self.log_trace()
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR, None)
            abort(404, resp_msg)

        self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_CFG_ALL)
        self._smgr_log.log(self._smgr_log.DEBUG, "Config returned: %s" % (config))
        return config
    # end get_server_mgr_config

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
        self._smgr_log.log(self._smgr_log.DEBUG, "Entity returned: %s" % (print_rest_response(entity)))
        return {"cluster": entity}
    # end get_cluster

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
        self._smgr_log.log(self._smgr_log.DEBUG, "Entity returned: %s" % (tag_dict))

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
        for data_item_key, data_item_value in data.iteritems():
            #If json data name is not present in list of
            #allowable fields silently ignore them.
            if data_item_key == "parameters" and modify == False:
                object_parameters = data_item_value
                default_object_parameters = eval(validation_data['parameters'])
                for key,value in default_object_parameters.iteritems():
                    if key not in object_parameters:
                        msg = "Default Object param added is %s:%s" % \
                                (key, value)
                        self._smgr_log.log(self._smgr_log.INFO,
                                   msg)
                        object_parameters[key] = value
                """

                for k,v in object_parameters.iteritems():
                    if k in default_object_parameters and v == ''
                    if v == '""':
                        object_parameters[k] = ''
                """
                data[data_item_key] = object_parameters
            elif data_item_key not in validation_data:
#                data.pop(data_item_key, None)
                remove_list.append(data_item_key)
                msg =  ("Value %s is not an option") % (data_item_key)
                self._smgr_log.log(self._smgr_log.ERROR,
                                   msg)
            if data_item_value == '""':
                data[data_item_key] = ''
        for item in remove_list:
            data.pop(item, None)

        #Added default fields
        for k,v in validation_data.items():
            if k == "match_keys" or k == "primary_keys" \
                or k == "obj_name":
                continue
            if k not in data and v and modify == False:
                msg = "Default added is %s:%s" % \
                                (k, v)
                self._smgr_log.log(self._smgr_log.INFO,
                                   msg)
                if k == 'parameters':
                    data[k] = eval(v)
                else:
                    data[k] = v

            """
            if k not in data:
                msg =  ("Field %s not present") % (k)
                self.log_and_raise_exception(msg)
            if v != '' and data[k] not in v:
                msg =  ("Value %s is not an option") % (data[k])
                self.log_and_raise_exception(msg)
            """
        if 'roles' in data:
            if 'storage-compute' in data['roles'] and 'compute' not in data['roles']:
                msg = "role 'storage-compute' needs role 'compute' in provision file"
                raise ServerMgrException(msg, ERR_OPR_ERROR)
            elif 'storage-master' in data['roles'] and 'openstack' not in data['roles']:
                msg = "role 'storage-master' needs role 'openstack' in provision file"
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

    def _validate_roles(self, cluster_id):
        # get list of all servers in this cluster
        servers = self._serverDb.get_server(
            {'cluster_id': cluster_id}, detail=True)
        role_list = [
                "database", "openstack", "config",
                "control", "collector", "webui", "compute" ]
        roles_set = set(role_list)

        optional_role_list = ["storage-compute", "storage-master"]
        optional_role_set = set(optional_role_list)

        cluster_role_list = []
        for server in servers:
            duplicate_roles = self.list_duplicates(eval(server['roles']))
            if len(duplicate_roles):
                msg = "Duplicate Roles '%s' present" % \
                        ", ".join(str(e) for e in duplicate_roles)
                self.log_and_raise_exception(msg)
            cluster_role_list.extend(eval(server['roles']))

        cluster_unique_roles = set(cluster_role_list)

        missing_roles = roles_set.difference(cluster_unique_roles)
        if len(missing_roles):
            msg = "Mandatory roles \"%s\" are not present" % \
            ", ".join(str(e) for e in missing_roles)
            self.log_and_raise_exception(msg)

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

    def validate_smgr_provision(self, validation_data, request , data=None):
        ret_data = {}
        ret_data['status'] = 1

        entity = request.json
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
                "control", "collector", "webui", "compute", "zookeeper", "storage-compute", "storage-master"]
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
            self._validate_roles(cluster_id)
            ret_data["status"] = 0
            ret_data["servers"] = servers
            ret_data["package_image_id"] = package_image_id
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

        if base_image_id is None:
            msg = "No base image id specified"
            self.log_and_raise_exception(msg)

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
                   keys = ["id", "mac_address","tag","cluster_id", "where"]):
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

        self._smgr_log.log(self._smgr_log.DEBUG, "ret_val_data returned: %s" % (ret_val_data))

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

    # This call returns status information about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server_status(self):
        ret_data = None
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server_status")
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
        self._smgr_log.log(self._smgr_log.DEBUG, "JSON response:%s" % (print_rest_response(servers)))
        return {"server": servers}
    # end get_server_status



    # This call returns information about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server(self):
        ret_data = None
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server")
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
        self._smgr_log.log(self._smgr_log.DEBUG, (print_rest_response(servers)))
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
            if detail:
                x['tag'] = {}
                for i in range(1, len(self._tags_list)+1):
                    tag = "tag" + str(i)
                    if x[tag]:
                        x['tag'][self._tags_dict[tag]] = x.pop(tag, None)
                    else:
                        x.pop(tag, None)
        return {"server": servers}
    # end get_server

    # API Call to list images
    def get_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_image")
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
        self._smgr_log.log(self._smgr_log.DEBUG, (print_rest_response(images)))
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
            self._smgr_log.log(self._smgr_log.DEBUG, "Server status Data %s" % server_data)
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

    def put_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "add_image")
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
                    extn = os.path.splitext(image_path)[1]
                    dest = self._args.server_manager_base_dir + 'images/' + \
                        image_id + extn
                    subprocess.check_call(["cp", "-f", image_path, dest])
                    if ((image_type == "contrail-centos-package") or
                        (image_type == "contrail-ubuntu-package") ):
                        puppet_manifest_version = self._create_repo(
                            image_id, image_type, image_version, dest)
                        image_params['puppet_manifest_version'] = \
                            puppet_manifest_version
                    elif image_type == "contrail-storage-ubuntu-package":
                        self._create_repo(
                            image_id, image_type, image_version, dest)
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
                                    image_version, dest,
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
        self._smgr_log.log(self._smgr_log.DEBUG, "put_cluster")
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
                    self._smgr_log.log(self._smgr_log.INFO, "Cluster Data %s" % cur_cluster)
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

    def put_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "add_server")
        entity = bottle.request.json
        if (not entity):
            msg = 'Server MAC or server_id not specified'
            resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
            abort(404, resp_msg)
        try:
            self.validate_smgr_entity("server", entity)
            servers = entity.get("server", None)
            for server in servers:
                self.validate_server_mgr_tags(server)
                if self._serverDb.check_obj(
                    "server", {"id" : server['id']},
                    raise_exception=False):
                    #TODO - Revisit this logic
                    # Do we need mac to be primary MAC
                    server_fields['primary_keys'] = "['id']"
                    self.validate_smgr_request("SERVER", "PUT", bottle.request,
                                                             server, True)
                    self._serverDb.modify_server(server)
                    server_fields['primary_keys'] = "['id', 'mac_address']"
                else:
                    self.validate_smgr_request("SERVER", "PUT", bottle.request,
                                                                        server)
                    server['status'] = "server_added"
                    self._serverDb.add_server(server)
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
        self._smgr_log.log(self._smgr_log.DEBUG, "add_tag")
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
            with open(_SERVER_TAGS_FILE, 'wb') as configfile:
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
        self._smgr_log.log(self._smgr_log.DEBUG, "function_start")
        return_data = {}
        return_data['return_code'] = ret_code
        return_data['return_msg'] = msg
        return_data['return_data'] = data
        
        return_data_str = print_rest_response(return_data)
        
        return return_data_str
       

    # API Call to add image file to server manager (file is copied at
    # <default_base_path>/images/filename.iso and distro, profile
    # created in cobbler. This is similar to function above (add_image),
    # but this call actually upload ISO image from client to the server.
    def upload_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "upload_image")
        image_id = bottle.request.forms.id
        image_version = bottle.request.forms.version
        image_type = bottle.request.forms.type
        msg = ""
        if (image_type not in [
                "centos", "fedora", "ubuntu",
                "contrail-ubuntu-package", "contrail-centos-package", "contrail-storage-ubuntu-package"]):
            msg = "Invalid Image type for %s" % (image_id) 
            resp_msg = self.form_operartion_data(msg, ERR_IMG_TYPE_INVALID, None)
            abort(404, resp_msg)
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
            if ((image_type == "contrail-centos-package") or
                (image_type == "contrail-ubuntu-package")):
                puppet_manifest_version = self._create_repo(
                    image_id, image_type, image_version, dest)
                image_params['puppet_manifest_version'] = \
                    puppet_manifest_version
            elif image_type == "contrail-storage-ubuntu-package":
                self._create_repo(
                    image_id, image_type, image_version, dest)
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
                'parameters' : image_params}
            self._serverDb.add_image(image_data)
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
            # Copy the tgz to tempdir
            cmd = ("cp -f %s ." %(puppet_modules_tgz))
            subprocess.check_call(cmd, shell=True)
            # untar the puppet modules tgz file
            cmd = ("tar xvzf contrail-puppet-manifest.tgz > /dev/null")
            subprocess.check_call(cmd, shell=True)
            # Changing the below logic. Instead of reading version from
            # version file, use image id as the version. Image id is unique
            # and hence it would be easy to correlate puppet modules to
            # contrail package being added. With this change, every image would
            # have it's own manifests, even though manifests between two contrail
            # versions might be identical.
            # Extract contents of version file.
            #with open('version','r') as f:
            #    version = f.read().splitlines()[0]
            version = image_id
            # Create modules directory if it does not exist.
            target_dir = "/etc/puppet/modules/contrail_" + version
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
            return version
        except subprocess.CalledProcessError as e:
            shutil.rmtree(tmpdirname) # delete directory
            msg = ("add_puppet_modules: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        finally:
            try:
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
            # create a repo-dir where we will create the repo
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
            cmd = "mkdir -p %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.check_call(cmd, shell=True)
            # Extract .tgz of contrail puppet manifest files
            cmd = (
                "rpm2cpio %s | cpio -ivd ./opt/contrail/puppet/"
                "contrail-puppet-manifest.tgz > /dev/null" %(dest))
            subprocess.check_call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            puppet_modules_tgz_path = mirror + \
                "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version = self._add_puppet_modules(
                puppet_modules_tgz_path, image_id)
            # Extract .tgz of other packages from the repo
            cmd = (
                "rpm2cpio %s | cpio -ivd ./opt/contrail/contrail_packages/"
                "contrail_rpms.tgz > /dev/null" %(dest))
            subprocess.check_call(cmd, shell=True)
            cmd = ("mv ./opt/contrail/contrail_packages/contrail_rpms.tgz .")
            subprocess.call(cmd, shell=True)
            cmd = ("rm -rf opt")
            subprocess.check_call(cmd, shell=True)
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
            return puppet_manifest_version
        except subprocess.CalledProcessError as e:
            msg = ("create_yum_repo: error %d when executing"
                   "\"%s\"" %(e.returncode, e.cmd))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        except Exception as e:
            raise(e)
    # end _create_yum_repo

    # Create debian repo
    # Create debian repo for "debian" packages.
    # repo created includes the wrapper package too.
    def _create_deb_repo(
        self, image_id, image_type, image_version, dest):
        puppet_manifest_version = ""
        try:
            # create a repo-dir where we will create the repo
            mirror = self._args.html_root_dir+"contrail/repo/"+image_id
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
            cmd = (
                "dpkg -x %s . > /dev/null" %(dest))
            subprocess.check_call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            puppet_modules_tgz_path = mirror + \
                "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version = self._add_puppet_modules(
                puppet_modules_tgz_path, image_id)
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
            # build repo using createrepo
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
            return puppet_manifest_version
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
            cmd = (
                "dpkg -x %s . > /dev/null" %(dest))
            subprocess.check_call(cmd, shell=True)
            cmd = ("mv ./opt/contrail/contrail_packages/contrail_storage_debs.tgz .")
            subprocess.check_call(cmd, shell=True)
            cmd = ("rm -rf opt")
            subprocess.check_call(cmd, shell=True)
            # untar tgz to get all packages
            cmd = ("tar xvzf contrail_storage_debs.tgz > /dev/null")
            subprocess.check_call(cmd, shell=True)
            # remove the tgz file itself, not needed any more
            cmd = ("rm -f contrail_storage_debs.tgz")
            subprocess.check_call(cmd, shell=True)
            # build repo using createrepo
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
        try:
            if (image_type == "contrail-centos-package"):
                puppet_manifest_version = self._create_yum_repo(
                    image_id, image_type, image_version, dest)
            elif (image_type == "contrail-ubuntu-package"):
                puppet_manifest_version = self._create_deb_repo(
                    image_id, image_type, image_version, dest)
            elif (image_type == "contrail-storage-ubuntu-package"):
                self._create_storage_deb_repo(
                    image_id, image_type, image_version, dest)

            else:
                pass
            return puppet_manifest_version
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
                    ubuntu_ks_file = 'kickstarts/contrail-ubuntu.ks'
                    kickstart = self._args.html_root_dir + \
                                "kickstarts/" + ubuntu_ks_file
                else:
                    ubuntu_ks_file = 'contrail/images/' + ks_file.split('/').pop()
                if not kseed_file:
                    ks_file = self._args.html_root_dir + \
                        "kickstarts/contrail-ubuntu.seed"
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
                resp_msg = self.form_operartion_data(msg, ERR_OPR_ERROR, None)
                abort(404, resp_msg)


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
        except Exception as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding image to cobbler %s" % repr(e))
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
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
                match_dict, detail= False)
            self._serverDb.delete_server(match_dict)
            # delete the system entries from cobbler
            for server in servers:
                self._smgr_cobbler.delete_system(server['id'])
            # Sync the above information
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
            if ((image['type'] == 'contrail-ubuntu-package') or
                (image['type'] == 'contrail-centos-package') or
                (image['type'] == 'contrail-storage-ubuntu-package')):
                ext_dir = {
                    "contrail-ubuntu-package" : ".deb",
                    "contrail-centos-package": ".rpm",
                    "contrail-storage-ubuntu-package": ".deb"}
                os.remove(self._args.server_manager_base_dir + 'images/' +
                          image_id + ext_dir[image['type']])

                # remove repo dir
                shutil.rmtree(
                    self._args.html_root_dir + "contrail/repo/" +
                    image_id, True)
                # delete repo from cobbler
                self._smgr_cobbler.delete_repo(image_id)
            else:
                # delete corresponding distro from cobbler
                self._smgr_cobbler.delete_distro(image_id)
                # Sync the above information
                self._smgr_cobbler.sync()
                # remove the file
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
            resp_msg = self.form_operartion_data(repr(e), ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
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
        if packages[0]['category'] and packages[0]['category'] != 'package':
            msg = "Category is not package, it is %s" (packages[0]['category'])
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
            raise ServerMgrException(msg)
        if images[0]['category'] and images[0]['category'] != 'image':
            msg = "Category is not image, it is %s" (images[0]['category'])
            raise ServerMgrException(msg)
        if images[0]['type'] not in self._iso_types:
            msg = "Image %s is not an iso" % (base_image_id)
            raise ServerMgrException(msg)
        return base_image_id, images[0]
    # end get_base_image
            
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
            base_image = {}
            if base_image_id:
                base_image_id, base_image = self.get_base_image(base_image_id)
            servers = self._serverDb.get_server(match_dict, detail=True)
            if len(servers) == 0:
                msg = "No Servers found for %s" % (match_value)
                self.log_and_raise_exception(msg)
            reimage_status = {}
            reimage_status['server'] = []
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

                image = base_image
                if not image:
                    base_image_id = server.get('base_image_id', '')
                    if not base_image_id and cluster:
                        base_image_id = cluster[0].get('base_image_id', '')
                    image_id, image = self.get_base_image(base_image_id)
                if not image:
                    msg = "No valid image id found for server %s" % (server['id'])
                    raise ServerMgrException(msg)
                password = mask = gateway = domain = None
                server_id = server['id']
                if 'password' in server and server['password']:
                    password = server['password']
                elif 'password' in cluster_parameters and cluster_parameters['password']:
                    password = cluster_parameters['password']
                else:
                    msg = "Missing Password for " + server_id
                    self.log_and_raise_exception(msg)

                if 'subnet_mask' in server and server['subnet_mask']:
                    subnet_mask = server['subnet_mask']
                elif 'subnet_mask' in cluster_parameters and cluster_parameters['subnet_mask']:
                    subnet_mask = cluster_parameters['subnet_mask']
                else:
                    msg = "Missing prefix/mask for " + server_id
                    self.log_and_raise_exception(msg)

                if 'gateway' in server and server['gateway']:
                    gateway = server['gateway']
                elif 'gateway' in cluster_parameters and cluster_parameters['gateway']:
                    gateway = cluster_parameters['gateway']
                else:
                    msg = "Missing gateway for " + server_id
                    self.log_and_raise_exception(msg)

                if 'domain' in server and server['domain']:
                    domain = server['domain']
                elif 'domain' in cluster_parameters and cluster_parameters['domain']:
                    domain = cluster_parameters['domain']
                else:
                    msg = "Missing domain for " + server_id
                    self.log_and_raise_exception(msg)

                if 'ip_address' in server and server['ip_address']:
                    ip = server['ip_address']
                else:
                    msg = "Missing ip for " + server_id
                    self.log_and_raise_exception(msg)

                reimage_parameters = {}
                if ((image['type'] == 'esxi5.1') or
                    (image['type'] == 'esxi5.5')):
                    reimage_parameters['server_license'] = server_parameters.get(
                        'server_license', '')
                    reimage_parameters['esx_nicname'] = server_parameters.get(
                        'esx_nicname', 'vmnic0')
                reimage_parameters['server_id'] = server['id']
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
                if 'ipmi_addresss' in server and server['ipmi_addresss'] == None:
                    msg = "Missing ipmi address for " + server_id
                    self.log_and_raise_exception(msg)
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
                reimage_parameters['ipmi_address'] = server.get(
                    'ipmi_address', '')
                reimage_parameters['partition'] = server_parameters.get('partition', '')
                self._do_reimage_server(
                    image, package_image_id, reimage_parameters)

                # Build list of servers to be rebooted.
                reboot_server = {
                    'id' : server['id'],
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

            # now reboot the servers, if no_reboot is not specified by user.
            if do_reboot:
                status_msg = self._power_cycle_servers(
                    reboot_server_list, True)
            #After all system entries are created sync.
            self._smgr_cobbler.sync()

        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE,
                                     False)
            resp_msg = self.form_operartion_data(e.msg, e.ret_code, None)
            abort(404, resp_msg)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE,
                                     False)
            print 'Exception error is: %s' % e
            resp_msg = self.form_operartion_data("Error in re-imaging server", ERR_GENERAL_ERROR,
                                                                            None)
            abort(404, resp_msg)
        reimage_status['return_code'] = "0"
        reimage_status['return_message'] = "server(s) reimage issued"
        return reimage_status
    # end reimage_server

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
                    'domain' : domain,
                    'ip' : server.get("ip_address", ""),
                    'password' : password,
                    'ipmi_address' : server.get('ipmi_address',"") }
                reboot_server_list.append(
                    reboot_server)
            # end for server in servers

            status_msg = self._power_cycle_servers(
                reboot_server_list, do_net_boot)
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

    #Function to get control section for all servers
    # belonging to the same VN
    def get_control_net(self, cluster_servers):
        server_control_list = {}
        for server in cluster_servers:
            if 'intf_control' not in server:
                    intf_control = ""
            else:
                intf_control = server['intf_control']
                server_control_list[server['ip_address']] = intf_control
        return server_control_list

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

    def get_server_packages(self, servers, package_image_id):
        server_packages = []
        if package_image_id:
            package_image_id, package = self.get_package_image(package_image_id)
            puppet_manifest_version = \
                eval(package['parameters'])['puppet_manifest_version']
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
                server_pkg['puppet_manifest_version'] = \
                    eval(package['parameters'])['puppet_manifest_version']
                server_pkg['package_type'] = package['type']
            else:
                server_pkg['package_image_id'] = package_image_id
                server_pkg['puppet_manifest_version'] = puppet_manifest_version
                server_pkg['package_type'] = package_type
            server_packages.append(server_pkg)
        return server_packages
    # end get_server_packages

    # Function to decide which type of monitoring info to fetch
    def get_mon_details(self):
        try:
            if self._config_set:
                return "Configuration for Monitoring set correctly."
            elif self._monitoring_args:
                return_data = ""
                if self._monitoring_args.collectors is None:
                    return_data += "The collectors IP parameter hasn't been correctly configured.\n"
                elif self._monitoring_args.monitoring_plugin is None:
                    return_data += "The Monitoring Plugin parameter hasn't been correctly configured.\n"

                return_data += "\nReset the configuration correctly and restart Server Manager.\n"
                return return_data
            else:
                return "Monitoring Parameters haven't been configured.\n" \
                       "Reset the configuration correctly and restart Server Manager.\n"
        except Exception as e:
            abort(404, e.message)

    # API call to provision server(s) as per roles/roles
    # defined for those server(s). This function creates the
    # puppet manifest file for the server and adds it to site
    # manifest file.
    def provision_server(self):
        package_type_list = ["contrail-ubuntu-package", "contrail-centos-package", "contrail-storage-ubuntu-package"]
        self._smgr_log.log(self._smgr_log.DEBUG, "provision_server")
        provision_status = {}
        try:
            entity = bottle.request.json
            interface_created = entity.pop("interface_created", None)

            role_servers = {}
            role_ips = {}
            role_ids = {}

            ret_data = self.validate_smgr_request("PROVISION", "PROVISION", bottle.request)
            if ret_data['status'] == 0:
                server_packages = ret_data['server_packages']
            else:
                msg = "Error validating request"
                self.log_and_raise_exception(msg)

            provision_status['server'] = []
            for server_pkg in server_packages:
                server = server_pkg['server']
                package_image_id = server_pkg['package_image_id']
                package_type = server_pkg['package_type']
                server_params = eval(server['parameters'])
                cluster = self._serverDb.get_cluster(
                    {"id" : server['cluster_id']},
                    detail=True)[0]
                cluster_params = eval(cluster['parameters'])
                # Get all the servers belonging to the CLUSTER that this server
                # belongs too.
                cluster_servers = self._serverDb.get_server(
                    {"cluster_id" : server["cluster_id"]},
                    detail="True")
                # build roles dictionary for this cluster. Roles dictionary will be
                # keyed by role-id and value would be list of servers configured
                # with this role.
                if not role_servers:
                    for role in ['database', 'openstack',
                                 'config', 'control',
                                 'collector', 'webui',
                                 'compute', 'storage-compute', 'storage-master']:
                        role_servers[role] = self.role_get_servers(
                            cluster_servers, role)
                        role_ips[role] = [x["ip_address"] for x in role_servers[role]]
                        role_ids[role] = [x["id"] for x in role_servers[role]]

                provision_params = {}
                provision_params['package_image_id'] = package_image_id
                provision_params['package_type'] = package_type
                puppet_manifest_version = server_pkg['puppet_manifest_version']
                provision_params['puppet_manifest_version'] = puppet_manifest_version
                provision_params['server_mgr_ip'] = self._args.listen_ip_addr
                provision_params['roles'] = role_ips
                provision_params['role_ids'] = role_ids
                provision_params['server_id'] = server['id']
                if server['domain']:
                    provision_params['domain'] = server['domain']
                else:
                        provision_params['domain'] = cluster_params['domain']

                provision_params['rmq_master'] = role_ids['config'][0]
                provision_params['uuid'] = cluster_params['uuid']
                provision_params['smgr_ip'] = self._args.listen_ip_addr
                if role_ids['config'][0] == server['id']:
                        provision_params['is_rmq_master'] = "yes"
                else:
                    provision_params['is_rmq_master'] = "no"
                provision_params['intf_control'] = ""
                provision_params['intf_bond'] = ""
                provision_params['intf_data'] = ""
                if 'intf_control' in server:
                    provision_params['intf_control'] = server['intf_control']
                if 'intf_data' in server:
                    provision_params['intf_data'] = server['intf_data']
                if 'intf_bond' in server:
                    provision_params['intf_bond'] = server['intf_bond']
                provision_params['control_net'] = self.get_control_net(cluster_servers)
                provision_params['server_ip'] = server['ip_address']
                provision_params['database_dir'] = cluster_params['database_dir']
                provision_params['database_token'] = cluster_params['database_token']
                provision_params['openstack_mgmt_ip'] = ''
                provision_params['openstack_passwd'] = ''
                provision_params['use_certificates'] = cluster_params['use_certificates']
                provision_params['multi_tenancy'] = cluster_params['multi_tenancy']
                provision_params['router_asn'] = cluster_params['router_asn']
                provision_params['encapsulation_priority'] = cluster_params['encapsulation_priority']
                provision_params['service_token'] = cluster_params['service_token']
                provision_params['keystone_username'] = cluster_params['keystone_username']
                provision_params['keystone_password'] = cluster_params['keystone_password']
                provision_params['keystone_tenant'] = cluster_params['keystone_tenant']
                provision_params['analytics_data_ttl'] = cluster_params['analytics_data_ttl']
                provision_params['phy_interface'] = server_params['interface_name']
                if 'gateway' in server and server['gateway']:
                    provision_params['server_gway'] = server['gateway']
                elif 'gateway' in cluster_params and cluster_params['gateway']:
                    provision_params['server_gway'] = cluster_params['gateway']
                else:
                    provision_params['server_gway'] = ''
                if 'rsyslog_params' in cluster_params:
                    cluster_params['rsyslog_params'] = cluster_params['rsyslog_params'].encode("ascii")
                    cluster_params['rsyslog_params'] = ast.literal_eval(cluster_params['rsyslog_params'])
                    provision_params['rsyslog_params'] = cluster_params['rsyslog_params']
                if 'kernel_upgrade' in server_params and server_params['kernel_upgrade']:
                    provision_params['kernel_upgrade'] = server_params['kernel_upgrade']
                elif 'kernel_upgrade' in cluster_params and cluster_params['kernel_upgrade']:
                    provision_params['kernel_upgrade'] = cluster_params['kernel_upgrade']
                else:
                    provision_params['kernel_upgrade'] = DEFAULT_KERNEL_UPGRADE

                if 'kernel_version' in server_params and server_params['kernel_version']:
                    provision_params['kernel_version'] = server_params['kernel_version']
                elif 'kernel_version' in cluster_params and cluster_params['kernel_version']:
                    provision_params['kernel_version'] = cluster_params['kernel_version']
                else:
                    provision_params['kernel_version'] = DEFAULT_KERNEL_VERSION


                provision_params['haproxy'] = cluster_params['haproxy']

                if 'setup_interface' in server_params.keys():
                    provision_params['setup_interface'] = \
                                                    server_params['setup_interface']
                else:
                     provision_params['setup_interface'] = "No"

                provision_params['haproxy'] = cluster_params['haproxy']
                if 'execute_script' in server_params.keys():
		            provision_params['execute_script'] = server_params['execute_script']
                else:
                    provision_params['execute_script'] = ""

                if 'esx_server' in server_params.keys():
                    provision_params['esx_uplink_nic'] = server_params['esx_uplink_nic']
                    provision_params['esx_fab_vswitch'] = server_params['esx_fab_vswitch']
                    provision_params['esx_vm_vswitch'] = server_params['esx_vm_vswitch']
                    provision_params['esx_fab_port_group'] = server_params['esx_fab_port_group']
                    provision_params['esx_vm_port_group'] = server_params['esx_vm_port_group']
                    provision_params['vm_deb'] = server_params['vm_deb'] if server_params.has_key('vm_deb') else ""
                    provision_params['esx_vmdk'] = server_params['esx_vmdk']
                    esx_servers = self._serverDb.get_server(
                        {'id' : server_params['esx_server']},
                        detail=True)
                    esx_server = esx_servers[0]
                    provision_params['esx_ip'] = esx_server['ip_address']
                    provision_params['esx_username'] = "root"
                    provision_params['esx_password'] = esx_server['password']
                    provision_params['esx_server'] = esx_server
                    provision_params['server_mac'] = server['mac_address']
                    provision_params['password'] = server['password']
                    if 'datastore' in server_params.keys():
                        provision_params['datastore'] = server_params['datastore']
                    else:
                        provision_params['datastore'] = "/vmfs/volumes/datastore1"
                else:
                   provision_params['esx_uplink_nic'] = ""
                   provision_params['esx_fab_vswitch'] = ""
                   provision_params['esx_vm_vswitch'] = ""
                   provision_params['esx_fab_port_group'] = ""
                   provision_params['esx_vm_port_group'] = ""
                   provision_params['esx_vmdk'] = ""
                   provision_params['esx_ip'] = ""
                   provision_params['esx_username'] = ""
                   provision_params['esx_password'] = ""

                if interface_created:
                    provision_params['setup_interface'] = "No"

                if 'region_name' in cluster_params.keys():
                    provision_params['region_name'] = cluster_params['region_name']
                else:
                    provision_params['region_name'] = "RegionOne"
                if 'execute_script' in server_params.keys():
                    provision_params['execute_script'] = server_params['execute_script']
                else:
                    provision_params['execute_script'] = ""
                if 'external_bgp' in cluster_params.keys():
                    provision_params['external_bgp'] = cluster_params['external_bgp']
                else:
                    provision_params['external_bgp'] = ""

                # Storage role params

                if 'subnet_mask' in server and server['subnet_mask']:
                    subnet_mask = server['subnet_mask']
                elif 'subnet_mask' in cluster_params and cluster_params['subnet_mask']:
                    subnet_mask = cluster_params['subnet_mask']

		if len(role_servers['storage-compute']):
		    msg = "Storage is enabled"
		    storage_status = '1'
		else:
		    msg = "Storage is disabled"
		    storage_status = '0'
                self._smgr_log.log(self._smgr_log.DEBUG, msg)

                # Calculate the total number of disks in the cluster
                total_osd = int(0)
                num_storage_hosts = int(0)
                live_migration = "disable"
                live_migration_host = ""
                live_migration_storage_scope = "local"
                for role_server in role_servers['storage-compute']:
                    server_params_compute = eval(role_server['parameters'])
                    if 'disks' in server_params_compute and len(server_params_compute['disks']) > 0:
                        total_osd += len(server_params_compute['disks'])
                        num_storage_hosts += 1
                    else:
                        pass
    
                for role_server in role_servers['storage-master']:
                    server_params_master = eval(role_server['parameters'])
                    if 'live_migration' in server_params_master and server_params_master['live_migration'] == "enable":
                      if 'live_migration_nfs_vm_host' in server_params_master and len(server_params_master['live_migration_nfs_vm_host']) > 0 :
                          live_migration = "enable"
                          live_migration_host = server_params_master['live_migration_nfs_vm_host']
                      else:
                          live_migration = "disable"
                          live_migration_host = ""

                      if 'live_migration_storage_scope' in server_params_master :
                          live_migration_storage_scope = server_params_master['live_migration_storage_scope']
		      else:
			  pass

                    else:
                        pass

		if live_migration_storage_scope == "local" or live_migration_storage_scope == "global":
		    pass
		else:
                    msg = "Invalid Live Migration Storage Scope (local/global are valid)"
                    raise ServerMgrException(msg)

		    
		provision_params['live_migration_storage_scope'] = live_migration_storage_scope
		provision_params['contrail-storage-enabled'] = storage_status
		provision_params['subnet-mask'] = subnet_mask
                provision_params['host_roles'] = eval(server['roles'])
                provision_params['storage_num_osd'] = total_osd
                provision_params['storage_fsid'] = cluster_params['storage_fsid']
                provision_params['storage_virsh_uuid'] = cluster_params['storage_virsh_uuid']
                provision_params['num_storage_hosts'] = num_storage_hosts
                provision_params['live_migration_host'] = live_migration_host
                if len(role_servers['storage-compute']):
                    if len(role_servers['storage-master']) == 0:
                        msg = "Storage nodes can only be provisioned when there is also a Storage-Manager node"
                        raise ServerMgrException(msg)
                    if 'storage_mon_secret' in cluster_params.keys():
                        if len(cluster_params['storage_mon_secret']) == 40:
                            provision_params['storage_mon_secret'] = cluster_params['storage_mon_secret']
                        else:
                            msg = "Storage Monitor Secret Key is the wrong length"
                            raise ServerMgrException(msg)
                    else:
                        provision_params['storage_mon_secret'] = ""
                    if 'osd_bootstrap_key' in cluster_params.keys():
                        if len(cluster_params['osd_bootstrap_key']) == 40:
                            provision_params['osd_bootstrap_key'] = cluster_params['osd_bootstrap_key']
                        else:
                            msg = "OSD Bootstrap Key is the wrong length"
                            raise ServerMgrException(msg)
                    else:
                        provision_params['osd_bootstrap_key'] = ""
                    if 'admin_key' in cluster_params.keys():
                        if len(cluster_params['admin_key']) == 40:
                            provision_params['admin_key'] = cluster_params['admin_key']
                        else:
                            msg = "Admin Key is the wrong length"
                            raise ServerMgrException(msg)
                    else:
                        provision_params['admin_key'] = ""
                    if 'disks' in server_params and total_osd > 0:
                        provision_params['storage_server_disks'] = []
                        provision_params['storage_server_disks'].extend(server_params['disks'])

                storage_mon_host_ip_set = set()
                for x in role_servers['storage-compute']:
                    storage_mon_host_ip_set.add(self._smgr_puppet.get_control_ip(provision_params, x["ip_address"]).strip('"'))
                for x in role_servers['storage-master']:
                    storage_mon_host_ip_set.add(self._smgr_puppet.get_control_ip(provision_params, x["ip_address"]).strip('"'))

                provision_params['storage_monitor_hosts'] = list(storage_mon_host_ip_set)

                # Multiple Repo support
                if 'storage_repo_id' in server_params.keys():
                    images = self.get_image()
                    image_ids = dict()
                    for image in images['image']:
                        match_dict = dict()
                        match_dict["id"] = image['id']
                        cur_image = self._serverDb.get_image(match_dict, None, detail=True)
                        if cur_image is not None:
                            image_ids[image['id']] = cur_image[0]['type']
                        else:
                            msg = "No images found"
                            self.log_and_raise_exception(msg)
                    if server_params['storage_repo_id'] in image_ids:
                        if image_ids[server_params['storage_repo_id']] == 'contrail-storage-ubuntu-package':
                            provision_params['storage_repo_id'] = server_params['storage_repo_id']
                        else:
                            msg = "Storage repo id specified doesn't match a contrail storage package"
                            raise ServerMgrException(msg)
                    else:
                        msg = "Storage repo id specified doesn't match any of the image ids"
                        raise ServerMgrException(msg)
                else:
                    provision_params['storage_repo_id'] = ""

                # Storage manager restrictions
                if len(role_servers['storage-master']):
                    if len(role_servers['storage-master']) > 1:
                        msg = "There can only be only one node with the role 'storage-master'"
                        raise ServerMgrException(msg)
                    elif len(role_servers['storage-compute']) == 0:
                        msg = "Storage manager node needs Storage nodes to also be provisioned"
                        raise ServerMgrException(msg)
                    else:
                        pass

                self._do_provision_server(provision_params)
                server_status = {}
                server_status['id'] = server['id']
                server_status['package_id'] = package_image_id
                provision_status['server'].append(server_status)
                #end of for
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
        provision_status['return_code'] = "0"
        provision_status['return_message'] = "server(s) provision issued"
        return provision_status
    # end provision_server

    # TBD
    def cleanup(self):
        print "called cleanup"
    # end cleanup

    # Private Methods
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
            'listen_ip_addr'             : _WEB_HOST,
            'listen_port'                : _WEB_PORT,
            'database_name'              : _DEF_CFG_DB,
            'server_manager_base_dir'    : _DEF_SMGR_BASE_DIR,
            'html_root_dir'              : _DEF_HTML_ROOT_DIR,
            'cobbler_ip_address'         : _DEF_COBBLER_IP,
            'cobbler_port'               : _DEF_COBBLER_PORT,
            'cobbler_username'           : _DEF_COBBLER_USERNAME,
            'cobbler_password'           : _DEF_COBBLER_PASSWORD,
            'ipmi_username'             : _DEF_IPMI_USERNAME,
            'ipmi_password'             : _DEF_IPMI_PASSWORD,
            'ipmi_type'                 : _DEF_IPMI_TYPE,
            'puppet_dir'                 : _DEF_PUPPET_DIR
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        try:
            for key in dict(config.items("SERVER-MANAGER")).keys():
                if key in serverMgrCfg.keys():
                    serverMgrCfg[key] = dict(config.items("SERVER-MANAGER"))[key]
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Configuration set for invalid parameter: %s" % key)

            self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form config file %s" % serverMgrCfg)
        except ConfigParser.NoSectionError:
            msg = "Server Manager doesn't have a configuration set."
            self.log_and_raise_exception(msg)

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
        self._parse_monitoring_args(args_str, args)
        self._args = parser.parse_args(remaining_argv)
        self._args.config_file = args.config_file
    # end _parse_args

    def _parse_monitoring_args(self, args_str, args):
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        self._monitoring_args = None
        try:
            if dict(config.items("MONITORING")).keys():
                # Handle parsing for monitoring
                monitoring_args = self._monitoring_base_plugin_obj.parse_args(args_str)
                if monitoring_args:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Monitoring arguments read from config.")
                    self._monitoring_args = monitoring_args
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
                    self._monitoring_args = None
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
                self._monitoring_args = None
        except ConfigParser.NoSectionError:
            self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
            self._monitoring_args = None
        if self._monitoring_args:
            try:
                if self._monitoring_args.monitoring_plugin:
                    module_components = str(self._monitoring_args.monitoring_plugin).split('.')
                    monitoring_module = __import__(str(module_components[0]))
                    monitoring_class = getattr(monitoring_module, module_components[1])
                    if self._monitoring_args.collectors:
                        self._dev_env_monitoring_obj = monitoring_class(1, self._monitoring_args.monitoring_frequency,
                                                                        self._monitoring_args.collectors)
                        self._dev_env_monitoring_obj.sandesh_init(self._monitoring_args.collectors)
                        self._config_set = True
                else:
                    self._smgr_log.log(self._smgr_log.ERROR, "Analytics IP and Monitoring API misconfigured, monitoring aborted")
                    self._dev_env_monitoring_obj = self._monitoring_base_plugin_obj
            except ImportError:
                    self._smgr_log.log(self._smgr_log.ERROR, "Configured modules are missing. Server Manager will quit now.")
                    raise ImportError
        else:
            self._dev_env_monitoring_obj = self._monitoring_base_plugin_obj
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

    # Private method to reboot the server after cobbler config is setup.
    # If power address is provided and power management system is configured
    # with cobbler, that is used to power cycle the server, else if SSH
    # connectivity is available to the server, that is used to login and reboot
    # the server.
    def _power_cycle_servers(
        self, reboot_server_list, net_boot=False):
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
                    self._smgr_cobbler.enable_system_netboot(
                        server['id'])
                    cmd = "puppet cert clean %s.%s" % (
                        server['id'], server['domain'])
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))
                    # Remove manifest file for this server
                    cmd = "rm -f /etc/puppet/manifests/%s.%s.pp" %(
                        server['id'], server['domain'])
                    ret_code = subprocess.call(cmd, shell=True)
                    self._smgr_log.log(
                        self._smgr_log.DEBUG,
                        cmd + "; ret_code = %d" %(ret_code))
                    # Remove entry for that server from site.pp
                    cmd = "sed -i \"/%s.%s.pp/d\" /etc/puppet/manifests/site.pp" %(
                        server['id'], server['domain'])
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
                    client.connect(server_ip, username='root', password=passwd)
                    stdin, stdout, stderr = client.exec_command('reboot')
                # end else
                # Update Server table to update time.
                update = {'id': server['id'],
                          'status' : 'restart_issued',
                          'last_update': strftime(
                             "%Y-%m-%d %H:%M:%S", gmtime())}
                self._serverDb.modify_server(update)
                success_list.append(server['id'])
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
        self._smgr_cobbler.sync()
        if power_reboot_list:
            try:
                self._smgr_cobbler.reboot_system(
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
                           package_image_id, reimage_parameters):
        try:
            # Profile name is based on image name.
            profile_name = base_image['id']
            # Setup system information in cobbler
            self._smgr_cobbler.create_system(
                reimage_parameters['server_id'], profile_name, package_image_id,
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
                reimage_parameters.get('partition', ''))

            # Sync the above information
            #self._smgr_cobbler.sync()

            # Update Server table to add image name
            update = {
                'mac_address': reimage_parameters['server_mac'],
                'reimaged_id': base_image['id'],
                'provisioned_id': package_image_id}
            self._serverDb.modify_server(update)

            # TBD Need to add a way to confirm that server came up with
            # upgrade OS and also add this info to the DB in server table
            # (version upgraded to and timestamp). Possibly start a process
            # to ping the server and when up, ssh and get contrail version.
        except Exception as e:
            raise e
    # end _do_reimage_server

    # Internal private call to provision server. This is called by REST API
    # provision_server and provision_cluster
    def _do_provision_server(self, provision_parameters):
        try:
            # Now call puppet to provision the server.
            self._smgr_puppet.provision_server(
                provision_parameters)

            # Update Server table with provisioned id
            update = {'id': provision_parameters['server_id'],
                      'provisioned_id': provision_parameters['package_image_id']}
            self._serverDb.modify_server(update)

            # Now kickstart agent run on the target
            host_name = provision_parameters['server_id'] + "." + \
                provision_parameters.get('domain', '')
            rc = subprocess.check_call(
                ["puppet", "kick", "--host", host_name])
            # Log, return error if return code is non-null - TBD Abhay
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
        bottle.run(app=pipe_start_app, host=server_ip, port=server_port)
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

