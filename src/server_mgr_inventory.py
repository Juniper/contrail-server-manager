#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_inventory.py
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

_DEF_COLLECTORS_IP = None
_DEF_MON_FREQ = 300
_DEF_INVENTORY_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_DEF_INTROSPECT_PORT = 8107


class ServerMgrInventory():
    types_list = ["fru_infos", "interface_infos", "cpu_info_state", "eth_controller_state", "mem_state"]
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

    def set_serverdb(self, server_db):
        self._serverDb = server_db
        self._base_obj.set_serverdb(server_db=server_db)

    def set_ipmi_defaults(self, ipmi_username, ipmi_password):
        self._default_ipmi_username = ipmi_username
        self._default_ipmi_password = ipmi_password

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
        self.log(self.INFO, "Sending UVE Info over Sandesh")
        self.log("info", "UVE Info = " + str(send_inst.data))
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
        except Exception as e:
            self.log(self.ERROR, "Could not get the FRU info for IP " + str(ip) + " Error: %s" + str(e))
            inventory_info_obj = ServerInventoryInfo()
            inventory_info_obj.name = hostname
            inventory_info_obj.fru_infos = None
            self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))
            return None
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
                elif sensor == "":
                    fru_obj_list.append(fru_info_obj)
                    rc = self._serverDb.add_inventory(fru_dict)
                    if rc != 0:
                        self.log(self.ERROR, "ERROR REPORTED BY INVENTORY ADD: %s" % rc)
            self.log(self.INFO, "Got the FRU info for IP: %s" % ip)
            inventory_info_obj.fru_infos = fru_obj_list
        else:
            self.log(self.INFO, "Could not get the FRU info for IP: %s" % ip)
            inventory_info_obj = ServerInventoryInfo()
            inventory_info_obj.name = hostname
            inventory_info_obj.fru_infos = None
        self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))

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
        server_inventory_info.total_numof_disks = int(numdisks)
        # Get the other inventory information from the facter tool
        try:
            filestr = sshclient.exec_command('facter')
            fileoutput = cStringIO.StringIO(filestr)
        except Exception as e:
            self.log(self.ERROR, "Could not get the Facter info for IP " + str(ip) + " Error: %s" + str(e))
            return
        if fileoutput is not None:
            self.log(self.INFO, "Got the Facter info for IP: %s" % ip)
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

    def get_field_value(self, sshclient, ip, cmd):
        times = datetime.datetime.now()
        filestr = sshclient.exec_command(cmd)
        if not filestr:
            return None
        if cmd == "lsblk" or cmd == "facter" or "statistics" in cmd:
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

    def get_cpu_info(self, hostname, ip, sshclient):
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
            server_inventory_info.cpu_info_state.clock_speed_MHz = float(self.get_field_value(sshclient, ip, clock_cmd))
            server_inventory_info.cpu_info_state.num_of_threads = int(self.get_field_value(sshclient, ip, thread_cmd))
            self.log(self.INFO, "Got the CPU info for IP: %s" % ip)
        else:
            self.log(self.DEBUG, "lscpu not installed on host : %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def get_ethernet_info(self, hostname, ip, sshclient):
        # Get the Ethernet information from server
        is_ethtool = sshclient.exec_command('which ethtool')
        server_inventory_info = ServerInventoryInfo()
        server_inventory_info.name = str(hostname)
        server_inventory_info.eth_controller_state = ethernet_controller()
        server_inventory_info.eth_controller_state.speed_Mb_per_sec = 0
        server_inventory_info.eth_controller_state.num_of_ports = 0
        server_inventory_info.eth_controller_state.model = "N/A"
        if not is_ethtool:
            self.log(self.DEBUG, "ethtool not installed on host : %s" % ip)
        else:
            eth_cmd = 'ethtool eth0 | grep Speed'
            port_cmd = 'ethtool eth0 | grep "Supported ports"'
            driver_cmd = 'ethtool -i eth0 | grep driver'
            server_inventory_info.eth_controller_state.speed_Mb_per_sec = self.get_field_value(sshclient, ip, eth_cmd)
            temp_var = re.findall('\d+|\D+', server_inventory_info.eth_controller_state.speed_Mb_per_sec)
            server_inventory_info.eth_controller_state.speed_Mb_per_sec = int(temp_var[0])
            server_inventory_info.eth_controller_state.num_of_ports = 0
            server_inventory_info.eth_controller_state.model = self.get_field_value(sshclient, ip, driver_cmd)
            self.log(self.INFO, "Got the Ethtool info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def get_memory_info(self, hostname, ip, sshclient):
        server_inventory_info = ServerInventoryInfo()
        server_inventory_info.name = str(hostname)
        server_inventory_info.mem_state = memory_info()
        server_inventory_info.mem_state.mem_type = "N/A"
        server_inventory_info.mem_state.mem_speed_MHz = 0
        server_inventory_info.mem_state.num_of_dimms = 0
        server_inventory_info.mem_state.dimm_size_mb = 0
        server_inventory_info.mem_state.swap_size_mb = 0.0
        dmi_cmd = 'which dmidecode'
        if self.get_field_value(sshclient, ip, dmi_cmd):
            type_cmd = 'dmidecode -t memory | grep -m2 "Type" | tail -n1'
            mem_cmd = 'dmidecode -t memory | grep "Speed" | head -n1'
            dimm_cmd = 'dmidecode -t memory | grep "Size" | head -n1'
            num_cmd = 'dmidecode -t memory | grep "Size" | wc -l'
            swap_cmd = 'facter | egrep -w swapsize_mb'
            server_inventory_info.mem_state.mem_type = self.get_field_value(sshclient, ip, type_cmd)
            mem_speed = self.get_field_value(sshclient, ip, mem_cmd)
            unit = mem_speed.split(" ")[1]
            if unit == "MHz":
                server_inventory_info.mem_state.mem_speed_MHz = int(mem_speed.split(" ")[0])
            dimm_size = self.get_field_value(sshclient, ip, dimm_cmd)
            if unit == "MB":
                server_inventory_info.mem_state.dimm_size_mb = int(dimm_size.split(" ")[0])
            server_inventory_info.mem_state.num_of_dimms = int(self.get_field_value(sshclient, ip, num_cmd))
            swap_size = self.get_field_value(sshclient, ip, swap_cmd)
            server_inventory_info.mem_state.swap_size_mb = float(swap_size.split(" ")[0])
            self.log(self.INFO, "Got the Memory info for IP: %s" % ip)
        else:
            self.log(self.INFO, "Couldn't get the Memory info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def add_inventory(self):
        servers = self._serverDb.get_server(None, detail=True)
        self.handle_inventory_trigger("add", servers)

    def delete_inventory_info(self, hostname):
        inventory_info_obj = ServerInventoryInfo()
        inventory_info_obj.name = str(hostname)
        inventory_info_obj.deleted = True
        self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))

    def gevent_runner_function(self, action, hostname, ip, ipmi, username, password, option="key"):
        if action == "add":
            try:
                sshclient = ServerMgrSSHClient(serverdb=self._serverDb)
                sshclient.connect(ip, option)
                self.get_fru_info(hostname, ipmi, username, password)
                self.get_facter_info(hostname, ip, sshclient)
                self.get_cpu_info(hostname, ip, sshclient)
                self.get_ethernet_info(hostname, ip, sshclient)
                self.get_memory_info(hostname, ip, sshclient)
                sshclient.close()
            except Exception as e:
                self.log(self.ERROR, "Gevent SSH Connect Execption: " + e.message)
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
        server_inv_info_fields = dict(xml_dict["data"]["ServerInventoryInfo"])
        for field in server_inv_info_fields:
            if field == "mem_state" and (field in type_list or "all" in type_list):
                server_mem_info_dict = xml_dict["data"]["ServerInventoryInfo"][field]["memory_info"]
                mem_info_dict = dict()
                for mem_field in server_mem_info_dict:
                    mem_info_dict[mem_field] = self.convert_type(server_mem_info_dict[mem_field])
                return_dict[field] = mem_info_dict
            elif field == "interface_infos" and (field in type_list or "all" in type_list):
                server_interface_list = \
                    list(xml_dict["data"]["ServerInventoryInfo"][field]["list"]["interface_info"])
                interface_dict_list = list()
                for interface in server_interface_list:
                    # interface = dict(interface)
                    server_interface_info_dict = dict()
                    for intf_field in interface:
                        server_interface_info_dict[intf_field] = self.convert_type(interface[intf_field])
                    interface_dict_list.append(server_interface_info_dict)
                return_dict[field] = interface_dict_list
            elif field == "fru_infos" and (field in type_list or "all" in type_list):
                server_fru_list = []
                if isinstance(xml_dict["data"]["ServerInventoryInfo"][field]["list"]["fru_info"], list):
                    server_fru_list = list(xml_dict["data"]["ServerInventoryInfo"][field]["list"]["fru_info"])
                elif isinstance(xml_dict["data"]["ServerInventoryInfo"][field]["list"]["fru_info"], dict):
                    server_fru_list.append(xml_dict["data"]["ServerInventoryInfo"][field]["list"]["fru_info"])
                fru_dict_list = list()
                for fru in server_fru_list:
                    # fru = dict(fru)
                    server_fru_info_dict = dict()
                    for fru_field in fru:
                        server_fru_info_dict[fru_field] = self.convert_type(fru[fru_field])
                    fru_dict_list.append(server_fru_info_dict)
                return_dict[field] = fru_dict_list
            elif field == "cpu_info_state" and (field in type_list or "all" in type_list):
                server_cpu_info_dict = xml_dict["data"]["ServerInventoryInfo"][field]["cpu_info"]
                cpu_info_dict = dict()
                for cpu_field in server_cpu_info_dict:
                    cpu_info_dict[cpu_field] = self.convert_type(server_cpu_info_dict[cpu_field])
                return_dict[field] = cpu_info_dict
            elif field == "eth_controller_state" and (field in type_list or "all" in type_list):
                server_eth_info_dict = xml_dict["data"]["ServerInventoryInfo"][field]["ethernet_controller"]
                eth_info_dict = dict()
                for eth_field in server_eth_info_dict:
                    eth_info_dict[eth_field] = self.convert_type(server_eth_info_dict[eth_field])
                return_dict[field] = eth_info_dict
            elif "all" in type_list:
                return_dict[field] = \
                    self.convert_type(server_inv_info_fields[field])
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
        try:
            entity = bottle.request
            ret_data = self._base_obj.validate_rest_api_args(entity, self.rev_tags_dict, self.types_list)
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
            for server in servers:
                server_hostname_list.append(str(server['id']))
                server_cluster_list.append(str(server['cluster_id']))
                tags_dict = dict()
                for tag_name in self.rev_tags_dict:
                    tags_dict[tag_name] = str(server[self.rev_tags_dict[tag_name]])
                server_tag_dict_list.append(dict(tags_dict))
            self.log(self.DEBUG, "Getting inventory info of following servers: " + str(server_hostname_list))
            url = "http://%s:%s/Snh_SandeshUVECacheReq?x=ServerInventoryInfo" % \
                  (str(self.smgr_ip), self.introspect_port)
            headers = {'content-type': 'application/json'}
            resp = requests.get(url, timeout=5, headers=headers)
            xml_data = resp.text
            data = xmltodict.parse(str(xml_data))
            json_obj = json.dumps(data, sort_keys=True, indent=4)
            data_dict = dict(json.loads(json_obj))
            if "msg" in data_dict or "type_msg" in data_dict:
                return data_dict
            data_list = list(data_dict["__ServerInventoryInfoUve_list"]["ServerInventoryInfoUve"])
            pruned_data_dict = dict()
            if data_dict and data_list:
                for server in data_list:
                    server = dict(server)
                    server_hostname = server["data"]["ServerInventoryInfo"]["name"]["#text"]
                    if server_hostname in server_hostname_list:
                        pruned_data_dict[str(server_hostname)] = server
                for server_hostname, server_cluster, server_tag_dict in \
                        zip(server_hostname_list, server_cluster_list, server_tag_dict_list):
                    return_dict = dict()
                    return_dict["name"] = str(server_hostname)
                    return_dict["cluster_id"] = str(server_cluster)
                    return_dict["tag"] = dict(server_tag_dict)
                    return_dict["ServerInventoryInfo"] = dict()
                    if server_hostname in pruned_data_dict:
                        return_dict["ServerInventoryInfo"] = \
                            self.filter_inventory_results(pruned_data_dict[str(server_hostname)], ret_data["type"])
                    list_return_dict.append(return_dict)
            else:
                return {}
        except ServerMgrException as e:
            self.log(self.ERROR, "Get Inventory Info Execption: " + e.message)
            raise e
        except Exception as e:
            self.log(self.ERROR, "Get Inventory Info Execption: " + e.message)
            raise e
        return json.dumps(list_return_dict)
        # end get_inventory_info

    def run_inventory(self):
        return_dict = dict()
        match_dict = dict()
        server_hostname_list = list()
        self.log(self.DEBUG, "run_inventory")
        try:
            entity = bottle.request.json
            ret_data = self._base_obj.validate_rest_api_args(entity, self.rev_tags_dict, self.types_list)
            if ret_data["status"]:
                match_key = ret_data["match_key"]
                match_value = ret_data["match_value"]
            else:
                return {"msg": ret_data["msg"], "type_msg": ret_data["type_msg"]}
            if match_key == "tag":
                match_dict = self._base_obj.process_server_tags(self.rev_tags_dict, match_value)
            elif match_key:
                match_dict[match_key] = match_value
            servers = self._serverDb.get_server(
                match_dict, detail=True)
            self.log(self.DEBUG, "Running inventory for following servers: " + str(server_hostname_list))
            self.handle_inventory_trigger("add", servers)
        except ServerMgrException as e:
            self.log(self.ERROR, "Run Inventory Execption: " + e.message)
            raise e
        except Exception as e:
            self.log(self.ERROR, "Run Inventory Execption: " + e.message)
            raise e
        inventory_status = dict()
        inventory_status['return_message'] = "server(s) run_inventory issued"
        return inventory_status

    def handle_inventory_trigger(self, action, servers):
        ipmi_list = list()
        hostname_list = list()
        server_ip_list = list()
        ipmi_username_list = list()
        ipmi_password_list = list()
        self._base_obj.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list, ipmi_username_list,
                                                  ipmi_password_list)
        gevent_threads = []
        if ipmi_list and len(ipmi_list) >= 1:
            for hostname, ip, ipmi, username, password in zip(hostname_list, server_ip_list, ipmi_list,
                                                              ipmi_username_list,
                                                              ipmi_password_list):
                thread = gevent.spawn(self.gevent_runner_function,
                                      action, hostname, ip, ipmi, username, password)
                gevent_threads.append(thread)
                # gevent.joinall(gevent_threads)

