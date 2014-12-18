import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import gevent
import cStringIO
import re
import socket
import pdb
import paramiko
import math
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


    def return_collector_ip(self):
        return self._collectors_ip

    def fetch_and_process_monitoring(self, hostname, ip, username, password, supported_sensors):
        ipmi_data = []
        data = ""
        sensor_type = None
        cmd = 'ipmitool -H %s -U %s -P %s sdr list all' % (ip, username, password)
        result = super(ServerMgrIPMIMonitoring, self).call_subprocess(cmd)
        if result is not None and "|" in result:
            fileoutput = cStringIO.StringIO(result)
            try:
                for line in fileoutput:
                    reading = line.split("|")
                    sensor = reading[0].strip()
                    reading_value = reading[1].strip()
                    status = reading[2].strip()
                    for i in supported_sensors:
                        if re.search(i, sensor) is not None:
                            sensor_type = 'unknown'
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
            except ValueError:
                pass
        else:
            self.base_obj.log("info", "IPMI Polling failed for " + str(ip))
        self.send_ipmi_stats(ipmi_data, hostname=hostname)


    def fetch_and_process_sel_logs(self, hostname, ip, username, password, sel_event_log_list):
        sel_cmd = 'ipmitool -H %s -U %s -P %s sel elist' % (ip, username, password)
        sel_result = super(ServerMgrIPMIMonitoring, self).call_subprocess(sel_cmd)
        if sel_result is not None:
            fileoutput = cStringIO.StringIO(sel_result)
            for line in fileoutput:
                sellog = IpmiSystemEventLog()
                sellog.name = str(hostname)
                col = line.split("|")
                hex_event_id = col[0]
                event_id = int(hex_event_id, 16)
                if event_id not in sel_event_log_list:
                    sel_event_log_list.append(event_id)
                    sellog.event_id = event_id
                    sellog.ipmi_timestamp = str(col[1]) + " " + str(col[2])
                    sensor_data = str(col[3])
                    sensor_data = sensor_data.split(" ")
                    sellog.sensor_type = str(sensor_data[1]) + " " + str(sensor_data[2])
                    sellog.sensor_name = str(sensor_data[3])
                    if len(sensor_data) >= 5:
                        sellog.sensor_name += " " + str(sensor_data[4])
                    sellog.ipmi_message = str(col[4])
                    if len(col) >= 6:
                        sellog.ipmi_message += " " + str(col[5])
                    self.base_obj.log("info", "Sending UVE: " + str(sellog))
                    # import pdb; pdb.set_trace()
                    sellog.send()
                else:
                    self.base_obj.log("info", "Log already sent for " + str(event_id))
        return sel_event_log_list

    def delete_monitoring_info(self, hostname_list):
        for hostname in hostname_list:
            sm_ipmi_info = SMIpmiInfo()
            sm_ipmi_info.name = str(hostname)
            ipmi_stats_trace = SMIpmiInfoTrace(data=sm_ipmi_info)
            self.call_send(ipmi_stats_trace)

    def gevent_runner_func(self, hostname, ip, username, password, supported_sensors, sel_log_dict):
        self.base_obj.log("info", "Gevent Thread created for %s" % ip)
        self.fetch_and_process_monitoring(hostname, ip, username, password, supported_sensors)
        if str(hostname) in sel_log_dict:
            return self.fetch_and_process_sel_logs(hostname, ip, username, password, sel_log_dict[str(hostname)])
        else:
            return self.fetch_and_process_sel_logs(hostname, ip, username, password, [])

    # The Thread's run function continually checks the list of servers in the Server Mgr DB and polls them.
    # It then calls other functions to send the information to the correct analytics server.
    def run(self):
        print "Starting monitoring thread"
        self.base_obj.log("info", "Starting monitoring thread")
        ipmi_data = []
        sel_log_dict = dict()
        ipmi_list = list()
        hostname_list = list()
        server_ip_list = list()
        ipmi_username_list = list()
        ipmi_password_list = list()
        supported_sensors = ['FAN|.*_FAN', '^PWR', 'CPU[0-9][" "].*', '.*_Temp', '.*_Power']
        while True:
            servers = self._serverDb.get_server(
                None, detail=True)
            old_server_set = set(hostname_list)
            del ipmi_list[:]
            del hostname_list[:]
            del server_ip_list[:]
            del ipmi_username_list[:]
            del ipmi_password_list[:]
            self.base_obj.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list,
                                                     ipmi_username_list, ipmi_password_list, [])
            new_server_set = set(hostname_list)
            deleted_servers = set(old_server_set.difference(new_server_set))
            if len(deleted_servers) > 0:
                self.base_obj.log("info", "Deleting monitoring info of certain servers that have been removed")
                self.delete_monitoring_info(list(deleted_servers))
            self.base_obj.log("info", "Started IPMI Polling")
            gevent_threads = []
            for ip, hostname, username, password in \
                    zip(ipmi_list, hostname_list, ipmi_username_list, ipmi_password_list):
                thread = gevent.spawn(
                    self.gevent_runner_func, hostname, ip, username, password, supported_sensors, sel_log_dict)
                sel_log_dict[str(hostname)] = thread.value
                gevent_threads.append(thread)
            gevent.joinall(gevent_threads)
            self.base_obj.log("info", "Monitoring thread is sleeping for " + str(self.freq) + " seconds")
            time.sleep(self.freq)
            self.base_obj.log("info", "Monitoring thread woke up")
