import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
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


# Class ServerMgrDevEnvMonitoring provides a base class that can be inherited by
# any implementation of a plugabble monitoring API that interacts with the
# analytics node
class ServerMgrDevEnvMonitoring():
    def __init__(self, val, frequency, serverdb, log, translog, analytics_ip=None):
        ''' Constructor '''
        self.val = val
        self.freq = float(frequency)
        self._serverDb = serverdb
        self._smgr_log = log
        self._smgr_trans_log = translog
        self._analytics_ip = analytics_ip

    # sandesh_init function opens a sandesh connection to the analytics node's ip
    # (this is recevied from Server Mgr's config or cluster config). The function is called only once.
    # For this node, a discovery client is set up and passed to the sandesh init_generator.
    def sandesh_init(self):
        try:
            self._smgr_log.log(self._smgr_log.INFO, "Initializing sandesh")
            analytics_ip_list = list()
            if self._analytics_ip is not None:
                self._smgr_log.log(self._smgr_log.INFO, "Sandesh is connecting to " + str(self._analytics_ip))
                analytics_ip_list = eval(self._analytics_ip)
            else:
                servers = self._serverDb.get_server(None, detail=True)
                for server in servers:
                    server = dict(server)
                    if 'cluster_id' in server and self.get_server_analytics_ip_list(server['cluster_id']) is not None:
                        analytics_ip_list += self.get_server_analytics_ip_list(server['cluster_id'])
                if len(analytics_ip_list) == 0:
                    self._smgr_log.log(self._smgr_log.INFO, "No analytics IP found, Sandesh init aborted")
                    return 0
                else:
                    self._analytics_ip = analytics_ip_list
                    self._smgr_log.log(self._smgr_log.INFO, "Sandesh is connecting to " + str(self._analytics_ip))
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
        else:
            return None
        return analytics_ip