import os
import syslog
import time
import signal
from StringIO import StringIO
import sys
import re
import abc
import datetime
import subprocess
import cStringIO
import pycurl
import json
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import ServerMgrTransactionlogger as ServerMgrTlog


# Class ServerMgrIPMIQuerying describes the API layer exposed to ServerManager to allow it to query
# the device environment information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Analytics Node that hosts the relevant DB.
class ServerMgrIPMIQuerying():
    _query_engine_port = 8081
    def __init__(self, log_obj):
        ''' Constructor '''
        self._mon_log = log_obj

    # Function handles the polling of info from an list of IPMI addresses using REST API calls to analytics DB
    # and returns the data as a dictionary (JSON)
    def return_curl_call(self, ip_add, hostname, collectors_ip):
        if ip_add is not None and hostname is not None:
            results_dict = dict()
            results_dict[str(ip_add)] = self.send_REST_request(collectors_ip, self._query_engine_port, hostname)
            return results_dict
        else:
            self._mon_log.log("error",
                               "Error Querying Server Env: Server details missing")
            raise ServerMgrException("Error Querying Server Env: Server details not available")

    # Calls the IPMI tool command as a subprocess
    def call_subprocess(self, cmd):
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            return p.stdout.read()
        except Exception as e:
            raise ServerMgrException("Error Querying Server Env: IPMI Polling command failed -> " + str(e))

    # Packages and sends a REST API call to the Analytics node
    def send_REST_request(self, collectors_ip, port, hostname):
        try:
            response = StringIO()
            collectors_ip_components = str(collectors_ip).split(':')
            collectors_ip_server = collectors_ip_components[0]
            collectors_ip_port = collectors_ip_components[1]
            url = "http://%s:%s/analytics/uves/server/%s?flat" % (collectors_ip_server,
                                                                  self._query_engine_port, hostname)
            self._mon_log.log("info", url)
            headers = ["Content-Type:application/json"]
            conn = pycurl.Curl()
            conn.setopt(pycurl.TIMEOUT, 5)
            conn.setopt(pycurl.URL, str(url))
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(conn.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.perform()
            json_data = response.getvalue()
            data = json.loads(json_data)
            sensor_data_list = list(data["SMIpmiInfo"]["sensor_state"])
            return sensor_data_list
        except Exception as e:
            self._mon_log.log("error", "Error Querying Server Env: REST request to Collector IP "
                               + str(collectors_ip) + " failed - > " + str(e.message))
            return None
    # end def send_REST_request

    # Filters the data returned from REST API call for requested information
    def filter_sensor_results(self, results_dict, key, match_patterns):
        return_data = dict()
        if results_dict and len(results_dict.keys()) >= 1:
            for server in results_dict:
                return_data[server] = dict()
                sensor_data_list = list(results_dict[server])
                return_data[server][key] = dict()
                for sensor_data_dict in sensor_data_list:
                    sensor_data_dict = dict(sensor_data_dict)
                    sensor = sensor_data_dict['sensor']
                    reading = sensor_data_dict['reading']
                    status = sensor_data_dict['status']
                    for pattern in match_patterns:
                        if re.match(pattern, sensor):
                            return_data[server][key][str(sensor)] = list()
                            return_data[server][key][str(sensor)].append(reading)
                            return_data[server][key][str(sensor)].append(status)
        else:
            return_data = None
        return return_data

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_env_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN', '^PWR', 'CPU[0-9][" "|_]Temp', '.*_Temp', '.*_Power']
        key = "ENV"
        self._mon_log.log("info", "Fetching ENV details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get FAN info from a set of server addressses
    def get_fan_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN']
        key = "FAN"
        self._mon_log.log("info", "Fetching FAN details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get TEMP info from a set of server addressses
    def get_temp_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['CPU[0-9][" "|_]Temp', '.*_Temp']
        key = "TEMP"
        self._mon_log.log("info", "Fetching TEMP details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get PWR info from a set of server addressses
    def get_pwr_consumption(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['^PWR', '.*_Power']
        key = "PWR"
        self._mon_log.log("info", "Fetching PWR details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

