import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
import argparse
import ConfigParser
from bottle import abort
from urlparse import urlparse, parse_qs
import logging
import logging.config
import logging.handlers
import inspect
import cStringIO
import re
import socket
import pdb
from threading import Thread
from server_mgr_exception import ServerMgrException as ServerMgrException

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
                self._monitoring_log.log(self.DEBUG, "Configuration set for invalid parameter: %s" % key)

        self._monitoring_log.log(self.DEBUG, "Arguments read form monitoring config file %s" % self.MonitoringCfg)
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

    # A place-holder run function that the Server Monitor defaults to in the absence of a configured
    # monitoring API layer to use.
    def run(self):
        self.log(self.INFO, "No monitoring API has been configured. Server Environement Info will not be monitored.")

