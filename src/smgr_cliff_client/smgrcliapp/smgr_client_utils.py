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
        ("template", "Template id for cluster"),
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
        ("template", "Template id for server"),
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
        ("template", "Template id for this image"),
        ("type",
         "ubuntu/centos/redhat/esxi5.1/esxi5.5/contrail-ubuntu-package/contrail-centos-package/contrail-storage-ubuntu-package"),
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
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = ""
            if method == "PUT" or method == "POST" and obj:
                url = "http://%s:%s/%s" % (
                    ip, port, obj)
                if match_key and match_value:
                    args_str += match_key + "=" + match_value
                if args_str != '':
                    url += "?" + args_str
            elif method == "GET":
                if rest_api_params:
                    url = "http://%s:%s/%s" % (ip, port, rest_api_params['object'])
                    if rest_api_params["select"]:
                        args_str += "select" + "=" \
                                    + urllib.quote_plus(rest_api_params["select"]) + "&"
                    if rest_api_params["match_key"] and rest_api_params["match_value"]:
                        args_str += urllib.quote_plus(rest_api_params["match_key"]) + "=" + \
                                    urllib.quote_plus(rest_api_params["match_value"])

                elif obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += match_key + "=" + match_value
                if force:
                    args_str += "&force"
                if detail:
                    args_str += "&detail"
                if args_str != '':
                    url += "?" + args_str
            elif method == "DELETE":
                if obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += match_key + "=" + match_value
                if force:
                    args_str += "&force"
                if args_str != '':
                    url += "?" + args_str
            else:
                return None
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, url)
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
            conn.setopt(pycurl.TIMEOUT, 30)
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
            data_dict = dict(ast.literal_eval(str(json_resp)))
            return_table = None
            if len(data_dict.keys()) == 1 and obj != "tag":
                obj_type, obj_value = data_dict.popitem()
                dict_list = eval(str(obj_value))
                if len(dict_list) == 0:
                    return []
                sample_dict = dict(dict_list[0])
                sameple_dict_key_list = sample_dict.keys()
                sameple_dict_key_list.remove("id")
                sameple_dict_key_list = ['id'] + sameple_dict_key_list
                return_table = PrettyTable(sameple_dict_key_list)
                return_table.align["id"] = "l"
                for d in dict_list:
                    d = dict(d)
                    dict_val_list = d.values()
                    dict_val_list.remove(d["id"])
                    dict_val_list = [d["id"]] + dict_val_list
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
            dict_list = list(ast.literal_eval(json_resp))
            data_item = None
            if len(dict_list) == 1:
                sample_server_dict = dict(dict_list[0])
                for key, val in sample_server_dict.iteritems():
                    if key == "ServerMonitoringInfo" or key == "ServerInventoryInfo" and select_item in val:
                        data_item = val[select_item]
            elif len(dict_list) == 0:
                error_msg = "No matching objects found for the query"
                return error_msg
            elif len(dict_list) >= 2:
                sample_server_dict = {}
                for test_dict in dict_list:
                    for key, val in test_dict.iteritems():
                        if key == "ServerMonitoringInfo" or key == "ServerInventoryInfo" and select_item in val:
                            sample_server_dict[key] = val
                            data_item = val[select_item]
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
                            for key, val in sorted(data_dict.iteritems()):
                                val_list.append(val)
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
                            for key, val in sorted(data_dict.iteritems()):
                                val_list.append(val)
                    else:
                        for x in range(len(key_list) - 1):
                            val_list.append("N/A")
                    return_table.add_row(val_list)
                else:
                    val_list = list()
                    val_list.append(server_id)
                    if select_item in data_info_dict:
                        val_list.append(data_info_dict[str(select_item)])
                    else:
                        val_list.append("N/A")
                    return_table.add_row(val_list)
        return return_table
