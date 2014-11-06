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
from threading import Thread
from contrail_sm_monitoring.ipmi.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.ttypes import Module, NodeType
from sandesh_common.vns.constants import ModuleNames, NodeTypeNames, \
    Module2NodeType, INSTANCE_ID_DEFAULT
from sandesh_common.vns.constants import *
from server_mgr_mon_base_plugin import ServerMgrMonBasePlugin


class IpmiData:
    sensor = ''
    reading = ''
    status = ''
    unit = ''
    sensor_type = ''

# Class ServerMgrIPMIMonitoring provides a monitoring object that runs as a thread
# when Server Manager starts/restarts. This thread continually polls all the servers
# that are stored in the Server Manager DB at any point. Before this polling can occur,
# Server Manager opens a Sandesh Connection to the Analytics node that hosts the
# Database to which the monitor pushes device environment information.
class ServerMgrIPMIMonitoring(ServerMgrMonBasePlugin):

    def __init__(self, val, frequency, collectors_ip=None):
        ''' Constructor '''
        ServerMgrMonBasePlugin.__init__(self)
        self.base_obj = ServerMgrMonBasePlugin()
        self.val = val
        self.freq = float(frequency)
        self._serverDb = None
        self._collectors_ip = collectors_ip

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        self.base_obj.log("info", "Sending UVE Info over Sandesh")
        send_inst.send()

    # send_ipmi_stats function packages and sends the IPMI info gathered from server polling
    # to the analytics node
    def send_ipmi_stats(self, ipmi_data, hostname):
        sm_ipmi_info = SMIpmiInfo()
        sm_ipmi_info.name = str(hostname)
        sm_ipmi_info.sensor_stats = []
        sm_ipmi_info.sensor_state = []
        for ipmidata in ipmi_data:
            ipmi_stats = IpmiSensor()
            ipmi_stats.sensor = ipmidata.sensor
            ipmi_stats.reading = ipmidata.reading
            ipmi_stats.status = ipmidata.status
            ipmi_stats.unit = ipmidata.unit
            ipmi_stats.sensor_type = ipmidata.sensor_type
            sm_ipmi_info.sensor_stats.append(ipmi_stats)
            sm_ipmi_info.sensor_state.append(ipmi_stats)
        ipmi_stats_trace = SMIpmiInfoTrace(data=sm_ipmi_info)
        self.call_send(ipmi_stats_trace)

    # sandesh_init function opens a sandesh connection to the analytics node's ip
    # (this is recevied from Server Mgr's config or cluster config). The function is called only once.
    # For this node, a list of collector ips is passed to the sandesh init_generator.
    def sandesh_init(self, collectors_ip_list=None):
        try:
            self.base_obj.log("info", "Initializing sandesh")
            # storage node module initialization part
            module = Module.IPMI_STATS_MGR
            module_name = ModuleNames[module]
            node_type = Module2NodeType[module]
            node_type_name = NodeTypeNames[node_type]
            instance_id = INSTANCE_ID_DEFAULT
            if collectors_ip_list:
                self.base_obj.log("info", "Collector IPs from config: "+str(collectors_ip_list))
                collectors_ip_list = eval(collectors_ip_list)
                sandesh_global.init_generator(
                    module_name,
                    socket.gethostname(),
                    node_type_name,
                    instance_id,
                    collectors_ip_list,
                    module_name,
                    HttpPortIpmiStatsmgr,
                    ['contrail_sm_monitoring.ipmi'])
            else:
                raise ServerMgrException("Error during Sandesh Init: No collector ips or Discovery server/port given")
        except Exception as e:
            raise ServerMgrException("Error during Sandesh Init: " + str(e))

    def return_collector_ip(self):
        return self._collectors_ip
    # The Thread's run function continually checks the list of servers in the Server Mgr DB and polls them.
    # It then calls other functions to send the information to the correct analytics server.
    def run(self):
        print "Starting monitoring thread"
        self.base_obj.log("info", "Starting monitoring thread")
        ipmi_data = []
        supported_sensors = ['FAN|.*_FAN', '^PWR', 'CPU[0-9][" "].*', '.*_Temp', '.*_Power']
        while True:
            servers = self._serverDb.get_server(
                None, detail=True)
            ipmi_list = list()
            hostname_list = list()
            server_ip_list = list()
            data = ""
            sensor_type = None
            if self._collectors_ip:
                for server in servers:
                    server = dict(server)
                    if 'ipmi_address' in server:
                        ipmi_list.append(server['ipmi_address'])
                    if 'id' in server:
                        hostname_list.append(server['id'])
                    if 'ip_address' in server:
                        server_ip_list.append(server['ip_address'])
                self.base_obj.log("info", "Started IPMI Polling")
                for ip, hostname in zip(ipmi_list, hostname_list):
                    ipmi_data = []
                    cmd = 'ipmitool -H %s -U admin -P admin sdr list all' % ip
                    result = super(ServerMgrIPMIMonitoring, self).call_subprocess(cmd)
                    if result is not None:
                        fileoutput = cStringIO.StringIO(result)
                        for line in fileoutput:
                            reading = line.split("|")
                            sensor = reading[0].strip()
                            reading_value = reading[1].strip()
                            status = reading[2].strip()
                            for i in supported_sensors:
                                if re.search(i, sensor) is not None:
                                    if 'FAN' in sensor:
                                        sensor_type = 'fan'
                                    elif 'PWR' in sensor or 'Power' in sensor:
                                        sensor_type = 'power'
                                    elif 'Temp' in sensor:
                                        sensor_type = 'temperature'
                                    value = reading_value.split()
                                    ipmidata = IpmiData()
                                    ipmidata.sensor = sensor
                                    ipmidata.status = status
                                    if status == "ns":
                                        pass
                                    elif status == "ok":
                                        ipmidata.reading = long(value[0].strip())
                                        ipmidata.unit = value[len(value) - 1].strip()
                                        ipmidata.sensor_type = sensor_type
                                        ipmi_data.append(ipmidata)
                    else:
                        self.base_obj.log("info", "IPMI Polling failed for " + str(ip))
                    self.send_ipmi_stats(ipmi_data, hostname=hostname)
            else:
                self.base_obj.log("error", "IPMI Polling: No Analytics IP info found")

            self.base_obj.log("info", "Monitoring thread is sleeping for " + str(self.freq) + " seconds")
            time.sleep(self.freq)
            self.base_obj.log("info", "Monitoring thread woke up")

