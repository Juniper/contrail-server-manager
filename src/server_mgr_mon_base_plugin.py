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
from threading import Thread
from server_mgr_exception import ServerMgrException as ServerMgrException
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import gevent
import math
import paramiko
from inventory_daemon.server_inventory.ttypes import *
from pysandesh.sandesh_base import *
from sandesh_common.vns.ttypes import Module, NodeType
from sandesh_common.vns.constants import ModuleNames, NodeTypeNames, \
    Module2NodeType, INSTANCE_ID_DEFAULT
from sandesh_common.vns.constants import *

_DEF_COLLECTORS_IP = None
_DEF_MON_FREQ = 300
_DEF_MONITORING_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'
_DEF_INTROSPECT_PORT = 8107

#JUST CHECKING
# Class ServerMgrDevEnvMonitoring provides a base class that can be inherited by
# any implementation of a plugabble monitoring API that interacts with the
# analytics node
class ServerMgrMonBasePlugin(Thread):
    val = 1
    freq = 300
    _dev_env_monitoring_obj = None
    _config_set = False
    _serverDb = None
    _monitoring_log = None
    _collectors_ip = None
    _discovery_server = None
    _discovery_port = None
    _default_ipmi_username = None
    _default_ipmi_password = None
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self):
        ''' Constructor '''
        Thread.__init__(self)
        self.MonitoringCfg = {
            'collectors': _DEF_COLLECTORS_IP,
            'monitoring_frequency': _DEF_MON_FREQ,
            'monitoring_plugin': _DEF_MONITORING_PLUGIN
        }
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._monitoring_log = logging.getLogger('MONITORING')
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
            print "Error logging msg" + e.message

    def parse_args(self, args_str):
        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        for key in dict(config.items("MONITORING")).keys():
            if key in self.MonitoringCfg.keys():
                self.MonitoringCfg[key] = dict(config.items("MONITORING"))[key]
            else:
                self.log(self.DEBUG, "Configuration set for invalid parameter: %s" % key)

        self.log(self.DEBUG, "Arguments read form monitoring config file %s" % self.MonitoringCfg)
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**self.MonitoringCfg)
        _args = parser.parse_args(remaining_argv)
        self._collectors_ip = _args.collectors
        return parser.parse_args(remaining_argv)

    def sandesh_init(self, collectors_ip_list=None):
        # Inventory node module initialization part
        try:
            self.log("info", "Initializing sandesh")
            module = Module.INVENTORY_AGENT
            module_name = ModuleNames[module]
            node_type = Module2NodeType[module]
            node_type_name = NodeTypeNames[node_type]
            instance_id = INSTANCE_ID_DEFAULT
            collectors_ip_list = eval(collectors_ip_list)
            if collectors_ip_list:
                self.log("info", "Collector IPs from config: " + str(collectors_ip_list))
                monitoring = True
                try:
                    __import__('contrail_sm_monitoring.ipmi')
                except ImportError:
                    monitoring = False
                    pass
                if monitoring:
                    sandesh_global.init_generator(
                        module_name,
                        socket.gethostname(),
                        node_type_name,
                        instance_id,
                        collectors_ip_list,
                        module_name,
                        HttpPortInventorymgr,
                        ['inventory_daemon.server_inventory', 'contrail_sm_monitoring.ipmi'])
                else:
                    sandesh_global.init_generator(
                        module_name,
                        socket.gethostname(),
                        node_type_name,
                        instance_id,
                        collectors_ip_list,
                        module_name,
                        HttpPortInventorymgr,
                        ['inventory_daemon.server_inventory'])
            else:
                pass
        except Exception as e:
            raise ServerMgrException("Error during Sandesh Init: " + str(e))

    # call_subprocess function runs the IPMI command passed to it and returns the result
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

    # call_send function is the sending function of the sandesh object (send_inst)
    def call_send(self, send_inst):
        sys.stderr.write('sending UVE:' + str(send_inst))
        send_inst.send()

    def populate_server_data_lists(self, servers, ipmi_list, hostname_list,
                                   server_ip_list, ipmi_username_list, ipmi_password_list, root_pwd_list):
        for server in servers:
            server = dict(server)
            if 'ipmi_address' in server and server['ipmi_address'] \
                    and 'id' in server and server['id'] \
                    and 'ip_address' in server and server['ip_address'] \
                    and 'password' in server and server['password']:
                ipmi_list.append(server['ipmi_address'])
                hostname_list.append(server['id'])
                server_ip_list.append(server['ip_address'])
                root_pwd_list.append(server['password'])
                if 'ipmi_username' in server and server['ipmi_username'] \
                        and 'ipmi_password' in server and server['ipmi_password']:

                    ipmi_username_list.append(server['ipmi_username'])
                    ipmi_password_list.append(server['ipmi_password'])
                else:
                    ipmi_username_list.append(self._default_ipmi_username)
                    ipmi_password_list.append(self._default_ipmi_password)


    def get_fru_info(self, hostname, ip, username, password):
        cmd = 'ipmitool -H %s -U %s -P %s fru' % (ip, username, password)
        try:
            result = self.call_subprocess(cmd)
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
                    fru_info_obj.chassis_type = " "
                    fru_dict['chassis_type'] = " "
                    fru_info_obj.chassis_serial_number = " "
                    fru_dict['chassis_serial_number'] = " "
                    fru_info_obj.board_mfg_date = " "
                    fru_dict['board_mfg_date'] = " "
                    fru_info_obj.board_manufacturer = " "
                    fru_dict['board_manufacturer'] = " "
                    fru_info_obj.board_product_name = " "
                    fru_dict['board_product_name'] = " "
                    fru_info_obj.board_serial_number = " "
                    fru_dict['board_serial_number'] = " "
                    fru_info_obj.board_part_number = " "
                    fru_dict['board_part_number'] = " "
                    fru_info_obj.product_manfacturer = " "
                    fru_dict['product_manfacturer'] = " "
                    fru_info_obj.product_name = " "
                    fru_dict['product_name'] = " "
                    fru_info_obj.product_part_number = " "
                    fru_dict['product_part_number'] = " "
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
            'virtual'		: 'virtual_machine',
            'memorytotal'			: 'total_memory_mb',
            'operatingsystem'		: 'os','operatingsystemrelease'	: 'os_version',
            'osfamily'			:'os_family',
            'kernelversion'			:'kernel_version',
            'uptime_seconds'		:'uptime_seconds',
            'ipaddress'			:'ip_addr',
            'netmask'			:'netmask',
            'macaddress'			: 'macaddress'
        }[key]

    def get_facter_info(self, hostname, ip, root_pwd):
        server_inventory_info = ServerInventoryInfo()
        # Get the total number of disks
        numdisks = self.call_subprocess('lsblk | grep disk | wc -l')
        server_inventory_info.total_numof_disks = int(numdisks)
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
                            #exp = '(^ipaddress_|^macaddress_|^netmask_).*'+name+'.*$'
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
                                setattr(intinfo, 'macaddress', " ")
                            if not getattr(intinfo, 'ip_addr'):
                                setattr(intinfo, 'ip_addr', " ")
                            if not getattr(intinfo, 'netmask'):
                                setattr(intinfo, 'netmask', " ")
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
            ip, root_pwd, 'cat /proc/cpuinfo | grep "model name" | head -n 1') else " "
        server_inventory_info.cpu_info_state.core_count = int(self.get_field_value(ip, root_pwd,
                                                                                   'cat /proc/cpuinfo | grep "cpu cores" | head -n 1')) if self.get_field_value(
            ip, root_pwd, 'cat /proc/cpuinfo | grep "cpu cores" | head -n 1') else 0
        server_inventory_info.cpu_info_state.clock_speed = self.get_field_value(ip, root_pwd,
                                                                                'cat /proc/cpuinfo | grep "cpu MHz" | head -n 1') + " MHz" if self.get_field_value(
            ip, root_pwd, 'cat /proc/cpuinfo | grep "cpu MHz" | head -n 1') else " "
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
            server_inventory_info.eth_controller_state.speed = " "
            server_inventory_info.eth_controller_state.num_of_ports = " "
            server_inventory_info.eth_controller_state.model = " "
            self.log(self.DEBUG, "ethtool not installed on host : %s" % ip)
        else:
            server_inventory_info = ServerInventoryInfo()
            server_inventory_info.name = str(hostname)
            server_inventory_info.eth_controller_state = ethernet_controller()
            server_inventory_info.eth_controller_state.speed = self.get_field_value(ip, root_pwd, 'ethtool eth0 | grep Speed') if self.get_field_value(ip, root_pwd, 'ethtool eth0 | grep Speed') else " "
            temp_var = re.findall('\d+|\D+', server_inventory_info.eth_controller_state.speed)
            server_inventory_info.eth_controller_state.speed = temp_var[0] + " " + temp_var[1]
            server_inventory_info.eth_controller_state.num_of_ports = self.get_field_value(ip, root_pwd,
                                                                                           'ethtool eth0 | grep "Supported ports"') if self.get_field_value(
                ip, root_pwd, 'ethtool eth0 | grep "Supported ports"') else " "
            server_inventory_info.eth_controller_state.model = self.get_field_value(ip, root_pwd,
                                                                                    'ethtool -i eth0 | grep driver') if self.get_field_value(
                ip, root_pwd, 'ethtool -i eth0 | grep driver') else " "
            self.log(self.INFO, "Got the Ethtool info for IP: %s" % ip)
        self.call_send(ServerInventoryInfoUve(data=server_inventory_info))

    def get_memory_info(self, hostname, ip, root_pwd):
        server_inventory_info = ServerInventoryInfo()
        server_inventory_info.name = str(hostname)
        server_inventory_info.mem_state = memory_info()
        server_inventory_info.mem_state.mem_type = self.get_field_value(ip, root_pwd,
                                                                        'dmidecode -t memory | grep -m2 "Type" | tail -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep -m2 "Type" | tail -n1') else " "
        server_inventory_info.mem_state.mem_speed = self.get_field_value(ip, root_pwd,
                                                                         'dmidecode -t memory | grep "Speed" | head -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep "Speed" | head -n1') else " "
        server_inventory_info.mem_state.dimm_size = self.get_field_value(ip, root_pwd,
                                                                         'dmidecode -t memory | grep "Size" | head -n1') if self.get_field_value(
            ip, root_pwd, 'dmidecode -t memory | grep "Size" | head -n1') else " "
        server_inventory_info.mem_state.num_of_dimms = int(
            self.get_field_value(ip, root_pwd, 'dmidecode -t memory | grep "Size" | wc -l')) if self.get_field_value(ip,
                                                                                                                     root_pwd,
                                                                                                                     'dmidecode -t memory | grep "Size" | wc -l') else 0
        server_inventory_info.mem_state.swap_size = self.get_field_value(ip, root_pwd,
                                                                         'facter | egrep -w swapsize') if self.get_field_value(
            ip, root_pwd, 'facter | egrep -w swapsize') else " "
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
        self.populate_server_data_lists(servers, ipmi_list, hostname_list, server_ip_list, ipmi_username_list,
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


    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self.log(self.INFO, "No monitoring API has been configured. Server Environement Info will not be monitored.")
