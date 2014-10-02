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

# Signal handler function. Exit on CTRL-C
def exit_gracefully(signal, frame):
    #Perform any cleanup actions in the logging system
    print "Exit"
    sys.exit(0)


'''
Class ServerMgrDevEnvQuerying describes the API layer exposed to ServerManager to allow it to query
the device environment information of the servers stored in its DB. The information is gathered through
REST API calls to the Server Mgr Analytics Node that hosts the relevant DB.
'''
class ServerMgrDevEnvQuerying():
    def __init__(self, log, translog):
        ''' Constructor '''
        self._smgr_log = log
        self._smgr_trans_log = translog

    def return_impi_call(self, ipmi_list=None):
        if ipmi_list is not None:
            results_dict = {}
            for address in ipmi_list:
                cmd = 'ipmitool -H ' + str(address) + ' -U admin -P admin sdr list all'
                result = self.call_subprocess(cmd)
                if result[0:5] == "Error":
                    results_dict[str(address)] = None
                    self._smgr_log.log(self._smgr_log.ERROR,
                                       "Error Polling server " + str(address) + ": " + result)
                else:
                    results_dict[str(address)] = result
            return results_dict
        else:
            self._smgr_log.log(self._smgr_log.ERROR,
                               "Error Querying Server Env: No Servers Found")
            raise ServerMgrException("Error Querying Server Env: Need to add servers before querying them")


    def return_curl_call(self, ip_add, hostname, analytics_ip):
        if ip_add is not None and hostname is not None:
            results_dict = dict()
            results_dict[str(ip_add)] = self.send_REST_request(analytics_ip, 8081, hostname)
            return results_dict
        else:
            self._smgr_log.log(self._smgr_log.ERROR,
                               "Error Querying Server Env: Server details missing")
            raise ServerMgrException("Error Querying Server Env: Server details not available")

    def call_subprocess(self, cmd):
        try:
            times = datetime.datetime.now()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            return p.stdout.read()
        except Exception as e:
            raise ServerMgrException("Error Querying Server Env: IPMI Polling command failed -> " + str(e))

    def send_REST_request(self, analytics_ip, port, hostname):
        try:
            response = StringIO()
            url = "http://%s:%s/analytics/uves/ipmi-stats/%s?flat" % (str(analytics_ip), port, hostname)
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
            sensor_data_list = list(data["SMIpmiInfo"]["sensor_status"])
            return sensor_data_list
        except Exception as e:
            self._smgr_log.log(self._smgr_log.ERROR, "Error Querying Server Env: REST request to Collector IP "
                               + str(analytics_ip) + " failed - > " + str(e))
            raise ServerMgrException("Error Querying Server Env: REST request to Collector IP "
                                     + str(analytics_ip) + " failed -> " + str(e))
    # end def send_REST_request


    def filter_impi_results(self, results_dict, key, match_patterns):
        return_data = dict()
        if len(results_dict.keys()) == 1 and "result" in results_dict:
            return_data = dict()
            fileoutput = cStringIO.StringIO(results_dict["result"])
            return_data[key] = dict()
            for line in fileoutput:
                reading = line.split("|")
                sensor = reading[0].strip()
                for pattern in match_patterns:
                    if re.match(pattern, sensor):
                        return_data[key][reading[0].strip()] = list()
                        return_data[key][reading[0].strip()].append(reading[1].strip())
                        return_data[key][reading[0].strip()].append(reading[2].strip())
        elif len(results_dict.keys()) >= 1 and "result" not in results_dict:
            for server in results_dict:
                return_data[server] = dict()
                fileoutput = cStringIO.StringIO(results_dict[server])
                return_data[server][key] = dict()
                for line in fileoutput:
                    reading = line.split("|")
                    sensor = reading[0].strip()
                    for pattern in match_patterns:
                        if re.match(pattern, sensor):
                            return_data[server][key][reading[0].strip()] = list()
                            return_data[server][key][reading[0].strip()].append(reading[1].strip())
                            return_data[server][key][reading[0].strip()].append(reading[2].strip())
        else:
            return_data = None
        return return_data

    def filter_sensor_results(self, results_dict, key, match_patterns):
        return_data = dict()
        if len(results_dict.keys()) >= 1:
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

    def get_env_details(self, analytics_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN', '^PWR', 'CPU[0-9][" "|_]Temp', '.*_Temp', '.*_Power']
        key = "ENV"
        self._smgr_log.log(self._smgr_log.INFO, "Fetching ENV details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    def get_fan_details(self, analytics_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN']
        key = "FAN"
        self._smgr_log.log(self._smgr_log.INFO, "Fetching FAN details for " + str(ip_add))
        self._smgr_log.log(self._smgr_log.INFO, "Fetching FAN details from " + str(analytics_ip))
        results_dict = self.return_curl_call(ip_add, hostname, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    def get_temp_details(self, analytics_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['CPU[0-9][" "|_]Temp', '.*_Temp']
        key = "TEMP"
        self._smgr_log.log(self._smgr_log.INFO, "Fetching TEMP details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    def get_pwr_consumption(self, analytics_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['^PWR', '.*_Power']
        key = "PWR"
        self._smgr_log.log(self._smgr_log.INFO, "Fetching PWR details for " + str(ip_add))
        results_dict = self.return_curl_call(ip_add, hostname, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

