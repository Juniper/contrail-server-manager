import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
import argparse
import ConfigParser
import cStringIO
import re
import socket
import pdb
from threading import Thread

_DEF_ANALYTICS_IP = None
_DEF_MON_FREQ = 300
_DEF_PLUGIN_MODULE = None
_DEF_PLUGIN_CLASS = None
_DEF_QUERY_MODULE = None
_DEF_QUERY_CLASS = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'

# Class ServerMgrDevEnvMonitoring provides a base class that can be inherited by
# any implementation of a plugabble monitoring API that interacts with the
# analytics node
class ServerMgrMonBasePlugin(Thread):

    val = 1
    freq = 300

    def __init__(self, log, translog):
        ''' Constructor '''
        Thread.__init__(self)
        self._smgr_log = log
        self._smgr_trans_log = translog

    def parse_args(self, args_str):
        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        MonitoringCfg = {
            'analytics_ip': _DEF_ANALYTICS_IP,
            'monitoring_freq': _DEF_MON_FREQ,
            'plugin_class': _DEF_PLUGIN_MODULE,
            'plugin_module': _DEF_PLUGIN_CLASS,
            'query_module': _DEF_QUERY_MODULE,
            'query_class': _DEF_QUERY_CLASS
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        for key in dict(config.items("MONITORING")).keys():
            if key in MonitoringCfg.keys():
                MonitoringCfg[key] = dict(config.items("MONITORING"))[key]
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "Configuration set for invalid parameter: %s" % key)

        self._smgr_log.log(self._smgr_log.DEBUG, "Arguments read form monitoring config file %s" % MonitoringCfg)
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**MonitoringCfg)
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
        self._smgr_log.log(self._smgr_log.INFO,
                           "No monitoring API has been configured. Server Environement Info will not be monitored.")
