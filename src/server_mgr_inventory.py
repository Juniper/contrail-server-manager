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
import gevent
import math
import paramiko
from inventory_daemon.server_inventory.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.constants import *
from server_mgr_mon_base_plugin import ServerMgrMonBasePlugin

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

    def __init__(self):
        ''' Constructor '''
        self._base_obj = ServerMgrMonBasePlugin()
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._inventory_log = logging.getLogger('INVENTORY')

    def set_serverdb(self, server_db):
        self._serverDb = server_db

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
        send_inst.send()

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
            fru_dict = dict()
            for line in fileoutput:
                if ":" in line:
                    reading = line.split(":")
                    sensor = reading[0].strip()
                    reading_value = reading[1].strip()
                else:
                    sensor = ""
                if sensor == "FRU Device Description":
                    fru_info_obj = fru_info()
                    fru_info_obj.fru_description = reading_value
                    fru_dict['fru_description'] = str(hostname) + " " + reading_value
                    fru_dict['id'] = hostname
                    fru_info_obj.chassis_type = "dummy"
                    fru_dict['chassis_type'] = "dummy"
                    fru_info_obj.chassis_serial_number = "dummy"
                    fru_dict['chassis_serial_number'] = "dummy"
                    fru_info_obj.board_mfg_date = "dummy"
                    fru_dict['board_mfg_date'] = "dummy"
                    fru_info_obj.board_manufacturer = "dummy"
                    fru_dict['board_manufacturer'] = "dummy"
                    fru_info_obj.board_product_name = "dummy"
                    fru_dict['board_product_name'] = "dummy"
                    fru_info_obj.board_serial_number = "dummy"
                    fru_dict['board_serial_number'] = "dummy"
                    fru_info_obj.board_part_number = "dummy"
                    fru_dict['board_part_number'] = "dummy"
                    fru_info_obj.product_manfacturer = "dummy"
                    fru_dict['product_manfacturer'] = "dummy"
                    fru_info_obj.product_name = "dummy"
                    fru_dict['product_name'] = "dummy"
                    fru_info_obj.product_part_number = "dummy"
                    fru_dict['product_part_number'] = "dummy"
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
        return {
            'hostname': 'name',
            'boardproductname': 'board_product_name',
            'boardserialnumber': 'board_serial_number',
            'boardmanufacturer': 'board_manufacturer',
            'hardwaremodel': 'hardware_model',
            'interfaces': 'interface_name', 'physicalprocessorcount': 'physical_processor_count',
            'processorcount': 'cpu_cores_count',
            'virtual'	: 'virtual_machine',
            'memorytotal'			: 'total_memory_mb',
            'operatingsystem'		: 'os','operatingsystemrelease'	: 'os_version',
            'osfamily':'os_family',
            'kernelversion'		:'kernel_version',
            'uptime_seconds'		:'uptime_seconds',
            'ipaddress'			:'ip_addr',
            'netmask'			:'netmask',
            'macaddress'			: 'macaddress'
        }[key]

    def get_facter_info(self, hostname, ip, root_pwd):
        server_inventory_info = ServerInventoryInfo()
        # Get the total number of disks
        numdisks = self._base_obj.call_subprocess('lsblk | grep disk | wc -l')
        server_inventory_info.total_numof_disks = int(numdisks)
        tx_bytes = self._base_obj.call_subprocess('cat /sys/class/net/eth0/statistics/tx_bytes')
        server_inventory_info.tx_bytes = int(tx_bytes)
        tx_packets = self._base_obj.call_subprocess('cat /sys/class/net/eth0/statistics/tx_packets')
        server_inventory_info.tx_packets = int(tx_packets)
        rx_bytes = self._base_obj.call_subprocess('cat /sys/class/net/eth0/statistics/rx_bytes')
        server_inventory_info.rx_bytes = int(rx_bytes)
        rx_packets = self._base_obj.call_subprocess('cat /sys/class/net/eth0/statistics/rx_packets')
        server_inventory_info.rx_packets = int(rx_packets)
        # Get the other inventory information from the facter tool
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, username='root', key_filename="/root/.ssh/server_mgr_rsa", timeout=3)
            stdin, stdout, stderr = ssh.exec_command('facter')
            filestr = stdout.read()
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
                                try:
                                    objkey = self.inventory_lookup(key=namekey[0].strip())
                                except KeyError:
                                    continue
                                value = actualkey[1].strip()
                                setattr(intinfo, objkey, value)
                            if not getattr(intinfo, 'macaddress'):
                                setattr(intinfo, 'macaddress', "dummy")
                            if not getattr(intinfo, 'ip_addr'):
                                setattr(intinfo, 'ip_addr', "dummy")
                            if not getattr(intinfo, 'netmask'):
                                setattr(intinfo, 'netmask', "dummy")
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
                        setattr(server_inventory_info, objkey, value)
                except KeyError:
                    continue
            server_inventory_info.name = str(hostname)
            server_inventory_info.interface_infos = intinfo_list
            self.call_send(ServerInventoryInfoUve(data=server_inventory_info))
        else:
            self.log(self.ERROR, "Could not get the Facter info for IP: %s" % ip)

    def get_field_value(self, ip, root_pwd, cmd):
        times = datetime.datetime.now()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username='root', key_filename="/root/.ssh/server_mgr_rsa", timeout=3)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        if stdout is None:
            return None
        filestr = stdout.read()
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

    def get_cpu_info(self, hostname, ip, root_pwd):
        server_inventory_info = ServerInventoryInfo()
        # Get the other inventory information from the facter tool
        server_inventory_info.name = str(hostname)
        server_inventory_info.cpu_info_state = cpu_info()
        server_inventory_info.cpu_info_state.model = self.get_field_value(ip, root_pwd,
                                                                          'cat /proc/cpuinfo | grep "model name" | head -n 1') if self.get_field_value(
            ip, root_pwd, 'cat /proc/cpuinfo | grep "model name" | head -n 1') else "dummy"
        server_inventory_info.cpu_info_state.core_count = int(self.get_field_value(ip, root_pwd,
                                                                                   'cat /proc/cpuinfo | grep "cpu cores" | head -n 1')) if self.get_field_value(
            ip, root_pwd, 'cat /proc/cpuinfo | grep "cpu cores" | head -n 1') else 0
        server_inventory_info.cpu_info_state.clock_speed = self.get_field_value(ip, root_pwd,
                                                                                'cat /proc/cpuinfo | grep "cpu MHz" | head -n 1') + " MHz" if self.get_field_value(
            ip, root_pwd, 'cat /proc/cpuinfo | grep "cpu MHz" | head -n 1') else "dummy"
        server_inventory_info.cpu_info_state.num_of_threads = int(
            self.get_field_value(ip, root_pwd, 'lscpu | grep "Thread"')) if self.get_field_value(ip, root_pwd,
                                                                                                 'lscpu | grep "Thread"') else 0
        self.log(self.INFO, "Got the CPU info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def get_ethernet_info(self, hostname, ip, root_pwd):
        is_ethtool = self.get_field_value(ip, root_pwd, 'which ethtool')
        if not is_ethtool:
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.eth_controller_state = ethernet_controller()
            server_inventory_info.eth_controller_state.speed = "dummy"
            server_inventory_info.eth_controller_state.num_of_ports = "dummy"
            server_inventory_info.eth_controller_state.model = "dummy"
            self.log(self.DEBUG, "ethtool not installed on host : %s" % ip)
        else:
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.eth_controller_state = ethernet_controller()
            server_inventory_info.eth_controller_state.speed = self.get_field_value(ip, root_pwd
                                                                                    , 'ethtool eth0 | grep Speed') if self. \
                get_field_value(ip, root_pwd, 'ethtool eth0 | grep Speed') else "dummy"
            temp_var = re.findall('\d+|\D+', server_inventory_info.eth_controller_state.speed)
            server_inventory_info.eth_controller_state.speed = temp_var[0] + " " + temp_var[1]
            server_inventory_info.eth_controller_state.num_of_ports = self.get_field_value(ip, root_pwd,
                                                                                           'ethtool eth0 | grep "Supported ports"') if self.get_field_value(
                ip, root_pwd, 'ethtool eth0 | grep "Supported ports"') else "dummy"
            server_inventory_info.eth_controller_state.model = self.get_field_value(ip, root_pwd,
                                                                                    'ethtool -i eth0 | grep driver') if self.get_field_value(
                ip, root_pwd, 'ethtool -i eth0 | grep driver') else "dummy"
            self.log(self.INFO, "Got the Ethtool info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def get_memory_info(self, hostname, ip, root_pwd):
        server_inventory_info = ServerInventoryInfo()
        server_inventory_info.name = str(hostname)
        server_inventory_info.mem_state = memory_info()
        server_inventory_info.mem_state.mem_type = self.get_field_value(ip, root_pwd,
                                                                        'dmidecode -t memory | grep -m2 "Type" | tail -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep -m2 "Type" | tail -n1') else "dummy"
        server_inventory_info.mem_state.mem_speed = self.get_field_value(ip, root_pwd,
                                                                         'dmidecode -t memory | grep "Speed" | head -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep "Speed" | head -n1') else "dummy"
        server_inventory_info.mem_state.dimm_size = self.get_field_value(ip, root_pwd,
                                                                         'dmidecode -t memory | grep "Size" | head -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep "Size" | head -n1') else "dummy"
        server_inventory_info.mem_state.num_of_dimms = int(
            self.get_field_value(ip, root_pwd, 'dmidecode -t memory | grep "Size" | wc -l')) if self.get_field_value(ip,
                                                                                                                     root_pwd,
                                                                                                                     'dmidecode -t memory | grep "Size" | wc -l') else 0
        server_inventory_info.mem_state.swap_size = self.get_field_value(ip, root_pwd,
                                                                         'facter | egrep -w swapsize') if self.get_field_value(
            ip, root_pwd, 'facter | egrep -w swapsize') else "dummy"
        self.log(self.INFO, "Got the Memory info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def add_inventory(self):
        ipmi_list = list()
        hostname_list = list()
        server_ip_list = list()
        ipmi_username_list = list()
        ipmi_password_list = list()
        root_pwd_list = list()
        servers = self._serverDb.get_server(None, detail=True)
        self._base_obj.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list, ipmi_username_list,
                                                  ipmi_password_list, root_pwd_list)
        self.handle_inventory_trigger("add", hostname_list, server_ip_list, ipmi_list, ipmi_username_list,
                                      ipmi_password_list, root_pwd_list)

    def delete_inventory_info(self, hostname):
        inventory_info_obj = ServerInventoryInfo()
        inventory_info_obj.name = str(hostname)
        inventory_info_obj.deleted = True
        self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))

    def gevent_runner_function(self, action, hostname, ip, ipmi, username, password, root_pw):
        if action == "add":
            self.get_fru_info(hostname, ipmi, username, password)
            self.get_facter_info(hostname, ip, root_pw)
            self.get_cpu_info(hostname, ip, root_pw)
            self.get_ethernet_info(hostname, ip, root_pw)
            self.get_memory_info(hostname, ip, root_pw)
        elif action == "delete":
            self.log(self.INFO, "Deleted info of server: %s" % hostname)
            self.delete_inventory_info(hostname)

    def handle_inventory_trigger(self, action, hostname_list, ip_list, ipmi_list, ipmi_un_list, ipmi_pw_list,
                                 root_pw_list):
        gevent_threads = []
        if ipmi_list and len(ipmi_list) >= 1:
            for hostname, ip, ipmi, username, password, root_pwd in zip(hostname_list, ip_list, ipmi_list, ipmi_un_list,
                                                                        ipmi_pw_list, root_pw_list):
                thread = gevent.spawn(self.gevent_runner_function,
                                      action, hostname, ip, ipmi, username, password, root_pwd)
                gevent_threads.append(thread)
                #gevent.joinall(gevent_threads)

