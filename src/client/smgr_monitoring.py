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
    _query_engine_port = 8107

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the Server Manager node
    def send_REST_request(self, server_ip, port):
        try:
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = "http://%s:%s/%s" % (server_ip, port, 'MonitorInfo')
            args_str = ''
            conn = pycurl.Curl()
            conn.setopt(pycurl.TIMEOUT, 3)
            conn.setopt(pycurl.URL, url)
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.perform()
            data_dict = response.getvalue()
            data_dict = dict(json.loads(data_dict))
            data_list = list(data_dict["__ServerMonitoringInfoTrace_list"]["ServerMonitoringInfoTrace"])
            return data_list
        except Exception as e:
            print "Error is: " + str(e)
            return None
    # end def send_REST_request

    # Filters the data returned from REST API call for requested information
    def filter_sensor_results(self, data_list, key, server_list):
        data_list = list(data_list)
        server_sensor_info_dict = dict()
        server_hostname_list = list()
        if data_list and server_list and len(data_list) >= 1 and len(server_list) >=1:
            for server in server_list:
                server = dict(server)
                server_hostname_list.append(server['id'])
            for server in data_list:
                server = dict(server)
                server_hostname = server["data"]["ServerMonitoringInfo"]["name"]["#text"]
                if server_hostname in server_hostname_list:
                    server_sensor_info_dict[str(server_hostname)] = dict()
                    server_sensor_list = list(server["data"]["ServerMonitoringInfo"]["sensor_state"]["list"]["IpmiSensor"])
                    for sensor in server_sensor_list:
                        sensor = dict(sensor)
                        sensor_name = sensor["sensor"]["#text"]
                        status = sensor["status"]["#text"]
                        reading = sensor["reading"]["#text"]
                        unit = sensor["unit"]["#text"]
                        sensor_type = sensor["sensor_type"]["#text"]
                        if key == "all" or key == sensor_type:
                            server_sensor_info_dict[str(server_hostname)][str(sensor_name)] = list()
                            server_sensor_info_dict[str(server_hostname)][str(sensor_name)].append(reading)
                            server_sensor_info_dict[str(server_hostname)][str(sensor_name)].append(unit)
                            server_sensor_info_dict[str(server_hostname)][str(sensor_name)].append(status)
        else:
            server_sensor_info_dict = None
        return server_sensor_info_dict

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
        rest_api_params['select'] = "ipmi_address, ip_address, id"
        rest_api_params['monitoring_key'] = None
        rest_api_params['monitoring_value'] = None
        return rest_api_params

    def handle_smgr_response(self, resp, ip_add=None, smgr_port=None, rest_api_params=None):
        data = json.loads(resp)
        server_list = list(data["server"])
        data = ""
        try:
            detail_type = dict(rest_api_params).get('monitoring_value')
            if detail_type == 'Env':
                env_details_dict = self.get_env_details(ip_add, smgr_port, server_list)
            elif detail_type == 'Temp':
                env_details_dict = self.get_temp_details(ip_add, smgr_port, server_list)
            elif detail_type == 'Fan':
                env_details_dict = self.get_fan_details(ip_add, smgr_port, server_list)
            elif detail_type == 'Pwr':
                env_details_dict = self.get_pwr_consumption(ip_add, smgr_port, server_list)
            else:
                return "No Environment Detail of that Type"

            if env_details_dict is None:
                data += "\nFailed to get details for query. Monitoring might not be configured on Server Manager.\n"
            else:
                env_details_dict = dict(env_details_dict)
                for hostname in env_details_dict:
                    sensor_list = dict(env_details_dict[str(hostname)])
                    data += "\nServer: " + str(hostname) + "\n"
                    data += "{0}{1}{2}{3}{4}{5}{6}\n".format("Sensor", " " * (25 - len("Sensor")),
                            "Reading", " " * (25 - len("Reading")), "Unit", " " * (25 - len("Unit")), "Status")
                    for sensor in sensor_list.keys():
                        reading_list = list(sensor_list[sensor])
                        sensor_name = sensor
                        data += "{0}{1}{2}{3}{4}{5}{6}\n".format(str(sensor_name), " " * (25 - len(str(sensor_name))),
                            str(reading_list[0]), " " * (25 - len(str(reading_list[0]))), str(reading_list[1]),
                            " " * (25 - len(str(reading_list[1]))), str(reading_list[2]))
            return data
        except Exception as e:
            msg = "Exception while handling the Server Manager Response: " + str(e)
            return msg

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_env_details(self, server_ip, smgr_port, server_list=None):
        key = "all"
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data = self.filter_sensor_results(data_list, key, server_list)
            return return_data
        else:
            return None

    # Function to get FAN info from a set of server addressses
    def get_fan_details(self, server_ip, smgr_port, server_list=None):
        key = "fan"
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data = self.filter_sensor_results(data_list, key, server_list)
            return return_data
        else:
            return None

    # Function to get TEMP info from a set of server addressses
    def get_temp_details(self, server_ip, smgr_port, server_list=None):
        key = "temperature"
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data = self.filter_sensor_results(data_list, key, server_list)
            return return_data
        else:
            return None

    # Function to get PWR info from a set of server addressses
    def get_pwr_consumption(self, server_ip, smgr_port, server_list=None):
        key = "power"
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data = self.filter_sensor_results(data_list, key, server_list)
            return return_data
        else:
            return None

