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
from threading import Thread
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_ssh_client import ServerMgrSSHClient
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
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

_DEF_COLLECTORS_IP = None
_DEF_MON_FREQ = 300
_DEF_MONITORING_PLUGIN = None
_DEF_INVENTORY_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_DEF_INTROSPECT_PORT = 8107


class ServerMgrMonBasePlugin(Thread):
    val = 1
    freq = 300
    _dev_env_monitoring_obj = None
    _config_set = False
    _serverDb = None
    _monitoring_log = None
    _collectors_ip = None
    _discovery_server = None
    _discovery_port = None
    _default_ipmi_username = None
    _default_ipmi_password = None
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self):
        ''' Constructor '''
        Thread.__init__(self)
        self.MonitoringCfg = {
            'monitoring_frequency': _DEF_MON_FREQ,
            'monitoring_plugin': _DEF_MONITORING_PLUGIN
        }
        self.InventoryCfg = {
            'inventory_plugin': _DEF_INVENTORY_PLUGIN
        }
        self._smgr_log = ServerMgrlogger()

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

    def sandesh_init(self, collectors_ip_list=None):
        # Inventory node module initialization part
        try:
            self._smgr_log.log(self._smgr_log.INFO, "Initializing sandesh")
            collectors_ip_list = eval(collectors_ip_list)
            if collectors_ip_list:
                self._smgr_log.log(self._smgr_log.INFO, "Collector IPs from config: " + str(collectors_ip_list))
                monitoring = True
                inventory = True
                try:
                    __import__('contrail_sm_monitoring.monitoring')
                except ImportError:
                    monitoring = False
                    pass
                try:
                    __import__('inventory_daemon.server_inventory')
                except ImportError:
                    inventory = False
                    pass

                if monitoring and inventory:
                    module = Module.INVENTORY_AGENT
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
                        HttpPortInventorymgr,
                        ['inventory_daemon.server_inventory', 'contrail_sm_monitoring.monitoring'])
                elif inventory:
                    module = Module.INVENTORY_AGENT
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
                        HttpPortInventorymgr,
                        ['inventory_daemon.server_inventory'])
                elif monitoring:
                    module = Module.IPMI_STATS_MGR
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
                        HttpPortIpmiStatsmgr,
                        ['contrail_sm_monitoring.monitoring'])
            else:
                pass
        except Exception as e:
            raise ServerMgrException("Error during Sandesh Init: " + str(e))

    # call_subprocess function runs the IPMI command passed to it and returns the result
    def call_subprocess(self, cmd):
        times = datetime.datetime.now()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        while p.poll() is None:
            time.sleep(0.1)
            now = datetime.datetime.now()
            diff = now - times
            if diff.seconds > 3:
                os.kill(p.pid, signal.SIGKILL)
                os.waitpid(-1, os.WNOHANG)
                self._smgr_log.log(self._smgr_log.INFO, "command:" + cmd + " --> hanged")
                return None
        return p.stdout.read()

    def create_store_copy_ssh_keys(self, server_id, server_ip):

        # Create the Keys using Pycrypto
        ssh_key = paramiko.RSAKey.generate(bits=2048)
        ssh_private_key_obj = StringIO.StringIO()
        ssh_key.write_private_key(ssh_private_key_obj)

        try:
            # Save Public key on Target Server
            with open("/opt/contrail/server_manager/" + str(server_id) + ".pub", 'w+') as content_file:
                content_file.write("ssh-rsa " + str(ssh_key.get_base64()))
                content_file.close()
            ssh = ServerMgrSSHClient(self._serverDb)
            ssh.connect(server_ip, option="password")
            source_file = "/opt/contrail/server_manager/" + str(server_id) + ".pub"
            dest_file = "/root/.ssh/authorized_keys"
            ssh.exec_command("mkdir -p /root/.ssh/")
            ssh.exec_command("touch /root/.ssh/authorized_keys")
            ssh.copy(source_file, dest_file)
            os.remove(source_file)

            # Update Server table with ssh public and private keys
            update = {'id': server_id,
                      'ssh_public_key': "ssh-rsa " + str(ssh_key.get_base64()),
                      'ssh_private_key': ssh_private_key_obj.getvalue()}
            self._serverDb.modify_server(update)
            ssh.close()
            return ssh_key
        except Exception as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error Creating Keys: " + e.message)
            return None

    def populate_server_data_lists(self, servers, ipmi_list, hostname_list,
                                   server_ip_list, ipmi_username_list, ipmi_password_list):
        for server in servers:
            server = dict(server)
            if 'ssh_private_key' not in server and 'id' in server and 'ip_address' in server:
                self.create_store_copy_ssh_keys(server['id'], server['ip_address'])
            elif server['ssh_private_key'] is None and 'id' in server and 'ip_address' in server:
                self.create_store_copy_ssh_keys(server['id'], server['ip_address'])
            if 'ipmi_address' in server and server['ipmi_address'] \
                    and 'id' in server and server['id'] \
                    and 'ip_address' in server and server['ip_address'] \
                    and 'password' in server and server['password']:
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

    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self._smgr_log.log(self._smgr_log.INFO,
                           "No monitoring API has been configured. Server Environement Info will not be monitored.")
