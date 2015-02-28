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
from StringIO import StringIO
import pycurl
import requests
import json
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


# Class ServerMgrIPMIMonitoring provides a monitoring object that runs as a thread
# when Server Manager starts/restarts. This thread continually polls all the servers
# that are stored in the Server Manager DB at any point. Before this polling can occur,
# Server Manager opens a Sandesh Connection to the Analytics node that hosts the
# Database to which the monitor pushes device environment information.
class ServerMgrIPMIMonitoring(ServerMgrMonBasePlugin):
    def __init__(self, val, frequency, smgr_ip=None, smgr_port=None, collectors_ip=None):
        ''' Constructor '''
        ServerMgrMonBasePlugin.__init__(self)
        self.base_obj = ServerMgrMonBasePlugin()
        self.val = val
        self.smgr_ip = smgr_ip
        self.smgr_port = smgr_port
        self.freq = float(frequency)
        self._serverDb = None
        self._collectors_ip = collectors_ip

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        self.base_obj.log("info", "Sending UVE Info over Sandesh")
        send_inst.send()

    # send_ipmi_stats function packages and sends the IPMI info gathered from server polling
    # to the analytics node
    def send_ipmi_stats(self, ip, ipmi_data, hostname, data_type):
        sm_ipmi_info = SMIpmiInfo()
        sm_ipmi_info.name = str(hostname)
        cmd = 'mpstat'
        fileoutput = self.ssh_execute_cmd(ip, cmd)
        if fileoutput is not None:
            for line in fileoutput:
                res = re.sub('\s+', ' ', line).strip()
                arr = res.split()
                if len(arr) == 12:
                    if "%idle" in arr:
                        continue
                    else:
                        sm_ipmi_info.cpu_usage = 100.0 - float(arr[11])
        cmd = 'vmstat -s | grep "used memory"'
        fileoutput = self.ssh_execute_cmd(ip, cmd)
        if fileoutput is not None:
            for line in fileoutput:
                arr = line.split()
                sm_ipmi_info.mem_usage = int(arr[0])
        if data_type == "ipmi_data":
            sm_ipmi_info.sensor_stats = []
            sm_ipmi_info.sensor_state = []
            for ipmidata in ipmi_data:
                sm_ipmi_info.sensor_stats.append(ipmidata)
                sm_ipmi_info.sensor_state.append(ipmidata)
            self.base_obj.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            self.base_obj.log("info", "UVE Info = " + str(sm_ipmi_info))
        elif data_type == "ipmi_chassis_data":
            sm_ipmi_info.chassis_state = ipmi_data
        elif data_type == "disk_list":
            sm_ipmi_info.disk_usage_stats = []
            sm_ipmi_info.disk_usage_state = []
            for data in ipmi_data:
                sm_ipmi_info.disk_usage_stats.append(data)
                sm_ipmi_info.disk_usage_state.append(data)
            self.base_obj.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            self.base_obj.log("info", "UVE Info = " + str(sm_ipmi_info))
        ipmi_stats_trace = SMIpmiInfoTrace(data=sm_ipmi_info)
        self.call_send(ipmi_stats_trace)

    # Packages and sends a REST API call to the ServerManager node
    def send_run_inventory_request(self, ip, port, payload):
        try:
            url = "http://%s:%s/run_inventory" % (ip, port)
            payload = json.dumps(payload)
            headers = {'content-type': 'application/json'}
            resp = requests.post(url, headers=headers, timeout=5, data=payload)
            self.base_obj.log("info", "URL for Run Inv: " + str(url))
            self.base_obj.log("info", "Payload for Run Inv: " + str(payload))
            self.base_obj.log("info", "Got immediate reply: " + str(resp.text))
            return resp.text
        except Exception as e:
            self.base_obj.log("error", "Error running inventory on  " + str(payload) + " : " + str(e))
            return None

    def return_collector_ip(self):
        return self._collectors_ip

    def fetch_and_process_monitoring(self, hostname, ipmi, ip, username, password, supported_sensors):
        ipmi_data = []
        cmd = 'ipmitool -H %s -U %s -P %s sdr list all' % (ipmi, username, password)
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
                            ipmidata = IpmiSensor()
                            ipmidata.sensor = sensor
                            ipmidata.status = status
                            if status == "ns":
                                pass
                            elif status == "ok":
                                ipmidata.reading = long(value[0].strip())
                                ipmidata.unit = value[len(value) - 1].strip()
                                ipmidata.sensor_type = sensor_type
                                ipmi_data.append(ipmidata)
            except Exception as e:
                self.base_obj.log("error", "Error getting dev env data for " + str(hostname) + " : " + str(e.message))
                return False
            self.send_ipmi_stats(ip, ipmi_data, hostname, "ipmi_data")
            return True
        else:
            self.base_obj.log("error", "IPMI Polling failed for " + str(ip))
            return False

    def fetch_and_process_chassis(self, hostname, ip, username, password):
        ipmi_chassis_data = IpmiChassis_status_info()
        cmd = 'ipmitool -H %s -U %s -P %s chassis status' % (ip, username, password)
        try:
            result = super(ServerMgrIPMIMonitoring, self).call_subprocess(cmd)
            if result is not None:
                fileoutput = cStringIO.StringIO(result)
                ipmichassisdata = IpmiChassis_status_info()
                for line in fileoutput:
                    reading = line.split(":")
                    chassis_key = reading[0].strip()
                    chassis_value = reading[1].strip()
                    if chassis_key == "System Power":
                        ipmichassisdata.system_power = chassis_value
                    elif chassis_key == "Power Overload" and chassis_value:
                        ipmichassisdata.power_overload = bool(chassis_value)
                    elif chassis_key == "Power Interlock" and chassis_value:
                        ipmichassisdata.power_interlock = chassis_value
                    elif chassis_key == "Main Power Fault" and chassis_value:
                        ipmichassisdata.main_power_fault = bool(chassis_value)
                    elif chassis_key == "Power Control Fault" and chassis_value:
                        ipmichassisdata.power_control_fault = bool(chassis_value)
                    elif chassis_key == "Power Restore Policy" and chassis_value:
                        ipmichassisdata.power_restore_policy = chassis_value
                    elif chassis_key == "Last Power Event" and chassis_value:
                        ipmichassisdata.last_power_event = chassis_value
                    elif chassis_key == "Chassis Intrusion" and chassis_value:
                        ipmichassisdata.chassis_intrusion = chassis_value
                    elif chassis_key == "Front-Panel Lockout" and chassis_value:
                        ipmichassisdata.front_panel_lockout = chassis_value
                    elif chassis_key == "Drive Fault" and chassis_value:
                        ipmichassisdata.drive_fault = bool(chassis_value)
                    elif chassis_value:
                        ipmichassisdata.cooling_fan_fault = bool(chassis_value)
                ipmi_chassis_data = ipmichassisdata
            self.send_ipmi_stats(ip, ipmi_chassis_data, hostname, "ipmi_chassis_data")
        except Exception as e:
            self.base_obj.log("error", "Error getting chassis data for " + str(hostname) + " : " + str(e.message))
    
    def ssh_execute_cmd(self, ip, cmd):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username='root', key_filename="/root/.ssh/server_mgr_rsa", timeout=3)
            stdin, stdout, stderr = ssh.exec_command(cmd)
            if stdout is None:
                return None
            filestr = stdout.read()
            fileoutput = cStringIO.StringIO(filestr)
            return fileoutput
        except Exception as e:
            self.base_obj.log("error", "Error in SSH getting disk info for " + str(ip) + " : " + str(e))

    def fetch_and_process_disk_info(self, hostname, ip):
        disk_list = []
        cmd = 'iostat -m'
        try:
            fileoutput = self.ssh_execute_cmd(ip, cmd)
            if fileoutput is not None:
                for line in fileoutput:
                    if line is not None:
                        if line.find('sd') != -1 or line.find('dm') != -1:
                            self.base_obj.log("info", "LINE: " + line)
                            disk_data = Disk()
                            res = re.sub('\s+', ' ', line).strip()
                            arr = res.split()
                            disk_data.disk_name = arr[0]
                            disk_data.read_MB = int(arr[4])
                            disk_data.write_MB = int(arr[5])
                            disk_list.append(disk_data)
                if disk_list:
                    self.send_ipmi_stats(ip, disk_list, hostname, "disk_list")
                    return True
                else:
                    return False
        except Exception as e:
            self.base_obj.log("error", "Error getting disk info for " + str(hostname) + " : " + str(e))
            return False

    def fetch_and_process_sel_logs(self, hostname, ip, username, password, sel_event_log_list):
        sel_cmd = 'ipmitool -H %s -U %s -P %s sel elist' % (ip, username, password)
        sel_result = super(ServerMgrIPMIMonitoring, self).call_subprocess(sel_cmd)
        try:
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
                        # self.base_obj.log("info", "Sending UVE: " + str(sellog))
                        sellog.send()
                    else:
                        self.base_obj.log("info", "Log already sent for host " +
                                          str(hostname) + " and event " + str(event_id))
            return sel_event_log_list
        except Exception as e:
            self.base_obj.log("error", "Error getting SEL Logs for " + str(hostname) + " : " + str(e.message))

    def delete_monitoring_info(self, hostname_list):
        for hostname in hostname_list:
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.name = str(hostname)
            sm_ipmi_info.deleted = True
            sm_ipmi_info.sensor_state = None
            sm_ipmi_info.sensor_stats = None
            sm_ipmi_info.disk_usage_stats = None
            sm_ipmi_info.disk_usage_state = None
            sm_ipmi_info.cpu_usage = None
            sm_ipmi_info.mem_usage = None
            ipmi_stats_trace = ServerMonitoringInfoTrace(data=sm_ipmi_info)
            self.call_send(ipmi_stats_trace)

    def gevent_runner_func(self, hostname, ipmi, ip, username, password, supported_sensors, sel_log_dict):
        return_dict = dict()
        self.base_obj.log("info", "Gevent Thread created for %s" % ip)
        self.fetch_and_process_disk_info(hostname, ip)
        return_dict["ipmi_status"] = \
            self.fetch_and_process_monitoring(hostname, ipmi, ip, username, password, supported_sensors)
        self.fetch_and_process_chassis(hostname, ipmi, username, password)
        if str(hostname) in sel_log_dict:
            return_dict["sel_log"] = \
                self.fetch_and_process_sel_logs(hostname, ip, username, password, sel_log_dict[str(hostname)])
        else:
            return_dict["sel_log"] = self.fetch_and_process_sel_logs(hostname, ip, username, password, [])
        return return_dict

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
        ipmi_state = dict()
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
                self.base_obj.log("info", "Deleted servers: " + str(list(deleted_servers)))
                self.delete_monitoring_info(list(deleted_servers))
            self.base_obj.log("info", "Started IPMI Polling")
            gevent_threads = dict()
            for ipmi, ip, hostname, username, password in \
                    zip(ipmi_list, server_ip_list, hostname_list, ipmi_username_list, ipmi_password_list):
                thread = gevent.spawn(
                    self.gevent_runner_func, hostname, ipmi, ip, username, password, supported_sensors, sel_log_dict)
                gevent_threads[str(hostname)] = thread
            self.base_obj.log("info", "Monitoring thread is sleeping for " + str(self.freq) + " seconds")
            time.sleep(self.freq)
            self.base_obj.log("info", "Monitoring thread woke up")
            for hostname in gevent_threads:
                thread = gevent_threads[str(hostname)]
                if thread.successful():
                    return_dict = dict(thread.value)
                    if hostname in ipmi_state and not ipmi_state[str(hostname)] and return_dict["ipmi_status"]:
                        # Trigger REST API CALL to inventory for Server Hostname
                        payload = dict()
                        payload["id"] = str(hostname)
                        self.send_run_inventory_request(self.smgr_ip, self.smgr_port, payload=payload)
                    ipmi_state[str(hostname)] = return_dict["ipmi_status"]
                    sel_log_dict[str(hostname)] = return_dict["sel_log"]
                else:
                    self.base_obj.log("error", "Greenlet returned error: " + thread.get())

