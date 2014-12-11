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
import xmltodict


# Class ServerMgrIPMIQuerying describes the API layer exposed to ServerManager to allow it to query
# the device environment information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Analytics Node that hosts the relevant DB.
class ServerMgrInventory():
    _query_engine_port = 8107

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the Analytics node
    def send_REST_request(self, server_ip, port):
        try:
            response = StringIO()
            url = "http://%s:%s/Snh_SandeshUVECacheReq?x=ServerInventoryInfo" % (str(server_ip), port)
            headers = ["Content-Type:application/json"]
            conn = pycurl.Curl()
            conn.setopt(pycurl.TIMEOUT, 5)
            conn.setopt(pycurl.URL, str(url))
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(conn.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.perform()
            xml_data = response.getvalue()
            data = xmltodict.parse(str(xml_data))
            json_obj = json.dumps(data, sort_keys=True, indent=4)
            data_dict = dict(json.loads(json_obj))
            data_list = list(data_dict["__ServerInventoryInfoUve_list"]["ServerInventoryInfoUve"])
            return data_list
        except Exception as e:
            msg = "Error Querying Server Env: REST request to Collector IP " \
                  + str(server_ip) + " failed - > " + str(e)
            return None

    # end def send_REST_request

    # Filters the data returned from REST API call for requested information
    def filter_sensor_results(self, data_list, key, server_list):
        data_list = list(data_list)
        server_fru_info_dict = dict()
        server_hostname_list = list()
        if data_list and server_list and len(data_list) >= 1 and len(server_list) >= 1:
            for server in server_list:
                server = dict(server)
                server_hostname_list.append(server['id'])
            for server in data_list:
                server = dict(server)
                server_hostname = server["data"]["ServerInventoryInfo"]["name"]["#text"]
                if server_hostname in server_hostname_list:
                    server_fru_info_dict[str(server_hostname)] = list()
                    server_fru_list = list(server["data"]["ServerInventoryInfo"]["fru_infos"]["list"]["fru_info"])
                    for fru in server_fru_list:
                        fru = dict(fru)
                        fru_description = fru["sensor"]["#text"]
                        status = fru["status"]["#text"]
                        reading = fru["reading"]["#text"]
                        unit = fru["unit"]["#text"]
                        sensor_type = fru["sensor_type"]["#text"]
                        if key == "all" or key == sensor_type:
                            server_fru_info_dict[str(server_hostname)][str(sensor_name)] = list()
                            server_fru_info_dict[str(server_hostname)][str(sensor_name)].append(reading)
                            server_fru_info_dict[str(server_hostname)][str(sensor_name)].append(unit)
                            server_fru_info_dict[str(server_hostname)][str(sensor_name)].append(status)
        else:
            server_sensor_info_dict = None
        return server_sensor_info_dict

    def show_inventory(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'Inventory'
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

    def get_wrapper_call_params(self, rest_api_params):
        rest_api_params['object'] = 'server'
        if rest_api_params['match_key'] != 'where':
            rest_api_params['match_value'] = str(rest_api_params['match_key']) \
                                             + " is '" + str(rest_api_params['match_value']) + "'"
            rest_api_params['match_key'] = 'where'
        rest_api_params['select'] = "ipmi_address, ip_address, id"
        return rest_api_params

    def handle_smgr_response(self, resp, ip_add=None, query_engine_port=None, rest_api_params=None):
        if query_engine_port:
            self._query_engine_port = query_engine_port
        data = json.loads(resp)
        server_list = list(data["server"])
        data = ""
        try:
            inv_details_dict = self.get_inventory(ip_add, server_list)

            if inv_details_dict is None:
                data += "\nFailed to get details for query. Monitoring might not be configured on Server Manager.\n"
            else:
                env_details_dict = dict(inv_details_dict)
                for hostname in env_details_dict:
                    sensor_list = dict(env_details_dict[str(hostname)])
                    data += "\nServer: " + str(hostname) + "\n"
                    data += "{0}{1}{2}{3}{4}{5}{6}\n".format("Sensor", " " * (25 - len("Sensor")),
                                                             "Reading", " " * (25 - len("Reading")), "Unit",
                                                             " " * (25 - len("Unit")), "Status")
                    for sensor in sensor_list.keys():
                        reading_list = list(sensor_list[sensor])
                        sensor_name = sensor
                        data += "{0}{1}{2}{3}{4}{5}{6}\n".format(str(sensor_name), " " * (25 - len(str(sensor_name))),
                                                                 str(reading_list[0]),
                                                                 " " * (25 - len(str(reading_list[0]))),
                                                                 str(reading_list[1]),
                                                                 " " * (25 - len(str(reading_list[1]))),
                                                                 str(reading_list[2]))
            return data
        except Exception as e:
            msg = "Exception while handling the Server Manager Response: " + str(e)
            return msg

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_inventory(self, server_ip, server_list=None):
        data_list = self.send_REST_request(server_ip, self._query_engine_port)
        if data_list:
            return_data = self.filter_sensor_results(data_list, server_list)
            return return_data
        else:
            return None
