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
from smgr_env_base import DeviceEnvBase
from server_mgr_exception import ServerMgrException as ServerMgrException

# Signal handler function. Exit on CTRL-C
def exit_gracefully(signal, frame):
    #Perform any cleanup actions in the logging system
    print "Exit"
    sys.exit(0)


class ServerMgrDevEnvQuerying():
    def __init__(self):
        ''' Constructor '''

    def return_impi_call(self, ipmi_list=None):
        if ipmi_list is None:
            cmd = 'ipmitool -H 10.87.129.207 -U admin -P admin sdr list all'
            result = self.call_subprocess(cmd)
            return {"result": result}
        else:
            results_dict = {}
            for address in ipmi_list:
                cmd = 'ipmitool -H ' + str(address) + ' -U admin -P admin sdr list all'
                result = self.call_subprocess(cmd)
                results_dict[str(address)] = result
            return results_dict

    def return_curl_call(self, ip_add_list, hostname_list, analytics_ip):
        if ip_add_list is None or hostname_list is None:
            return 0
        else:
            results_dict = dict()
            for ip, hostname in zip(ip_add_list, hostname_list):
                results_dict[str(ip)] = self.send_REST_request(analytics_ip, 8081, hostname)
            return results_dict

    def call_subprocess(self, cmd):
        times = datetime.datetime.now()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        return p.stdout.read()

    def send_REST_request(self, analytics_ip, port, hostname):
        try:
            response = StringIO()
            url = "http://%s:%s/analytics/uves/ipmi-stats/%s?flat" % (str(analytics_ip), port, hostname)
            print(url)
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
            raise ServerMgrException("Error Sending Py Curl REST request" + e.message)
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

    def get_env_details(self, analytics_ip, ipmi_list=None, ip_add_list=None, hostname_list=None):
        match_patterns = ['FAN', '.*_FAN', '^PWR', 'CPU[0-9][" "|_]Temp', '.*_Temp', '.*_Power']
        key = "ENV"
        #results_dict = dict(self.return_impi_call(ipmi_list))
        #return_data = self.filter_impi_results(results_dict, key, match_patterns)
        results_dict = self.return_curl_call(ip_add_list, hostname_list, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data


    def get_fan_details(self, analytics_ip, ipmi_list=None, ip_add_list=None, hostname_list=None):
        match_patterns = ['FAN', '.*_FAN']
        key = "FAN"
        #results_dict = dict(self.return_impi_call(ipmi_list))
        #return_data = self.filter_impi_results(results_dict, key, match_patterns)
        results_dict = self.return_curl_call(ip_add_list, hostname_list, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data



    def get_temp_details(self, analytics_ip, ipmi_list=None, ip_add_list=None, hostname_list=None):
        match_patterns = ['CPU[0-9][" "|_]Temp', '.*_Temp']
        key = "TEMP"
        #results_dict = dict(self.return_impi_call(ipmi_list))
        #return_data = self.filter_impi_results(results_dict, key, match_patterns)
        results_dict = self.return_curl_call(ip_add_list, hostname_list, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    def get_pwr_consumption(self, analytics_ip, ipmi_list=None, ip_add_list=None, hostname_list=None):
        match_patterns = ['^PWR', '.*_Power']
        key = "PWR"
        #results_dict = dict(self.return_impi_call(ipmi_list))
        #return_data = self.filter_impi_results(results_dict, key, match_patterns)
        results_dict = self.return_curl_call(ip_add_list, hostname_list, analytics_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

"""
import StringIO
import json
import pycurl
response = StringIO.StringIO()
url = "http://172.16.70.30:8081/analytics/uves/ipmi-stats/host05?flat"
headers = ["Content-Type:application/json"]
conn = pycurl.Curl()
conn.setopt(pycurl.TIMEOUT, 5)
conn.setopt(pycurl.URL, url)
conn.setopt(pycurl.HTTPHEADER, headers)
conn.setopt(pycurl.WRITEFUNCTION, response.write)
conn.setopt(pycurl.HTTPGET, 1)
conn.perform()
conn.close()
json_data = response.getvalue()
sensor_data_list = list(data["SMIpmiInfo"]["sensor_status"])
print sensor_data_list
"""
