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
_DEF_QUERYING_PLUGIN = None
_DEF_SMGR_BASE_DIR = '/opt/contrail/server_manager/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'sm-config.ini'

# Class ServerMgrDevEnvMonitoring provides a base class that can be inherited by
# any implementation of a plugabble monitoring API that interacts with the
# analytics node
class ServerMgrMonBasePlugin(Thread):

    val = 1
    freq = 300
    _dev_env_querying_obj = None
    _dev_env_monitoring_obj = None
    _config_set = False
    _serverDb = None
    _monitoring_log = None
    _collectors_ip = None
    _discovery_server = None
    _discovery_port = None
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
            'monitoring_plugin': _DEF_MONITORING_PLUGIN,
            'querying_plugin': _DEF_QUERYING_PLUGIN
        }
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._monitoring_log = logging.getLogger('MONITORING')

    def set_serverdb(self, server_db):
        self._serverDb = server_db

    def set_querying_obj(self, query_obj):
        self._dev_env_querying_obj = query_obj

    def log(self, level, msg):
        frame, filename, line_number, function_name, lines, index = inspect.stack()[1]
        log_dict = dict()
        log_dict['log_frame'] = frame
        log_dict['log_filename'] = os.path.basename(filename)
        log_dict['log_line_number'] = line_number
        log_dict['log_function_name'] = function_name
        log_dict['log_line'] = lines
        log_dict['log_index'] = index
        print "Log command"
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

    # This function converts the string of tags received in REST call and make
    # a dictionary of tag keys that can be passed to match servers from DB.
    # The match_value (tags received are in form tag1=value,tag2=value etc.
    # This function maps the tag name to tag number and value and makes
    # a dictionary of those.

    def _process_server_tags(self, match_value, tags_dict):
        if not match_value:
            return {}
        match_dict = {}
        tag_list = match_value.split(',')
        for x in tag_list:
            tag = x.strip().split('=')
            if tag[0] in tags_dict:
                match_dict[tags_dict[tag[0]]] = tag[1]
            else:
                msg = ("Unknown tag %s specified" % (
                    tag[0]))
                self.log(self.ERROR, msg)
                raise ServerMgrException(msg)
                # end else
        return match_dict
        # end _process_server_tags

    # Generic function to return env details based on key
    def get_server_env_details_by_type(self, ret_data, detail_type, tags_dict):
        try:
            if ret_data['status'] == 0:
                match_key = ret_data['match_key']
                match_value = ret_data['match_value']
                match_dict = {}
                if match_key is not None:
                    if match_key == 'tag':
                        match_dict = self._process_server_tags(match_value, tags_dict)
                    else:
                        match_dict[match_key] = match_value
                    detail = True
                    servers = self._serverDb.get_server(
                        match_dict, detail=detail)
                    ipmi_add = ""
                    hostname = ""
                    server_ip = ""
                    data = ""
                    collectors_ip = list()
                    env_details_dict = None
                    for server in servers:
                        server = dict(server)
                        if 'ipmi_address' in server:
                            ipmi_add = server['ipmi_address']
                        if 'id' in server:
                            hostname = server['id']
                        if 'ip_address' in server:
                            server_ip = server['ip_address']
                        if self._collectors_ip:
                            collectors_ip = eval(str(self._collectors_ip))
                        else:
                            self.log(self.ERROR, "Missing analytics node IP address for " + str(server['id']))
                            msg = "Missing analytics node IP address for " + \
                                  str(server['id'] + "\n" +
                                      "This needs to be configured in the Server Manager config\n")
                            raise ServerMgrException(msg)
                        # Query is sent only to first Analytics IP in the list of Analytics IPs
                        # We are assuming that all these Analytics nodes hold the same information
                        self.log(self.INFO, "Sending the query to: " + str(collectors_ip[0]))
                        if detail_type == 'ENV':
                            env_details_dict = self._dev_env_querying_obj.get_env_details(collectors_ip[0], ipmi_add,
                                                                                          server_ip, hostname)
                        elif detail_type == 'TEMP':
                            env_details_dict = self._dev_env_querying_obj.get_temp_details(collectors_ip[0], ipmi_add,
                                                                                           server_ip, hostname)
                        elif detail_type == 'FAN':
                            env_details_dict = self._dev_env_querying_obj.get_fan_details(collectors_ip[0], ipmi_add,
                                                                                          server_ip, hostname)
                        elif detail_type == 'PWR':
                            env_details_dict = self._dev_env_querying_obj.get_pwr_consumption(collectors_ip[0], ipmi_add,
                                                                                              server_ip, hostname)
                        else:
                            self.log(self.ERROR, "No Environment Detail of the type specified")
                            raise ServerMgrException("No Environment Detail of that Type")

                        if env_details_dict is None:
                            self.log(self.ERROR,
                                     "Failed to get details for server: "
                                               + str(hostname) + " with IP " + str(server_ip))
                            data += "\nFailed to get details for server: " + str(hostname) + \
                                    " with IP " + str(server_ip) + "\n"
                        else:
                            env_details_dict = dict(env_details_dict)
                            data += "\nServer: " + str(hostname) + "\nServer IP Address: " + str(server_ip) + "\n"
                            data += "{0}{1}{2}{3}{4}\n".format("Sensor", " " * (25 - len("Sensor")), "Reading",
                                                               " " * (35 - len("Reading")), "Status")
                            if server_ip in env_details_dict:
                                if detail_type in env_details_dict[str(server_ip)]:
                                    env_data = dict(env_details_dict[str(server_ip)][detail_type])
                                    for key in env_data:
                                        data_list = list(env_data[key])
                                        data += "{0}{1}{2}{3}{4}\n".format(str(key), " " * (25 - len(str(key))),
                                                                           str(data_list[0]),
                                                                           " " * (35 - len(str(data_list[0]))),
                                                                           str(data_list[1]))
                else:
                    raise ServerMgrException("Missing argument value in command line arguements"
                                             + "\nPlease specify one of the following options with this command:"
                                             + "\n--server_id <server_id>: To get the environment details of just one server"
                                             + "\n--cluster_id <cluster_id>: To get the environment details of all servers in the cluster"
                                             + "\n--tag <tag>: To get the environement details of all servers with a tag")
            else:
                raise ServerMgrException("Please specify one of the following options with this command:"
                                         + "\n--server_id <server_id>: To get the environment details of just one server"
                                         + "\n--cluster_id <cluster_id>: To get the environment details of all servers in the cluster"
                                         + "\n--tag <tag>: To get the environement details of all servers with a tag")
            return data
        except ServerMgrException as e:
            self.log(self.ERROR, "Error while Querying" + e.value)
            return e.value
        except Exception as e:
            self.log(self.ERROR, "Error while Querying" + e.message)
            return None

    # Function to get all env details
    def get_env_details(self, key_dict, tags_dict):
        try:
            return self.get_server_env_details_by_type(key_dict, 'ENV', tags_dict)
        except ServerMgrException as e:
            self.log(self.ERROR, "Exception while Querying" + e.value)
            return None

    # Function to get fan details
    def get_fan_details(self, key_dict, tags_dict):
        try:
            return self.get_server_env_details_by_type(key_dict, 'FAN', tags_dict)
        except ServerMgrException as e:
            self.log(self.ERROR, "Exception while Querying" + e.value)
            return None

    # Function to get temp details
    def get_temp_details(self, key_dict, tags_dict):
        try:
            return self.get_server_env_details_by_type(key_dict, 'TEMP', tags_dict)
        except ServerMgrException as e:
            self.log(self.ERROR, "Exception while Querying" + e.value)
            return None


    # Function to get pwr details
    def get_pwr_details(self, key_dict, tags_dict):
        try:
            return self.get_server_env_details_by_type(key_dict, 'PWR', tags_dict)
        except ServerMgrException as e:
            self.log(self.ERROR, "Exception while Querying" + e.value)
            return None

    def validate_smgr_env(self, request):
        ret_data = dict()
        ret_data['status'] = 1
        query_args = parse_qs(urlparse(request.url).query,
                              keep_blank_values=True)
        match_key = None
        match_value = None
        if len(query_args) == 0:
            raise ServerMgrException("No Type specified for monitoring object: Zero Arguments")
        elif len(query_args) == 1:
            ret_data["status"] = 0
            monitoring_key, monitoring_value = query_args.popitem()
            ret_data["monitoring_key"] = str(monitoring_key)
            ret_data["monitoring_value"] = str(monitoring_value[0])
            ret_data["match_key"] = match_key
            ret_data["match_value"] = match_value
            if str(monitoring_value[0]) != "Status" or str(monitoring_key) != "Type":
                raise ServerMgrException("No Type specified for monitoring object: One Argument" + str(monitoring_key) + "   " + str(monitoring_value[0]))
        elif len(query_args) == 2:
            monitoring_key, monitoring_value = query_args.popitem()
            ret_data["monitoring_key"] = str(monitoring_key)
            ret_data["monitoring_value"] = str(monitoring_value[0])
            if str(monitoring_value[0]) == "Status" or str(monitoring_key) != "Type":
                raise ServerMgrException("No Type specified for monitoring object: Two Arguments")
            match_key, match_value = query_args.popitem()
            match_keys = list()
            match_keys.append('id')
            match_keys.append('cluster_id')
            match_keys.append('tag')
            match_keys.append('discovered')
            if match_key not in match_keys:
                raise ServerMgrException("Match Key not present")
            if match_value is None or match_value[0] == '':
                raise ServerMgrException("Match Value not Specified")
            ret_data["status"] = 0
            ret_data["match_key"] = str(match_key)
            ret_data["match_value"] = str(match_value[0])
        return ret_data

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
