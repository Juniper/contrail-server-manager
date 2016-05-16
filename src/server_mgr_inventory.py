#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_inventory.py
   Author : Nitish Krishna
   Description : Main Server Managaer Inventory Module. This module provides the functions to fetch and process
   inventory info from a set of servers that have monitoring configured. It also provides the functions to expose the
   collected information stored in the Sandesh UVE Cache trough REST API.
"""

import os
import time
import signal
import sys
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
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import requests
import xmltodict
import json
import gevent
import math
import paramiko
from inventory_daemon.server_inventory.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.constants import *
from server_mgr_mon_base_plugin import ServerMgrMonBasePlugin
from server_mgr_ssh_client import ServerMgrSSHClient
from server_mgr_exception import ServerMgrException as ServerMgrException
from datetime import datetime

_DEF_COLLECTORS_IP = None
_DEF_MON_FREQ = 300
_DEF_INVENTORY_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_DEF_INTROSPECT_PORT = 8107


class ServerMgrInventory():
    _serverDb = None
    _inventory_log = None
    _collectors_ip = None
    _default_ipmi_username = None
    _default_ipmi_password = None
    _base_obj = None
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self, smgr_ip, smgr_port, introspect_port, rev_tags_dict):
        ''' Constructor '''
        self._base_obj = ServerMgrMonBasePlugin()
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._inventory_log = logging.getLogger('INVENTORY')
        self.smgr_ip = smgr_ip
        self.smgr_port = smgr_port
        self.introspect_port = introspect_port
        self.rev_tags_dict = rev_tags_dict
        self.ssh_access_method = "key"

    def set_serverdb(self, server_db):
        self._serverDb = server_db
        self._base_obj.set_serverdb(server_db=server_db)

    def set_ipmi_defaults(self, ipmi_username, ipmi_password):
        self._default_ipmi_username = ipmi_username
        self._default_ipmi_password = ipmi_password
        self._base_obj.set_ipmi_defaults(ipmi_username, ipmi_password)

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
                self._inventory_log.debug(msg, extra=log_dict)
            elif level == self.INFO:
                self._inventory_log.info(msg, extra=log_dict)
            elif level == self.WARN:
                self._inventory_log.warn(msg, extra=log_dict)
            elif level == self.ERROR:
                self._inventory_log.error(msg, extra=log_dict)
            elif level == self.CRITICAL:
                self._inventory_log.critical(msg, extra=log_dict)
        except Exception as e:
            print "Error logging msg in Inv" + e.message

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        #self.log(self.INFO, "Sending UVE Info over Sandesh")
        #self.log("info", "UVE Info = " + str(send_inst.data))
        send_inst.send()

    @staticmethod
    def fru_dict_init(hostname):
        fru_dict = dict()
        fru_dict['id'] = hostname
        fru_dict['fru_description'] = "N/A"
        fru_dict['chassis_type'] = "N/A"
        fru_dict['chassis_serial_number'] = "N/A"
        fru_dict['board_mfg_date'] = "N/A"
        fru_dict['board_manufacturer'] = "N/A"
        fru_dict['board_product_name'] = "N/A"
        fru_dict['board_serial_number'] = "N/A"
        fru_dict['board_part_number'] = "N/A"
        fru_dict['product_manfacturer'] = "N/A"
        fru_dict['product_name'] = "N/A"
        fru_dict['product_part_number'] = "N/A"
        return fru_dict

    @staticmethod
    def fru_obj_init(hostname):
        fru_info_obj = fru_info()
        fru_info_obj.fru_description = "N/A"
        fru_info_obj.chassis_type = "N/A"
        fru_info_obj.chassis_serial_number = "N/A"
        fru_info_obj.board_mfg_date = "N/A"
        fru_info_obj.board_manufacturer = "N/A"
        fru_info_obj.board_product_name = "N/A"
        fru_info_obj.board_serial_number = "N/A"
        fru_info_obj.board_part_number = "N/A"
        fru_info_obj.product_manfacturer = "N/A"
        fru_info_obj.product_name = "N/A"
        fru_info_obj.product_part_number = "N/A"
        return fru_info_obj

    def get_fru_info(self, hostname, ip, username, password):
        cmd = 'ipmitool -H %s -U %s -P %s fru' % (ip, username, password)
        try:
            result = self._base_obj.call_subprocess(cmd)
            sensor = ""
            if result:
                inventory_info_obj = ServerInventoryInfo()
                inventory_info_obj.name = hostname
                fileoutput = cStringIO.StringIO(result)
                fru_obj_list = list()
                fru_dict = self.fru_dict_init(hostname)
                fru_info_obj = self.fru_obj_init(hostname)
                for line in fileoutput:
                    if ":" in line:
                        reading = line.split(":")
                        sensor = reading[0].strip()
                        reading_value = reading[1].strip()
                        if reading_value == "":
                            reading_value = "N/A"
                    else:
                        sensor = ""
                    if sensor == "FRU Device Description":
                        fru_dict = self.fru_dict_init(hostname)
                        fru_info_obj = self.fru_obj_init(hostname)
                        fru_info_obj.fru_description = reading_value
                        fru_dict['fru_description'] = str(hostname) + " " + reading_value
                    elif sensor == "Chassis Type":
                        fru_info_obj.chassis_type = reading_value
                        fru_dict['chassis_type'] = reading_value
                    elif sensor == "Chassis Serial":
                        fru_info_obj.chassis_serial_number = reading_value
                        fru_dict['chassis_serial_number'] = reading_value
                    elif sensor == "Board Mfg Date":
                        fru_info_obj.board_mfg_date = reading_value
                        fru_dict['board_mfg_date'] = reading_value
                    elif sensor == "Board Mfg":
                        fru_info_obj.board_manufacturer = reading_value
                        fru_dict['board_manufacturer'] = reading_value
                    elif sensor == "Board Product":
                        fru_info_obj.board_product_name = reading_value
                        fru_dict['board_product_name'] = reading_value
                    elif sensor == "Board Serial":
                        fru_info_obj.board_serial_number = reading_value
                        fru_dict['board_serial_number'] = reading_value
                    elif sensor == "Board Part Number":
                        fru_info_obj.board_part_number = reading_value
                        fru_dict['board_part_number'] = reading_value
                    elif sensor == "Product Manufacturer":
                        fru_info_obj.product_manfacturer = reading_value
                        fru_dict['product_manfacturer'] = reading_value
                    elif sensor == "Product Name":
                        fru_info_obj.product_name = reading_value
                        fru_dict['product_name'] = reading_value
                    elif sensor == "Product Part Number":
                        fru_info_obj.product_part_number = reading_value
                        fru_dict['product_part_number'] = reading_value
                    elif fru_dict['fru_description'] != "N/A" and sensor == "":
                        fru_obj_list.append(fru_info_obj)
                        rc = self._serverDb.add_inventory(fru_dict)
                        if rc != 0:
                            self.log(self.ERROR, "ERROR REPORTED BY INVENTORY ADD TO DICT: %s" % rc)
                        fru_dict = self.fru_dict_init(hostname)
                        fru_info_obj = self.fru_obj_init(hostname)
                if fru_dict['fru_description'] != "N/A":
                    fru_obj_list.append(fru_info_obj)
                    rc = self._serverDb.add_inventory(fru_dict)
                    if rc != 0:
                        self.log(self.ERROR, "ERROR REPORTED BY INVENTORY ADD TO DICT: %s" % rc)
                inventory_info_obj.fru_infos = fru_obj_list
            else:
                self.log(self.INFO, "Could not get the FRU info for IP: %s" % ip)
                inventory_info_obj = ServerInventoryInfo()
                inventory_info_obj.name = hostname
                inventory_info_obj.fru_infos = None
            self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))
        except Exception as e:
            self.log(self.ERROR, "Could not get the FRU info for IP " + str(ip) + " Error: %s" + str(e))
            inventory_info_obj = ServerInventoryInfo()
            inventory_info_obj.name = hostname
            inventory_info_obj.fru_infos = None
            self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))
            raise e

    @staticmethod
    def inventory_lookup(key):
        inv_dict = {
            'hostname': 'name',
            'boardproductname': 'board_product_name',
            'boardserialnumber': 'board_serial_number',
            'boardmanufacturer': 'board_manufacturer',
            'hardwaremodel': 'hardware_model',
            'interfaces': 'interface_name', 'physicalprocessorcount': 'physical_processor_count',
            'processorcount': 'cpu_cores_count',
            'virtual': 'virtual_machine',
            'memorytotal'		: 'total_memory_mb',
            'operatingsystem'		: 'os','operatingsystemrelease'	: 'os_version',
            'osfamily':'os_family',
            'kernelversion':'kernel_version',
            'uptime_seconds':'uptime_seconds',
            'ipaddress'		:'ip_addr',
            'netmask'			:'netmask',
            'macaddress'			: 'macaddress'
        }
        if key in inv_dict:
            return inv_dict[key]
        else:
            return None


    def get_facter_info(self, hostname, ip, sshclient):
        server_inventory_info = ServerInventoryInfo()
        # Get the total number of disks
        numdisks = self.get_field_value(sshclient, ip, 'lsblk | grep disk | wc -l')
        is_ethtool = sshclient.exec_command('which ethtool')
        server_inventory_info.total_numof_disks = int(numdisks)
        # Get the other inventory information from the facter tool
        try:
            filestr = sshclient.exec_command('facter')
            fileoutput = cStringIO.StringIO(filestr)
            if fileoutput is not None:
                interface_dict = {}
                intinfo_list = []
                for line in fileoutput:
                    inventory = line.split('=>')
                    try:
                        key = inventory[0].strip()
                        if len(inventory) > 1:
                            value = inventory[1].strip()
                        if key == 'interfaces':
                            interface_list = value.split(',')
                            for name in interface_list:
                                # Skip the loopback interface
                                if name.strip() == 'lo':
                                    continue
                                intinfo = interface_info()
                                intinfo.interface_name = name
                                intinfo.speed_Mb_per_sec = 0
                                intinfo.model = "N/A"
                                if not is_ethtool:
                                    self.log(self.DEBUG, "ethtool not installed on host : %s" % ip)
                                else:
                                    eth_cmd = 'ethtool ' + name + ' | grep Speed'
                                    driver_cmd = 'ethtool -i ' + name + ' | grep driver'
                                    intinfo.speed_Mb_per_sec = self.get_field_value(sshclient, ip, eth_cmd)
                                    if bool(re.search(r'\d', str(intinfo.speed_Mb_per_sec))):
                                        temp_var = re.findall('\d+|\D+', str(intinfo.speed_Mb_per_sec))
                                        intinfo.speed_Mb_per_sec = int(temp_var[0].strip())
                                    else:
                                        intinfo.speed_Mb_per_sec = 0
                                    intinfo.model = self.get_field_value(sshclient, ip, driver_cmd)

                                exp = '.*_' + name + '.*$'
                                # exp = '(^ipaddress_|^macaddress_|^netmask_).*'+name+'.*$'
                                res = re.findall(exp, filestr, re.MULTILINE)
                                for items in res:
                                    actualkey = items.split('=>')
                                    namekey = actualkey[0].split('_')
                                    objkey = self.inventory_lookup(key=namekey[0].strip())
                                    value = actualkey[1].strip()
                                    if objkey:
                                        setattr(intinfo, objkey, value)
                                if not getattr(intinfo, 'macaddress'):
                                    setattr(intinfo, 'macaddress', "N/A")
                                if not getattr(intinfo, 'ip_addr'):
                                    setattr(intinfo, 'ip_addr', "N/A")
                                if not getattr(intinfo, 'netmask'):
                                    setattr(intinfo, 'netmask', "N/A")
                                intinfo_list.append(intinfo)
                        else:
                            objkey = self.inventory_lookup(key)
                            if key == 'physicalprocessorcount' or key == 'processorcount' or key == 'uptime_seconds':
                                value = int(value)
                            elif key == 'memorytotal':
                                memval = value.split()
                                value = math.trunc(float(memval[0]))
                                if memval[1].strip() == 'GB':
                                    value *= 1024
                            if objkey:
                                setattr(server_inventory_info, objkey, value)
                    except Exception as KeyError:
                        self.log(self.INFO, "keyerror: %s " + str(KeyError) + " for IP: %s" % ip)
                        continue
                server_inventory_info.name = str(hostname)
                server_inventory_info.interface_infos = intinfo_list
                self.call_send(ServerInventoryInfoUve(data=server_inventory_info))
            else:
                self.log(self.ERROR, "Could not get the Facter info for IP: %s" % ip)
        except Exception as e:
            self.log(self.ERROR, "Could not get the Facter info for IP " + str(ip) + " Error: %s" + str(e))
            raise e

    def get_field_value(self, sshclient, ip, cmd):
        try:
            filestr = sshclient.exec_command(cmd)
            if not filestr:
                return None
            if cmd == "lsblk" or cmd == "facter" or "statistics" in cmd or cmd == "vmstat" or cmd == "lspci":
                return filestr
            else:
                fileoutput = cStringIO.StringIO(filestr)
                if fileoutput is not None:
                    for line in fileoutput:
                        if "=>" in line:
                            value = line.rstrip("\n").split("=>")[1].lstrip()
                            return value
                        elif ":" not in line:
                            return line
                        value = line.rstrip("\n").split(":")[1].lstrip()
                        return value
        except Exception as e:
            self.log(self.ERROR, "Error in get_field_value: " + str(ip) + " Command = " + str(cmd) + "Error: " + str(e))
            return None

    def get_cpu_info(self, hostname, ip, sshclient):
        try:
            # Get the CPU information from server
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.cpu_info_state = cpu_info()
            check_cmd = 'cat /proc/cpuinfo'
            lscpu__cmd = 'which lscpu'
            server_inventory_info.cpu_info_state.model = "N/A"
            server_inventory_info.cpu_info_state.core_count = 0
            server_inventory_info.cpu_info_state.clock_speed_MHz = 0.0
            server_inventory_info.cpu_info_state.num_of_threads = 0
            if self.get_field_value(sshclient, ip, check_cmd) and self.get_field_value(sshclient, ip, lscpu__cmd):
                model_cmd = 'cat /proc/cpuinfo | grep "model name" | head -n 1'
                core_cmd = 'cat /proc/cpuinfo | grep "cpu cores" | head -n 1'
                clock_cmd = 'cat /proc/cpuinfo | grep "cpu MHz" | head -n 1'
                thread_cmd = 'lscpu | grep "Thread"'
                server_inventory_info.cpu_info_state.model = self.get_field_value(sshclient, ip, model_cmd)
                server_inventory_info.cpu_info_state.core_count = int(self.get_field_value(sshclient, ip, core_cmd))
                server_inventory_info.cpu_info_state.clock_speed_MHz = float(
                    self.get_field_value(sshclient, ip, clock_cmd))
                server_inventory_info.cpu_info_state.num_of_threads = int(
                    self.get_field_value(sshclient, ip, thread_cmd))
            else:
                self.log(self.DEBUG, "lscpu not installed on host : %s" % ip)
            self.call_send(ServerInventoryInfoUve(data=server_inventory_info))
        except Exception as e:
            self.log(self.ERROR, "Error in get_cpu_info: " + str(ip) + "Error: " + str(e))
            raise e


    def get_ethernet_info(self, hostname, ip, sshclient):
        try:
            # Get the Ethernet information from server
            is_lspci = sshclient.exec_command('which lspci')
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.eth_controller_state = ethernet_controller()
            server_inventory_info.eth_controller_state.num_of_ports = 0
            if not is_lspci:
                self.log(self.DEBUG, "lspci not installed on host : %s" % ip)
            else:
                port_cmd = 'lspci | grep Net | wc -l'
                server_inventory_info.eth_controller_state.num_of_ports = int(
                    self.get_field_value(sshclient, ip, port_cmd))
            self.call_send(ServerInventoryInfoUve(data=server_inventory_info))
        except Exception as e:
            self.log(self.ERROR, "Error in get_ethernet_info: " + str(ip) + "Error: " + str(e))
            raise e

    def get_memory_info(self, hostname, ip, sshclient):
        try:
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.mem_state = memory_info()
            server_inventory_info.mem_state.mem_type = "N/A"
            server_inventory_info.mem_state.mem_speed_MHz = 0
            server_inventory_info.mem_state.num_of_dimms = 0
            server_inventory_info.mem_state.dimm_size_mb = 0
            server_inventory_info.mem_state.total_mem__mb = 0
            server_inventory_info.mem_state.swap_size_mb = 0.0
            dmi_cmd = 'which dmidecode'
            if self.get_field_value(sshclient, ip, dmi_cmd):
                type_cmd = 'dmidecode -t memory |  grep "Type:" | grep -v "Unknown" | grep -v "Error" | head -n1'
                mem_cmd = 'dmidecode -t memory | grep "Speed" | grep -v "Unknown" | head -n1'
                dimm_cmd = 'dmidecode -t memory | grep "Size" | grep -v "No Module" | head -n1'
                num_cmd = 'dmidecode -t memory | grep "Size" | grep -v "No Module" | wc -l'
                swap_cmd = 'facter | egrep -w swapsize_mb'
                total_mem_cmd = 'vmstat -s | grep "total memory"'
                server_inventory_info.mem_state.mem_type = self.get_field_value(sshclient, ip, type_cmd)
                mem_speed = self.get_field_value(sshclient, ip, mem_cmd)
                unit = mem_speed.split(" ")[1]
                if unit == "MHz":
                    server_inventory_info.mem_state.mem_speed_MHz = int(mem_speed.split(" ")[0])
                dimm_size = self.get_field_value(sshclient, ip, dimm_cmd)
                unit = dimm_size.split(" ")[1]
                if unit == "MB":
                    server_inventory_info.mem_state.dimm_size_mb = int(dimm_size.split(" ")[0])
                server_inventory_info.mem_state.num_of_dimms = int(self.get_field_value(sshclient, ip, num_cmd))
                swap_size = self.get_field_value(sshclient, ip, swap_cmd)
                server_inventory_info.mem_state.swap_size_mb = float(swap_size.split(" ")[0])
                total_mem = self.get_field_value(sshclient, ip, total_mem_cmd)
                server_inventory_info.mem_state.total_mem_mb = int(int(total_mem.lstrip().split(" ")[0]) / 1024)
            else:
                self.log(self.INFO, "Couldn't get the Memory info for IP: %s" % ip)
            self.call_send(ServerInventoryInfoUve(data=server_inventory_info))
        except Exception as e:
            self.log(self.ERROR, "Error in get_memory_info: " + str(ip) + "Error: " + str(e))
            raise e

    def add_inventory(self):
        servers = self._serverDb.get_server(None, detail=True)
        gevent.spawn(self.handle_inventory_trigger, "add", servers)

    def delete_inventory_info(self, hostname):
        inventory_info_obj = ServerInventoryInfo()
        inventory_info_obj.name = str(hostname)
        inventory_info_obj.deleted = True
        inventory_info_obj.fru_infos = None
        inventory_info_obj.interface_infos = None
        inventory_info_obj.cpu_info_state = None
        inventory_info_obj.eth_controller_state = None
        self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))

    def gevent_runner_function(self, action, hostname, ip=None, ipmi=None, username=None, password=None, option="key"):
        sshclient = None
        if action == "add" and ip and ipmi and username and password:
            try:
                sshclient = ServerMgrSSHClient(serverdb=self._serverDb)
                sshclient.connect(ip, hostname, option)
                self.get_facter_info(hostname, ip, sshclient)
                self.get_cpu_info(hostname, ip, sshclient)
                self.get_ethernet_info(hostname, ip, sshclient)
                self.get_memory_info(hostname, ip, sshclient)
                sshclient.close()
            except Exception as e:
                if sshclient:
                    sshclient.close()
                self.log("error", "Gevent SSH Connect Exception for server id: " + str(hostname) + " Error : " + str(e))
                pass
            try:
                self.get_fru_info(hostname, ipmi, username, password)
            except Exception as e:
                self.log("error", "Error in getting Inventory Info through IPMI for server id: " + str(hostname) + " Error : " + str(e))
                pass
        elif action == "delete":
            self.log(self.INFO, "Deleted info of server: %s" % hostname)
            self.delete_inventory_info(hostname)

    ######## INVENTORY GET INFO SECTION ###########

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

    def filter_inventory_results(self, xml_dict, type_list):
        return_dict = {}
        if "all" in type_list:
            return_dict = dict(xml_dict)
        else:
            selected_fields = set(xml_dict.keys()).intersection(type_list)
            for selected_field in selected_fields:
                return_dict[selected_field] = xml_dict[selected_field]
        return return_dict

    @staticmethod
    def get_inv_conf_details(self):
        return "Configuration for Inventory set correctly."

    def get_inventory_info(self):
        list_return_dict = list()
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        server_cluster_list = list()
        server_tag_dict_list = list()
        self.log(self.DEBUG, "get_inventory_info")
        uve_name = "ServerInventoryInfo"
        try:
            entity = bottle.request
            ret_data = self._base_obj.validate_rest_api_args(entity, self.rev_tags_dict)
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self._base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            if match_dict.keys():
                servers = self._serverDb.get_server(
                    match_dict, detail=True)
            else:
                servers = self._serverDb.get_server(detail=True)
            #self.log(self.DEBUG, "Getting inventory info of following servers: " + str(servers))
            if len(servers) == 1:
                url = self._base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, uve_name,
                                                     dict(servers[0])['id'])
            else:
                url = self._base_obj.get_sandesh_url(self.smgr_ip, self.introspect_port, uve_name)
            headers = {'content-type': 'application/json'}
            resp = requests.get(url, timeout=300, headers=headers)
            xml_data = resp.text
            data = xmltodict.parse(str(xml_data))
            data_dict = dict(data["__" + str(uve_name) + "Uve_list"])
            parsed_data_list = self._base_obj.parse_sandesh_xml(data_dict, uve_name)
            parsed_data_dict = dict()
            if parsed_data_list and servers:
                for parsed_server in parsed_data_list:
                    parsed_server = dict(parsed_server)
                    parsed_data_dict[str(parsed_server["data"]["name"])] = dict(parsed_server["data"])
                for server in servers:
                    server = dict(server)
                    server_hostname = str(server['id'])
                    if server_hostname in parsed_data_dict.keys():
                        return_dict = dict()
                        return_dict["name"] = str(server_hostname)
                        return_dict["cluster_id"] = server['cluster_id']
                        return_dict[str(uve_name)] = self.filter_inventory_results(
                            parsed_data_dict[str(server_hostname)],
                            ret_data["type"])
                        list_return_dict.append(return_dict)
                    else:
                        self.log(self.ERROR, "Server Details missing in cache. ")
                        self.log(self.ERROR, "Server Hostname = " + str(server_hostname))
                        pass
            else:
                self.log(self.ERROR, "Server Details missing in db. ")
                return {}
        except ServerMgrException as e:
            self.log(self.ERROR, "Get Inventory Info Exception: " + str(e.message))
            return json.dumps({})
        except Exception as e:
            self.log(self.ERROR, "Get Inventory Info Exception: " + str(e.message))
            return json.dumps({})
        #self.log("debug", "Exited get_inventory_info " + str(datetime.now()))
        return json.dumps(list_return_dict)
        # end get_inventory_info

    def run_inventory(self):
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        self.log(self.DEBUG, "run_inventory")
        try:
            entity = bottle.request
            ret_data = self._base_obj.validate_rest_api_args(entity, self.rev_tags_dict)
            #ret_data = self._base_obj.validate_run_inv_params(entity, self.rev_tags_dict)
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self._base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            if match_dict.keys():
                servers = self._serverDb.get_server(
                    match_dict, detail=True)
            else:
                servers = self._serverDb.get_server(detail=True)
            self.handle_inventory_trigger("add", servers)
        except ServerMgrException as e:
            self.log("error", "Run Inventory Exception: " + e.message)
            raise e
        except Exception as e:
            self.log("error", "Run Inventory Exception: " + e.message)
            raise e
        inventory_status = dict()
        inventory_status['return_message'] = "server(s) run_inventory issued"
        return inventory_status

    def handle_inventory_trigger(self, action, servers):
        server_dict = self._base_obj.create_server_dict(servers)

        gevent_threads = []
        if len(server_dict.keys()) >= 1:
            for server_id in server_dict:
                server = dict(server_dict[str(server_id)])
                if action == "add":
                    if 'id' in server and 'ip_address' in server and 'ipmi_address' in server and 'ipmi_username' \
                            in server and 'ipmi_password' in server:
                        thread = gevent.spawn(self.gevent_runner_function, action, server['id'], server['ip_address'],
                                              server['ipmi_address'], server['ipmi_username'], server['ipmi_password'],
                                              self.ssh_access_method)
                        gevent_threads.append(thread)
                    else:
                        self.log(self.ERROR, "Missing fields in server dictionary - skipping inventory addition")
                elif action == "delete":
                    if 'id' in server:
                        thread = gevent.spawn(self.gevent_runner_function, action, server['id'], self.ssh_access_method)
                        gevent_threads.append(thread)
                    else:
                        self.log(self.ERROR, "Missing id field in server dictionary - skipping inventory deletion")
                time.sleep(1)
        self.log(self.DEBUG, "Finished Running Inventory")
                # gevent.joinall(gevent_threads)

