#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_ipmi_monitoring.py
   Author : Nitish Krishna
   Description : Main Server Managaer Monitoring Module. This module provides the functions to fetch and process
   monitoring info from a set of servers that have monitoring configured. It also provides the functions to expose the
   collected information stored in the Sandesh UVE Cache trough REST API.
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
from gevent import queue as gevent_queue
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
from datetime import datetime
from server_mgr_disk_filesystem_view import file_system_disk_view
import math
import time
import urllib


class base_mon_uve():
    UVE_NONE = 0
    UVE_INFO = 1
    UVE_SUMMARY = 2


# Class ServerMgrIPMIMonitoring provides a monitoring object that runs as a thread
# when Server Manager starts/restarts. This thread continually polls all the servers
# that are stored in the Server Manager DB at any point. Before this polling can occur,
# Server Manager opens a Sandesh Connection to the Analytics node that hosts the
# Database to which the monitor pushes device environment information.
class ServerMgrIPMIMonitoring():
    host_disklist = dict()
    host_nw_info_list = dict()
    _default_ipmi_username = None
    _default_ipmi_password = None
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"
    _serverDb = None
    sleep_period = 10
    ssh_access_method = ""
    log_file = '/opt/contrail/server_manager/logger.conf'

    def __init__(self, val, frequency, smgr_ip=None, smgr_port=None, collectors_ip=None, introspect_port=None,
                 rev_tags_dict=None):
        ''' Constructor '''
        self.base_obj = ServerMgrMonBasePlugin()
        logging.config.fileConfig(self.log_file)
        # create logger
        self._monitoring_log = logging.getLogger('MONITORING')
        self.val = val
        self.smgr_ip = smgr_ip
        self.smgr_port = smgr_port
        self.introspect_port = introspect_port
        self.freq = float(frequency)
        self._collectors_ip = collectors_ip
        self.rev_tags_dict = rev_tags_dict
        self.ssh_access_method = "key"

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
        #self.log("info", "Sending UVE Info over Sandesh")
        send_inst.send()

    #This function returns the boolean value needed in the Sandesh Payload
    def str2bool(self,value):
        return value.lower() in ("true")

    # send_ipmi_stats function packages and sends the IPMI info gathered from server polling
    # to the analytics node
    def send_ipmi_stats(self, ip, ipmi_data, hostname, data_type):
        base_send_type = base_mon_uve.UVE_NONE
        if data_type == "ipmi_data":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.sensor_stats = []
            for ipmidata in ipmi_data:
                sm_ipmi_info.sensor_stats.append(ipmidata)
        elif data_type == "ipmi_chassis_data":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.chassis_state = ipmi_data
        elif data_type == "disk_list":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.disk_usage_stats = []
            for data in ipmi_data:
                sm_ipmi_info.disk_usage_stats.append(data)
        elif data_type == "disk_list_tot":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.disk_usage_totals = []
            for data in ipmi_data:
                sm_ipmi_info.disk_usage_totals.append(data)
        elif data_type == "resource_info_stats":
            base_send_type = base_mon_uve.UVE_SUMMARY
            sm_ipmi_info = ServerMonitoringSummary()
            sm_ipmi_info.resource_info_stats = ipmi_data
        elif data_type == "intinfo_list_tot":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.network_info_totals = []
            for data in ipmi_data:
                sm_ipmi_info.network_info_totals.append(data)
        elif data_type == "intinfo_list":
            base_send_type = base_mon_uve.UVE_SUMMARY
            sm_ipmi_info = ServerMonitoringSummary()
            sm_ipmi_info.network_info_stats = []
            for data in ipmi_data:
                sm_ipmi_info.network_info_stats.append(data)
        elif data_type == "file_system_view_list":
            base_send_type = base_mon_uve.UVE_INFO
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.file_system_view_stats = []
            for data in ipmi_data:
                sm_ipmi_info.file_system_view_stats.append(data)
            # self.log("info", "Sending Monitoring UVE Info for: " + str(data_type))
            # self.log("info", "UVE Interface Info = " + str(sm_ipmi_info))

        # assign hostname
        sm_ipmi_info.name = str(hostname)
        sm_ipmi_info.deleted = False
        # Send info based on base type
        if base_send_type == base_mon_uve.UVE_INFO:
            ipmi_stats_trace = ServerMonitoringInfoUve(data=sm_ipmi_info)
        elif base_send_type == base_mon_uve.UVE_SUMMARY:
            ipmi_stats_trace = ServerMonitoringSummaryUve(data=sm_ipmi_info)
        elif base_send_type == base_mon_uve.UVE_NONE:
            self.log("error", "Error base mon uve type for " + str(data_type))

        # self.log("info", "UVE Info Sent= " + str(sm_ipmi_info))
        self.call_send(ipmi_stats_trace)

    # Packages and sends a REST API call to the ServerManager node
    def send_run_inventory_request(self, ip, port, payload):
        try:
            url = "http://%s:%s/run_inventory" % (ip, port)
            args_str = ''
            match_key, match_value = payload.popitem()
            if match_key and match_value:
                args_str += urllib.quote_plus(str(match_key)) + "=" \
                            + urllib.quote_plus(str(match_value))
            if args_str != '':
                url += "?" + args_str
            headers = {'content-type': 'application/json'}
            resp = requests.post(url, headers=headers, timeout=300)
            return resp.text
        except Exception as e:
            self.log("error", "Error running inventory on  " + str(payload) + " : " + str(e))
            return None

    def return_collector_ip(self):
        return self._collectors_ip

    def isfloat(self, num):
        try:
            float(num)
        except ValueError:
           return False
        return True

    def fetch_and_process_monitoring(self, hostname, ipmi, ip, username, password, supported_sensors):
        try:
            ipmi_data = []
            cmd = 'ipmitool -H %s -U %s -P %s sdr list all' % (ipmi, username, password)
            result = self.base_obj.call_subprocess(cmd)
            if result is not None and "|" in result:
                fileoutput = cStringIO.StringIO(result)
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
                            elif status == "ok" and self.isfloat(value[0].strip()):
                                ipmidata.reading = long(value[0].strip())
                                ipmidata.unit = value[len(value) - 1].strip()
                                ipmidata.sensor_type = sensor_type
                                ipmi_data.append(ipmidata)
                self.send_ipmi_stats(ip, ipmi_data, hostname, "ipmi_data")
                return True
            else:
                self.log("error", "Error getting Sesnsor info for: " + str(hostname) +
                         " Data returned was: " + str(result))
                return False
        except Exception as e:
            self.log("error", "Error getting Sesnsor info for: " + str(hostname) + " Error is: " + str(e))
            raise

    def fetch_and_process_chassis(self, hostname, ipmi, ip, username, password):
        ipmi_chassis_data = IpmiChassis_status_info()
        cmd = 'ipmitool -H %s -U %s -P %s chassis status' % (ipmi, username, password)
        try:
            result = self.base_obj.call_subprocess(cmd)
            if result is not None:
                fileoutput = cStringIO.StringIO(result)
                ipmichassisdata = IpmiChassis_status_info()
                for line in fileoutput:
                    if len(line.split(":")) >= 2:
                        reading = line.split(":")
                        chassis_key = reading[0].strip()
                        chassis_value = reading[1].strip()
                        if chassis_key == "System Power":
                            ipmichassisdata.system_power = chassis_value
                        elif chassis_key == "Power Overload" and chassis_value:
                            ipmichassisdata.power_overload = self.str2bool(chassis_value)
                        elif chassis_key == "Power Interlock" and chassis_value:
                            ipmichassisdata.power_interlock = chassis_value
                        elif chassis_key == "Main Power Fault" and chassis_value:
                            ipmichassisdata.main_power_fault = self.str2bool(chassis_value)
                        elif chassis_key == "Power Control Fault" and chassis_value:
                            ipmichassisdata.power_control_fault = self.str2bool(chassis_value)
                        elif chassis_key == "Power Restore Policy" and chassis_value:
                            ipmichassisdata.power_restore_policy = chassis_value
                        elif chassis_key == "Last Power Event" and chassis_value:
                            ipmichassisdata.last_power_event = chassis_value
                        elif chassis_key == "Chassis Intrusion" and chassis_value:
                            ipmichassisdata.chassis_intrusion = chassis_value
                        elif chassis_key == "Front-Panel Lockout" and chassis_value:
                            ipmichassisdata.front_panel_lockout = chassis_value
                        elif chassis_key == "Drive Fault" and chassis_value:
                            ipmichassisdata.drive_fault = self.str2bool(chassis_value)
                        elif chassis_value:
                            ipmichassisdata.cooling_fan_fault = self.str2bool(chassis_value)
                    else:
                        pass
                ipmi_chassis_data = ipmichassisdata
            self.send_ipmi_stats(ip, ipmi_chassis_data, hostname, "ipmi_chassis_data")
        except Exception as e:
            self.log("error", "Error getting chassis data for " + str(hostname) + " : " + str(e.message))
            raise

    def fetch_and_process_disk_info(self, hostname, ip, sshclient):
        disk_list = []
        disk_list_tot = []
        cmd = 'iostat -m'

        is_sysstat = sshclient.exec_command('which iostat')
        if not is_sysstat:
            #self.log("info", "sysstat package not installed on " + str(ip))
            disk_data = Disk()
            disk_data_tot = Disk_totals()
            disk_data.disk_name = "N/A"
            disk_data.read_bytes = int(0)
            disk_data.write_bytes = int(0)
            disk_data_tot.total_read_bytes = int(0)
            disk_data_tot.total_write_bytes = int(0)
            disk_list.append(disk_data)
            disk_list_tot.append(disk_data_tot)
            self.send_ipmi_stats(ip, disk_list, hostname, "disk_list")
            self.send_ipmi_stats(ip, disk_list_tot, hostname, "disk_list_tot")
        else:
            try:
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    #lookup for host dictionary
                    if hostname not in self.host_disklist:
                        #if empty insert the disklist dictionary
                        dict_disk = dict()
                        self.host_disklist[hostname] = dict_disk
                    else:
                        # disklist entry found
                        dict_disk = self.host_disklist[hostname]

                    for line in fileoutput:
                        if line is not None:
                            if (line.find('sd') != -1 or line.find('dm') != -1) and line.find('Linux')!=0:
                                disk_data = Disk()
                                disk_data_tot = Disk_totals()
                                prev_disk_info = Disk_totals()
                                res = re.sub('\s+', ' ', line).strip()
                                arr = res.split()
                                disk_data.disk_name = arr[0]
                                disk_data_tot.disk_name = arr[0]
                                disk_data_tot.total_read_bytes = int(arr[4])
                                disk_data_tot.total_write_bytes = int(arr[5])
                                if len(dict_disk) != 0:
                                    if disk_data_tot.disk_name in dict_disk:
                                        disk_data.read_bytes = disk_data_tot.total_read_bytes - dict_disk[
                                            disk_data_tot.disk_name].total_read_bytes
                                        disk_data.write_bytes = disk_data_tot.total_write_bytes - dict_disk[
                                            disk_data_tot.disk_name].total_write_bytes
                                        disk_list.append(disk_data)

                                prev_disk_info.total_read_bytes = disk_data_tot.total_read_bytes
                                prev_disk_info.total_write_bytes = disk_data_tot.total_write_bytes
                                dict_disk[disk_data_tot.disk_name] = prev_disk_info
                                disk_list_tot.append(disk_data_tot)
                    if disk_list:
                        self.send_ipmi_stats(ip, disk_list, hostname, "disk_list")
                        #return True  no return
                    if disk_list_tot:
                        self.send_ipmi_stats(ip, disk_list_tot, hostname, "disk_list_tot")
                        return True
                    else:
                        return False
            except Exception as e:
                self.log("error", "Error getting disk info for " + str(hostname) + " : " + str(e))
                raise

    #This function gets the mounted file system view. This will be the output of the df command
    def fetch_and_process_file_system_view(self, hostname, ip, sshclient):
        try:
            fs_view = file_system_disk_view()
            file_system_view_list = fs_view.get_file_system_view(sshclient)
            self.send_ipmi_stats(ip, file_system_view_list, hostname, "file_system_view_list")
        except Exception as e:
            self.log("error", "Error getting file system view info for " + str(hostname) + " : " + str(e))
            raise e

    def fetch_and_process_resource_info(self, hostname, ip, sshclient):
        try:
            resource_info1 = resource_info()
            is_mpstat = sshclient.exec_command('which mpstat')
            if not is_mpstat:
                resource_info1.cpu_usage_percentage = 0.0
            else:
                cmd = 'mpstat'
                filestr = sshclient.exec_command(cmd=cmd)
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    idle_index = -1
                    for line in fileoutput:
                        res = re.sub('\s+', ' ', line).strip()
                        arr = res.split()
                        if idle_index != -1:
                            resource_info1.cpu_usage_percentage = (100.0 - float(arr[idle_index]))
                            break
                        if "%idle" not in arr:
                            continue
                        else:
                            idle_index = arr.index('%idle')
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

            self.send_ipmi_stats(ip, resource_info1, hostname, "resource_info_stats")
        except Exception as e:
            self.log("error", "Error in getting resource info for  " + str(hostname) + str(e))
            raise e

    def fetch_and_process_network_info(self, hostname, ip, sshclient):
        try:
            intinfo_list = []
            intinfo_list_tot = []
            phys_intf_checker = sshclient.exec_command("ls -l /sys/class/net/")
            phys_intf_list = list()
            if phys_intf_checker:
                checker_output = cStringIO.StringIO(phys_intf_checker)
                for line in checker_output:
                    line = str(line)
                    if "virtual" not in line and "total" not in line and len(line.split(' ')) > 8:
                        line = line.split('/')
                        phys_intf_list.append(line[len(line) - 1].rstrip('\n'))

            result = sshclient.exec_command("ls /sys/class/net/")
            if result:
                output = cStringIO.StringIO(result)
                net_dictinfo = None
                #lookup for host dictionary
                if hostname not in self.host_nw_info_list:
                    #if empty insert the net dict info
                    net_dictinfo = dict()
                    self.host_nw_info_list[hostname] = net_dictinfo
                else:
                    # disklist entry found
                    net_dictinfo = self.host_nw_info_list[hostname]

                for line in output:
                    intinfo = network_info()
                    intinfo_tot = network_info_totals()
                    prev_nw = network_info_totals()
                    if line.rstrip() in phys_intf_list:
                        cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/tx_bytes"
                        tx_bytes = sshclient.exec_command(cmd=cmd)
                        cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/tx_packets"
                        tx_packets = sshclient.exec_command(cmd=cmd)
                        cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/rx_bytes"
                        rx_bytes = sshclient.exec_command(cmd=cmd)
                        cmd = "cat /sys/class/net/" + line.rstrip() + "/statistics/rx_packets"
                        rx_packets = sshclient.exec_command(cmd=cmd)
                        intinfo_tot.interface_name = line.rstrip()
                        intinfo.interface_name = line.rstrip()
                        intinfo_tot.total_tx_bytes = int(tx_bytes.rstrip())
                        intinfo_tot.total_tx_packets = int(tx_packets.rstrip())
                        intinfo_tot.total_rx_bytes = int(rx_bytes.rstrip())
                        intinfo_tot.total_rx_packets = int(rx_packets.rstrip())
                        if len(net_dictinfo) != 0:
                            if intinfo_tot.interface_name in net_dictinfo:
                                intinfo.tx_bytes = intinfo_tot.total_tx_bytes - net_dictinfo[
                                    intinfo_tot.interface_name].total_tx_bytes
                                intinfo.rx_bytes = intinfo_tot.total_rx_bytes - net_dictinfo[
                                    intinfo_tot.interface_name].total_rx_bytes
                                intinfo.tx_packets = intinfo_tot.total_tx_packets - net_dictinfo[
                                    intinfo_tot.interface_name].total_tx_packets
                                intinfo.rx_packets = intinfo_tot.total_rx_packets - net_dictinfo[
                                    intinfo_tot.interface_name].total_rx_packets
                                intinfo_list.append(intinfo)
                        prev_nw.total_tx_bytes = intinfo_tot.total_tx_bytes
                        prev_nw.total_rx_bytes = intinfo_tot.total_rx_bytes
                        prev_nw.total_tx_packets = intinfo_tot.total_tx_packets
                        prev_nw.total_rx_packets = intinfo_tot.total_rx_packets
                        net_dictinfo[intinfo_tot.interface_name] = prev_nw
                        intinfo_list_tot.append(intinfo_tot)
                if intinfo_list:
                    self.send_ipmi_stats(ip, intinfo_list, hostname, "intinfo_list")
                if intinfo_list_tot:
                    self.send_ipmi_stats(ip, intinfo_list_tot, hostname, "intinfo_list_tot")
                    return True
                else:
                    return False
        except Exception as e:
            self.log("error", "Error in getting network info for " + str(hostname) + " Error: " + str(e))
            raise e

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
                    hex_event_id = col[0].strip()
                    if hex_event_id.isdigit():
                        event_id = int(hex_event_id, 16)
                    else:
                        event_id = None
                    if event_id and event_id not in sel_event_log_list:
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
                        sellog.send()
                    else:
                        pass
            return sel_event_log_list
        except Exception as e:
            self.log("error", "Error getting SEL Logs for " + str(hostname) + " : " + str(e.message))
            raise e

    def delete_monitoring_info(self, hostname_list):
        for hostname in hostname_list:
            sm_ipmi_info = ServerMonitoringInfo()
            sm_ipmi_info.name = str(hostname)
            sm_ipmi_info.deleted = True
            sm_ipmi_info.chassis_state = None
            ipmi_stats_trace = ServerMonitoringInfoUve(data=sm_ipmi_info)
            self.call_send(ipmi_stats_trace)

    def gevent_runner_func(self, hostname, ipmi, ip, username, password, supported_sensors, ipmi_state,
                           sel_event_log_list, option="key"):
        return_dict = dict()
        #self.log("info", "Gevent Thread created for %s" % hostname)
        try:
            sshclient = ServerMgrSSHClient(serverdb=self._serverDb)
            sshclient.connect(ip, hostname, option)
            self.fetch_and_process_resource_info(hostname, ip, sshclient)
            self.fetch_and_process_network_info(hostname, ip, sshclient)
            self.fetch_and_process_disk_info(hostname, ip, sshclient)
            self.fetch_and_process_file_system_view(hostname, ip, sshclient)
            sshclient.close()
        except Exception as e:
            self.log("error", "Gevent SSH Connect Exception for server id: " + str(hostname) + " Error : " + str(e))
            sshclient.close()
            pass
        try:
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
            # self.log("info", "Payload return dict:\n" + str(return_dict))
            return return_dict
        except Exception as e:
            self.log("error", "Error in getting monitoring info through IPMI for server id: " + str(hostname) + " Error : " + str(e))
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
    def filter_monitoring_results(self, xml_dict, type_list):
        return_dict = {}
        if "all" in type_list:
            return_dict = dict(xml_dict)
        else:
            selected_fields = set(xml_dict.keys()).intersection(type_list)
            for selected_field in selected_fields:
                return_dict[selected_field] = xml_dict[selected_field]
        return return_dict

    def get_mon_conf_details(self):
        list_return_dict = list()
        main_return_dict = dict()
        return_dict = dict()
        return_dict["monitoring_frequency"] = self.freq
        return_dict["http_introspect_port"] = self.introspect_port
        return_dict["analytics_node_ips"] = list(self._collectors_ip)
        main_return_dict["config"] = dict(return_dict)
        list_return_dict.append(main_return_dict)
        return json.dumps(list_return_dict)

    def get_monitoring_info(self):
        list_return_dict = list()
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        server_cluster_list = list()
        server_tag_dict_list = list()
        self.log("debug", "get_monitoring_info")
        #self.log("debug", "Entered get_monitoring_info " + str(datetime.now()))
        uve_name = "ServerMonitoringInfo"
        summary_uve_name = "ServerMonitoringSummary"
        try:
            entity = bottle.request
            ret_data = self.base_obj.validate_rest_api_args(entity, self.rev_tags_dict)
            #self.log("debug", "Validated rest api params " + str(datetime.now()))
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self.base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            #self.log("debug", "Before server db read " + str(datetime.now()))
            if match_dict.keys():
                servers = self._serverDb.get_server(
                    match_dict, detail=True)
            else:
                servers = self._serverDb.get_server(detail=True)
            #self.log("debug", "After server read " + str(datetime.now()))
            #self.log("debug", "Getting monitoring info of following servers: " + str(server_hostname_list))
            if len(servers) == 1:
                url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, uve_name,
                                                    dict(servers[0])['id'])
                summary_url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, summary_uve_name,
                                                            dict(servers[0])['id'])
            else:
                url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, uve_name)
                summary_url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, summary_uve_name)
            headers = {'content-type': 'application/json'}
            #self.log("debug", "After get_sandesh_url, before REST API call " + str(datetime.now()))
            #time_before = time.time()
            resp = requests.get(url, timeout=300, headers=headers)
            sum_resp = requests.get(summary_url, timeout=300, headers=headers)
            xml_data = resp.text
            sum_xml_data = sum_resp.text
            #time_after = time.time()
            #time_sec = time_after - time_before
            #self.log("debug", "Sandesh REST API Call : Time taken = " + str(time_sec)
            #         + " Resp length = " + str(len(xml_data)))
            #self.log("debug", "After REST API call " + str(datetime.now()))
            time_before = time.time()
            data = xmltodict.parse(str(xml_data))
            sum_data = xmltodict.parse(str(sum_xml_data))
            #self.log("debug", "After XMLtoDict" + str(datetime.now()))
            time_after = time.time()
            time_sec = time_after - time_before
            #self.log("debug", "XMLtoDict Call : Time taken = " + str(time_sec))
            data_dict = dict(data["__" + str(uve_name) + "Uve_list"])
            sum_data_dict = dict(sum_data["__" + str(summary_uve_name) + "Uve_list"])
            #self.log("debug", "Before  processing " + str(datetime.now()))
            parsed_data_list = self.base_obj.parse_sandesh_xml(data_dict, uve_name)
            sum_parsed_data_list = self.base_obj.parse_sandesh_xml(sum_data_dict, summary_uve_name)
            parsed_data_dict = dict()
            sum_parsed_data_dict = dict()
            if parsed_data_list and sum_parsed_data_list and servers:
                for parsed_server in parsed_data_list:
                    parsed_server = dict(parsed_server)
                    parsed_data_dict[str(parsed_server["data"]["name"])] = dict(parsed_server["data"])
                for sum_parsed_server in sum_parsed_data_list:
                    sum_parsed_server = dict(sum_parsed_server)
                    sum_parsed_data_dict[str(sum_parsed_server["data"]["name"])] = dict(sum_parsed_server["data"])
                for server in servers:
                    server = dict(server)
                    server_hostname = str(server['id'])
                    if server_hostname in parsed_data_dict.keys():
                        return_dict = dict()
                        return_dict["name"] = str(server['id'])
                        return_dict["cluster_id"] = server['cluster_id']
                        if str(server['id']) in parsed_data_dict.keys():
                            main_dict = self.filter_monitoring_results(
                                parsed_data_dict[str(server['id'])],
                                ret_data["type"])
                        else:
                            main_dict = {}
                        if str(server['id']) in sum_parsed_data_dict.keys():
                            summary_dict = self.filter_monitoring_results(
                                sum_parsed_data_dict[str(server['id'])],
                                ret_data["type"])
                        else:
                            summary_dict = {}
                        for summary_key in summary_dict:
                            main_dict[str(summary_key)] = summary_dict[summary_key]
                        return_dict[str(uve_name)] = main_dict
                        #self.log("info", "All Keys:" + str(return_dict.keys()))
                        #self.log("info", "All Smgr Keys:" + str(return_dict[str(uve_name)].keys()))
                        list_return_dict.append(return_dict)
                    else:
                        self.log(self.ERROR, "Server Details missing in cache. ")
                        self.log(self.ERROR, "Server Hostname = " + str(server_hostname))
                        pass
            else:
                self.log(self.ERROR, "Server Details missing in db. ")
                pass
        except ServerMgrException as e:
            self.log("error", "Get Monitoring Info Exception: " + str(e.message))
            return_dict = {}
            list_return_dict = list()
            list_return_dict.append(return_dict)
            return json.dumps(list_return_dict)
        except Exception as e:
            self.log("error", "Get Monitoring Info Exception: " + str(e.message))
            return_dict = {}
            list_return_dict = list()
            list_return_dict.append(return_dict)
            return json.dumps(list_return_dict)
        #self.log("debug", "Exited get_monitoring_info " + str(datetime.now()))
        return json.dumps(list_return_dict)

    def get_monitoring_info_summary(self):
        list_return_dict = list()
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        server_cluster_list = list()
        server_tag_dict_list = list()
        self.log("debug", "get_monitoring_info_summary")
        #self.log("debug", "Entered get_monitoring_info " + str(datetime.now()))
        uve_name = "ServerMonitoringInfo"
        summary_uve_name = "ServerMonitoringSummary"
        try:
            entity = bottle.request
            ret_data = self.base_obj.validate_rest_api_args(entity, self.rev_tags_dict)
            #self.log("debug", "Validated rest api params " + str(datetime.now()))
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self.base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            #self.log("debug", "Before server db read " + str(datetime.now()))
            if match_dict.keys():
                servers = self._serverDb.get_server(
                    match_dict, detail=True)
            else:
                servers = self._serverDb.get_server(detail=True)
            #self.log("debug", "After server read " + str(datetime.now()))
            #self.log("debug", "Getting monitoring info of following servers: " + str(server_hostname_list))
            if len(servers) == 1:
                summary_url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, summary_uve_name,
                                                            dict(servers[0])['id'])
            else:
                summary_url = self.base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, summary_uve_name)
            headers = {'content-type': 'application/json'}
            #self.log("debug", "After get_sandesh_url, before REST API call " + str(datetime.now()))
            #time_before = time.time()
            sum_resp = requests.get(summary_url, timeout=300, headers=headers)
            sum_xml_data = sum_resp.text
            #time_after = time.time()
            #time_sec = time_after - time_before
            #self.log("debug", "Sandesh REST API Call : Time taken = " + str(time_sec)
            #         + " Resp length = " + str(len(xml_data)))
            #self.log("debug", "After REST API call " + str(datetime.now()))
            time_before = time.time()
            sum_data = xmltodict.parse(str(sum_xml_data))
            #self.log("debug", "After XMLtoDict" + str(datetime.now()))
            time_after = time.time()
            time_sec = time_after - time_before
            #self.log("debug", "XMLtoDict Call : Time taken = " + str(time_sec))
            sum_data_dict = dict(sum_data["__" + str(summary_uve_name) + "Uve_list"])
            #self.log("debug", "Before  processing " + str(datetime.now()))
            sum_parsed_data_list = self.base_obj.parse_sandesh_xml(sum_data_dict, summary_uve_name)
            sum_parsed_data_dict = dict()
            if sum_parsed_data_list and servers:
                for sum_parsed_server in sum_parsed_data_list:
                    sum_parsed_server = dict(sum_parsed_server)
                    sum_parsed_data_dict[str(sum_parsed_server["data"]["name"])] = dict(sum_parsed_server["data"])
                for server in servers:
                    server = dict(server)
                    server_hostname = str(server['id'])
                    if server_hostname in sum_parsed_data_dict.keys():
                        return_dict = dict()
                        return_dict["name"] = str(server['id'])
                        return_dict["cluster_id"] = server['cluster_id']
                        return_dict[str(summary_uve_name)] = self.filter_monitoring_results(
                            sum_parsed_data_dict[str(server['id'])],
                            ret_data["type"]
                        )
                        return_dict[str(uve_name)] = return_dict[str(summary_uve_name)]
                        return_dict.pop(str(summary_uve_name))
                        list_return_dict.append(return_dict)
                    else:
                        self.log(self.ERROR, "Server Details missing in cache. ")
                        self.log(self.ERROR, "Server Hostname = " + str(server_hostname))
                        pass
            else:
                self.log(self.ERROR, "Server Details missing in db. ")
                pass
        except ServerMgrException as e:
            self.log("error", "Get Monitoring Info Summary Exception: " + str(e.message))
            return_dict = {}
            list_return_dict = list()
            list_return_dict.append(return_dict)
            return json.dumps(list_return_dict)
        except Exception as e:
            self.log("error", "Get Monitoring Info Summary Exception: " + str(e.message))
            return_dict = {}
            list_return_dict = list()
            list_return_dict.append(return_dict)
            return json.dumps(list_return_dict)
        #self.log("debug", "Exited get_monitoring_info " + str(datetime.now()))
        return json.dumps(list_return_dict)

    def cleanup(self, obj):
        if obj:
            obj.kill()

    # The Thread's run function continually checks the list of servers in the Server Mgr DB and polls them.
    # It then calls other functions to send the information to the correct analytics server.
    def run(self):
        print "Starting monitoring thread"
        #self.log("info", "Starting monitoring thread")
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
            #self.base_obj.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list,
             #                                        ipmi_username_list, ipmi_password_list, "monitoring")
            server_dict = self.base_obj.create_server_dict(servers)
            hostname_list = list(server_dict.keys())
            new_server_set = set(hostname_list)
            deleted_servers = set(old_server_set.difference(new_server_set))

            if len(hostname_list) == 0:
                time.sleep(self.freq)
                continue
            if len(deleted_servers) > 0:
                #self.log("info", "Deleting monitoring info of certain servers that have been removed")
                #self.log("info", "Deleted servers: " + str(list(deleted_servers)))
                self.delete_monitoring_info(list(deleted_servers))
            self.log("info", "Started IPMI Polling")
            gevent_threads = dict()
            gevent_priority_queue = gevent_queue.PriorityQueue()
            for server_id in server_dict:
                gevent_priority_queue.put(dict(server_dict[str(server_id)]))
            total_no_of_servers = gevent_priority_queue.qsize()
            sleep_period = self.sleep_period
            servers_per_period = int(math.floor(float(total_no_of_servers / self.freq * sleep_period)))
            #self.log("info", "Total number of servers this round: " + str(total_no_of_servers))
            #self.log("info", "Servers per period this round: " + str(servers_per_period))

            sleep_period = 1
            time_set_success = False
            while not time_set_success:
                servers_per_period = int(math.floor(float(total_no_of_servers / self.freq * sleep_period)))
                if servers_per_period >= 1:
                    time_set_success = True
                else:
                    sleep_period += 1
            try:
                counter = servers_per_period
                times_slept = 0
                spawned = 0
                total_spawned = 0
                for server_id in server_dict:
                    counter -= 1
                    spawned += 1
                    total_spawned += 1
                    server = dict(server_dict[str(server_id)])
                    if server['id'] not in ipmi_state and server['id'] not in sel_log_dict:
                        ipmi_state[str(server['id'])] = True
                        sel_log_dict[str(server['id'])] = None
                    if 'id' in server and 'ip_address' in server and 'ipmi_address' in server and 'ipmi_username' \
                            in server and 'ipmi_password' in server and server['id'] and server['ip_address'] \
                            and server['ipmi_address'] and server['ipmi_username'] and server['ipmi_password']:
                        thread = gevent.spawn(
                            self.gevent_runner_func, server['id'], server['ipmi_address'], server['ip_address'],
                            server['ipmi_username'], server['ipmi_password'],
                            supported_sensors, ipmi_state[str(server['id'])], sel_log_dict[str(server['id'])],
                            self.ssh_access_method)
                        gevent_threads[str(server['id'])] = thread
                    else:
                        self.log("error", "Missing fields in server dictionary - skipping monitoring run")
                    if counter > 0:
                        pass
                    else:
                        #self.log("debug", "Round of Spawning completed. Sleeping for 10 secs. ")
                        #self.log("debug", "Number of gevents spawned this round: " + str(spawned))
                        #self.log("debug", "Total spawned: " + str(total_spawned))
                        time.sleep(sleep_period)
                        times_slept += 1
                        counter = servers_per_period
                        spawned = 0
                #self.log("debug", "Slept for " + str(times_slept*sleep_period) + " s, sleeping for an additional " +
                         #str(self.freq - times_slept * sleep_period))
                if (self.freq - times_slept*sleep_period) > 0:
                    time.sleep(max(self.freq-times_slept*sleep_period, 0))
                else:
                    #self.log("debug", "No additional sleep. ")
                    pass

                for hostname in gevent_threads:
                    thread = gevent_threads[str(hostname)]
                    if thread.successful() and thread.value:
                        return_dict = dict(thread.value)
                        ipmi_state[str(hostname)] = return_dict["ipmi_status"]
                        sel_log_dict[str(hostname)] = return_dict["sel_log"]
                        thread.kill()
                    else:
                        self.log("error", "Greenlet for server " + str(hostname) + " didn't return successfully: "
                                 + str(thread.get()))
                        thread.kill()
                        pass

            except Exception as e:
                self.log("error", "Exception occured while spawning gevents. Error = " + str(e))
                pass

