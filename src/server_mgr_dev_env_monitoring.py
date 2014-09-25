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


class ServerMgrDevEnvMonitoring(Thread):
    def __init__(self, val, frequency, serverDb):
        ''' Constructor '''
        Thread.__init__(self)
        self.val = val
        self.freq = frequency
        self._serverDb = serverDb

    def sandesh_init(self):
        servers = self._serverDb.get_server(None, detail=True)
        collector_addr_list = list()
        hostname_list = list()
        for x in servers:
            x = dict(x)
            if 'roles' in x:
                roles_list = eval(x['roles'])
                if 'collector' in roles_list:
                    collector_addr_list.append(x['ip_address'])
                    hostname_list.append(x['id'])
        #storage node module initialization part
        module = Module.IPMI_STATS_MGR
        module_name = ModuleNames[module]
        node_type = Module2NodeType[module]
        node_type_name = NodeTypeNames[node_type]
        instance_id = INSTANCE_ID_DEFAULT
        print "Initializing SANDESH"
        print collector_addr_list
        print hostname_list
        for ip, hostname in zip(collector_addr_list, hostname_list):
            _disc = client.DiscoveryClient(str(ip), '5998', module_name)
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
        return str(collector_addr_list[0])

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

    def call_send(self, send_inst):
        #sys.stderr.write('sending UVE:' + str(send_inst))
        send_inst.send()

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

    def run(self):
        print "Run thread started"
        ipmi_data = []
        i = True
        supported_sensors = ['FAN|.*_FAN', '^PWR', 'CPU[0-9][" "].*', '.*_Temp', '.*_Power']
        while i:
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
            print ipmi_list
            print hostname_list
            for ip, hostname in zip(ipmi_list, hostname_list):
                ipmi_data = []
                cmd = 'ipmitool -H %s -U admin -P admin sdr list all' % ip
                print cmd
                result = self.call_subprocess(cmd)
                if result is not None:
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
                self.send_ipmi_stats(ipmi_data, hostname=hostname)
            time.sleep(self.freq)
