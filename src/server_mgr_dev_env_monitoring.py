import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
import argparse
import ConfigParser
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import cStringIO
import re
import socket
import pdb
import server_mgr_db
from server_mgr_db import ServerMgrDb as db
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog
from threading import Thread
import discoveryclient.client as client
from ipmi.ipmi.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.ttypes import Module, NodeType
from sandesh_common.vns.constants import ModuleNames, NodeTypeNames, \
    Module2NodeType, INSTANCE_ID_DEFAULT
from sandesh_common.vns.constants import *

_DEF_ANALYTICS_IP = None
_DEF_MON_FREQ = 300
_DEF_PLUGIN_MODULE = None
_DEF_PLUGIN_CLASS = None
_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'

# Class ServerMgrDevEnvMonitoring provides a base class that can be inherited by
# any implementation of a plugabble monitoring API that interacts with the
# analytics node
class ServerMgrDevEnvMonitoring(Thread):

    val = 1
    freq = 300

    def __init__(self, val, frequency, serverdb, log, translog, analytics_ip=None):
        ''' Constructor '''
        Thread.__init__(self)
        if val:
            self.val = val
        if frequency:
            self.freq = float(frequency)
        self._serverDb = serverdb
        self._smgr_log = log
        self._smgr_trans_log = translog
        self._analytics_ip = analytics_ip

    def parse_args(self, args_str):
        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        MonitoringCfg = {
            'analytics_ip': _DEF_ANALYTICS_IP,
            'monitoring_freq': _DEF_MON_FREQ,
            'plugin_class': _DEF_PLUGIN_MODULE,
            'plugin_module': _DEF_PLUGIN_CLASS
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([args.config_file])
        for key in dict(config.items("MONITORING")).keys():
            if key in MonitoringCfg.keys():
                MonitoringCfg[key] = dict(config.items("MONITORING"))[key]
            else:
                self._smgr_log.log(self._smgr_log.DEBUG,
                                   "No configuration found for %s" % key)

        self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form monitoring config file %s" % MonitoringCfg)
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**MonitoringCfg)
        return parser.parse_args(remaining_argv)

    # sandesh_init function opens a sandesh connection to the analytics node's ip
    # (this is recevied from Server Mgr's config or cluster config). The function is called only once.
    # For this node, a discovery client is set up and passed to the sandesh init_generator.
    def sandesh_init(self, analytics_ip_list):
        try:
            self._smgr_log.log(self._smgr_log.INFO, "Initializing sandesh")
            # storage node module initialization part
            module = Module.IPMI_STATS_MGR
            module_name = ModuleNames[module]
            node_type = Module2NodeType[module]
            node_type_name = NodeTypeNames[node_type]
            instance_id = INSTANCE_ID_DEFAULT
            analytics_ip_set = set()
            for ip in analytics_ip_list:
                analytics_ip_set.add(ip)
            for analytics_ip in analytics_ip_set:
                _disc = client.DiscoveryClient(str(analytics_ip), '5998', module_name)
                sandesh_global.init_generator(
                    module_name,
                    socket.gethostname(),
                    node_type_name,
                    instance_id,
                    [],
                    module_name,
                    HttpPortIpmiStatsmgr,
                    ['ipmi.ipmi'],
                    _disc)
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
                syslog.syslog("command:" + cmd + " --> hanged")
                return None
        return p.stdout.read()

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        self._smgr_log.log(self._smgr_log.INFO, "Sending UVE Info over Sandesh")
        send_inst.send()

    # get_server_analytics_ip_list function returns the analytics ip of a particular cluster/server
    def get_server_analytics_ip_list(self, cluster_id):
        analytics_ip = []
        cluster = self._serverDb.get_cluster({"id": cluster_id}, detail=True)[0]
        cluster_params = eval(cluster['parameters'])
        if 'analytics_ip' in cluster_params and cluster_params['analytics_ip']:
            analytics_ip += eval(cluster_params['analytics_ip'])
            analytics_ip_list = set()
            for ip in analytics_ip:
                analytics_ip_list.add(ip)
        else:
            return None
        return analytics_ip_list

    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self._smgr_log.log(self._smgr_log.INFO,
                           "No monitoring API has been configured. Server Environement Info will not be monitored.")