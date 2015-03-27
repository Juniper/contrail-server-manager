#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_monitoring.py
   Author : Nitish Krishna
   Description : TBD
"""

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
import pdb


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

    def show_mon_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'MonitorInfo'
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
        if args.type:
            rest_api_params['select'] = args.type
            if args.type == "status":
                rest_api_params['object'] = 'MonitorConf'
        else:
            rest_api_params['select'] = None
        return rest_api_params
    # end def show_mon_details

"""
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
        type_dict = {
            'Env': "all",
            'Temp': "temperature",
            'Fan': "fan",
            'Pwr': "power"
        }
        data = ""
        try:
            detail_type = dict(rest_api_params).get('monitoring_value')
            if detail_type and detail_type in type_dict:
                mon_info_dict = dict(self.get_details(ip_add, smgr_port,
                                                      key=type_dict[detail_type], server_list=server_list))
            else:
                return "No Environment Detail of that Type"

            if mon_info_dict is None:
                data += "\nFailed to get details for query. Monitoring might not be configured on Server Manager.\n"
            else:
                #Sensor Info
                sensor_info_dict = dict(mon_info_dict["sensor"])
                for hostname in sensor_info_dict:
                    sensor_list = dict(sensor_info_dict[str(hostname)])
                    data += "\nServer: " + str(hostname) + "\n"
                    data += "{0}{1}{2}{3}{4}{5}{6}\n".format("Sensor", " " * (25 - len("Sensor")),
                            "Reading", " " * (25 - len("Reading")), "Unit", " " * (25 - len("Unit")), "Status")
                    for sensor in sensor_list.keys():
                        reading_list = list(sensor_list[sensor])
                        sensor_name = sensor
                        data += "{0}{1}{2}{3}{4}{5}{6}\n".format(str(sensor_name), " " * (25 - len(str(sensor_name))),
                                                                 str(reading_list[0]),
                                                                 " " * (25 - len(str(reading_list[0]))),
                                                                 str(reading_list[1]),
                                                                 " " * (25 - len(str(reading_list[1]))),
                                                                 str(reading_list[2]))
                #Chassis Info
                chassis_info_dict = dict(mon_info_dict["chassis"])
                for hostname in chassis_info_dict:
                    chassis_dict = dict(chassis_info_dict[str(hostname)])
                    data += "\n\nServer: " + str(hostname) + "\n"
                    data += "{0}{1}{2}\n".format("Chassis Detail", " " * (25 - len("Chassis Detail")), "Value")
                    for chassis_key in chassis_dict.keys():
                        data += "{0}{1}{2}\n".format(str(chassis_key), " " * (25 - len(str(chassis_key))),
                                                     str(chassis_dict[chassis_key]))
                #Disk Info
                disk_info_dict = dict(mon_info_dict["disk"])
                for hostname in disk_info_dict:
                    disk_list = dict(disk_info_dict[str(hostname)])
                    data += "\n\nServer: " + str(hostname) + "\n"
                    data += "{0}{1}{2}{3}{4}\n".format("Disk", " " * (25 - len("Disk")),
                                                       "ReadMB", " " * (25 - len("ReadMB")), "WriteMB")
                    for disk in disk_list.keys():
                        disk_info_list = list(disk_list[disk])
                        disk_name = disk
                        data += "{0}{1}{2}{3}{4}\n".format(str(disk_name), " " * (25 - len(str(disk_name))),
                                                           str(disk_info_list[0]),
                                                           " " * (25 - len(str(disk_info_list[0]))),
                                                           str(disk_info_list[1]))
            return data
        except Exception as e:
            msg = "Exception while handling the Server Manager Response: " + str(e)
            return msg

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_details(self, server_ip, smgr_port, key="all", server_list=None):
        return_data = dict()
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data["sensor"] = self.filter_sensor_results(data_list, key, server_list)
            return_data["chassis"] = self.filter_chassis_results(data_list, server_list)
            return_data["disk"] = self.filter_disk_results(data_list, server_list)
            return return_data
        else:
            return None
            """

