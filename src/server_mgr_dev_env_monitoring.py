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
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog
from threading import Thread
import discoveryclient.client as client
from ipmistats.sandesh.ipmi.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.ttypes import Module, NodeType
from sandesh_common.vns.constants import ModuleNames, NodeTypeNames, \
    Module2NodeType, INSTANCE_ID_DEFAULT
from sandesh_common.vns.constants import *

# Signal handler function. Exit on CTRL-C
def exit_gracefully(signal, frame):
    #Perform any cleanup actions in the logging system
    print "Exit"
    sys.exit(0)


class IpmiData:
    sensor = ''
    reading = ''
    status = ''

'''
Class ServerMgrDevEnvMonitoring provides a monitoring object that runs as a thread
when Server Manager starts/restarts. This thread continually polls all the servers
that are stored in the Server Manager DB at any point. Before this polling can occur,
Server Manager opens a Sandesh Connection to the Analytics node that hosts the
Database to which the monitor pushes device environment information.
'''
class ServerMgrDevEnvMonitoring(Thread):
    def __init__(self, val, frequency, serverdb, log, translog):
        ''' Constructor '''
        Thread.__init__(self)
        self.val = val
        self.freq = frequency
        self._serverDb = serverdb
        self._smgr_log = log
        self._smgr_trans_log = translog

    '''
    sandesh_init function opens a sandesh connection to the analytics node's ip
    (this is recevied from Server Mgr's config or cluster config). The function is called only once.
    For this node, a discovery client is set up and passed to the sandesh init_generator.
    '''
    def sandesh_init(self):
        servers = self._serverDb.get_server(None, detail=True)
        self._smgr_log.log(self._smgr_log.INFO, "Initializing sandesh")
        analytics_ip_list = list()
        hostname_list = list()
        for server in servers:
            server = dict(server)
            if 'id' in server and self.get_server_analytics_ip_list(server['id']) is not None:
                analytics_ip_list += self.get_server_analytics_ip_list(server['id'])
                hostname_list.append(server['id'])
        #storage node module initialization part
        module = Module.IPMI_STATS_MGR
        module_name = ModuleNames[module]
        node_type = Module2NodeType[module]
        node_type_name = NodeTypeNames[node_type]
        instance_id = INSTANCE_ID_DEFAULT
        analytics_ip_set = set()
        for ip in analytics_ip_list:
            analytics_ip_set.add(ip)
        for analytics_ip, hostname in zip(analytics_ip_set, hostname_list):
            _disc = client.DiscoveryClient(str(analytics_ip), '5998', module_name)
            sandesh_global.init_generator(
                module_name,
                str(hostname),
                node_type_name,
                instance_id,
                [],
                module_name,
                HttpPortIpmiStatsmgr,
                ['ipmistats.sandesh.ipmi'],
                _disc)
        return analytics_ip_list

    '''
    call_subprocess function runs the IPMI command passed to it and returns the result
    '''
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

    '''
    call_send function is the sending function of the sandesh object (send_inst)
    '''
    def call_send(self, send_inst):
        self._smgr_log.log(self._smgr_log.INFO, "Sending UVE Info over Sandesh")
        send_inst.send()

    '''
    send_ipmi_stats function packages and sends the IPMI info gathered from server polling
    to the analytics node
    '''
    def send_ipmi_stats(self, ipmi_data, hostname):
        sm_ipmi_info = SMIpmiInfo()
        sm_ipmi_info.name = str(hostname)
        sm_ipmi_info.sensor_stats = []
        sm_ipmi_info.sensor_status = []
        for ipmidata in ipmi_data:
            ipmi_stats = IpmiSensor()
            ipmi_stats.sensor = ipmidata.sensor
            ipmi_stats.reading = ipmidata.reading
            ipmi_stats.status = ipmidata.status
            sm_ipmi_info.sensor_stats.append(ipmi_stats)
            sm_ipmi_info.sensor_status.append(ipmi_stats)
        ipmi_stats_trace = SMIpmiInfoTrace(data=sm_ipmi_info)
        self.call_send(ipmi_stats_trace)

    '''
    get_server_analytics_ip_list function returns the analytics ip of a particular cluster/server
    '''
    def get_server_analytics_ip_list(self, server_id):
        match_dict = {'id': server_id}
        server = self._serverDb.get_server(
            match_dict, detail=True)[0]
        server = dict(server)
        analytics_ip = []
        cluster = self._serverDb.get_cluster({"id": server['cluster_id']}, detail=True)[0]
        cluster_params = eval(cluster['parameters'])
        server_params = eval(server['parameters'])
        if 'analytics_ip' in server_params and server_params['analytics_ip']:
            analytics_ip.append(server_params['analytics_ip'])
        elif 'analytics_ip' in cluster_params and cluster_params['analytics_ip']:
            analytics_ip.append(cluster_params['analytics_ip'])
        else:
            return None
        return analytics_ip

    '''
    The Thread's run function continually checks the list of servers in the Server Mgr DB and polls them.
    It then calls other functions to send the information to the correct analytics server.
    '''
    def run(self):
        print "Starting monitoring thread"
        self._smgr_log.log(self._smgr_log.INFO, "Starting monitoring thread")
        ipmi_data = []
        supported_sensors = ['FAN|.*_FAN', '^PWR', 'CPU[0-9][" "].*', '.*_Temp', '.*_Power']
        while True:
            servers = self._serverDb.get_server(
                None, detail=True)
            ipmi_list = list()
            hostname_list = list()
            server_ip_list = list()
            data = ""
            for x in servers:
                x = dict(x)
                if 'ipmi_address' in x:
                    ipmi_list.append(x['ipmi_address'])
                if 'id' in x:
                    hostname_list.append(x['id'])
                if 'ip_address' in x:
                    server_ip_list.append(x['ip_address'])
            for ip, hostname in zip(ipmi_list, hostname_list):
                ipmi_data = []
                cmd = 'ipmitool -H %s -U admin -P admin sdr list all' % ip
                result = self.call_subprocess(cmd)
                if result is not None:
                    self._smgr_trans_log.log("IPMI Polling: " + str(ip), self._smgr_trans_log.SMGR_POLL_DEV, True)
                    fileoutput = cStringIO.StringIO(result)
                    for line in fileoutput:
                        reading = line.split("|")
                        sensor = reading[0].strip()
                        reading_value = reading[1].strip()
                        status = reading[2].strip()
                        for i in supported_sensors:
                            if re.search(i, sensor) is not None:
                                ipmidata = IpmiData()
                                ipmidata.sensor = sensor
                                ipmidata.reading = reading_value
                                ipmidata.status = status
                                ipmi_data.append(ipmidata)
                            else:
                                self._smgr_trans_log.log(
                                    "IPMI Polling: " + str(ip), self._smgr_trans_log.SMGR_POLL_DEV, False)
                                self._smgr_log.log(self._smgr_log.ERROR,
                                                   "IPMI Polling: Missing Sensor Info for " + str(ip))
                else:
                    self._smgr_trans_log.log("IPMI Polling: " + str(ip), self._smgr_trans_log.SMGR_POLL_DEV, False)
                self.send_ipmi_stats(ipmi_data, hostname=hostname)
            self._smgr_log.log(self._smgr_log.INFO, "Monitoring thread is sleeping for " + self.freq + " seconds")
            time.sleep(self.freq)
            self._smgr_log.log(self._smgr_log.INFO, "Monitoring thread woke up")
