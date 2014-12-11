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
import ast
from threading import Thread
from server_mgr_exception import ServerMgrException as ServerMgrException
from gevent import monkey
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
        self._collectors_ip = self.MonitoringCfg['collectors']
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

    def get_inventory_info(self, hostname_list, ipmi_list, ipmi_un_list, ipmi_pw_list):
        for hostname, ip, username, password in zip(hostname_list, ipmi_list, ipmi_un_list, ipmi_pw_list):
            cmd = 'ipmitool -H %s -U %s -P %s fru' % (ip, username, password)
            result = self.call_subprocess(cmd)
            if result:
                inventory_info_obj = ServerInventoryInfo()
                inventory_info_obj.name = hostname
                fileoutput = cStringIO.StringIO(result)
                fru_obj_list = list()
                for line in fileoutput:
                    self.log(self.INFO, "%s" % line)
                    if ":" in line:
                        reading = line.split(":")
                        sensor = reading[0].strip()
                        reading_value = reading[1].strip()
                    else:
                        sensor = ""
                    if sensor == "FRU Device Description":
                        fru_info_obj = fru_info()
                        fru_info_obj.fru_description = reading_value
                        fru_info_obj.chassis_type = "Not Available"
                        fru_info_obj.chassis_serial_number = "Not Available"
                        fru_info_obj.board_mfg_date = "Not Available"
                        fru_info_obj.board_manufacturer = "Not Available"
                        fru_info_obj.board_product_name = "Not Available"
                        fru_info_obj.board_serial_number = "Not Available"
                        fru_info_obj.board_part_number = "Not Available"
                        fru_info_obj.product_manfacturer = "Not Available"
                        fru_info_obj.product_name = "Not Available"
                        fru_info_obj.product_part_number = "Not Available"
                    elif sensor == "Chassis Type":
                        fru_info_obj.chassis_type = reading_value
                    elif sensor == "Chassis Serial":
                        fru_info_obj.chassis_serial_number = reading_value
                    elif sensor == "Board Mfg Date":
                        fru_info_obj.board_mfg_date = reading_value
                    elif sensor == "Board Mfg":
                        fru_info_obj.board_manufacturer = reading_value
                    elif sensor == "Board Product":
                        fru_info_obj.board_product_name = reading_value
                    elif sensor == "Board Serial":
                        fru_info_obj.board_serial_number = reading_value
                    elif sensor == "Board Part Number":
                        fru_info_obj.board_part_number = reading_value
                    elif sensor == "Product Manufacturer":
                        fru_info_obj.product_manfacturer = reading_value
                    elif sensor == "Product Name":
                        fru_info_obj.product_name = reading_value
                    elif sensor == "Product Part Number":
                        fru_info_obj.product_part_number = reading_value
                    elif sensor == "":
                        fru_obj_list.append(fru_info_obj)
                inventory_info_obj.fru_infos = fru_obj_list
            else:
                inventory_info_obj = ServerInventoryInfo
                inventory_info_obj.name = hostname
                inventory_info_obj.fru_infos = None
            self.call_send(ServerInventoryInfoUve(data=inventory_info_obj))


    def handle_inventory_trigger(self, caller, hostname_list, ip_list, ipmi_un_list, ipmi_pw_list):
        if caller == "put_server" and ip_list and len(ip_list) >= 1:
            worker = Thread(target=self.get_inventory_info(hostname_list, ip_list, ipmi_un_list, ipmi_pw_list))
            worker.start()

    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self.log(self.INFO, "No monitoring API has been configured. Server Environement Info will not be monitored.")
