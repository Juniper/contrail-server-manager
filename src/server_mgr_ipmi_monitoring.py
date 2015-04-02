#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_ipmi_monitoring.py
   Author : Nitish Krishna
   Description : TBD
"""

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
import paramiko.channel
import xmltodict
import inspect
import math
from server_mgr_db import ServerMgrDb as db
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_ssh_client import ServerMgrSSHClient
from threading import Thread
import logging
import logging.config
import logging.handlers
from contrail_sm_monitoring.monitoring.ttypes import *
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
class ServerMgrIPMIMonitoring():
    types_list = ["sensor_state", "chassis_state", "disk_usage_state", "network_info_state", "resource_info_state"]
    sub_types_list = ["fan", "temperature", "power"]
    _default_ipmi_username = None
    _default_ipmi_password = None
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"
    _serverDb = None

    def __init__(self, val, frequency, smgr_ip=None, smgr_port=None, collectors_ip=None, introspect_port=None,
                 rev_tags_dict=None):
        ''' Constructor '''
        self.base_obj = ServerMgrMonBasePlugin()
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._monitoring_log = logging.getLogger('MONITORING')
        self.val = val
        self.smgr_ip = smgr_ip
        self.smgr_port = smgr_port
        self.introspect_port = introspect_port
        self.freq = float(frequency)
        self._collectors_ip = collectors_ip
        self.rev_tags_dict = rev_tags_dict

    def log(self, level, msg):
        frame, filename, line_number, function_name, lines, index = inspect.stack()[1]
        log_dict = dict()
        log_dict['log_frame'] = frame
        log_dict['log_filename'] = os.path.basename(filename)
        log_dict['log_line_number'] = line_number
        log_dict['log_function_name'] = function_name
        log_dict['log_line'] = lines
        log_dict['log_index'] = index
        try:
            if level == self.DEBUG:
                self._monitoring_log.debug(msg, extra=log_dict)
            elif level == self.INFO:
                self._monitoring_log.info(msg, extra=log_dict)
            elif level == self.WARN:
                self._monitoring_log.warn(msg, extra=log_dict)
            elif level == self.ERROR:
                self._monitoring_log.error(msg, extra=log_dict)
            elif level == self.CRITICAL:
                self._monitoring_log.critical(msg, extra=log_dict)
        except Exception as e:
            print "Error logging msg in Mon" + e.message

    def set_serverdb(self, server_db):
        self._serverDb = server_db
        self.base_obj.set_serverdb(server_db=server_db)

    def set_ipmi_defaults(self, ipmi_username, ipmi_password):
        self._default_ipmi_username = ipmi_username
        self._default_ipmi_password = ipmi_password
        self.base_obj.set_ipmi_defaults(ipmi_username, ipmi_password)

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        self.log("info", "Sending UVE Info over Sandesh")
        send_inst.send()

    # send_ipmi_stats function packages and sends the IPMI info gathered from server polling
    # to the analytics node
    def send_ipmi_stats(self, ip, ipmi_data, hostname, data_type):
        sm_ipmi_info = ServerMonitoringInfo()
        sm_ipmi_info.name = str(hostname)
        if data_type == "ipmi_data":
            sm_ipmi_info.sensor_stats = []
            sm_ipmi_info.sensor_state = []
            for ipmidata in ipmi_data:
                sm_ipmi_info.sensor_stats.append(ipmidata)
                sm_ipmi_info.sensor_state.append(ipmidata)
            self.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            self.log("info", "UVE Info = " + str(sm_ipmi_info))
        elif data_type == "ipmi_chassis_data":
            sm_ipmi_info.chassis_state = ipmi_data
        elif data_type == "disk_list":
            sm_ipmi_info.disk_usage_stats = []
            sm_ipmi_info.disk_usage_state = []
            for data in ipmi_data:
                sm_ipmi_info.disk_usage_stats.append(data)
                sm_ipmi_info.disk_usage_state.append(data)
            self.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            self.log("info", "UVE Info = " + str(sm_ipmi_info))
        elif data_type == "resource_info":
            sm_ipmi_info.resource_info_state = ipmi_data
        elif data_type == "resource_info_list":
            sm_ipmi_info.resource_info_stats = []
            for data in ipmi_data:
                sm_ipmi_info.resource_info_stats.append(data)
        elif data_type == "network_info":
            sm_ipmi_info.network_info_stats = []
            sm_ipmi_info.network_info_state = []
            for data in ipmi_data:
                sm_ipmi_info.network_info_stats.append(data)
                sm_ipmi_info.network_info_state.append(data)
            self.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            self.log("info", "UVE Interface Info = " + str(sm_ipmi_info))
        ipmi_stats_trace = ServerMonitoringInfoUve(data=sm_ipmi_info)
        self.call_send(ipmi_stats_trace)

    # Packages and sends a REST API call to the ServerManager node
    def send_run_inventory_request(self, ip, port, payload):
        try:
            url = "http://%s:%s/run_inventory" % (ip, port)
            payload = json.dumps(payload)
            headers = {'content-type': 'application/json'}
            resp = requests.post(url, headers=headers, timeout=5, data=payload)
            self.log("info", "URL for Run Inv: " + str(url))
            self.log("info", "Payload for Run Inv: " + str(payload))
            self.log("info", "Got immediate reply: " + str(resp.text))
            return resp.text
        except Exception as e:
            self.log("error", "Error running inventory on  " + str(payload) + " : " + str(e))
            return None

    def return_collector_ip(self):
        return self._collectors_ip

    def fetch_and_process_monitoring(self, hostname, ipmi, ip, username, password, supported_sensors):
        ipmi_data = []
        cmd = 'ipmitool -H %s -U %s -P %s sdr list all' % (ipmi, username, password)
        result = self.base_obj.call_subprocess(cmd)
        if result is not None and "|" in result:
            fileoutput = cStringIO.StringIO(result)
            try:
                for line in fileoutput:
                    reading = line.split("|")
                    sensor = reading[0].strip()
                    reading_value = reading[1].strip()
                    status = reading[2].strip()
                    for i in supported_sensors:
                        if re.search(i, sensor, re.IGNORECASE) is not None:
                            sensor_type = 'unknown'
                            if 'FAN' in sensor or 'fan' in sensor or 'Fan' in sensor:
                                sensor_type = 'fan'
                            elif 'PWR' in sensor or 'Power' in sensor:
                                sensor_type = 'power'
                            elif 'Temp' in sensor or 'TEMP' in sensor or 'temp' in sensor:
                                sensor_type = 'temperature'
                            value = reading_value.split()
                            ipmidata = IpmiSensor()
                            ipmidata.sensor = sensor
                            ipmidata.status = status
                            if status == "ns":
                                pass
                            elif status == "ok" and value[len(value) - 1].strip() != '0x00':
                                ipmidata.reading = long(value[0].strip())
                                ipmidata.unit = value[len(value) - 1].strip()
                                ipmidata.sensor_type = sensor_type
                                ipmi_data.append(ipmidata)
            except Exception as e:
                self.log("error", "Error getting dev env data for " + str(hostname) + " : " + str(e.message))
                return False
            self.send_ipmi_stats(ip, ipmi_data, hostname, "ipmi_data")
            return True
        else:
            self.log("error", "IPMI Polling failed for " + str(ip))
            return False

    def fetch_and_process_chassis(self, hostname, ipmi, ip, username, password):
        ipmi_chassis_data = IpmiChassis_status_info()
        cmd = 'ipmitool -H %s -U %s -P %s chassis status' % (ipmi, username, password)
        try:
            result = self.base_obj.call_subprocess(cmd)
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
            self.log("error", "Error getting chassis data for " + str(hostname) + " : " + str(e.message))

    def fetch_and_process_disk_info(self, hostname, ip, sshclient):
        disk_list = []
        cmd = 'iostat -m'

        is_sysstat = sshclient.exec_command('which iostat')
        if not is_sysstat:
            self.log("info", "sysstat package not installed on " + str(ip))
            disk_data = Disk()
            disk_data.disk_name = "N/A"
            disk_data.read_MB = int(0)
            disk_data.write_MB = int(0)
            disk_list.append(disk_data)
            self.send_ipmi_stats(ip, disk_list, hostname, "disk_list")
        else:
            try:
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    for line in fileoutput:
                        if line is not None:
                            if line.find('sd') != -1 or line.find('dm') != -1:
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
                self.log("error", "Error getting disk info for " + str(hostname) + " : " + str(e))
                return False

    def fetch_and_process_resource_info(self, hostname, ip, sshclient):
        try:
            resource_info_list = []
            resource_info1 = resource_info()
            is_mpstat = sshclient.exec_command('which mpstat')
            if not is_mpstat:
                resource_info1.cpu_usage_percentage = 0.0
            else:
                cmd = 'mpstat'
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    for line in fileoutput:
                        res = re.sub('\s+', ' ', line).strip()
                        arr = res.split()
                        if len(arr) == 12:
                            if "%idle" in arr:
                                continue
                            else:
                                resource_info1.cpu_usage_percentage = (100.0 - float(arr[11]))
            is_vmstat = sshclient.exec_command('which vmstat')
            if not is_vmstat:
                resource_info1.mem_usage_mb = 0
                resource_info1.mem_usage_percent = 0
            else:
                cmd = 'vmstat -s | grep "used memory"'
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    for line in fileoutput:
                        arr = line.split()
                        resource_info1.mem_usage_mb = int(int(arr[0])/1024)
                cmd = 'vmstat -s | grep "total memory"'
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    for line in fileoutput:
                        arr = line.split()
                        resource_info1.mem_usage_percent = float("{0:.2f}".format(
                            (resource_info1.mem_usage_mb/float(int(arr[0])/1024))*100))
                resource_info_list.append(resource_info1)
            self.send_ipmi_stats(ip, resource_info_list, hostname, "resource_info_list")
            self.send_ipmi_stats(ip, resource_info1, hostname, "resource_info")
        except Exception as e:
            self.log("error", "Error in getting resource info for  " + str(hostname) + str(e))

    def fetch_and_process_network_info(self, hostname, ip, sshclient):
        try:
            intinfo_list = []
            result = sshclient.exec_command("ls /sys/class/net/")
            if result:
                output = cStringIO.StringIO(result)
                for line in output:
                    intinfo = network_info()
                    cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/tx_bytes"
                    tx_bytes = sshclient.exec_command(cmd=cmd)
                    cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/tx_packets"
                    tx_packets = sshclient.exec_command(cmd=cmd)
                    cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/rx_bytes"
                    rx_bytes = sshclient.exec_command(cmd=cmd)
                    cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/rx_packets"
                    rx_packets = sshclient.exec_command(cmd=cmd)
                    intinfo.interface_name = line.rstrip()
                    intinfo.tx_bytes = int(tx_bytes.rstrip())
                    intinfo.tx_packets = int(tx_packets.rstrip())
                    intinfo.rx_bytes = int(rx_bytes.rstrip())
                    intinfo.rx_packets = int(rx_packets.rstrip())
                    intinfo_list.append(intinfo)
            self.send_ipmi_stats(ip, intinfo_list, hostname, "network_info")
        except Exception as e:
            self.log("error", "Error in getting network info for " + str(hostname) + str(e))

    def fetch_and_process_sel_logs(self, hostname, ip, username, password, sel_event_log_list):
        sel_cmd = 'ipmitool -H %s -U %s -P %s sel elist' % (ip, username, password)
        sel_result = self.base_obj.call_subprocess(sel_cmd)
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
                        # self.log("info", "Sending UVE: " + str(sellog))
                        sellog.send()
                    else:
                        self.log("info", "Log already sent for host " +
                                 str(hostname) + " and event " + str(event_id))
            return sel_event_log_list
        except Exception as e:
            self.log("error", "Error getting SEL Logs for " + str(hostname) + " : " + str(e.message))

    def delete_monitoring_info(self, hostname_list):
        for hostname in hostname_list:
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.name = str(hostname)
            sm_ipmi_info.deleted = True
            sm_ipmi_info.sensor_state = None
            sm_ipmi_info.sensor_stats = None
            sm_ipmi_info.disk_usage_stats = None
            sm_ipmi_info.disk_usage_state = None
            ipmi_stats_trace = ServerMonitoringInfoUve(data=sm_ipmi_info)
            self.call_send(ipmi_stats_trace)

    def gevent_runner_func(self, hostname, ipmi, ip, username, password, supported_sensors, ipmi_state,
                           sel_event_log_list, option="key"):
        return_dict = dict()
        self.log("info", "Gevent Thread created for %s" % ip)
        try:
            sshclient = ServerMgrSSHClient(serverdb=self._serverDb)
            sshclient.connect(ip, option)
            self.fetch_and_process_resource_info(hostname, ip, sshclient)
            self.fetch_and_process_network_info(hostname, ip, sshclient)
            self.fetch_and_process_disk_info(hostname, ip, sshclient)
            return_dict["ipmi_status"] = \
                self.fetch_and_process_monitoring(hostname, ipmi, ip, username, password, supported_sensors)
            self.fetch_and_process_chassis(hostname, ipmi, ip, username, password)
            if sel_event_log_list:
                return_dict["sel_log"] = \
                    self.fetch_and_process_sel_logs(hostname, ipmi, username, password, sel_event_log_list)
            else:
                return_dict["sel_log"] = self.fetch_and_process_sel_logs(hostname, ipmi, username, password, [])
            if not ipmi_state and return_dict["ipmi_status"]:
                # Trigger REST API CALL to inventory for Server Hostname
                payload = dict()
                payload["id"] = str(hostname)
                self.send_run_inventory_request(self.smgr_ip, self.smgr_port, payload=payload)
            sshclient.close()
            return return_dict
        except Exception as e:
            self.log("error", "Gevent SSH Connect Execption for server id: " + str(hostname) + " Error : " + e.message)
            pass

    # ####### MONITORING GET INFO SECTION ###########

    def convert_type(self, field_dict):
        data_type = field_dict["@type"]
        if "#text" in field_dict:
            if data_type == "bool":
                return json.loads(field_dict["#text"])
            elif data_type == "double":
                return float(field_dict["#text"])
            elif data_type == "u64":
                return int(field_dict["#text"])
            else:
                return str(field_dict["#text"])
        else:
            return "N/A"

    # Filters the data returned from REST API call for requested information
    def filter_sensor_results(self, xml_dict, key):
        return_sensor_list = []
        server_sensor_list = \
            xml_dict["data"]["ServerMonitoringInfo"]["sensor_state"]["list"]["IpmiSensor"]
        if isinstance(server_sensor_list, list):
            for sensor in server_sensor_list:
                res_sensor = dict()
                sensor = dict(sensor)
                if key == "all" or key == sensor["sensor_type"]["#text"]:
                    for field in sensor:
                        res_sensor[field] = self.convert_type(dict(sensor[field]))
                    return_sensor_list.append(res_sensor)
        elif isinstance(server_sensor_list, dict):
            res_sensor = dict()
            sensor = server_sensor_list
            for field in sensor:
                res_sensor[field] = self.convert_type(dict(sensor[field]))
            return_sensor_list.append(res_sensor)
        return return_sensor_list

    def filter_chassis_results(self, xml_dict):
        server_chassis_info_dict = dict()
        server_chassis_info_xml = \
            dict(xml_dict["data"]["ServerMonitoringInfo"]["chassis_state"]["IpmiChassis_status_info"])
        for chassis_key in server_chassis_info_xml:
            server_chassis_info_dict[chassis_key] = self.convert_type(dict(server_chassis_info_xml[chassis_key]))
        return server_chassis_info_dict

    def filter_disk_results(self, xml_dict):
        return_disk_list = []
        server_disk_list = \
            xml_dict["data"]["ServerMonitoringInfo"]["disk_usage_state"]["list"]["Disk"]
        if isinstance(server_disk_list, list):
            for disk in server_disk_list:
                res_disk = dict()
                disk = dict(disk)
                for key in disk:
                    res_disk[key] = self.convert_type(dict(disk[key]))
                return_disk_list.append(res_disk)
        elif isinstance(server_disk_list, dict):
            res_disk = dict()
            disk = server_disk_list
            for key in disk:
                res_disk[key] = self.convert_type(dict(disk[key]))
            return_disk_list.append(res_disk)
        return return_disk_list

    def filter_network_info_results(self, xml_dict):
        return_intf_list = []
        server_intf_list = xml_dict["data"]["ServerMonitoringInfo"]["network_info_state"]["list"]["network_info"]
        if isinstance(server_intf_list, list):
            for intf in server_intf_list:
                res_intf = dict()
                intf = dict(intf)
                for key in intf:
                    res_intf[key] = self.convert_type(dict(intf[key]))
                return_intf_list.append(res_intf)
        elif isinstance(server_intf_list, dict):
            res_intf = dict()
            intf = server_intf_list
            for key in intf:
                res_intf[key] = self.convert_type(dict(intf[key]))
            return_intf_list.append(res_intf)
        return return_intf_list

    def filter_resource_info_results(self, xml_dict):
        server_res_info_dict = dict()
        server_res_info_xml = \
            dict(xml_dict["data"]["ServerMonitoringInfo"]["resource_info_state"]["resource_info"])
        for res_key in server_res_info_xml:
            server_res_info_dict[res_key] = self.convert_type(dict(server_res_info_xml[res_key]))
        return server_res_info_dict

    def filter_global_results(self, xml_dict):
        return_dict = dict()
        global_dict = xml_dict["data"]["ServerMonitoringInfo"]
        for key in global_dict:
            if key not in self.types_list:
                return_dict[key] = self.convert_type(dict(global_dict[key]))
        return return_dict

    def get_mon_conf_details(self):
        return "Configuration for Monitoring set correctly."

    def get_monitoring_info(self):
        list_return_dict = list()
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        server_cluster_list = list()
        server_tag_dict_list = list()
        self.log("debug", "get_monitoring_info")
        try:
            entity = bottle.request
            ret_data = self.base_obj.validate_rest_api_args(entity, self.rev_tags_dict, self.types_list,
                                                            self.sub_types_list)
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self.base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            if match_dict.keys():
                servers = self._serverDb.get_server(
                    match_dict, detail=True)
            else:
                servers = self._serverDb.get_server(detail=True)
            for server in servers:
                server_hostname_list.append(str(server['id']))
                server_cluster_list.append(str(server['cluster_id']))
                tags_dict = dict()
                for tag_name in self.rev_tags_dict:
                    tags_dict[tag_name] = str(server[self.rev_tags_dict[tag_name]])
                server_tag_dict_list.append(dict(tags_dict))
            self.log("debug", "Getting monitoring info of following servers: " + str(server_hostname_list))
            url = "http://%s:%s/Snh_SandeshUVECacheReq?x=ServerMonitoringInfo" % (str(self.smgr_ip),
                                                                                  self.introspect_port)
            headers = {'content-type': 'application/json'}
            resp = requests.get(url, timeout=5, headers=headers)
            xml_data = resp.text
            data = xmltodict.parse(str(xml_data))
            json_obj = json.dumps(data, sort_keys=True, indent=4)
            data_dict = dict(json.loads(json_obj))
            if "msg" in data_dict or "type_msg" in data_dict:
                return data_dict
            data_list = list(data_dict["__ServerMonitoringInfoUve_list"]["ServerMonitoringInfoUve"])
            pruned_data_dict = dict()
            if data_dict and data_list:
                for server in data_list:
                    server = dict(server)
                    server_hostname = server["data"]["ServerMonitoringInfo"]["name"]["#text"]
                    if server_hostname in server_hostname_list:
                        pruned_data_dict[str(server_hostname)] = server
                for server_hostname, server_cluster, server_tag_dict in \
                        zip(server_hostname_list, server_cluster_list, server_tag_dict_list):
                    return_dict = dict()
                    return_dict["name"] = str(server_hostname)
                    return_dict["cluster_id"] = str(server_cluster)
                    return_dict["tag"] = dict(server_tag_dict)
                    return_dict["ServerMonitoringInfo"] = dict()
                    if server_hostname in pruned_data_dict:
                        if any(field in ["all"] for field in ret_data["type"]):
                            return_dict["ServerMonitoringInfo"] = \
                                self.filter_global_results(pruned_data_dict[str(server_hostname)])
                        if any(field in ["all", "sensor_state"] for field in
                               ret_data["type"]) and "sub_type" in ret_data:
                            return_dict["ServerMonitoringInfo"]["sensor_state"] = \
                                self.filter_sensor_results(pruned_data_dict[str(server_hostname)], ret_data["sub_type"])
                        if any(field in ["all", "chassis_state"] for field in ret_data["type"]):
                            return_dict["ServerMonitoringInfo"]["chassis_state"] = \
                                self.filter_chassis_results(pruned_data_dict[str(server_hostname)])
                        if any(field in ["all", "disk_usage_state"] for field in ret_data["type"]):
                            return_dict["ServerMonitoringInfo"]["disk_usage_state"] = \
                                self.filter_disk_results(pruned_data_dict[str(server_hostname)])
                        if any(field in ["all", "network_info_state"] for field in ret_data["type"]):
                            return_dict["ServerMonitoringInfo"]["network_info_state"] = \
                                self.filter_network_info_results(pruned_data_dict[str(server_hostname)])
                        if any(field in ["all", "resource_info_state"] for field in ret_data["type"]):
                            return_dict["ServerMonitoringInfo"]["resource_info_state"] = \
                                self.filter_resource_info_results(pruned_data_dict[str(server_hostname)])
                    list_return_dict.append(return_dict)
            else:
                return {}
        except ServerMgrException as e:
            self.log("error", "Get Monitoring Info Execption: " + e.message)
            raise e
        except Exception as e:
            self.log("error", "Get Monitoring Info Execption: " + e.message)
            raise e
        return json.dumps(list_return_dict)

    # The Thread's run function continually checks the list of servers in the Server Mgr DB and polls them.
    # It then calls other functions to send the information to the correct analytics server.
    def run(self):
        print "Starting monitoring thread"
        self.log("info", "Starting monitoring thread")
        sel_log_dict = dict()
        ipmi_list = list()
        hostname_list = list()
        server_ip_list = list()
        ipmi_username_list = list()
        ipmi_password_list = list()
        ipmi_state = dict()
        supported_sensors = ['FAN|.*_FAN', '^PWR', '.*Temp', '.*_Power']
        while True:
            servers = self._serverDb.get_server(
                None, detail=True)
            old_server_set = set(hostname_list)
            del ipmi_list[:]
            del hostname_list[:]
            del server_ip_list[:]
            del ipmi_username_list[:]
            del ipmi_password_list[:]
            for server in servers:
                if 'ssh_private_key' not in server and 'id' in server and 'ip_address' in server:
                    self.base_obj.create_store_copy_ssh_keys(server['id'], server['ip_address'])
                elif server['ssh_private_key'] is None and 'id' in server and 'ip_address' in server:
                    self.base_obj.create_store_copy_ssh_keys(server['id'], server['ip_address'])
            self.base_obj.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list,
                                                     ipmi_username_list, ipmi_password_list)
            new_server_set = set(hostname_list)
            deleted_servers = set(old_server_set.difference(new_server_set))
            if len(deleted_servers) > 0:
                self.log("info", "Deleting monitoring info of certain servers that have been removed")
                self.log("info", "Deleted servers: " + str(list(deleted_servers)))
                self.delete_monitoring_info(list(deleted_servers))
            self.log("info", "Started IPMI Polling")
            gevent_threads = dict()
            for ipmi, ip, hostname, username, password in \
                    zip(ipmi_list, server_ip_list, hostname_list, ipmi_username_list, ipmi_password_list):
                if hostname not in ipmi_state and hostname not in sel_log_dict:
                    ipmi_state[str(hostname)] = True
                    sel_log_dict[str(hostname)] = None
                thread = gevent.spawn(
                    self.gevent_runner_func, hostname, ipmi, ip, username, password,
                    supported_sensors, ipmi_state[str(hostname)], sel_log_dict[str(hostname)])
                gevent_threads[str(hostname)] = thread
            self.log("info", "Monitoring thread is sleeping for " + str(self.freq) + " seconds")
            time.sleep(self.freq)
            self.log("info", "Monitoring thread woke up")
            for hostname in gevent_threads:
                thread = gevent_threads[str(hostname)]
                if thread.successful() and thread.value:
                    return_dict = dict(thread.value)
                    ipmi_state[str(hostname)] = return_dict["ipmi_status"]
                    sel_log_dict[str(hostname)] = return_dict["sel_log"]
                else:
                    self.log("error", "Greenlet for server " + str(hostname) + " didn't return successfully: "
                                      + str(thread.get()))

