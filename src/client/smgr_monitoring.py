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


# Class ServerMgrIPMIQuerying describes the API layer exposed to ServerManager to allow it to query
# the device environment information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Analytics Node that hosts the relevant DB.
class ServerMgrIPMIQuerying():
    _query_engine_port = 8081

    def __init__(self):
        ''' Constructor '''

    # Function handles the polling of info from an list of IPMI addresses using REST API calls to analytics DB
    # and returns the data as a dictionary (JSON)
    def return_curl_call(self, ip_add, hostname, collectors_ip):
        if ip_add and hostname and collectors_ip:
            results_dict = dict()
            results_dict[str(ip_add)] = self.send_REST_request(collectors_ip, self._query_engine_port, hostname)
            return results_dict
        else:
            return "Error Querying Server Env: Server details not available"

    # Calls the IPMI tool command as a subprocess
    def call_subprocess(self, cmd):
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
            return p.stdout.read()
        except Exception as e:
            return "Error Querying Server Env: IPMI Polling command failed -> " + str(e)

    # Packages and sends a REST API call to the Analytics node
    def send_REST_request(self, collectors_ip, port, hostname):
        try:
            response = StringIO()
            collectors_ip_server = str(collectors_ip)
            url = "http://%s:%s/analytics/uves/server/%s?flat" % (collectors_ip_server,
                                                                  self._query_engine_port, hostname)
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
            msg = "Error Querying Server Env: REST request to Collector IP " \
                  + str(collectors_ip) + " failed - > " + str(e.message)
            return msg

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

    def show_fan_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'Monitor'
        rest_api_params['monitoring_key'] = 'Type'
        rest_api_params['monitoring_value'] = 'Fan'
        rest_api_params['select'] = None
        if args.server_id:
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif args.cluster_id:
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif args.tag:
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif args.where:
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    # end def show_fan_details

    def show_temp_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'Monitor'
        rest_api_params['monitoring_key'] = 'Type'
        rest_api_params['monitoring_value'] = 'Temp'
        rest_api_params['select'] = None
        if args.server_id:
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif args.cluster_id:
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif args.tag:
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif args.where:
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    # end def show_temp_details

    def show_pwr_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'Monitor'
        rest_api_params['monitoring_key'] = 'Type'
        rest_api_params['monitoring_value'] = 'Pwr'
        rest_api_params['select'] = None
        if args.server_id:
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif args.cluster_id:
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif args.tag:
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif args.where:
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    # end def show_pwr_details

    def show_env_details(slef, args):
        rest_api_params = {}
        rest_api_params['object'] = 'Monitor'
        rest_api_params['monitoring_key'] = 'Type'
        rest_api_params['monitoring_value'] = 'Env'
        rest_api_params['select'] = None
        if args.server_id:
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif args.cluster_id:
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif args.tag:
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif args.where:
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    # end def show_env_details

    def show_mon_status(self, args):
        rest_api_params = {}
        rest_api_params['select'] = None
        rest_api_params['object'] = 'Monitor'
        rest_api_params['monitoring_key'] = 'Type'
        rest_api_params['monitoring_value'] = 'Status'
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
        return rest_api_params

    def get_wrapper_call_params(self, rest_api_params):
        rest_api_params['object'] = 'server'
        if rest_api_params['match_key'] != 'where':
            rest_api_params['match_value'] = str(rest_api_params['match_key']) \
                + " is '" + str(rest_api_params['match_value']) + "'"
            rest_api_params['match_key'] = 'where'
        rest_api_params['select'] = "ipmi_address, ip_address, id, email"
        rest_api_params['monitoring_key'] = None
        rest_api_params['monitoring_value'] = None
        return rest_api_params

    def handle_smgr_response(self, resp, collector_ips=None, rest_api_params=None):
        data = json.loads(resp)
        server_list = list(data["server"])
        data = ""
        try:
            for server in server_list:
                server = dict(server)
                if 'ipmi_address' in server:
                    ipmi_add = server['ipmi_address']
                if 'id' in server:
                    hostname = server['id']
                if 'ip_address' in server:
                    server_ip = server['ip_address']
                if not collector_ips:
                    msg = "Missing analytics node IP address for " + \
                          str(server['id'] + "\n" +
                              "This needs to be configured in the Server Manager config\n")
                    return msg
                # Query is sent only to first Analytics IP in the list of Analytics IPs
                # We are assuming that all these Analytics nodes hold the same information
                detail_type = rest_api_params['monitoring_value']
                if detail_type == 'Env':
                    env_details_dict = self.get_env_details(collector_ips[0], ipmi_add, server_ip, hostname)
                elif detail_type == 'Temp':
                    env_details_dict = self.get_temp_details(collector_ips[0], ipmi_add, server_ip, hostname)
                elif detail_type == 'Fan':
                    env_details_dict = self.get_fan_details(collector_ips[0], ipmi_add, server_ip, hostname)
                elif detail_type == 'Pwr':
                    env_details_dict = self.get_pwr_consumption(collector_ips[0], ipmi_add, server_ip, hostname)
                else:
                    return "No Environment Detail of that Type"

                if env_details_dict is None:
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
            return data
        except Exception as e:
            msg = "Exception while handling the Server Manager Response: " + str(e)
            return msg

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_env_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN', '^PWR', 'CPU[0-9][" "|_]Temp', '.*_Temp', '.*_Power']
        key = "Env"
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get FAN info from a set of server addressses
    def get_fan_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['FAN', '.*_FAN']
        key = "Fan"
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get TEMP info from a set of server addressses
    def get_temp_details(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['CPU[0-9][" "|_]Temp', '.*_Temp']
        key = "Temp"
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

    # Function to get PWR info from a set of server addressses
    def get_pwr_consumption(self, collectors_ip, ipmi_add=None, ip_add=None, hostname=None):
        match_patterns = ['^PWR', '.*_Power']
        key = "Pwr"
        results_dict = self.return_curl_call(ip_add, hostname, collectors_ip)
        return_data = self.filter_sensor_results(results_dict, key, match_patterns)
        return return_data

