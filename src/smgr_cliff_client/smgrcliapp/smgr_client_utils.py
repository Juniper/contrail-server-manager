#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4

from StringIO import StringIO
import pycurl
import json
import urllib
from prettytable import PrettyTable
import ast
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

_DEF_SMGR_IP = "127.0.0.1"
_DEF_SMGR_PORT = 9001


# Below array of dictionary's is used by add and edit
# function to add payload when user choses to input
# object parameter values manually instead of providing a
# json file.
main_object_dict = {
    "cluster": OrderedDict([
        ("id", "Specify unique id for this cluster"),
        ("email", "Email id for notifications"),
        ("base_image_id", "Base image id"),
        ("package_image_id", "Package id"),
        ("parameters", OrderedDict([
            ("router_asn", "Router asn value"),
            ("subnet_mask", "Subnet mask"),
            ("gateway", "Default gateway for servers in this cluster"),
            ("password", "Default password for servers in this cluster"),
            ("domain", "Default domain for servers in this cluster"),
            ("database_dir", "home directory for cassandra"),
            ("database_token", "initial database token"),
            ("use_certificates", "whether to use certificates for auth (True/False)"),
            ("multi_tenancy", "Openstack multitenancy (True/False)"),
            ("service_token", "Service token for openstack access"),
            ("keystone_username", "Keystone user name"),
            ("keystone_password", "keystone password"),
            ("keystone_tenant", "keystone tenant name"),
            ("analytics_data_ttl", "analytics data TTL"),
            ("osd_bootstrap_key", "OSD Bootstrap Key"),
            ("admin_key", "Admin Authentication Key"),
            ("storage_mon_secret", "Storage Monitor Secret Key")]))
    ]),
    "server": OrderedDict([
        ("id", "server id value"),
        ("host_name", "host name of the server"),
        ("ip_address", "server ip address"),
        ("mac_address", "server mac address"),
        ("roles", "comma-separated list of roles for this server"),
        ("contrail", OrderedDict([
            ("control_data_interface", "Name of control_data_interface")
        ])),
        ("parameters", OrderedDict([
            ("interface_name", "Ethernet Interface name"),
            ("partition", "Use this partition and create lvm"),
            ("disks", "Storage OSDs (default none)")])),
        ("network", OrderedDict([
            ("management_interface", "Name of the management interface"),
            ("provisioning", "provisioning method"),
            ("interfaces", list([
                OrderedDict([
                    ("name", "name of interface"),
                    ("ip_address", "ip_address of interface"),
                    ("mac_address", "mac_address of interface"),
                    ("default_gateway", "default_gateway of interface"),
                    ("dhcp", "dhcp status of interface"),
                    ("type", "Type of interface"),
                    ("member_interfaces", list([])),
                    ("bond_options", OrderedDict([
                        ("miimon", "miimon"),
                        ("mode", "mode"),
                        ("xmit_hash_policy", "xmit_hash_policy")
                    ]))
                ])
            ]))
        ])),
        ("cluster_id", "cluster id the server belongs to"),
        ("tag", "tag dict for server"),
        ("tag1", "tag value for this tag"),
        ("tag2", "tag value for this tag"),
        ("tag3", "tag value for this tag"),
        ("tag4", "tag value for this tag"),
        ("tag5", "tag value for this tag"),
        ("tag6", "tag value for this tag"),
        ("tag7", "tag value for this tag"),
        ("subnet_mask", "subnet mask (default use value from cluster table)"),
        ("gateway", "gateway (default use value from cluster table)"),
        ("domain", "domain name (default use value from cluster table)"),
        ("password", "root password (default use value from cluster table)"),
        ("ipmi_password", "IPMI password"),
        ("ipmi_username", "IPMI username"),
        ("ipmi_address", "IPMI address"),
        ("email", "email id for notifications (default use value from server's cluster)"),
        ("base_image_id", "Base image id"),
        ("package_image_id", "Package id")
    ]),
    "image": OrderedDict([
        ("id", "Specify unique image id for this image"),
        ("version", "Specify version for this image"),
        ("category", "image/package"),
        ("type",
         "ubuntu/redhat/esxi5.1/esxi5.5/contrail-ubuntu-package/contrail-storage-ubuntu-package"),
        ("path", "complete path where image file is located on server"),
        ("parameters", OrderedDict([
            ("kickstart", "kickstart file for base image"),
            ("kickseed", "kickseed file for base image")])),
    ]),
    "tag": OrderedDict([
        ("tag1", "Specify tag name for tag1"),
        ("tag2", "Specify tag name for tag2"),
        ("tag3", "Specify tag name for tag3"),
        ("tag4", "Specify tag name for tag4"),
        ("tag5", "Specify tag name for tag5"),
        ("tag6", "Specify tag name for tag6"),
        ("tag7", "Specify tag name for tag7"),
    ]),
    "dhcp_host": OrderedDict([
        ("host_fqdn", "Specify unique FQDN for this host"),
        ("mac_address", "Specify unique MAC for this host"),
        ("host_name", "Specify host name for this host"),
        ("ip_address", "Specify IP Address of this host"),
    ]),
    "dhcp_subnet": OrderedDict([
        ("subnet_address", "Specify unique Subnet Address for cobbler to control"),
        ("subnet_mask", "Specify Subnet mask for this subnet"),
        ("subnet_domain", "Specify Subnet domain for this subnet"),
        ("subnet_gateway", "Specify Subnet gateway for this subnet"),
        ("dns_server_list", "Specify DNS Server List for this subnet"),
        ("search_domains_list", "Specify List of Search domains for this subnet"),
        ("default_lease_time", "Default lease time for leases to this subnet"),
        ("max_lease_time", "Max lease time for leases to this subnet"),
    ]),
    "server_keys": "['id','mac_address']",
    "cluster_keys": "['id']",
    "image_keys": "['id']"
}


class SmgrClientUtils():
    smgr_ip = _DEF_SMGR_IP
    smgr_port = _DEF_SMGR_PORT
    object_dict = main_object_dict

    def __init__(self, smgr_ip=None, smgr_port=None):
        if smgr_ip:
            self.smgr_ip = smgr_ip
        if smgr_port:
            self.smgr_port = smgr_port

    # Return object dict
    def get_object_dict(self):
        return self.object_dict

    #start print_rest_response
    @staticmethod
    def print_rest_response(resp):
        if resp:
            try:
                resp_str = json.loads(resp)
                resp = json.dumps(resp_str, sort_keys=True, indent=4)
            except ValueError:
                pass
        return resp
    #end print_rest_resp

    @staticmethod
    def send_REST_request(ip, port, obj=None, rest_api_params=None,
                          payload=None, match_key=None, match_value=None, detail=False, force=False, method="PUT"):
        try:
            args_str = ""
            show_pass = False
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = ""
            if method == "PUT" or method == "POST" and obj:
                url = "http://%s:%s/%s" % (
                    ip, port, obj)
                if match_key and match_value:
                    args_str += urllib.quote_plus(match_key) + "=" + urllib.quote_plus(match_value)
                if args_str != '':
                    url += "?" + args_str
            elif method == "GET":
                if rest_api_params:
                    url = "http://%s:%s/%s" % (ip, port, rest_api_params['object'])
                    if 'show_passwords' in rest_api_params:
                        show_pass=True
                    if rest_api_params["select"]:
                        args_str += "select" + "=" \
                                    + urllib.quote_plus(rest_api_params["select"]) + "&"
                    if rest_api_params["match_key"] and rest_api_params["match_value"]:
                        args_str += urllib.quote_plus(rest_api_params["match_key"]) + "=" + \
                                    urllib.quote_plus(rest_api_params["match_value"])
                    if rest_api_params["object"] == "log" and \
                            rest_api_params["file_key"]:
                        args_str += "&" + \
                        urllib.quote_plus(rest_api_params["file_key"]) + \
                        "=" + urllib.quote_plus(rest_api_params["file_value"])

                elif obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += urllib.quote_plus(match_key) + "=" + urllib.quote_plus(match_value)
                if force:
                    args_str += "&force"
                if detail:
                    args_str += "&detail"
                if show_pass:
                    args_str += "&show_pass=true"
                if args_str != '':
                    url += "?" + args_str
            elif method == "DELETE":
                if obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += urllib.quote_plus(match_key) + "=" + urllib.quote_plus(match_value)
                if force:
                    args_str += "&force"
                if args_str != '':
                    url += "?" + args_str
            else:
                return None
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, url)
            if obj != "image/upload":
                conn.setopt(pycurl.HTTPHEADER, headers)
            if method == "POST" and payload:
                conn.setopt(pycurl.POST, 1)
                conn.setopt(pycurl.POSTFIELDS, '%s' % json.dumps(payload))
            elif method == "PUT" and payload:
                conn.setopt(pycurl.POST, 1)
                if obj == "image/upload":
                    conn.setopt(pycurl.HTTPPOST, payload.items())
                else:
                    conn.setopt(pycurl.POSTFIELDS, '%s' % json.dumps(payload))
                conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
            elif method == "GET":
                conn.setopt(pycurl.HTTPGET, 1)
            elif method == "DELETE":
                conn.setopt(pycurl.CUSTOMREQUEST, "delete")
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.TIMEOUT, 4800)
            conn.perform()
            return response.getvalue()
        except Exception as e:
            return "Error: " + str(e)
            # end def send_REST_request

    @staticmethod
    def convert_json_to_list(obj, json_resp):
        return_list = list()
        data_dict = dict(json_resp)
        if len(data_dict.keys()) == 1 and obj in ['server', 'cluster', 'image', 'mac', 'ip']:
            key, value = data_dict.popitem()
            dict_list = eval(str(value))
            for d in dict_list:
                d = dict(d)
                id_key, id_value = d.popitem()
                return_list.append(id_value)
        elif obj == 'tag':
            for key in data_dict:
                return_list.append(data_dict[key])
        return return_list

    @staticmethod
    def convert_json_to_table(obj, json_resp, select_item=None):
        if obj != "monitoring" and obj != "inventory":
            try:
                data_dict = json.loads(str(json_resp),object_pairs_hook=OrderedDict)
            except Exception as e:
                return "Exception found: " + str(e)
            return_table = None
            if len(data_dict.keys()) == 1 and obj != "tag":
                obj_type, obj_value = data_dict.popitem()
                if isinstance(obj_value,list):
                    dict_list = obj_value
                else:
                    dict_list = eval(str(obj_value))
                if len(dict_list) == 0:
                    return []
                sample_dict = OrderedDict(dict_list[0])
                sample_dict_key_list = sample_dict.keys()
                if "id" in sample_dict_key_list:
                    sample_dict_key_list.insert(0, sample_dict_key_list.pop(sample_dict_key_list.index("id")))
                return_table = PrettyTable(sample_dict_key_list)
                for d in dict_list:
                    d = dict(d)
                    dict_val_list = []
                    for key in sample_dict_key_list:
                        dict_val_list.append(d[key])
                    return_table.add_row(dict_val_list)
            elif obj == "tag":
                return_table = PrettyTable(["Tag No.", "Tag"])
                return_table.align["Tag"] = "l"
                for key in data_dict:
                    if str(key).startswith("tag"):
                        tag_no = key[3:]
                        tag = data_dict[key]
                        return_table.add_row([tag_no, tag])
        else:
            try:
                dict_list = list(json.loads(str(json_resp)))
            except Exception as e:
                return "Exception found: " + str(e)
            data_item = None
            if len(dict_list) == 0:
                error_msg = "No matching objects found for the query"
                return error_msg
            elif len(dict_list) >= 1:
                sample_server_dict = dict(dict_list[0])
                for key, val in sample_server_dict.iteritems():
                    if key == "ServerMonitoringInfo" or key == "ServerInventoryInfo":
                        if select_item in val:
                            sample_server_dict[key] = val
                            data_item = val[select_item]
                        elif "," in select_item:
                            select_item_list = select_item.split(",")
                            data_item = {}
                            for item in select_item_list:
                                if item in val:
                                    data_item[item] = val[item]
            if not data_item:
                error_msg = str(select_item) + " isn't found for the server(s) you requested"
                return error_msg
            data_dict = {}
            if isinstance(data_item, dict):
                data_dict = data_item
            elif isinstance(data_item, list) and len(data_item) >= 1:
                data_dict = data_item[0]
            elif data_item:
                data_dict[str(select_item)] = data_item

            key_list = list()
            key_list.append("server_name")
            for key, val in sorted(dict(data_dict).iteritems()):
                key_list.append(key)
            return_table = PrettyTable(key_list)
            for server_dict in dict_list:
                server_dict = dict(server_dict)
                server_id = server_dict["name"]
                if "ServerMonitoringInfo" in server_dict:
                    data_info_dict = server_dict["ServerMonitoringInfo"]
                elif "ServerInventoryInfo" in server_dict:
                    data_info_dict = server_dict["ServerInventoryInfo"]
                val_list = list()
                val_list.append(server_id)
                if select_item in ["disk_usage_stats", "disk_usage_totals", "network_info_stats", "network_info_totals",
                                   "sensor_stats"]:
                    if select_item in data_info_dict:
                        data_dict_list = list(data_info_dict[select_item])
                        for data_dict in data_dict_list:
                            data_dict = dict(data_dict)
                            val_list = list()
                            val_list.append(server_id)
                            for key in key_list[1:]:
                                val = data_dict.get(key)
                                if val:
                                    val_list.append(val)
                                else:
                                    val_list.append("N/A")
                            return_table.add_row(val_list)
                    else:
                        for x in range(len(key_list)-1):
                            val_list.append("N/A")
                    return_table.add_row(val_list)
                elif select_item in ["chassis_state", "resource_info_stats"]:
                    if select_item in data_info_dict:
                        data_dict = dict(data_info_dict[select_item])
                        for key, val in sorted(data_dict.iteritems()):
                            val_list.append(val)
                    else:
                        for x in range(len(key_list) - 1):
                            val_list.append("N/A")
                    return_table.add_row(val_list)
                elif select_item in ["cpu_info_state", "mem_state", "eth_controller_state"]:
                    if select_item in data_info_dict:
                        data_dict = dict(data_info_dict[select_item])
                        for key, val in sorted(data_dict.iteritems()):
                            val_list.append(val)
                    else:
                        for x in range(len(key_list) - 1):
                            val_list.append("N/A")
                    return_table.add_row(val_list)
                elif select_item in ["interface_infos", "fru_infos"]:
                    if select_item in data_info_dict:
                        data_dict_list = list(server_dict["ServerInventoryInfo"][select_item])
                        for data_dict in data_dict_list:
                            data_dict = dict(data_dict)
                            val_list = list()
                            val_list.append(server_id)
                            for key in key_list[1:]:
                                val = data_dict.get(key)
                                if val:
                                    val_list.append(val)
                                else:
                                    val_list.append("N/A")
                            return_table.add_row(val_list)
                    else:
                        for x in range(len(key_list) - 1):
                            val_list.append("N/A")
                        return_table.add_row(val_list)
                else:
                    val_list = list()
                    val_list.append(server_id)
                    if select_item in data_info_dict:
                        val_list.append(data_info_dict[str(select_item)])
                    elif "," in select_item:
                        select_item_list = select_item.split(",")
                        for item in select_item_list:
                            if item in data_info_dict and item in key_list:
                                val_list.append(data_info_dict[str(item)])
                    else:
                        val_list.append("N/A")
                    return_table.add_row(val_list)
        return return_table
