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
import pdb

# Class ServerMgrInventory describes the API layer exposed to ServerManager to allow it to query
# the device inventory information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Node that hosts the relevant DB and Cache.
class ServerMgrInventory():

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the ServerManager node
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
                    server_inv_info_fields = dict(server["data"]["ServerInventoryInfo"])
                    for field in server_inv_info_fields:
                        if field == "mem_state":
                            server_mem_info_dict = server["data"]["ServerInventoryInfo"][field]["memory_info"]
                            mem_info_dict = dict()
                            for mem_field in server_mem_info_dict:
                                mem_info_dict[mem_field] = server_mem_info_dict[mem_field]["#text"]
                            server_inventory_info_dict[str(server_hostname)][field] = mem_info_dict
                        elif field == "interface_infos":
                            server_interface_list = \
                                list(server["data"]["ServerInventoryInfo"][field]["list"]["interface_info"])
                            interface_dict_list = list()
                            for interface in server_interface_list:
                                #interface = dict(interface)
                                server_interface_info_dict = dict()
                                for intf_field in interface:
                                        server_interface_info_dict[intf_field] = interface[intf_field]["#text"]
                                interface_dict_list.append(server_interface_info_dict)
                                server_inventory_info_dict[str(server_hostname)][field] = interface_dict_list
                        elif field == "fru_infos":
                            server_fru_list = list(server["data"]["ServerInventoryInfo"][field]["list"]["fru_info"])
                            fru_dict_list = list()
                            for fru in server_fru_list:
                                #fru = dict(fru)
                                server_fru_info_dict = dict()
                                for fru_field in fru:
                                    server_fru_info_dict[fru_field] = fru[fru_field]["#text"]
                                fru_dict_list.append(server_fru_info_dict)
                            server_inventory_info_dict[str(server_hostname)][field] = fru_dict_list
                        elif field == "cpu_info_state":
                            server_cpu_info_dict = server["data"]["ServerInventoryInfo"][field]["cpu_info"]
                            cpu_info_dict = dict()
                            for cpu_field in server_cpu_info_dict:
                                cpu_info_dict[cpu_field] = server_cpu_info_dict[cpu_field]["#text"]
                            server_inventory_info_dict[str(server_hostname)][field] = cpu_info_dict
                        elif field == "eth_controller_state":
                            server_eth_info_dict = server["data"]["ServerInventoryInfo"][field]["ethernet_controller"]
                            eth_info_dict = dict()
                            for eth_field in server_eth_info_dict:
                                eth_info_dict[eth_field] = server_eth_info_dict[eth_field]["#text"]
                            server_inventory_info_dict[str(server_hostname)][field] = eth_info_dict
                        else:
                            server_inventory_info_dict[str(server_hostname)][field] = \
                                server_inv_info_fields[field]["#text"]
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
                data += "\nFailed to get details for query. " \
                        "Inventory collectors and introspect port might not be configured on Server Manager.\n"
            else:
                inv_details_dict = dict(inv_details_dict)
                for hostname in inv_details_dict:
                    data += "\n\n{0}{1}{2}\n\n".format("Hostname", " " * (25 - len("Hostname")), str(hostname))
                    inventory_info = dict(inv_details_dict[str(hostname)])
                    for key in inventory_info.keys():
                        if key == "mem_state":
                            data += "\n{0}{1}{2}\n".format("Mem_Key", " " * (25 - len("Mem_Key")), "Value")
                            mem_state_dict = dict(inventory_info[key])
                            for mem_key in mem_state_dict:
                                data += "{0}{1}{2}\n".format(str(mem_key), " " * (25 - len(str(mem_key))),
                                                             str(mem_state_dict[mem_key]))
                        elif key == "cpu_info_state":
                            data += "\n{0}{1}{2}\n".format("CPU_Key", " " * (25 - len("CPU_Key")), "Value")
                            cpu_state_dict = dict(inventory_info[key])
                            for cpu_key in cpu_state_dict:
                                data += "{0}{1}{2}\n".format(str(cpu_key), " " * (25 - len(str(cpu_key))),
                                                             str(cpu_state_dict[cpu_key]))
                        elif key == "eth_controller_state":
                            data += "\n{0}{1}{2}\n".format("Eth_Key", " " * (25 - len("Eth_Key")), "Value")
                            eth_state_dict = dict(inventory_info[key])
                            for eth_key in eth_state_dict:
                                data += "{0}{1}{2}\n".format(str(eth_key), " " * (25 - len(str(eth_key))),
                                                             str(eth_state_dict[eth_key]))
                        elif key == "fru_infos":
                            fru_dict_list = list(inventory_info[key])
                            data += "\n{0}{1}{2}\n".format("FRU_Key", " " * (25 - len("FRU_Key")), "Value")
                            for index, fru_dict in enumerate(fru_dict_list):
                                data += "{0}\n".format("FRU " + str(int(index+1)))
                                fru_dict = dict(fru_dict)
                                for fru_key in fru_dict:
                                    data += "{0}{1}{2}\n".format(str(fru_key), " " * (25 - len(str(fru_key))),
                                                                 str(fru_dict[fru_key]))
                        elif key == "interface_infos":
                            intf_dict_list = list(inventory_info[key])
                            data += "\n{0}{1}{2}\n".format("Inft_Key", " " * (25 - len("FRU_Key")), "Value")
                            for index, intf_dict in enumerate(intf_dict_list):
                                data += "{0}\n".format("FRU " + str(int(index + 1)))
                                intf_dict = dict(intf_dict)
                                for intf_key in intf_dict:
                                    data += "{0}{1}{2}\n".format(str(intf_key), " " * (25 - len(str(intf_key))),
                                                                 str(intf_dict[intf_key]))
                        else:
                            data += "\n{0}{1}{2}\n".format(str(key), " " * (25 - len(str(key))), str(inventory_info[key]))
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
