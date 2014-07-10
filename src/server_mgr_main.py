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
from server_mgr_defaults import *
from server_mgr_db import ServerMgrDb as db
from server_mgr_cobbler import ServerMgrCobbler as ServerMgrCobbler
from server_mgr_puppet import ServerMgrPuppet as ServerMgrPuppet
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog
from server_mgr_exception import ServerMgrException as ServerMgrException
from send_mail import send_mail
import tempfile

bottle.BaseRequest.MEMFILE_MAX = 2 * 102400

_WEB_HOST = '127.0.0.1'
_WEB_PORT = 9001
_DEF_CFG_DB = 'vns_server_mgr.db'
_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'smgr_config.ini'
_DEF_HTML_ROOT_DIR = '/var/www/html/'
_DEF_COBBLER_IP = '127.0.0.1'
_DEF_COBBLER_PORT = None
_DEF_COBBLER_USER = 'cobbler'
_DEF_COBBLER_PASSWD = 'cobbler'
_DEF_POWER_USER = 'ADMIN'
_DEF_POWER_PASSWD = 'ADMIN'
_DEF_POWER_TOOL = 'ipmilan'
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

        if not args_str:
            args_str = sys.argv[1:]
        self._parse_args(args_str)

        # Connect to the cluster-servers database
        try:
            self._serverDb = db(
                self._args.smgr_base_dir+self._args.db_name)
        except:
            self._smgr_log.log(self._smgr_log.DEBUG,
                     "Error Connecting to Server Database %s"
                    % (self._args.smgr_base_dir+self._args.db_name))
            exit()

        # Create an instance of cobbler interface class and connect to it.
        try:
            self._smgr_cobbler = ServerMgrCobbler(self._args.smgr_base_dir,
                                                  self._args.cobbler_ip,
                                                  self._args.cobbler_port,
                                                  self._args.cobbler_user,
                                                  self._args.cobbler_passwd)
        except:
            print "Error connecting to cobbler"
            exit()

        # Create an instance of puppet interface class.
        try:
            # TBD - Puppet params to be added.
            self._smgr_puppet = ServerMgrPuppet(self._args.smgr_base_dir,
                                                self._args.puppet_dir)
        except:
            self._smgr_log.log(self._smgr_log.DEBUG, "Error creating instance of puppet class")
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

        self._base_url = "http://%s:%s" % (self._args.listen_ip_addr,
                                           self._args.listen_port)
        self._pipe_start_app = bottle.app()

        # All bottle routes to be defined here...
        # REST calls for GET methods (Get Info about existing records)
        bottle.route('/all', 'GET', self.get_server_mgr_config)
        bottle.route('/cluster', 'GET', self.get_cluster)
        bottle.route('/vns', 'GET', self.get_vns)
        bottle.route('/server', 'GET', self.get_server)
        bottle.route('/image', 'GET', self.get_image)
        bottle.route('/status', 'GET', self.get_status)

        # REST calls for PUT methods (Create New Records)
        bottle.route('/all', 'PUT', self.create_server_mgr_config)
        bottle.route('/image/upload', 'PUT', self.upload_image)
        bottle.route('/status', 'PUT', self.put_status)


        #smgr_add
        bottle.route('/cluster', 'PUT', self.put_cluster)
        bottle.route('/server', 'PUT', self.put_server)
        bottle.route('/image', 'PUT', self.put_image)
        bottle.route('/vns', 'PUT', self.put_vns)

        # REST calls for DELETE methods (Remove records)
        bottle.route('/cluster', 'DELETE', self.delete_cluster)
        bottle.route('/vns', 'DELETE', self.delete_vns)
        bottle.route('/server', 'DELETE', self.delete_server)
        bottle.route('/image', 'DELETE', self.delete_image)

        # REST calls for POST methods
        bottle.route('/cluster', 'POST', self.modify_cluster)
        bottle.route('/vns', 'POST', self.modify_vns)
        bottle.route('/server', 'POST', self.modify_server)
        bottle.route('/image', 'POST', self.modify_image)
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
    # clusters, VNSs & all servers is returned.
    def get_server_mgr_config(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server_mgr_config")
        config = {}
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Check if request arguments has detail parameter
            detail = ("detail" in query_args)
            config['cluster'] = self._serverDb.get_cluster(detail=detail)
            config['vns'] = self._serverDb.get_vns(detail=detail)
            config['server'] = self._serverDb.get_server(detail=detail)
            config['image'] = self._serverDb.get_image(detail=detail)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_ALL,
                                     False)
            self.log_trace()
            abort(404, repr(e))

        self._smgr_trans_log.log(bottle.request, self._smgr_trans_log.GET_SMGR_CFG_ALL)
        return config
    # end get_server_mgr_config

    # REST API call to get sever manager config - configuration of all
    # clusters, with all servers and roles is returned. This call
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
                detail = ret_data["detail"]

            entity = self._serverDb.get_cluster(match_value, detail)
        except ServerMgrException as e:
            abort(404, e.value)
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_CLUSTER, False)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_CLUSTER, False)
            self.log_trace()
            abort(404, repr(e))

        self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.GET_SMGR_CFG_CLUSTER)
        return {"cluster": entity}
    # end get_cluster

    # REST API call to get sever manager config - configuration of all
    # VNSs, with all servers and roles is returned. This call
    # provides all the configuration as in get_server_mgr_config() call
    # above. This call additionally provides a way of getting all the
    # configuration for a particular vns.
    def get_vns(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "get_vns")
        try:
            ret_data = self.validate_smgr_request("VNS", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                detail = ret_data["detail"]
                entity = self._serverDb.get_vns(match_value, detail)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_VNS,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_VNS,
                                     False)
            self.log_trace()
            abort(404, repr(e))
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_VNS,
                                     False)
        self._smgr_trans_log.log(bottle.request,
                                 self._smgr_trans_log.GET_SMGR_CFG_VNS)
        return {"vns": entity}
    # end get_vns

    def validate_smgr_entity(self, type, entity):
        obj_list = entity.get(type, None)
        if obj_list is None:
           msg = "%s data not available in JSON" % \
                        type
           self._smgr_log.log(self._smgr_log.ERROR,
                        msg )
           raise ServerMgrException(msg)

    def validate_smgr_get(self, validation_data, request, data=None):
        ret_data = {}
        ret_data['status'] = 1
        query_args = parse_qs(urlparse(request.url).query,
                                    keep_blank_values=True)
        detail = ("detail" in query_args)
        query_args.pop("detail", None)

        if len(query_args) == 0:
            match_key = None
            match_value = None
            ret_data["status"] = 0
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_value
            ret_data["detail"] = detail
        elif len(query_args) == 1:
            match_key, match_value = query_args.popitem()
            match_keys_str = validation_data['match_keys']
            match_keys = eval(match_keys_str)
            if (match_key not in match_keys):
                raise ServerMgrException("Match Key not present")
            if match_value == None or match_value[0] == '':
                raise ServerMgrException("Match Value not Specified")
            ret_data["status"] = 0
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_value[0]
            ret_data["detail"] = detail
        return ret_data

    def validate_smgr_put(self, validation_data, request, data=None,
                                                        modify = False):
        ret_data = {}
        ret_data['status'] = 1
        try:
            json_data = json.load(request.body)
        except ValueError as e :
            msg = "Invalid JSON data : %s " % e
            self._smgr_log.log(self._smgr_log.ERROR,
                               msg )
            raise ServerMgrException(msg)
        entity = request.json
        #check if json data is present
        if (not entity):
            msg = "No JSON data specified"
            self._smgr_log.log(self._smgr_log.ERROR,
                               msg )
            raise ServerMgrException(msg)
        #Check if object is present
        obj_name = validation_data['obj_name']
        objs = entity.get(obj_name)
        if len(objs) == 0:
            msg = ("No %s data specified") % \
                    (obj_name)
            self._smgr_log.log(self._smgr_log.ERROR,
            msg)
            raise ServerMgrException(msg)
        #check if primary_keys are present
        primary_keys_str = validation_data['primary_keys']
        primary_keys = eval(primary_keys_str)
        for primary_key in primary_keys:
            if primary_key not in data:
                msg =  ("Primary Key %s not present") % (primary_key)
                self._smgr_log.log(self._smgr_log.ERROR,
                msg)
                raise ServerMgrException(msg)
        #Parse for the JSON to find allowable fields
        remove_list = []
        for data_item_key, data_item_value in data.iteritems():
            #If json data name is not present in list of
            #allowable fields silently ignore them.
            if data_item_key == obj_name + "_params" and modify == False:
                object_params = data_item_value
                default_object_params = eval(validation_data[obj_name +'_params'])
                for key,value in default_object_params.iteritems():
                    if key not in object_params:
                        msg = "Default Object param added is %s:%s" % \
                                (key, value)
                        self._smgr_log.log(self._smgr_log.INFO,
                                   msg)
                        object_params[key] = value
                """

                for k,v in object_params.iteritems():
                    if k in default_object_params and v == ''
                    if v == '""':
                        object_params[k] = ''
                """
                data[data_item_key] = object_params
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
                data[k] = v

            """
            if k not in data:
                msg =  ("Field %s not present") % (k)
                self._smgr_log.log(self._smgr_log.ERROR,
                                   msg)
                raise ServerMgrException(msg)
            if v != '' and data[k] not in v:
                msg =  ("Value %s is not an option") % (data[k])
                self._smgr_log.log(self._smgr_log.ERROR,
                                   msg)
                raise ServerMgrException(msg)
            """
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
        if len(query_args) == 0:
            msg = "No selection criteria specified"
            self._smgr_log.log(self._smgr_log.ERROR,
                     msg)
            raise ServerMgrException(msg)
        elif len(query_args) == 1:
            match_key, match_value = query_args.popitem()
            # check that match key is a valid one
            if (match_key not in match_keys):
                msg = "Invalid match key %s" % (match_key)
                raise ServerMgrException(msg)
            elif match_value[0] == '':
                raise ServerMgrException("Match Value not Specified")
            ret_data["status"] = 0
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_value[0]
            ret_data["force"] = force
        return ret_data

    #TODO Need to reomve
    def validate_smgr_modify(self, validation_data, request, data = None):

        ret_data = {}
        ret_data['status'] = 1

        entity = request.json
        if (not entity):
            self._smgr_log.log(self._smgr_log.ERROR,
                     "No JSON data specified")
            abort(404, 'No JSON data specified')
        #check if match_keys are present
        match_keys_str = validation_data['match_keys']
        match_keys = eval(match_keys_str)
        for match_key in match_keys:
            if match_key not in data:
                msg =  ("Match Key %s not present") % (match_key)
                self._smgr_log.log(self._smgr_log.ERROR,
                     msg)
                raise ServerMgrException(msg)
        #TODO Handle replace
        return ret_data

    def _validate_roles(self, match_key, match_value):
        if match_key == 'server_id':
            server = self._serverDb.get_server(
                        "server_id", match_value, detail=True)
            if server and server[0]:
                vns_id = server [0] ['vns_id']
                if vns_id is None:
                    msg =  ("No VNS associated with server %s") % (match_value)
                    raise ServerMgrException(msg)
            else:
                msg =  ("No server present for %s") % (match_value)
                raise ServerMgrException(msg)
        elif match_key == 'vns_id':
            vns_id = match_value

        servers = self._serverDb.get_server(
                            'vns_id', vns_id, detail=True)
        role_list = [
                "database", "openstack", "config",
                "control", "collector", "webui", "compute", "esx"]
        roles_set = set(role_list)

        vns_role_list = []
        for server in servers:
            vns_role_list.extend(eval(server['roles']))

        vns_unique_roles = set(vns_role_list)

        missing_roles = roles_set.difference(vns_unique_roles)
        if len(missing_roles):
            msg = "Mandatory roles \"%s\" are not present" % \
            ", ".join(str(e) for e in missing_roles)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
            raise ServerMgrException(msg)

        unknown_roles = vns_unique_roles.difference(roles_set)
        if len(unknown_roles):
            msg = "Unknown Roles: %s" % \
            ", ".join(str(e) for e in unknown_roles)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
            raise ServerMgrException(msg)

        return 0

    def validate_smgr_provision(self, validation_data, request , data=None):

        ret_data = {}
        ret_data['status'] = 1

        entity = request.json
        package_image_id = entity.pop("package_image_id", None)
        if package_image_id is None:
            msg = "No contrail package specified for provisioning"
            raise ServerMgrException(msg)
        req_provision_params = entity.pop("provision_params", None)
        # if req_provision_params are specified, check contents for
        # validity, store the info in DB and proceed with the
        # provisioning step.
        if req_provision_params is not None:
            role_list = [
                "database", "openstack", "config",
                "control", "collector", "webui", "compute", "zookeeper"]
            roles = req_provision_params.get("roles", None)
            if roles is None:
                msg = "No provisioning roles specified"
                raise ServerMgrException(msg)
            if (type(roles) != type({})):
                msg = "Invalid roles definition"
                raise ServerMgrException(msg)
            prov_servers = {}
            for key, value in roles.iteritems():
                if key not in role_list:
                    msg = "invalid role %s in provision file" %(
                            key)
                    raise ServerMgrException(msg)
                if type(value) != type ([]):
                    msg = "role %s needs to have server list" %(
                        key)
                    raise ServerMgrException(msg)
                for server in value:
                    if server not in prov_servers:
                        prov_servers[server] = [key]
                    else:
                        prov_servers[server].append(key)
                # end for server
            # end for key
            vns_id = None
            servers = []
            for key in prov_servers:
                server = self._serverDb.get_server(
                    "server_id", key, detail=True)
                if server:
                    server = server[0]
                servers.append(server)
                if ((vns_id != None) and
                    (server['vns_id'] != vns_id)):
                    msg = "all servers must belong to same vns"
                    raise ServerMgrException(msg)
                vns_id = server['vns_id']
            # end for
            #Modify the roles
            for key, value in prov_servers.iteritems():
                new_server = {
                    'server_id' : key,
                    'roles' : value }
                self._serverDb.modify_server(new_server)
            # end for
            if len(servers) == 0:
                msg = "No servers found"
                raise ServerMgrException(msg)
            ret_data["status"] = 0
            ret_data["servers"] = servers
        else:
            if (len(entity) == 0):
                msg = "No servers specified"
                raise ServerMgrException(msg)
            elif len(entity) == 1:
                match_key, match_value = entity.popitem()
                # check that match key is a valid one
                if (match_key not in (
                    "server_id", "mac", "cluster_id",
                    "rack_id", "pod_id", "vns_id")):
                    msg = "Invalid Query arguments"
                    raise ServerMgrException(msg)
            else:
                msg = "No servers specified"
                raise ServerMgrException(msg)
            # end else
            servers = self._serverDb.get_server(
                match_key, match_value, detail=True)
            if len(servers) == 0:
                msg = "No servers found for %s" % \
                            (match_value)
                raise ServerMgrException(msg)

            self._validate_roles(match_key, match_value)
            ret_data["status"] = 0
            ret_data["servers"] = servers
            ret_data["package_image_id"] = package_image_id
        return ret_data

    def validate_smgr_reboot(self, validation_data, request , data=None):

        ret_data = {}
        ret_data['status'] = 1

        entity = request.json
        # Get parameter to check if netboot should be enabled.
        net_boot = entity.pop("net_boot", None)
        if ((not net_boot) or
            (net_boot not in ["y","Y","1"])):
            net_boot = False
        else:
            net_boot = True
        if len(entity) == 0:
            msg = "No servers specified"
            raise ServerMgrException(msg)
        elif len(entity) == 1:
            match_key, match_value = entity.popitem()
            # check that match key is a valid one
            if (match_key not in ("server_id", "mac", "cluster_id",
                                  "rack_id", "pod_id", "vns_id")):
                msg = "Invalid Query arguments"
                raise ServerMgrException(msg)
        else:
            msg = "Invalid Query arguments"
            raise ServerMgrException(msg)
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
        no_reboot = entity.pop("no_reboot", None)
        if ((no_reboot) and
            (no_reboot in ["y","Y","1"])):
            do_reboot = False

        # Get image version parameter
        base_image_id = entity.pop("base_image_id", None)
        if base_image_id is None:
            msg = "No base image id specified"
            raise ServerMgrException(msg)
        package_image_id = entity.pop("package_image_id", '')
        # Now process other parameters there should be only one more
        if (len(entity) == 0):
            msg = "No servers specified"
            raise ServerMgrException(msg)
        elif len(entity) == 1:
            match_key, match_value = entity.popitem()
            # check that match key is a valid one
            if (match_key not in ("server_id", "mac", "cluster_id",
                                  "rack_id", "pod_id", "vns_id")):
                msg = "Invalid Query arguments"
                raise ServerMgrException(msg)
        else:
            msg = "No servers specified"
            raise ServerMgrException(msg)
        ret_data['status'] = 0
        ret_data['match_key'] = match_key
        ret_data['match_value'] = match_value
        ret_data['base_image_id'] = base_image_id
        ret_data['package_image_id'] = package_image_id
        ret_data['do_reboot'] = do_reboot
        return ret_data
        # end else



    def validate_smgr_request(self, type, oper, request, data = None, modify =
                              False):
        ret_data = {}
        ret_data['status'] = 1

        ret_data = {}
        ret_data['status'] = 1
        if type == "SERVER":
            validation_data = server_fields
        elif type == "VNS":
            validation_data = vns_fields
        elif type == "CLUSTER":
            validation_data = cluster_fields
        elif type == "IMAGE":
            validation_data = image_fields
        else: 
            validation_data = None

        if oper == "GET":
            return self.validate_smgr_get(validation_data, request, data)
        elif oper == "PUT":
            return self.validate_smgr_put(validation_data, request, data, modify)
        elif oper == "DELETE":
            return self.validate_smgr_delete(validation_data, request, data)
        elif oper == "MODIFY":
            return self.validate_smgr_modify(validation_data, request, data)
        elif oper == "PROVISION":
            return self.validate_smgr_provision(validation_data, request, data)
        elif oper == "REBOOT":
            return self.validate_smgr_reboot(validation_data, request, data)
        elif oper == "REIMAGE":
            return self.validate_smgr_reimage(validation_data, request, data)


    # This call returns information about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server(self):
        ret_data = None
        self._smgr_log.log(self._smgr_log.DEBUG, "get_server")
        try:
            ret_data = self.validate_smgr_request("SERVER", "GET",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                detail = ret_data["detail"]
                servers = self._serverDb.get_server(match_key, match_value,
                                                    detail)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER, False)
            abort(404, repr(e))
        self._smgr_log.log(self._smgr_log.DEBUG, servers)
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_SERVER)
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
                detail = ret_data["detail"]
            images = self._serverDb.get_image(match_key, match_value,
                                              detail)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE, False)
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.GET_SMGR_CFG_IMAGE)
        return {"image": images}
    # end get_image

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
        servers = self._serverDb.get_server("server_id", server_id, True)
        if not servers:
            msg = "No server found with server_id " + server_id
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return
        server = servers[0]
        email_to = []
        if 'email' in server and server['email']:
            email_to = self.get_email_list(server['email'])
        else:
            # Get VNS entry to find configured e-mail
            if 'vns_id' in server and server['vns_id']:
                vns_id = server['vns_id']
                vns = self._serverDb.get_vns(vns_id, True)
                if vns and 'email' in vns[0] and vns[0]['email']:
                        email_to = self.get_email_list(vns[0]['email'])
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                       "vns or server doesn't configured for email")
                    return
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "server not associated with a vns")
                return
        send_mail(event, message, '', email_to, self._smgr_cobbler._cobbler_ip, '25')
        msg = "An email is sent to " + ','.join(email_to) + " with content " + message
        self._smgr_log.log(self._smgr_log.DEBUG, msg)
    # send_status_mail

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
                            "server_id", "mac", "cluster_id",
                            "rack_id", "pod_id", "vns_id", "ip")) or
                            (len(match_value) != 1)):
                self._smgr_log.log(self._smgr_log.ERROR, "Invalid Query data")
                abort(404, "Invalid Query arguments")
        if match_value[0] == '':
            abort(404, "Match value not present")
        server_id = match_value[0]
        body = bottle.request.body.read()
        server_data = {}
        server_data['server_id'] = server_id
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
            abort(404, repr(e))


    def get_status(self):
        server_id = bottle.request.query['server_id']
        servers = self._serverDb.get_status('server_id',
                        server_id, True)
        if servers:
            return servers[0]
        else:
            return None

    def put_cluster(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "put_cluster")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("cluster", entity)
            clusters = entity.get('cluster', None)
            for cluster in clusters:
                if self._serverDb.check_obj("cluster", "cluster_id",
                                            cluster['cluster_id'], False):
                    self.validate_smgr_request("CLUSTER", "PUT", bottle.request,
                                                cluster, True)
                    #nothing to do for now
                    return
                else:
                    self.validate_smgr_request("CLUSTER", "PUT", bottle.request,
                                                cluster)
                    self._serverDb.add_cluster(cluster)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER, False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER, False)
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_CLUSTER)
        return entity


    def put_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "add_image")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("image", entity)
            images = entity.get("image", None)
            for image in images:
                #use macros for obj type
                if self._serverDb.check_obj("image", "image_id",
                                            image['image_id'], False):
                    self.validate_smgr_request("IMAGE", "PUT", bottle.request,
                                                image, True)

                    self._serverDb.modify_image(image)
                else:
                    self.validate_smgr_request("IMAGE", "PUT", bottle.request,
                                                image)
                    image_id = image.get("image_id", None)
                    image_version = image.get("image_version", None)
                    # Get Image type
                    image_type = image.get("image_type", None)
                    image_path = image.get("image_path", None)
                    if (not image_id) or (not image_path):
                        self._smgr_log.log(self._smgr_log.ERROR,
                                     "image id or location not specified")
                        raise ServerMgrException("image id or location not specified")
                    if (image_type not in [
                            "centos", "fedora", "ubuntu",
                            "contrail-ubuntu-package", "contrail-centos-package"]):
                        self._smgr_log.log(self._smgr_log.ERROR,
                                    "image type not specified or invalid for image %s" %(
                                    image_id))
                        raise ServerMgrException("image type not specified or invalid for image %s" %(
                                image_id))
                    #TODO:remove this
                    '''
                    db_images = self._serverDb.get_image(
                        'image_id', image_id, False)
                    if db_images:
                        self._smgr_log.log(self._smgr_log.ERROR,
                            "image %s already exists" %(
                                image_id))
                        raise ServerMgrException(
                                "image %s already exists" %(
                                image_id))
                    '''
                    if not os.path.exists(image_path):
                        raise ServerMgrException("image not found at %s" % \
                                                (image_path))
                    extn = os.path.splitext(image_path)[1]
                    dest = self._args.smgr_base_dir + 'images/' + \
                        image_id + extn
                    subprocess.call(["cp", "-f", image_path, dest])
                    image_params = {}
                    if ((image_type == "contrail-centos-package") or
                        (image_type == "contrail-ubuntu-package")):
                        subprocess.call(
                            ["cp", "-f", dest,
                             self._args.html_root_dir + "contrail/images"])
                        puppet_manifest_version = self._create_repo(
                            image_id, image_type, image_version, dest)
                        image_params['puppet_manifest_version'] = \
                            puppet_manifest_version 
                    else:
                        self._add_image_to_cobbler(image_id, image_type,
                                                   image_version, dest)
                    image_data = {
                        'image_id': image_id,
                        'image_version': image_version,
                        'image_type': image_type,
                        'image_params' : image_params}
                    self._serverDb.add_image(image_data)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_IMAGE, False)
            abort(404, repr(e))

        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_IMAGE)
        return entity

    def put_vns(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "put_vns")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("vns", entity)
            vns = entity.get('vns', None)
            for cur_vns in vns:
                #use macros for obj type
                if self._serverDb.check_obj("vns", "vns_id",
                                            cur_vns['vns_id'], False):
                    #TODO Handle uuid here
                    self.validate_smgr_request("VNS", "PUT", bottle.request,
                                                cur_vns, True)
                    self._serverDb.modify_vns(cur_vns)
                else:
                    self.validate_smgr_request("VNS", "PUT", bottle.request,
                                                cur_vns)
                    str_uuid = str(uuid.uuid4())
                    cur_vns["vns_params"].update({"uuid":str_uuid})
                    self._smgr_log.log(self._smgr_log.INFO, "VNS Data %s" % cur_vns)
                    self._serverDb.add_vns(cur_vns)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_VNS,
                                False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_VNS,
                                False)
            abort(404, repr(e))

        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.PUT_SMGR_CFG_VNS)
        return entity

    def put_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "add_server")
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Server MAC or server_id not specified')
        try:
            self.validate_smgr_entity("server", entity)
            servers = entity.get("server", None)
            for server in servers:
                #commenting out now, untill i find a better way for this code
                # self.validate_smgr_request("SERVER", "PUT", bottle.request,
                #                                                       server)
                if self._serverDb.check_obj("server", "server_id",
                                            server['server_id'], False):
                    #TODO - Revisit this logic
                    # Do we need mac to be primary MAC
                    server_fields['primary_keys'] = "['server_id']"
                    self.validate_smgr_request("SERVER", "PUT", bottle.request,
                                                             server, True)
                    self._serverDb.modify_server(server)
                    server_fields['primary_keys'] = "['server_id', 'mac']"
                else:
                    self.validate_smgr_request("SERVER", "PUT", bottle.request,
                                                                        server)
                    self._serverDb.add_server(server)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.PUT_SMGR_CFG_SERVER, False)
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.PUT_SMGR_CFG_SERVER)
        return entity


    # API Call to add image file to server manager (file is copied at
    # <default_base_path>/images/filename.iso and distro, profile
    # created in cobbler. This is similar to function above (add_image),
    # but this call actually upload ISO image from client to the server.
    def upload_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "upload_image")
        image_id = bottle.request.forms.image_id
        image_version = bottle.request.forms.image_version
        image_type = bottle.request.forms.image_type
        if (image_type not in [
                "centos", "fedora", "ubuntu",
                "contrail-ubuntu-package", "contrail-centos-package"]):
            abort(404, "image type not specified or invalid")
        file_obj = bottle.request.files.file
        file_name = file_obj.filename
        db_images = self._serverDb.get_image(
            'image_id', image_id, False)
        if db_images:
            abort(
                404,
                "image %s already exists" %(
                    image_id))
        extn = os.path.splitext(file_name)[1]
        dest = self._args.smgr_base_dir + 'images/' + \
            image_id + extn
        try:
            if file_obj.file:
                with open(dest, 'w') as open_file:
                    open_file.write(file_obj.file.read())
            image_params = {}
            if ((image_type == "contrail-centos-package") or
                (image_type == "contrail-ubuntu-package")):
                subprocess.call(
                    ["cp", "-f", dest,
                     self._args.html_root_dir + "contrail/images"])
                puppet_manifest_version = self._create_repo(
                    image_id, image_type, image_version, dest)
                image_params['puppet_manifest_version'] = \
                    puppet_manifest_version 
            else:
                self._add_image_to_cobbler(image_id, image_type,
                                           image_version, dest)
            image_data = {
                'image_id': image_id,
                'image_version': image_version,
                'image_type': image_type,
                'image_params' : image_params}
            self._serverDb.add_image(image_data)
        except Exception as e:
            self.log_trace()
            abort(404, repr(e))
    # End of upload_image

    # The below function takes the tgz path for puppet modules in the repo
    # being added, checks if that version of modules is already added to
    # puppet and adds it if not already added.
    def _add_puppet_modules(self, puppet_modules_tgz):
        tmpdirname = tempfile.mkdtemp()
        try:
            # change dir to the temp dir created
            cwd = os.getcwd()
            os.chdir(tmpdirname)
            # Copy the tgz to tempdir
            cmd = ("cp -f %s ." %(puppet_modules_tgz))
            subprocess.call(cmd, shell=True)
            # untar the puppet modules tgz file
            cmd = ("tar xvzf contrail-puppet-manifest.tgz > /dev/null")
            subprocess.call(cmd, shell=True)
            # Extract contents of version file.
            with open('version','r') as f:
                version = f.read().splitlines()[0]
            # Create modules directory if it does not exist.
            target_dir = "/etc/puppet/modules/contrail_" + version
            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            # This contrail puppet modules version does not exist. Add it.
            cmd = ("cp -rf ./contrail/* " + target_dir)
            subprocess.call(cmd, shell=True)
            # Replace the class names in .pp files to have the version number
            # of this contrail modules.
            filelist = target_dir + "/manifests/*.pp"
            cmd = ("sed -i \"s/__\$version__/contrail_%s/g\" %s" %(
                    version, filelist))
            subprocess.call(cmd, shell=True)
            os.chdir(cwd)
            return version
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
            subprocess.call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.call(cmd, shell=True)
            # Extract .tgz of contrail puppet manifest files 
            cmd = (
                "rpm2cpio %s | cpio -ivd ./opt/contrail/puppet/"
                "contrail-puppet-manifest.tgz > /dev/null" %(dest))
            subprocess.call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            puppet_modules_tgz_path = mirror + \
                "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version = self._add_puppet_modules(
                puppet_modules_tgz_path)
            # Extract .tgz of other packages from the repo
            cmd = (
                "rpm2cpio %s | cpio -ivd ./opt/contrail/contrail_packages/"
                "contrail_rpms.tgz > /dev/null" %(dest))
            subprocess.call(cmd, shell=True)
            cmd = ("mv ./opt/contrail/contrail_packages/contrail_rpms.tgz .")
            subprocess.call(cmd, shell=True)
            cmd = ("rm -rf opt")
            subprocess.call(cmd, shell=True)
            # untar tgz to get all packages
            cmd = ("tar xvzf contrail_rpms.tgz > /dev/null")
            subprocess.call(cmd, shell=True)
            # remove the tgz file itself, not needed any more
            cmd = ("rm -f contrail_rpms.tgz")
            subprocess.call(cmd, shell=True)
            # build repo using createrepo
            cmd = ("createrepo . > /dev/null")
            subprocess.call(cmd, shell=True)
            # change directory back to original
            os.chdir(cwd)
            # cobbler add repo
            self._smgr_cobbler.create_repo(
                image_id, mirror)
            return puppet_manifest_version
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
            subprocess.call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # add wrapper package itself to the repo
            cmd = "cp -f %s %s" %(
                dest, mirror)
            subprocess.call(cmd, shell=True)
            # Extract .tgz of other packages from the repo
            cmd = (
                "dpkg -x %s . > /dev/null" %(dest))
            subprocess.call(cmd, shell=True)
            # Handle the puppet manifests in this package.
            puppet_modules_tgz_path = mirror + \
                "/opt/contrail/puppet/contrail-puppet-manifest.tgz"
            puppet_manifest_version = self._add_puppet_modules(
                puppet_modules_tgz_path)
            cmd = ("mv ./opt/contrail/contrail_packages/contrail_debs.tgz .")
            subprocess.call(cmd, shell=True)
            cmd = ("rm -rf opt")
            subprocess.call(cmd, shell=True)
            # untar tgz to get all packages
            cmd = ("tar xvzf contrail_debs.tgz > /dev/null")
            subprocess.call(cmd, shell=True)
            # remove the tgz file itself, not needed any more
            cmd = ("rm -f contrail_debs.tgz")
            subprocess.call(cmd, shell=True)
            # build repo using createrepo
            cmd = (
                "dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz")
            subprocess.call(cmd, shell=True)
            # change directory back to original
            os.chdir(cwd)
            # cobbler add repo
            # TBD - This is working for "centos" only at the moment,
            # will need to revisit and make it work for ubuntu - Abhay
            # self._smgr_cobbler.create_repo(
            #     image_id, mirror)
            return puppet_manifest_version
        except Exception as e:
            raise(e)
    # end _create_deb_repo

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
                              image_version, dest):
        # Mount the ISO
        distro_name = image_id
        copy_path = self._args.html_root_dir + \
            'contrail/images/' + distro_name

        try:
            if ((image_type == "fedora") or (image_type == "centos")):
                kernel_file = "/isolinux/vmlinuz"
                initrd_file = "/isolinux/initrd.img"
                ks_file = self._args.html_root_dir + \
                    "kickstarts/contrail-centos.ks"
                kernel_options = ''
                ks_meta = ''
            elif ((image_type == "esxi5.1") or
                  (image_type == "esxi5.5")):
                kernel_file = "/mboot.c32"
                initrd_file = "/imgpayld.tgz"
                ks_file = self._args.html_root_dir + \
                    "kickstarts/contrail-esxi.ks"
                kernel_options = ''
                ks_meta = 'ks_file=%s' %(ks_file)
            elif (image_type == "ubuntu"):
                kernel_file = "/install/netboot/ubuntu-installer/amd64/linux"
                initrd_file = (
                    "/install/netboot/ubuntu-installer/amd64/initrd.gz")
                ks_file = self._args.html_root_dir + \
                    "kickstarts/contrail-ubuntu.seed"
                kernel_options = (
                    "lang=english console-setup/layoutcode=us locale=en_US "
                    "auto=true console-setup/ask_detect=false "
                    "priority=critical interface=auto "
                    "console-keymaps-at/keymap=us "
                    "ks=http://%s/kickstarts/contrail-ubuntu.ks ") % (
                    self._args.listen_ip_addr)
                ks_meta = ''
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "Invalid image type")
                abort(404, "invalid image type")
            self._mount_and_copy_iso(dest, copy_path, distro_name,
                                     kernel_file, initrd_file)
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
        except Exception as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error adding image to cobbler %s" % e.value)
            abort(404, repr(e))
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

            self._serverDb.delete_cluster(match_value)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Error while deleting cluster %s" % (repr(e)))
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
            self._smgr_trans_log.DELETE_SMGR_CFG_CLUSTER)
        return "Cluster deleted"
    # end delete_cluster

    # API call to delete a vns from server manager config. Along with
    # vns, all servers in that vns and associated roles are also
    # deleted.
    def delete_vns(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_vns")
        try:
            ret_data = self.validate_smgr_request("VNS", "DELETE",
                                                         bottle.request)
            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
                force = ret_data["force"]
                self._serverDb.delete_vns(match_value, force)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_VNS,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_VNS,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Error while deleting vns %s" % (repr(e)))
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_VNS)
        return "VNS deleted"
    # end delete_vns

    # API call to delete a server from the configuration.
    def delete_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_server")
        try:
            ret_data = self.validate_smgr_request("SERVER", "DELETE",
                                                         bottle.request)

            if ret_data["status"] == 0:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]

            servers = self._serverDb.get_server(match_key, match_value, False)
            '''
            if not servers:
                msg = "No Server found for match key %s" % \
                        (match_key)
                self._smgr_log.log(self._smgr_log.ERROR,
                        msg )
                raise ServerMgrException(msg)
            '''
            self._serverDb.delete_server(match_key, match_value)
            # delete the system entries from cobbler
            for server in servers:
                self._smgr_cobbler.delete_system(server['server_id'])
            # Sync the above information
            self._smgr_cobbler.sync()
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                        "Unable to delete server, %s" % (repr(e)))
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_SERVER)
        return "Server deleted"
    # end delete_server

    # API Call to delete an image
    def delete_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "delete_image")
        try:
            image_id = bottle.request.query.image_id
            if not image_id:
                msg = "Image Id not specified"
                raise ServerMgrException(msg)
            images = self._serverDb.get_image("image_id", image_id, True)
            if not images:
                msg = "Image %s doesn't exist" % (image_id)
                raise ServerMgrException(msg)
                self._smgr_log.log(self._smgr_log.ERROR,
                        msg)
            image = images[0]
            if ((image['image_type'] == 'contrail-ubuntu-package') or
                (image['image_type'] == 'contrail-centos-package')):
                ext_dir = {
                    "contrail-ubuntu-package" : ".deb",
                    "contrail-centos-package": ".rpm" }
                # remove the file
                os.remove(self._args.smgr_base_dir + 'images/' +
                          image_id + ext_dir[image['image_type']])
                os.remove(self._args.html_root_dir +
                          'contrail/images/' +
                          image_id + ext_dir[image['image_type']])

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
                os.remove(self._args.smgr_base_dir + 'images/' +
                          image_id + '.iso')
                # Remove the tree copied under cobbler.
                dir_path = self._args.html_root_dir + \
                    'contrail/images/' + image_id
                shutil.rmtree(dir_path, True)
            # remove the entry from DB
            self._serverDb.delete_image(image_id)
        except ServerMgrException as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE,
                                     False)
            self._smgr_log.log(self._smgr_log.ERROR,
                "Unable to delete image, %s" % (repr(e)))
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                    self._smgr_trans_log.DELETE_SMGR_CFG_IMAGE)
        return "Server Deleted" 
    # End of delete_image

    # API to modify parameters for a server. User can modify IP, MAC, cluster
    # name (moving the server to a different cluster) , roles configured on
    # the server, or server parameters.
    def modify_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "modify_server")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("server", entity)
            servers = entity.get("server", None)
            for server in servers:
                self.validate_smgr_request("SERVER", "MODIFY", bottle.request,
                                                server)

            self._serverDb.modify_server(server)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                    self._smgr_trans_log.MODIFY_SMGR_CFG_SERVER,
                                    False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                    self._smgr_trans_log.MODIFY_SMGR_CFG_SERVER,
                                    False)
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                    self._smgr_trans_log.MODIFY_SMGR_CFG_SERVER)
        return entity
    # end modify_server

    # API to modify parameters for a VNS.
    def modify_vns(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "modify_vns")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("vns", entity)
            vns_list = entity.get("vns", None)
            for vns in vns_list:
                self.validate_smgr_request("VNS", "MODIFY", bottle.request,
                                                vns)
                self._serverDb.modify_vns(vns)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_VNS,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_VNS,
                                     False)

            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_VNS)
        return entity
    # end modify_vns

    # API to modify parameters for an image.
    def modify_image(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "modify_image")
        entity = bottle.request.json
        try:
            self.validate_smgr_entity("image", entity)
            images = entity.get("image", None)
            for image in images:
               self.validate_smgr_request("IMAGE", "MODIFY", bottle.request,
                                                image)
               self._serverDb.modify_image(image)
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_IMAGE,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_IMAGE,
                                     False)
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.MODIFY_SMGR_CFG_IMAGE)

        return entity
    # end modify_image

    # API to modify parameters for a cluster. Currently no-op, but code
    # will be added later to change other cluster parameters.
    def modify_cluster(self):
        return
    # end modify_cluster

    # API to create the server manager configuration DB from provided JSON
    # file.
    def create_server_mgr_config(self):
        entity = bottle.request.json
        if not entity:
            abort(404, "No JSON config file specified")
        # Validate the config for sematic correctness.
        self._validate_config(entity)
        # Store the initial configuration in our DB
        try:
            self._create_server_manager_config(entity)
        except Exception as e:
            self.log_trace()
            abort(404, repr(e))
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
            abort(404, repr(e))
        return entity
    # end process_dhcp_event

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
                do_reboot = ret_data['do_reboot']
            reboot_server_list = []
            images = self._serverDb.get_image("image_id", base_image_id, True)
            packages = self._serverDb.get_image("image_id", package_image_id, True)
            if len(images) == 0:
                msg = "No Image %s found" % (base_image_id)
                raise ServerMgrException(msg)
            if len(packages) == 0:
                msg = "No Package %s found" % (package_image_id)
                raise ServerMgrException(msg)
            base_image = images[0]
            servers = self._serverDb.get_server(
                match_key, match_value, detail=True)
            if len(servers) == 0:
                msg = "No Servers found for %s" % (match_value)
                raise ServerMgrException(msg)
            for server in servers:
                vns = None
                server_params = eval(server['server_params'])
                # build all parameters needed for re-imaging
                if server['vns_id']:
                    vns = self._serverDb.get_vns(server['vns_id'],
                                                    detail=True)
                vns_params = {}
                if vns and vns[0]['vns_params']:
                    vns_params = eval(vns[0]['vns_params'])

                passwd = mask = gway = domain = None
                server_id = server['server_id']
                if 'passwd' in server and server['passwd']:
                    passwd = server['passwd']
                elif 'passwd' in vns_params and vns_params['passwd']:
                    passwd = vns_params['passwd']
                else:
                    msg = "Missing Password for " + server_id
                    raise ServerMgrException(msg)

                if 'mask' in server and server['mask']:
                    mask = server['mask']
                elif 'mask' in vns_params and vns_params['mask']:
                    mask = vns_params['mask']
                else:
                    msg = "Missing prefix/mask for " + server_id
                    raise ServerMgrException(msg)

                if 'gway' in server and server['gway']:
                    gway = server['gway']
                elif 'gway' in vns_params and vns_params['gway']:
                    gway = vns_params['gway']
                else:
                    msg = "Missing gateway for " + server_id
                    raise ServerMgrException(msg)

                if 'domain' in server and server['domain']:
                    domain = server['domain']
                elif 'domain' in vns_params and vns_params['domain']:
                    domain = vns_params['domain']
                else:
                    msg = "Missing domain for " + server_id
                    raise ServerMgrException(msg)

                if 'ip' in server and server['ip']:
                    ip = server['ip']
                else:
                    msg = "Missing ip for " + server_id
                    raise ServerMgrException(msg)

                reimage_params = {}
                if ((base_image['image_type'] == 'esxi5.1') or
                    (base_image['image_type'] == 'esxi5.5')):
                    reimage_params['server_license'] = server_params.get(
                        'server_license', '')
                    reimage_params['esx_nicname'] = server_params.get(
                        'esx_nicname', 'vmnic0')
                reimage_params['server_id'] = server['server_id']
                reimage_params['server_ip'] = server['ip']
                reimage_params['server_mac'] = server['mac']
                reimage_params['server_passwd'] = self._encrypt_passwd(
                    passwd)
                reimage_params['server_mask'] = mask
                reimage_params['server_gway'] = gway
                reimage_params['server_domain'] = domain
                if 'ifname' not in server_params:
                    msg = "Missing ifname for " + server_id
                    raise ServerMgrException(msg)
                if 'power_address' in server and server['power_address'] == None:
                    msg = "Missing power address for " + server_id
                    raise ServerMgrException(msg)
                reimage_params['server_ifname'] = server_params['ifname']
                reimage_params['power_type'] = server.get('power_type')
                if not reimage_params['power_type']:
                    reimage_params['power_type'] = self._args.power_type
                reimage_params['power_user'] = server.get('power_user')
                if not reimage_params['power_user']:
                    reimage_params['power_user'] = self._args.power_user
                reimage_params['power_pass'] = server.get('power_pass')
                if not reimage_params['power_pass']:
                    reimage_params['power_pass'] = self._args.power_pass
                reimage_params['power_address'] = server.get(
                    'power_address', '')
                self._do_reimage_server(
                    base_image, package_image_id, reimage_params)

                # Build list of servers to be rebooted.
                reboot_server = {
                    'server_id' : server['server_id'],
                    'domain' : domain,
                    'ip' : server.get("ip", ""),
                    'passwd' : passwd,
                    'power_address' : server.get('power_address',"") }
                reboot_server_list.append(
                    reboot_server)
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
            abort(404, e.value)
        except Exception as e:
            self.log_trace()
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REIMAGE,
                                     False)
            abort(404, "Error in upgrading Server")
        return "server(s) upgraded"
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
            reboot_server_list = []
            servers = self._serverDb.get_server(
                    match_key, match_value, detail=True)
            if len(servers) == 0:
                msg = "No Servers found for match %s" % \
                    (match_value)
                raise ServerMgrException(msg)
            for server in servers:
                vns = None
                #if its None,It gets the VNS list
                if server['vns_id']:
                    vns = self._serverDb.get_vns(server['vns_id'],
                                             detail=True)
                vns_params = {}
                if vns and vns[0]['vns_params']:
                    vns_params = eval(vns[0]['vns_params'])

                server_id = server['server_id']
                if 'passwd' in server:
                    passwd = server['passwd']
                elif 'passwd' in vns_params:
                    passwd = vns_params['passwd']
                else:
                    abort(404, "Missing password for " + server_id)

                if 'domain' in server and server['domain']:
                    domain = server['domain']
                elif 'domain' in vns_params and vns_params['domain']:
                    domain = vns_params['domain']
                else:
                    abort(404, "Missing Domain for " + server_id)

                # Build list of servers to be rebooted.
                reboot_server = {
                    'server_id' : server['server_id'],
                    'domain' : domain,
                    'ip' : server.get("ip", ""),
                    'passwd' : passwd,
                    'power_address' : server.get('power_address',"") }
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
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REBOOT,
                                     False)
            self.log_trace()
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_REBOOT)
        return status_msg
    # end restart_server

    # Function to get all servers in a VNS configured for given role.
    def role_get_servers(self, vns_servers, role_type):
        servers = []
        for server in vns_servers:
            if role_type in server['roles']:
                servers.append(server)
        return servers

    #Function to get control section for all servers
    # belonging to the same VN
    def get_control_net(self, vns_servers):
        server_control_list = {}
        for server in vns_servers:
            if 'intf_control' not in server:
                    intf_control = ""
            else:
                intf_control = server['intf_control']
                server_control_list[server['ip']] = intf_control
        return server_control_list

    # Function to get map server name to server ip
    # accepts list of server names and returns list of
    # server ips
    def get_server_ip_list(self, server_names, servers):
        server_ips = []
        for server_name in server_names:
            for server in servers:
                if server['server_id'] == server_name:
                    server_ips.append(
                        server['server_ip'])
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
        self._smgr_log.log(self._smgr_log.DEBUG, "*****TRACEBACK-START*****")
	tb_lines = traceback.format_exception(exc_type, exc_value,
                          exc_traceback)
	for tb_line in tb_lines:
            self._smgr_log.log(self._smgr_log.DEBUG, tb_line)
        self._smgr_log.log(self._smgr_log.DEBUG, "*****TRACEBACK-END******")

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

    # API call to provision server(s) as per roles/roles
    # defined for those server(s). This function creates the
    # puppet manifest file for the server and adds it to site
    # manifest file.
    def provision_server(self):
        self._smgr_log.log(self._smgr_log.DEBUG, "provision_server")
        try:
            entity = bottle.request.json
            interface_created = entity.pop("interface_created", None)

            role_servers = {}
            role_ips = {}
            role_ids = {}
            ret_data = self.validate_smgr_request("PROVISION", "PROVISION", bottle.request)

            if ret_data['status'] == 0:
                servers = ret_data['servers']
                package_image_id = ret_data['package_image_id']
            else:
                msg = "Error validating request"
                raise ServerMgrException(msg)

            for server in servers:
                server_params = eval(server['server_params'])
                vns = self._serverDb.get_vns(server['vns_id'],
                                             detail=True)[0]
                vns_params = eval(vns['vns_params'])
                # Get all the servers belonging to the VNS that this server
                # belongs too.
                vns_servers = self._serverDb.get_server(
                    match_key="vns_id", match_value=server["vns_id"],
                    detail="True")
                # build roles dictionary for this vns. Roles dictionary will be
                # keyed by role-id and value would be list of servers configured
                # with this role.
                if not role_servers:
                    for role in ['database', 'openstack',
                                 'config', 'control',
                                 'collector', 'webui',
                                 'compute']:
                        role_servers[role] = self.role_get_servers(
                            vns_servers, role)
                        role_ips[role] = [x["ip"] for x in role_servers[role]]
                        role_ids[role] = [x["server_id"] for x in role_servers[role]]
                provision_params = {}
                provision_params['package_image_id'] = package_image_id
                # Get puppet manifest version corresponding to this package_image_id
                image = self._serverDb.get_image(
                    "image_id", package_image_id, True)[0]
                puppet_manifest_version = eval(image['image_params'])['puppet_manifest_version']
                provision_params['puppet_manifest_version'] = puppet_manifest_version
                provision_params['server_mgr_ip'] = self._args.listen_ip_addr
                provision_params['roles'] = role_ips
                provision_params['role_ids'] = role_ids
                provision_params['server_id'] = server['server_id']
                if server['domain']:
                    provision_params['domain'] = server['domain']
                else:
                        provision_params['domain'] = vns_params['domain']

                provision_params['rmq_master'] = role_ids['config'][0]
                provision_params['uuid'] = vns_params['uuid']
                provision_params['smgr_ip'] = self._args.listen_ip_addr
                if role_ids['config'][0] == server['server_id']:
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
                provision_params['control_net'] = self.get_control_net(vns_servers)
                provision_params['server_ip'] = server['ip']
                provision_params['database_dir'] = vns_params['database_dir']
                provision_params['db_initial_token'] = vns_params['db_initial_token']
                provision_params['openstack_mgmt_ip'] = vns_params['openstack_mgmt_ip']
                provision_params['use_certs'] = vns_params['use_certs']
                provision_params['multi_tenancy'] = vns_params['multi_tenancy']
                provision_params['router_asn'] = vns_params['router_asn']
                provision_params['encap_priority'] = vns_params['encap_priority']
                provision_params['service_token'] = vns_params['service_token']
                provision_params['ks_user'] = vns_params['ks_user']
                provision_params['ks_passwd'] = vns_params['ks_passwd']
                provision_params['ks_tenant'] = vns_params['ks_tenant']
                provision_params['openstack_passwd'] = vns_params['openstack_passwd']
                provision_params['analytics_data_ttl'] = vns_params['analytics_data_ttl']
                provision_params['phy_interface'] = server_params['ifname']
                provision_params['compute_non_mgmt_ip'] = server_params['compute_non_mgmt_ip']
                provision_params['compute_non_mgmt_gway'] = server_params['compute_non_mgmt_gway']
                provision_params['server_gway'] = server['gway']
                provision_params['haproxy'] = vns_params['haproxy']
                if 'setup_interface' in server_params.keys():
                    provision_params['setup_interface'] = \
                                                    server_params['setup_interface']
                else:
                     provision_params['setup_interface'] = "No"

                provision_params['haproxy'] = vns_params['haproxy']
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
                    esx_servers = self._serverDb.get_server('server_id', server_params['esx_server'],
                                                            detail=True)
                    esx_server = esx_servers[0]
                    provision_params['esx_ip'] = esx_server['ip']
                    provision_params['esx_username'] = "root"
                    provision_params['esx_passwd'] = esx_server['passwd']
                    provision_params['esx_server'] = esx_server
                    provision_params['server_mac'] = server['mac']
                    provision_params['passwd'] = server['passwd']

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
                   provision_params['esx_passwd'] = ""



                if interface_created:
                    provision_params['setup_interface'] = "No"

                if 'region_name' in vns_params.keys():
                    provision_params['region_name'] = vns_params['region_name']
                else:
                    provision_params['region_name'] = "RegionOne"
                if 'execute_script' in server_params.keys():
                    provision_params['execute_script'] = server_params['execute_script']
                else:
                    provision_params['execute_script'] = ""
                if 'ext_bgp' in vns_params.keys():
                    provision_params['ext_bgp'] = vns_params['ext_bgp']
                else:
                    provision_params['ext_bgp'] = ""

                self._do_provision_server(provision_params)
                #end of for
        except ServerMgrException as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION,
                                     False)
            abort(404, e.value)
        except Exception as e:
            self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION,
                                     False)
            self.log_trace()
            abort(404, repr(e))
        self._smgr_trans_log.log(bottle.request,
                                     self._smgr_trans_log.SMGR_PROVISION)
        return "server(s) provisioned"
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
                                         --db_name vns_server_mgr.db
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
            'listen_ip_addr'   : _WEB_HOST,
            'listen_port'      : _WEB_PORT,
            'db_name'          : _DEF_CFG_DB,
            'smgr_base_dir'    : _DEF_SMGR_BASE_DIR,
            'html_root_dir'    : _DEF_HTML_ROOT_DIR,
            'cobbler_ip'       : _DEF_COBBLER_IP,
            'cobbler_port'     : _DEF_COBBLER_PORT,
            'cobbler_user'     : _DEF_COBBLER_USER,
            'cobbler_passwd'   : _DEF_COBBLER_PASSWD,
            'power_user'       : _DEF_POWER_USER,
            'power_pass'       : _DEF_POWER_PASSWD,
            'power_type'       : _DEF_POWER_TOOL,
            'puppet_dir'       : _DEF_PUPPET_DIR
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([args.config_file])
            for key in serverMgrCfg.keys():
                serverMgrCfg[key] = dict(config.items("SERVER-MANAGER"))[key]
        except:
            # if config file could not be read, use default values
            pass

        self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form config file %s" % serverMgrCfg )

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
            "-d", "--db_name",
            help=(
                "Name where server DB is maintained, default %s"
                % (_DEF_CFG_DB)))
        parser.add_argument(
            "-l", "--server_list",
            help=(
                "Name of JSON file containing list of cluster and servers,"
                " default None"))
        self._args = parser.parse_args(remaining_argv)
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
                            kernel_file, initrd_file):
        try:
            mount_path = self._args.smgr_base_dir + "mnt/"
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
                        server['server_id'])
                    cmd = "puppet cert clean %s.%s" % (
                        server['server_id'], server['domain'])
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                        cmd)
                    subprocess.call(cmd, shell=True)
                    # Remove manifest file for this server
                    cmd = "rm -f /etc/puppet/manifests/%s.%s.pp" %(
                        server['server_id'], server['domain'])
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                        cmd)

                    subprocess.call(cmd, shell=True)
                    # Remove entry for that server from site.pp
                    cmd = "sed -i \"/%s.%s.pp/d\" /etc/puppet/manifests/site.pp" %(
                        server['server_id'], server['domain'])
                    self._smgr_log.log(self._smgr_log.DEBUG,
                                        cmd)
                    subprocess.call(cmd, shell=True)
                # end if
                if server['power_address']:
                    power_reboot_list.append(
                        server['server_id'])
                else:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(
                        paramiko.AutoAddPolicy())
                    client.connect(
                        server_ip, username='root', password=passwd)
                    stdin, stdout, stderr = client.exec_command('reboot')
                # end else
                # Update Server table to update time.
                update = {'server_id': server['server_id'],
                          'update_time': strftime(
                             "%Y-%m-%d %H:%M:%S", gmtime())}
                self._serverDb.modify_server(update)
                success_list.append(server['server_id'])
            except Exception as e:
                self._smgr_log.log(self._smgr_log.ERROR,
                                            repr(e))

                self._smgr_log.log(self._smgr_log.ERROR,
                                "Failed re-booting for server %s" % \
                                (server['server_id']))
                failed_list.append(server['server_id'])
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

    def _encrypt_passwd(self, server_passwd):
        try:
            xyz = subprocess.Popen(
                ["openssl", "passwd", "-1", "-noverify", server_passwd],
                stdout=subprocess.PIPE).communicate()[0]
        except:
            return None
        return xyz

    # Internal private call to upgrade server. This is called by REST
    # API update_server and upgrade_cluster
    def _do_reimage_server(self, base_image,
                           package_image_id, reimage_params):
        try:
            # Profile name is based on image name.
            profile_name = base_image['image_id']
            # Setup system information in cobbler
            self._smgr_cobbler.create_system(
                reimage_params['server_id'], profile_name, package_image_id,
                reimage_params['server_mac'], reimage_params['server_ip'],
                reimage_params['server_mask'], reimage_params['server_gway'],
                reimage_params['server_domain'], reimage_params['server_ifname'],
                reimage_params['server_passwd'],
                reimage_params.get('server_license', ''),
                reimage_params.get('esx_nicname', 'vmnic0'),
                reimage_params.get('power_type',self._args.power_type),
                reimage_params.get('power_user',self._args.power_user),
                reimage_params.get('power_pass',self._args.power_pass),
                reimage_params.get('power_address',''),
                base_image, self._args.listen_ip_addr)

            # Sync the above information
            #self._smgr_cobbler.sync()

            # Update Server table to add image name
            update = {
                'mac': reimage_params['server_mac'],
                'base_image_id': base_image['image_id'],
                'package_image_id': package_image_id}
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
    def _do_provision_server(self, provision_params):
        try:
            # Now call puppet to provision the server.
            self._smgr_puppet.provision_server(
                provision_params)
            # Now kickstart agent run on the target
            host_name = provision_params['server_id'] + "." + \
                provision_params.get('domain', '')
            rc = subprocess.call(
                ["puppet", "kick", "--host", host_name])
            # Log, return error if return code is non-null - TBD Abhay

            # TBD Update Server table to stamp provisioned time.
            # update = {'server_id':server_id,
            #          'image_id':image_id}
            # self._serverDb.modify_server(update)

        except Exception as e:
            raise e
    # end _do_provision_server

    def _create_server_manager_config(self, config):
        try:
            clusters = config.get("clusters", None)
            if clusters:
                for cluster in clusters:
                    self._serverDb.add_cluster(cluster)
            vns_list = config.get("vns", None)
            if vns_list:
                for vns in vns_list:
                    self._serverDb.add_vns(vns)
            servers = config.get("servers", None)
            if servers:
                for server in servers:
                    self._serverDb.add_server(server)
        except Exception as e:
            raise e
    # end _create_server_manager_config

# End class VncServerManager()


def main(args_str=None):
    vnc_server_mgr = VncServerManager(args_str)
    pipe_start_app = vnc_server_mgr.get_pipe_start_app()

    server_ip = vnc_server_mgr.get_server_ip()
    server_port = vnc_server_mgr.get_server_port()

    server_mgr_pid = os.getpid()
    pid_file = "/var/run/contrail_smgrd/contrail_smgrd.pid"
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
        vnc_server_mgr.cleanup()

# End of main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    main()
# End if __name__
