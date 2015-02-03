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

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the Analytics node
    def send_REST_request(self, server_ip, port):
        try:
            response = StringIO()
            url = "http://%s:%s/%s" % (server_ip, port, 'InventoryInfo')
            headers = ["Content-Type:application/json"]
            conn = pycurl.Curl()
            conn.setopt(pycurl.TIMEOUT, 3)
            conn.setopt(pycurl.URL, str(url))
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(conn.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.perform()
            data_dict = response.getvalue()
            data_dict = dict(json.loads(data_dict))
            data_list = list(data_dict["__ServerInventoryInfoUve_list"]["ServerInventoryInfoUve"])
            return data_list
        except Exception as e:
            print "Inventory Error is: " + str(e)
            return None

    # end def send_REST_request

    # Filters the data returned from REST API call for requested information
    def filter_inventory_results(self, data_list, server_list):
        data_list = list(data_list)
        server_inventory_info_dict = dict()
        server_hostname_list = list()
        if data_list and server_list and len(data_list) >= 1 and len(server_list) >= 1:
            for server in server_list:
                server = dict(server)
                server_hostname_list.append(server['id'])
            for server in data_list:
                server = dict(server)
                server_hostname = server["data"]["ServerInventoryInfo"]["name"]["#text"]
                if server_hostname in server_hostname_list:
                    server_inventory_info_dict[str(server_hostname)] = dict()
                    server_inventory_info_dict[str(server_hostname)]["name"] = server_hostname
                    server_inventory_info_dict[str(server_hostname)]["hardware_model"] = \
                        server["data"]["ServerInventoryInfo"]["hardware_model"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["physical_processor_count"] = \
                        server["data"]["ServerInventoryInfo"]["physical_processor_count"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["cpu_cores_count"] = \
                        server["data"]["ServerInventoryInfo"]["cpu_cores_count"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["virtual_machine"] = \
                        server["data"]["ServerInventoryInfo"]["virtual_machine"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["total_numof_disks"] = \
                        server["data"]["ServerInventoryInfo"]["total_numof_disks"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["os"] = \
                        server["data"]["ServerInventoryInfo"]["os"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["os_version"] = \
                        server["data"]["ServerInventoryInfo"]["os_version"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["os_family"] = \
                        server["data"]["ServerInventoryInfo"]["os_family"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["kernel_version"] = \
                        server["data"]["ServerInventoryInfo"]["kernel_version"]["#text"]
                    server_inventory_info_dict[str(server_hostname)]["uptime_seconds"] = \
                        server["data"]["ServerInventoryInfo"]["uptime_seconds"]["#text"]
                    """
                    server_fru_list = list(server["data"]["ServerInventoryInfo"]["fru_infos"]["list"]["fru_info"])
                    fru_dict_list = list()
                    for fru in server_fru_list:
                        fru = dict(fru)
                        server_fru_info_dict = dict()
                        server_fru_info_dict["fru_description"] = fru["fru_description"]["#text"]
                        server_fru_info_dict["chassis_type"] = fru["chassis_type"]["#text"]
                        server_fru_info_dict["chassis_serial_number"] = fru["chassis_serial_number"]["#text"]
                        server_fru_info_dict["board_mfg_date"] = fru["board_mfg_date"]["#text"]
                        server_fru_info_dict["board_manufacturer"] = fru["board_manufacturer"]["#text"]
                        server_fru_info_dict["board_product_name"] = fru["board_product_name"]["#text"]
                        server_fru_info_dict["board_serial_number"] = fru["board_serial_number"]["#text"]
                        server_fru_info_dict["board_part_number"] = fru["board_part_number"]["#text"]
                        server_fru_info_dict["product_manfacturer"] = fru["product_manfacturer"]["#text"]
                        server_fru_info_dict["product_name"] = fru["product_name"]["#text"]
                        server_fru_info_dict["product_part_number"] = fru["product_part_number"]["#text"]
                        fru_dict_list.append(server_fru_info_dict)
                    server_inventory_info_dict[str(server_hostname)]["fru_infos"] = fru_dict_list
                    server_interface_list = \
                        list(server["data"]["ServerInventoryInfo"]["interface_infos"]["list"]["interface_info"])
                    interface_dict_list = list()
                    for interface in server_interface_list:
                        interface = dict(interface)
                        server_interface_info_dict = dict()
                        server_interface_info_dict["interface_name"] = interface["interface_name"]["#text"]
                        if "macaddress" in interface:
                            server_interface_info_dict["macaddress"] = interface["macaddress"]["#text"]
                        if "ip_addr" in interface:
                            server_interface_info_dict["ip_addr"] = interface["ip_addr"]["#text"]
                        if "netmask" in interface:
                            server_interface_info_dict["netmask"] = interface["netmask"]["#text"]
                        interface_dict_list.append(server_interface_info_dict)
                    server_inventory_info_dict[str(server_hostname)]["interface_infos"] = interface_dict_list
                    """
        else:
            server_inventory_info_dict = None
        return server_inventory_info_dict

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

    def handle_smgr_response(self, resp, ip_add=None, smgr_port=None, rest_api_params=None):
        data = json.loads(resp)
        server_list = list(data["server"])
        data = ""
        try:
            inv_details_dict = self.get_inventory(ip_add, smgr_port, server_list)
            if inv_details_dict is None:
                data += "\nFailed to get details for query. Monitoring might not be configured on Server Manager.\n"
            else:
                inv_details_dict = dict(inv_details_dict)
                for hostname in inv_details_dict:
                    data += "\n\n{0}{1}{2}\n\n".format("Hostname", " " * (25 - len("Hostname")), str(hostname))
                    inventory_info = dict(inv_details_dict[str(hostname)])
                    for key in inventory_info.keys():
                        data += "{0}{1}{2}\n".format(str(key), " " * (25 - len(str(key))), str(inventory_info[key]))
            return data
        except Exception as e:
            msg = "Exception while handling the Server Manager Response: " + str(e)
            return msg

    # Function to get environment info of all types (TEMP, FAN, PWR) from a set of server addressses
    def get_inventory(self, server_ip, smgr_port,  server_list=None):
        data_list = self.send_REST_request(server_ip, smgr_port)
        if data_list:
            return_data = self.filter_inventory_results(data_list, server_list)
            return return_data
        else:
            return None
