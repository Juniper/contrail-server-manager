#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_mon_base_plugin.py
   Author : Nitish Krishna
   Description : This module is the base plugin module for monitoring and inventory features. If neither feature is
   configured, this module takes over and returns default stub messages. It also provides some common functionality to
   both these features such as config argument parsing.
"""

import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
import argparse
import ConfigParser
from urlparse import urlparse, parse_qs
import logging
import logging.config
import logging.handlers
import inspect
import threading
import cStringIO
import re
import socket
import pdb
import re
import ast
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
from threading import Thread
from bottle import route, run, request, abort
from server_mgr_err import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_ssh_client import ServerMgrSSHClient
from server_mgr_utils import *
import json
import requests
import gevent
import math
import paramiko
from pysandesh.sandesh_base import *
from sandesh_common.vns.ttypes import Module, NodeType
from sandesh_common.vns.constants import ModuleNames, NodeTypeNames, \
    Module2NodeType, INSTANCE_ID_DEFAULT
from Crypto.PublicKey import RSA
import StringIO
from sandesh_common.vns.constants import *
from datetime import datetime

_DEF_COLLECTORS_IP = None
_DEF_MON_FREQ = 300
_DEF_MONITORING_PLUGIN = None
_DEF_INVENTORY_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_DEF_INTROSPECT_PORT = 8107


class ServerMgrMonBasePlugin():
    val = 1
    freq = 300
    _config_set = False
    _serverDb = None
    _monitoring_log = None
    _collectors_ip = None
    _discovery_server = None
    _discovery_port = None
    _default_ipmi_username = None
    _default_ipmi_password = None
    _provision_immediately_after_reimage = False
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self):
        ''' Constructor '''
        self.MonitoringCfg = {
            'monitoring_frequency': _DEF_MON_FREQ,
            'monitoring_plugin': _DEF_MONITORING_PLUGIN
        }
        self.InventoryCfg = {
            'inventory_plugin': _DEF_INVENTORY_PLUGIN
        }
        self._smgr_log = ServerMgrlogger()
        self.monitoring_args = None
        self.monitoring_config_set = False
        self.inventory_args = None
        self.inventory_config_set = False
        self.server_monitoring_obj = None
        self.server_inventory_obj = None
        self.monitoring_gevent_thread_obj = None

    def set_serverdb(self, server_db):
        self._serverDb = server_db

    def set_ipmi_defaults(self, ipmi_username, ipmi_password):
        self._default_ipmi_username = ipmi_username
        self._default_ipmi_password = ipmi_password

    def parse_args(self, args_str, section):
        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        if section == "MONITORING":
            for key in dict(config.items("MONITORING")).keys():
                if key in self.MonitoringCfg.keys():
                    self.MonitoringCfg[key] = dict(config.items("MONITORING"))[key]
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Configuration set for invalid parameter: %s" % key)
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "Arguments read from monitoring config file %s" % self.MonitoringCfg)
            parser.set_defaults(**self.MonitoringCfg)
        elif section == "INVENTORY":
            for key in dict(config.items("INVENTORY")).keys():
                if key in self.InventoryCfg.keys():
                    self.InventoryCfg[key] = dict(config.items("INVENTORY"))[key]
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Configuration set for invalid parameter: %s" % key)
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "Arguments read from inventory config file %s" % self.InventoryCfg)
            parser.set_defaults(**self.InventoryCfg)
        return parser.parse_args(remaining_argv)

    def parse_monitoring_args(self, args_str, args, sm_args, _rev_tags_dict, base_obj):
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        try:
            if dict(config.items("MONITORING")).keys():
                # Handle parsing for monitoring
                monitoring_args = self.parse_args(args_str, "MONITORING")
                if monitoring_args:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Monitoring arguments read from config.")
                    self.monitoring_args = monitoring_args
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
        except ConfigParser.NoSectionError:
            self._smgr_log.log(self._smgr_log.DEBUG, "No monitoring configuration set.")
        if self.monitoring_args:
            try:
                if self.monitoring_args.monitoring_plugin:
                    module_components = str(self.monitoring_args.monitoring_plugin).split('.')
                    monitoring_module = __import__(str(module_components[0]))
                    monitoring_class = getattr(monitoring_module, module_components[1])
                    if sm_args.collectors:
                        self.server_monitoring_obj = monitoring_class(1, self.monitoring_args.monitoring_frequency,
                                                                      sm_args.listen_ip_addr,
                                                                      sm_args.listen_port, sm_args.collectors,
                                                                      sm_args.http_introspect_port, _rev_tags_dict)
                        self.monitoring_config_set = True
                else:
                    self._smgr_log.log(self._smgr_log.ERROR,
                                       "Analytics IP and Monitoring API misconfigured, monitoring aborted")
                    self.server_monitoring_obj = base_obj
            except ImportError as ie:
                self._smgr_log.log(self._smgr_log.ERROR,
                                   "Configured modules are missing. Server Manager will quit now.")
                self._smgr_log.log(self._smgr_log.ERROR, "Error: " + str(ie))
                raise ImportError
        else:
            self.server_monitoring_obj = base_obj
        return self.server_monitoring_obj

    def parse_inventory_args(self, args_str, args, sm_args, _rev_tags_dict, base_obj):
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        try:
            if dict(config.items("INVENTORY")).keys():
                # Handle parsing for monitoring
                inventory_args = self.parse_args(args_str, "INVENTORY")
                if inventory_args:
                    self._smgr_log.log(self._smgr_log.DEBUG, "Inventory arguments read from config.")
                    self.inventory_args = inventory_args
                else:
                    self._smgr_log.log(self._smgr_log.DEBUG, "No inventory configuration set.")
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "No inventory configuration set.")
        except ConfigParser.NoSectionError:
            self._smgr_log.log(self._smgr_log.DEBUG, "No inventory configuration set.")

        if self.inventory_args:
            try:
                if self.inventory_args.inventory_plugin:
                    module_components = str(self.inventory_args.inventory_plugin).split('.')
                    inventory_module = __import__(str(module_components[0]))
                    inventory_class = getattr(inventory_module, module_components[1])
                    if sm_args.collectors:
                        self.server_inventory_obj = inventory_class(sm_args.listen_ip_addr, sm_args.listen_port,
                                                                    sm_args.http_introspect_port, _rev_tags_dict)
                        self.inventory_config_set = True
                else:
                    self._smgr_log.log(self._smgr_log.ERROR,
                                       "Iventory API misconfigured, inventory aborted")
                    self.server_inventory_obj = base_obj
            except ImportError:
                self._smgr_log.log(self._smgr_log.ERROR,
                                   "Configured modules are missing. Server Manager will quit now.")
                raise ImportError
        else:
            self.server_inventory_obj = base_obj
        return self.server_inventory_obj

    def validate_rest_api_args(self, request, rev_tags_dict):
        ret_data = {"msg": None, "type_msg": None}
        match_keys = list(['id', 'cluster_id', 'tag', 'where'])
        print_match_keys = list(['server_id', 'cluster_id', 'tag', 'where'])
        self._smgr_log.log(self._smgr_log.DEBUG,
                           "Validating bottle arguments.")
        ret_data['status'] = 1
        query_args = parse_qs(urlparse(request.url).query,
                              keep_blank_values=True)
        if len(query_args) == 0:
            ret_data["type"] = ["all"]
            ret_data["status"] = True
            ret_data["match_key"] = None
            ret_data["match_value"] = None
        elif len(query_args) >= 1:
            select_value_list = None
            if "select" in query_args:
                select_value_list = query_args.get("select", None)[0]
                select_value_list = str(select_value_list).split(',')
                self._smgr_log.log(self._smgr_log.DEBUG,
                                   "Select value list=" + str(select_value_list))
                query_args.pop("select")
            if not select_value_list:
                ret_data["type"] = ["all"]
            else:
                ret_data["type"] = select_value_list
            match_key = match_value = None
            if query_args:
                match_key, match_value = query_args.popitem()
            if match_key and match_key not in match_keys:
                ret_data["status"] = False
                ret_data["msg"] = "Wrong Match Key Specified. " + "Choose one of the following keys: " + \
                                  str(['--{0}'.format(key) for key in print_match_keys]).strip('[]')
                self._smgr_log.log(self._smgr_log.ERROR,
                                   "Wrong Match Key")
            elif match_key and (match_value is None or match_value[0] == ''):
                ret_data["status"] = False
                self._smgr_log.log(self._smgr_log.ERROR,
                                   "No macth value given")
                ret_data["msg"] = "No Match Value Specified.\n"
            else:
                ret_data["status"] = True
                if match_key:
                    ret_data["match_key"] = str(match_key)
                else:
                    ret_data["match_key"] = None
                if match_value:
                    ret_data["match_value"] = str(match_value[0])
                else:
                    ret_data["match_value"] = None
        return ret_data

    def process_server_tags(self, rev_tags_dict, match_value):
        if not match_value:
            return {}
        match_dict = {}
        tag_list = match_value.split(',')
        for x in tag_list:
            tag = x.strip().split('=')
            if tag[0] in rev_tags_dict:
                match_dict[rev_tags_dict[tag[0]]] = tag[1]
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "Wrong tag specified in rest api request.")
                return {}
        return match_dict

    def sandesh_init(self, sm_args, mon_config_set, inv_config_set):
        # Inventory node module initialization part
        try:
            module = None
            port = None
            module_list = None
            self._smgr_log.log(self._smgr_log.INFO, "Initializing sandesh")
            collectors_ip_list = eval(sm_args.collectors)
            if collectors_ip_list:
                self._smgr_log.log(self._smgr_log.INFO, "Collector IPs from config: " + str(collectors_ip_list))
                monitoring = True
                inventory = True

                if mon_config_set and inv_config_set:
                    try:
                        __import__('contrail_sm_monitoring.monitoring')
                    except ImportError:
                        mon_config_set = False
                        pass
                    try:
                        __import__('inventory_daemon.server_inventory')
                    except ImportError:
                        inv_config_set = False
                        pass
                    module = Module.INVENTORY_AGENT
                    port = int(sm_args.http_introspect_port)
                    module_list = ['inventory_daemon.server_inventory', 'contrail_sm_monitoring.monitoring']
                elif inv_config_set:
                    try:
                        __import__('inventory_daemon.server_inventory')
                    except ImportError:
                        inv_config_set = False
                        pass
                    module = Module.INVENTORY_AGENT
                    port = int(sm_args.http_introspect_port)
                    module_list = ['inventory_daemon.server_inventory']
                elif mon_config_set:
                    try:
                        __import__('contrail_sm_monitoring.monitoring')
                    except ImportError:
                        mon_config_set = False
                        pass
                    module = Module.IPMI_STATS_MGR
                    port = int(sm_args.http_introspect_port)
                    module_list = ['contrail_sm_monitoring.monitoring']
                if mon_config_set or inv_config_set:
                    module_name = ModuleNames[module]
                    node_type = Module2NodeType[module]
                    node_type_name = NodeTypeNames[node_type]
                    instance_id = INSTANCE_ID_DEFAULT
                    sandesh_global.init_generator(
                        module_name,
                        socket.gethostname(),
                        node_type_name,
                        instance_id,
                        collectors_ip_list,
                        module_name,
                        port,
                        module_list)
                    sandesh_global.set_logging_params(level=sm_args.sandesh_log_level)
                else:
                    self._smgr_log.log(self._smgr_log.INFO, "Sandesh wasn't initialized")
            else:
                pass
        except Exception as e:
            raise ServerMgrException("Error during Sandesh Init: " + str(e))

    def call_subprocess(self, cmd):
        p = None
        try:
            times = datetime.now()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, close_fds=True)
            while p.poll() is None:
                time.sleep(0.3)
                now = datetime.now()
                diff = now - times
                if diff.seconds > 2:
                    if p and p.poll() != 0:
                        if p.stdout:
                            p.stdout.close()
                        if p.stderr:
                            p.stderr.close()
                        if p.stdin:
                            p.stdin.close()
                        if p:
                            p.terminate()
                    os.waitpid(-1, os.WNOHANG)
                    self._smgr_log.log(self._smgr_log.INFO, "command:" + cmd + " --> hanged")
                    return None
            result = p.communicate()[0].strip()
            return result
        except Exception as e:
            if p and p.poll() != 0:
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
                if p.stdin:
                    p.stdin.close()
                if p:
                    p.terminate()
            self._smgr_log.log(self._smgr_log.INFO, "Exception in call_subprocess: " + str(e))
            return None

    def copy_ssh_keys_to_server(self, ip_address, server_id):
      self._smgr_log.log(self._smgr_log.DEBUG, "COPY-KEY: Server: " + str(server_id))

      tries = 0
      gevent.sleep(60)
      success = False
      while True:
        try:
          tries = tries + 1
          #avoid overflow
          if tries > 10000:
            tries = 10000

          # We keep trying infinitely for this, so if server is deleted before
          # this, we need to know about it and pull new_public_key
          servers = self._serverDb.get_server({"id": server_id}, detail=True)
          if not servers :
            self._smgr_log.log(self._smgr_log.DEBUG, "COPY-KEY: Server: " + str(server_id) + " NOT FOUND")
            return False

          server = servers[0]
          ssh_key = server["ssh_public_key"]
          #try to connect first if target node is up
          source_file = "/tmp/" + str(server_id) + ".pub"
          ssh = ServerMgrSSHClient(self._serverDb)
          ssh.connect(ip_address, server_id, option="password")

          subprocess.call(['mkdir', '-p', '/tmp'])
          with open("/tmp/" + str(server_id) + ".pub", 'w+') as content_file:
            content_file.write(str(ssh_key))
            content_file.close()

          key_dest_file = "/root/" + str(server_id) + ".pub"
          dest_file = "/root/.ssh/authorized_keys"
          ssh.exec_command("mkdir -p /root/.ssh/")
          ssh.exec_command("touch " + str(key_dest_file))
          ssh.exec_command("touch " + str(dest_file))

          if os.path.exists(source_file):
            # Copy Public key on Target Server
            #TODO: check if authrized keys are already available
            bytes_sent = ssh.copy(source_file, key_dest_file)
            cmd = "grep -q -f " + str(key_dest_file) + " " + str(dest_file) + ";" \
                  + " RETVAL=$? ; " \
                  + " if [[ $RETVAL -eq 1 ]]; then \
                        echo '' >> " + str(dest_file) + "; \
                        cat " + str(key_dest_file) + " >> " + str(dest_file) + ";\
                        echo '' >> " + str(dest_file) + "; fi; \
                      rm -f " + str(key_dest_file) + "; "

            self._smgr_log.log(self._smgr_log.DEBUG, cmd)
            ssh.exec_command(cmd)
          ssh.close()
          if os.path.exists(source_file):
            os.remove(source_file)
          msg =  "COPY-KEYS: %s bytes copied on %s: " %(str(bytes_sent), str(server_id))
          self._smgr_log.log(self._smgr_log.DEBUG, msg)
          success = True
          return success

        except Exception as e:
          msg = "COPY-KEYS: Host : %s Try: %d: ERROR Copying Keys: %s" % (str(server_id), tries, str(e))
          self._smgr_log.log(self._smgr_log.ERROR, msg)
          if os.path.exists(source_file):
            os.remove(source_file)
          if ssh:
            ssh.close()
          if tries >= 20:
            sleep_time = 120
          else:
            sleep_time = 30

          gevent.sleep(sleep_time)

      #if we are here, then SSH Keys are not copied
      #if tries >= 10:
        #msg = "COPY-KEYS: Host : %s Try: %d: SSH-COPY Failed" % (str(server_id), tries)
        #self._smgr_log.log(self._smgr_log.ERROR, msg)
        #return False

    def create_store_copy_ssh_keys(self, server_id, server_ip, generate_keys = True):
        self._smgr_log.log(self._smgr_log.DEBUG, "Generating : " + str(server_id) + " " + str(generate_keys))
        if generate_keys == True:
          # Create the Keys using Pycrypto
          self._smgr_log.log(self._smgr_log.DEBUG, "Generating & Copying keys for server: " + str(server_id))
          ssh_key = paramiko.RSAKey.generate(bits=2048)
          ssh_private_key_obj = StringIO.StringIO()
          ssh_key.write_private_key(ssh_private_key_obj)

          # Update Server table with ssh public and private keys
          update = {'id': server_id,
                    'ssh_public_key': "ssh-rsa " + str(ssh_key.get_base64()),
                    'ssh_private_key': ssh_private_key_obj.getvalue()}
          self._serverDb.modify_server(update)

        #copy the ssh keys to target server
        self.copy_ssh_keys_to_server(server_ip, server_id)


    def populate_server_data_lists(self, servers, ipmi_list, hostname_list,
                                   server_ip_list, ipmi_username_list, ipmi_password_list, feature):
        smutil = ServerMgrUtil()
        for server in servers:
            server = dict(server)
            server_password= smutil.get_password(server,self._serverDb)
            if 'parameters' in server:
                server_parameters = eval(server['parameters'])
                if feature == "monitoring" and "enable_monitoring" in server_parameters \
                        and server_parameters["enable_monitoring"] in ["true", "True"]:
                    continue
                elif feature == "inventory" and "enable_inventory" in server_parameters \
                        and server_parameters["enable_inventory"] in ["true", "True"]:
                    continue
            if 'ipmi_address' in server and server['ipmi_address'] \
                    and 'id' in server and server['id'] \
                    and 'ip_address' in server and server['ip_address'] \
                    and server_password:
                ipmi_list.append(server['ipmi_address'])
                hostname_list.append(server['id'])
                server_ip_list.append(server['ip_address'])
                if 'ipmi_username' in server and server['ipmi_username'] \
                        and 'ipmi_password' in server and server['ipmi_password']:
                    ipmi_username_list.append(server['ipmi_username'])
                    ipmi_password_list.append(server['ipmi_password'])
                else:
                    ipmi_username_list.append(self._default_ipmi_username)
                    ipmi_password_list.append(self._default_ipmi_password)

    # Packages and sends a REST API call to the ServerManager node
    def copy_ssh_keys_to_servers(self, ip, port, payload, sm_args=None):
        servers = self._serverDb.get_server({"id": str(payload["id"])}, detail=True)
        server = servers[0]
        success = self.copy_ssh_keys_to_server(str(server["ip_address"]), str(server["id"]))

        self._smgr_log.log(self._smgr_log.DEBUG, "COPY-KEY: Host: " + server["id"] + " /Status: " + str(success))

        if success and self._provision_immediately_after_reimage == True:
            gevent.spawn(self.gevent_puppet_agent_action, server, self._serverDb, sm_args, "start")
        if success and self.inventory_config_set:
            try:
                url = "http://%s:%s/run_inventory" % (ip, port)
                payload = json.dumps(payload)
                headers = {'content-type': 'application/json'}
                resp = requests.post(url, headers=headers, timeout=5, data=payload)
                return resp.text
            except Exception as e:
                self._smgr_log.log("error", "Error running inventory on  " + str(payload) + " : " + str(e))
                return None

    def get_list_name(self, lst):
        sname = ""
        for sattr in lst.keys():
            if sattr[0] not in ['@']:
                sname = sattr
        return sname

    def parse_sandesh_xml(self, inp, uve_name):
        try:
            sname = ""
            if '@type' not in inp:
                return None
            if inp['@type'] == 'slist':
                sname = str(uve_name) + "Uve"
                ret = []
                items = inp[sname]
                if not isinstance(items, list):
                    items = [items]
                lst = []
                for elem in items:
                    if not isinstance(elem, dict):
                        lst.append(elem)
                    else:
                        lst_elem = {}
                        for k, v in elem.items():
                            lst_elem[k] = self.parse_sandesh_xml(v, uve_name)
                        lst.append(lst_elem)
                # ret[sname] = lst
                ret = lst
                return ret
            elif inp['@type'] == 'sandesh':
                sname = "data"
                ret = {}
                for k, v in inp[sname].items():
                    ret[k] = self.parse_sandesh_xml(v, uve_name)
                return ret
            elif inp['@type'] == 'struct':
                sname = self.get_list_name(inp)
                if (sname == ""):
                    self._smgr_log.log("error", "Error parsing sandesh xml dict : " + str('Struct Parse Error'))
                    return None
                ret = {}
                for k, v in inp[sname].items():
                    ret[k] = self.parse_sandesh_xml(v, uve_name)
                return ret
            elif (inp['@type'] == 'list'):
                sname = self.get_list_name(inp['list'])
                ret = []
                if (sname == ""):
                    return ret
                items = inp['list'][sname]
                if not isinstance(items, list):
                    items = [items]
                lst = []
                for elem in items:
                    if not isinstance(elem, dict):
                        lst.append(elem)
                    else:
                        lst_elem = {}
                        for k, v in elem.items():
                            lst_elem[k] = self.parse_sandesh_xml(v, uve_name)
                        lst.append(lst_elem)
                # ret[sname] = lst
                ret = lst
                return ret
            else:
                if '#text' not in inp:
                    return None
                if inp['@type'] in ['i16', 'i32', 'i64', 'byte',
                                    'u64', 'u32', 'u16']:
                    return int(inp['#text'])
                elif inp['@type'] in ['float', 'double']:
                    return float(inp['#text'])
                elif inp['@type'] in ['bool']:
                    if inp['#text'] in ["false"]:
                        return False
                    elif inp['#text'] in ["true"]:
                        return True
                    else:
                        return inp['#text']
                else:
                    return inp['#text']
        except Exception as e:
            self._smgr_log.log("error", "Error parsing sandesh xml dict : " + str(e))
            return None

    def get_sandesh_url(self, ip, introspect_port, uve_name, server_id=None):
        if server_id:
            url = "http://%s:%s/Snh_SandeshUVECacheReq?tname=%s&key=%s" % \
                  (str(ip), str(introspect_port), uve_name, server_id)
        else:
            url = "http://%s:%s/Snh_SandeshUVECacheReq?x=%s" % \
                  (str(ip), str(introspect_port), uve_name)
        return url

    def initialize_features(self, sm_args, serverdb):
        self.sandesh_init(sm_args, self.monitoring_config_set, self.inventory_config_set)
        self.set_serverdb(serverdb)
        if self.monitoring_config_set:
            self.server_monitoring_obj.set_serverdb(serverdb)
            self.server_monitoring_obj.set_ipmi_defaults(sm_args.ipmi_username, sm_args.ipmi_password)
            self.monitoring_gevent_thread_obj = gevent.spawn(self.server_monitoring_obj.run)
        else:
            self._smgr_log.log(self._smgr_log.ERROR, "Monitoring configuration not set. "
                                                     "You will be unable to get Monitor information of servers.")

        if self.inventory_config_set:
            self.server_inventory_obj.set_serverdb(serverdb)
            self.server_inventory_obj.set_ipmi_defaults(sm_args.ipmi_username, sm_args.ipmi_password)
            self.server_inventory_obj.add_inventory()
        else:
            self._smgr_log.log(self._smgr_log.ERROR, "Inventory configuration not set. "
                                                     "You will be unable to get Inventory information from servers.")

    def setup_keys(self, server_db=None, new_servers=None):
        if server_db is not None:
            servers = self._serverDb.get_server(None, detail=True)
        elif new_servers is not None:
            servers = new_servers

        for server in servers:
            ## If NO ssh keys are added then create new keys for all the servers, store them in DB, copy them to the target
            ## If keys are the deleted from the DB then create and copy them to the target
            if ('ssh_private_key' not in server or server['ssh_private_key'] is None or \
                  server['ssh_private_key'] == "")  \
                 and 'id' in server and 'ip_address' in server and server['id']:
                self._smgr_log.log(self._smgr_log.DEBUG, "SETUP-KEYS: 2 : " + str(server["id"]))
                gevent.spawn(self.create_store_copy_ssh_keys, server['id'], server['ip_address'])
            ## 
            elif 'ssh_private_key' in server and 'ssh_public_key' in server  \
                 and 'id' in server and 'ip_address' in server and server['id']:

                self._smgr_log.log(self._smgr_log.DEBUG, "SETUP-KEYS: 3 : " + str(server["id"]))
                gevent.spawn(self.create_store_copy_ssh_keys, 
                  server['id'], server['ip_address'], generate_keys = False)

            ## TODO: if keys are configured already or we are starting up, then
            ## try to add again.
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "SETUP-KEYS: ALREADY configured for Server: " + str(server["id"]))
                #self._smgr_log.log(self._smgr_log.DEBUG, "SETUP-KEYS: " +
                   #str(server["id"]) + "PUB: " + server['ssh_public_key'] +
#"PRIVATE : " + server['ssh_private_key'] )

        if self.inventory_config_set and new_servers:
                self.server_inventory_obj.handle_inventory_trigger("add", servers)


    def create_server_dict(self, servers):
        return_dict = dict()
        for server in servers:
            server = dict(server)
            if 'ipmi_username' not in server or not server['ipmi_username'] \
                    or 'ipmi_password' not in server or not server['ipmi_password']:
                server['ipmi_username'] = self._default_ipmi_username
                server['ipmi_password'] = self._default_ipmi_password
            return_dict[str(server['id'])] = server
        return return_dict

    def get_mon_conf_details(self):
        resp = self.return_error("Monitoring Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def get_inv_conf_details(self):
        resp = self.return_error("Inventory Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def get_inventory_info(self):
        resp = self.return_error("Inventory Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def get_monitoring_info(self):
        resp = self.return_error("Monitoring Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def get_monitoring_info_summary(self):
        resp = self.return_error("Monitoring Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def run_inventory(self):
        resp = self.return_error("Inventory Parameters haven't been configured.\n"
                                 "Reset the configuration correctly and restart Server Manager.\n")
        abort(404, resp)

    def handle_inventory_trigger(self, action=None, servers=None):
        self._smgr_log.log(self._smgr_log.INFO, "Inventory of added servers will not be read.")
        return "Inventory Parameters haven't been configured.\n" \
               "Reset the configuration correctly and restart Server Manager.\n"

    def add_inventory(self):
        self._smgr_log.log(self._smgr_log.ERROR, "Inventory Parameters haven't been configured.\n" +
                                                 "Reset the configuration correctly to add inventory.\n")
        return "Inventory Parameters haven't been configured.\n" \
               "Reset the configuration correctly and restart Server Manager.\n"

    def cleanup(self, obj=None):
        self._smgr_log.log(self._smgr_log.INFO, "Monitoring Parameters haven't been configured.\n" +
                           "No cleanup needed.\n")
        return "Inventory Parameters haven't been configured.\n" \
               "Reset the configuration correctly and restart Server Manager.\n"

    def return_error(self, msg, ret_code=ERR_GENERAL_ERROR, data=None):
        self._smgr_log.log(self._smgr_log.ERROR, msg)
        return_data = dict()
        return_data['return_code'] = ret_code
        return_data['return_msg'] = msg
        return_data['return_data'] = data
        resp = json.dumps(return_data, sort_keys=True, indent=4)
        return resp

    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self._smgr_log.log(self._smgr_log.INFO,
                           "No monitoring API has been configured. Server Environement Info will not be monitored.")

   
    #Function to stop the puppet agent in the target servers
    def gevent_puppet_agent_action(self,server, serverDb, sm_args, action,access_method="key"):
        success = False
        tries = 0
        gevent.sleep(30)
        self._smgr_log.log("debug", "Going to %s the puppet agent on the server %s"% (action, str(server['id'])))
        while not success and tries < int(sm_args.puppet_agent_retry_count):
            try:
                tries += 1
                sshclient = ServerMgrSSHClient(serverdb=serverDb)
                sshclient.connect(str(server['ip_address']), str(server['id']), access_method)
                op = sshclient.exec_command('python -c "import platform; print platform.linux_distribution()"')
                self._smgr_log.log("debug", "OP is %s" %op)
                os_type = 'centos' if 'centos' in op.lower() else 'ubuntu'
                if os_type == 'centos':
                    enable_puppet_svc_cmd = "chkconfig puppet on"
                    disable_puppet_svc_cmd = "chkconfig puppet off"
                else:
                    enable_puppet_svc_cmd = " sed -i 's/START=.*$/START=yes/' /etc/default/puppet && "\
                                            "/usr/bin/puppet resource service puppet ensure=running enable=true "
                    disable_puppet_svc_cmd = " sed -i 's/START=.*$/START=no/' /etc/default/puppet && " \
                                             "/usr/bin/puppet resource service puppet ensure=stopped enable=false "

                self._smgr_log.log("debug", "PUPPET START Command is %s" %enable_puppet_svc_cmd)
                if action == "start":
                    output = sshclient.exec_command(enable_puppet_svc_cmd)
                    self._smgr_log.log("debug", "OUTPUT1 is %s" %output)
                    output = sshclient.exec_command("puppet agent --enable")
                    self._smgr_log.log("debug", "OUTPUT2 is %s" %output)
                    output = sshclient.exec_command("service puppet restart")
                    self._smgr_log.log("debug", "OUTPUT3 is %s" %output)

                    self._smgr_log.log("debug", "Successfully started the puppet agent on the server " + str(server['id']))
                    self._provision_immediately_after_reimage = False
                else:
                    output = sshclient.exec_command(disable_puppet_svc_cmd)
                    output = sshclient.exec_command("puppet agent --disable")
                    output = sshclient.exec_command("service puppet stop")
                    self._smgr_log.log("debug", "Successfully stopped the puppet agent on the server " + str(server['id']))
                success = True
                sshclient.close()
            except Exception as e:
                if action == "start":
                    servers = self._serverDb.get_server({"id": server['id']}, detail=True)
                    server_state = servers[0]['status']
                    if server_state == "reimage_started" or server_state == "restart_issued" \
                       or server_state == "reimage_completed" or server_state == "provision_issued":
                        self._provision_immediately_after_reimage = True 
                if sshclient:
                    sshclient.close()
                self._smgr_log.log(self._smgr_log.ERROR, "Gevent SSH Connect Exception for server id: " + server['id'] + " Error : " + str(e))
            self._smgr_log.log(self._smgr_log.DEBUG, "Still trying to %s the puppet agent in the server %s, try %s" %(action, str(server["id"]), str(tries)))
            gevent.sleep(int(sm_args.puppet_agent_retry_poll_interval_seconds))
        if tries >= int(sm_args.puppet_agent_retry_count) and success is False:
            if action == "start":
                self._smgr_log.log(self._smgr_log.ERROR, "Starting the puppet agent failed on  " + str(server["id"]))
            else:
                self._smgr_log.log(self._smgr_log.ERROR, "Stopping the puppet agent failed on  " + str(server["id"]))
   
