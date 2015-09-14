#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_add.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   add server manager configuration objects.
   Objects can be cluster, server, or image.
"""
import logging
import pdb
import sys
import ast
from itertools import izip
import json
import readline
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command

# Below array of dictionary's is used by add_payload
# function to add payload when user choses to input
# object parameter values manually instead of providing a
# json file.
object_dict = {
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


class Add(Command):
    log = logging.getLogger(__name__)
    command_dictionary = dict()
    multilevel_param_classes = dict()
    mandatory_params = {}
    mandatory_params_args = {}
    smgr_objects = list()
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_mandatory_options(self):
        return self.mandatory_params_args

    def get_description(self):
        return "Add an Object to Server Manager Database"

    def get_parser(self, prog_name):

        self.smgr_objects = ["server", "cluster", "image", "tag"]
        self.mandatory_params["server"] = ['id', 'cluster_id', 'mac_address', 'ip_address', 'ipmi_address', 'password',
                                           'subnet_mask', 'gateway']
        self.mandatory_params["cluster"] = ['id']
        self.mandatory_params["image"] = ['id', 'category', 'version', 'type', 'path']
        self.mandatory_params["tag"] = []
        self.multilevel_param_classes["server"] = ["network", "parameters", "tag", "contrail"]
        self.multilevel_param_classes["cluster"] = ["parameters"]
        self.multilevel_param_classes["image"] = ["parameters"]

        parser = super(Add, self).get_parser(prog_name)
        # Process the arguments

        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for objects',
                                           dest='object')

        # Subparser for server edit
        parser_server = subparsers.add_parser(
            "server", help='Create server')
        parser_server.add_argument(
            "--file_name", "-f",
            help="json file containing server param values", default=None)
        for param in object_dict["server"]:
            if param not in self.multilevel_param_classes["server"]:
                parser_server.add_argument(
                    "--" + str(param),
                    help="Value for parameter " + str(param) + " for the server config being edited",
                    default=None
                )

        # Subparser for server tags edit
        parser_tag = subparsers.add_parser(
            "tag", help='Create tags')
        parser_tag.add_argument(
            "--file_name", "-f",
            help="json file containing tag values", default=None)

        # Subparser for cluster edit
        parser_cluster = subparsers.add_parser(
            "cluster", help='Create cluster')
        for param in object_dict["cluster"]:
            if param not in self.multilevel_param_classes["cluster"]:
                parser_cluster.add_argument(
                    "--" + str(param),
                    help="Parameter " + str(param) + " for the cluster being added",
                    default=None
                )
        parser_cluster.add_argument(
            "--file_name", "-f",
            help="json file containing cluster param values", default=None)

        # Subparser for image edit
        parser_image = subparsers.add_parser(
            "image", help='Create image')
        for param in object_dict["image"]:
            if param not in self.multilevel_param_classes["image"]:
                parser_image.add_argument(
                    "--" + str(param),
                    help="Parameter " + str(param) + " for the image being added",
                    default=None
                )
        parser_image.add_argument(
            "--file_name", "-f",
            help="json file containing image param values", default=None)

        for obj in self.smgr_objects:
            self.command_dictionary[str(obj)] = ['f', 'file_name']
        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        for key in self.mandatory_params:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.mandatory_params[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.mandatory_params[key] if len(s) == 1]
            self.mandatory_params_args[key] = new_dict[key]

        return parser
    # end def parse_arguments

    def object_exists(self, obj, object_id_key, object_id_value, payload):
        # post a request for each object
        resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port,
                                 obj=obj, payload=payload, match_key=object_id_key,
                                 match_value=object_id_value, detail=True, method="GET")
        if resp:
            smgr_object_dict = json.loads(resp)
            if len(smgr_object_dict[obj]):
                return True

        return False
    # end object_exists

    def get_object_config_ini_entries(self, obj):
        default_config_dict = self.app.get_default_config()
        return default_config_dict[obj]

    # end get_object_config_ini_entries

    def get_default_object(self, obj):
        # Get the code defaults from two levels:
        # 1. defaults in ini file
        # 2. Template can be supplied with template id as parameter
        # Precedence order: backend_code_defaults < ini file at backend < ini file at client < template < json
        payload = {}
        resp = smgrutils.send_REST_request(
            self.smgr_ip, self.smgr_port,
            obj="tag", payload=payload, detail=True, method="GET")
        tag_dict = json.loads(resp)
        rev_tag_dict = dict((v, k) for k, v in tag_dict.iteritems())
        default_object = {}
        config_ini_object_defaults = self.get_object_config_ini_entries(obj)
        if not config_ini_object_defaults:
            return default_object
        default_object["parameters"] = {}
        default_object["tag"] = {}
        for key, value in config_ini_object_defaults:
            if key in object_dict[obj]:
                default_object[key] = value
            elif key in object_dict[obj]["parameters"]:
                default_object["parameters"][key] = value
            elif key in rev_tag_dict:
                default_object["tag"][key] = value
        return default_object

    # end get_default_object

    def merge_with_defaults(self, object_item, payload):
        if object_item not in payload or not payload[object_item]:
            return
        default_object = self.get_default_object(object_item)
        for i in range(len(payload[object_item])):
            obj = payload[object_item][i]
            obj_id = "id"
            param_object = {}
            if "parameters" in obj and "parameters" in default_object:
                param_object = dict(default_object["parameters"].items() + obj["parameters"].items())
            elif "parameters" in default_object:
                param_object = default_object["parameters"]
            tag_object = {}
            if "tag" in obj and "tag" in default_object:
                tag_object = dict(default_object["tag"].items() + obj["tag"].items())
            elif "tag" in default_object:
                tag_object = default_object["tag"]
            payload[object_item][i] = dict(default_object.items() + obj.items())
            if param_object:
                payload[object_item][i]["parameters"] = param_object
            if tag_object:
                payload[object_item][i]["tag"] = tag_object

    # end merge_with_defaults

    def pairwise(self, iterable):
        a = iter(iterable)
        return izip(a, a)

    def process_val(self, val_set):
        return_dict = dict()
        if "," in val_set and "=" in val_set:
            key_val_pairs = str(val_set).split(",")
            for key_val_pair in key_val_pairs:
                key, val = key_val_pair.split("=")
                if key and val:
                    return_dict[key] = val
            return return_dict
        elif "=" in val_set:
            key, val = val_set.split("=")
            if key and val:
                return_dict[key] = val
            return return_dict
        elif "," in val_set:
            return_list = val_set.split(",")
            return_list = [str(x) if isinstance(x, str) or isinstance(x, unicode) else x
                           for x in return_list]
            return return_list
        else:
            return val_set

    def parse_remaining_args(self, obj, obj_payload, multilevel_obj_params, rem_args):
        rem_args = ast.literal_eval(str(rem_args))
        if len(multilevel_obj_params) == 0:
            return 0
        # Check each multilevel param arguement has an attached value
        if (len(rem_args) % 2) != 0:
            self.app.print_error_message_and_quit("\nNumber of arguements and values do not match.\n")
        for arg, val in self.pairwise(rem_args):
            working_object = obj_payload
            working_object_type = "dict"
            saved_param_name = None
            saved_working_object = None
            saved_list_index = 0
            if str(arg).startswith("--"):
                arg = str(arg)[2:]
                top_level_arg = arg.split(".")[0]
                top_level_arg = top_level_arg.split("[")[0]
                # The main top level arg we are trying to configure should be one of the multilevel params
                if top_level_arg not in multilevel_obj_params:
                    self.app.print_error_message_and_quit("\nUnrecognized parameter: " + str(top_level_arg) + "\n")
                if "." in arg:
                    arg_parts = arg.split(".")
                    for arg_part in arg_parts:
                        if "[" not in arg_part and "]" not in arg_part:
                            # This level is a dict key
                            if working_object_type == "dict":
                                if arg_part not in working_object:
                                    working_object[str(arg_part)] = {}
                                saved_working_object = working_object
                                working_object = working_object[str(arg_part)]
                            elif working_object_type == "list":
                                if len(working_object) == saved_list_index:
                                    working_object.append({})
                                elif len(working_object) > saved_list_index:
                                    pass
                                else:
                                    self.app.print_error_message_and_quit(
                                        "\nIndexError: list assignment index out of range\n")
                                working_object = working_object[int(saved_list_index)]
                                if arg_part not in working_object:
                                    working_object[arg_part] = {}
                                saved_working_object = working_object
                                working_object = working_object[str(arg_part)]
                            saved_param_name = arg_part
                            working_object_type = "dict"
                        elif "[" in arg_part and "]" in arg_part:
                            # This level is a list
                            start = arg_part.index("[") + 1
                            end = arg_part.index("]")
                            current_list_index = int(arg_part[start:end])
                            param_name = arg_part.split("[")[0]
                            if working_object_type == "dict":
                                if param_name and param_name not in working_object:
                                    working_object[str(param_name)] = []
                                elif not param_name:
                                    self.app.print_error_message_and_quit("\nError: Missing key name for list in dict"
                                                                          " -> list must have a key name\n")
                                working_object = working_object[str(param_name)]
                            elif working_object_type == "list":
                                if len(working_object) == saved_list_index:
                                    working_object.append([])
                                elif len(working_object) > saved_list_index:
                                    pass
                                else:
                                    self.app.print_error_message_and_quit(
                                        "\nIndexError: list assignment index out of range\n")
                                working_object = working_object[int(saved_list_index)]
                            if len(working_object) == current_list_index:
                                working_object.append([])
                            elif len(working_object) < current_list_index:
                                self.app.print_error_message_and_quit(
                                    "\nIndexError: list assignment index out of range\n")
                            saved_list_index = current_list_index
                            working_object_type = "list"
                    # end_for
                    if working_object_type == "dict" and saved_param_name and saved_working_object:
                        saved_working_object[saved_param_name] = self.process_val(val)
                    elif working_object_type == "list":
                        working_object[saved_list_index] = self.process_val(val)
                elif "[" in arg and "]" in arg:
                    # This level is a list
                    start = arg.index("[") + 1
                    end = arg.index("]")
                    current_list_index = int(arg[start:end])
                    param = arg.split("[")[0]
                    if param and param not in working_object:
                        working_object[str(param)] = []
                    working_object = working_object[str(param)]
                    if len(working_object) == current_list_index:
                        # Doesn't matter what you append
                        working_object.append({})
                    if len(working_object) < current_list_index:
                        self.app.print_error_message_and_quit("\nIndexError: list assignment index out of range\n")
                    working_object[current_list_index] = self.process_val(val)
                else:
                    return_val = self.process_val(val)
                    if arg not in working_object:
                        working_object[str(arg)] = return_val
                    elif isinstance(return_val, dict) and isinstance(working_object[str(arg)], dict):
                        for key, value in return_val.iteritems():
                            working_object[arg][key] = value
                    elif isinstance(return_val, list) and isinstance(working_object[arg], list):
                        for value in return_val:
                            if value not in working_object[arg]:
                                working_object[arg].append(value)

        return obj_payload

    def add_object(self, obj, parsed_args, remaining_args=None):
        obj_payload = {}
        top_level_object_params = object_dict[obj].keys()
        multilevel_obj_params = self.multilevel_param_classes[obj]
        for arg in vars(parsed_args):
            if arg in top_level_object_params and arg not in multilevel_obj_params and getattr(parsed_args, arg, None):
                obj_payload[arg] = self.process_val(getattr(parsed_args, arg, None))
        if remaining_args:
            self.parse_remaining_args(obj, obj_payload, multilevel_obj_params, remaining_args)
        return obj_payload

    def take_action(self, parsed_args, remaining_args=None):

        try:
            self.smgr_ip = self.smgr_port = None
            smgr_dict = self.app.get_smgr_config()

            if smgr_dict["smgr_ip"]:
                self.smgr_ip = smgr_dict["smgr_ip"]
            else:
                self.app.report_missing_config("smgr_ip")
            if smgr_dict["smgr_port"]:
                self.smgr_port = smgr_dict["smgr_port"]
            else:
                self.app.report_missing_config("smgr_port")

        except Exception as e:
            sys.exit("Exception: %s : Error getting smgr config" % e.message)

        smgr_obj = getattr(parsed_args, "object", None)
        payload = None

        try:
            if getattr(parsed_args, "file_name", None) and smgr_obj in self.smgr_objects:
                payload = json.load(open(parsed_args.file_name))
                for obj_payload in payload[str(smgr_obj)]:
                    if "tag" in obj_payload and smgr_obj == "server":
                        self.verify_edited_tags(smgr_obj, obj_payload)
                    if "id" not in obj_payload:
                        self.app.print_error_message_and_quit("No id specified for object being added")
            elif not getattr(parsed_args, "id", None):
                # 1. Check if parsed args has id for object
                self.app.print_error_message_and_quit(
                    "\nYou need to specify the id to edit an object (Arguement --id).\n")
            elif smgr_obj not in self.smgr_objects:
                self.app.print_error_message_and_quit(
                    "\nThe object: " + str(smgr_obj) + " is not a valid one.\n")
            else:
                payload = {}
                # 2. Check that id duplicate doesn't exist for this added object
                resp = smgrutils.send_REST_request(
                    self.smgr_ip, self.smgr_port,
                    obj=smgr_obj, detail=True, method="GET")
                existing_objects_dict = json.loads(resp)
                existing_objects = existing_objects_dict[smgr_obj]
                obj_id_list = list()
                added_obj_id = getattr(parsed_args, "id", None)
                for ex_obj in existing_objects:
                    obj_id_list.append(ex_obj["id"])
                if added_obj_id in obj_id_list:
                    self.app.print_error_message_and_quit(
                        "\n" + str(smgr_obj) + " with this id already exists. You cannot add it again.\n")
                payload[smgr_obj] = list()
                # 3. Collect object payload from parsed_args and remaining args
                payload[smgr_obj].append(self.add_object(smgr_obj, parsed_args, remaining_args))
                # 4. Merge obj_payload with ini defaults, in code defaults (same func)
                self.merge_with_defaults(smgr_obj, payload)
                # 5. Verify tags and mandatory params added for given object
                for obj_payload in payload[smgr_obj]:
                    if "tag" in obj_payload and smgr_obj == "server":
                        self.verify_edited_tags(smgr_obj, obj_payload)
                    mandatory_params_set = set(self.mandatory_params[smgr_obj])
                    added_params_set = set(obj_payload.keys())
                    if mandatory_params_set.difference(added_params_set):
                        self.app.stdout.write("\nMandatory parameters for object " + str(smgr_obj) + " not entered\n")
                        self.app.print_error_message_and_quit("\nList of missing mandatory parameters are: " + str(list(
                            mandatory_params_set.difference(added_params_set))) + "\n")
        except ValueError as e:
            self.app.stdout.write("\nError in CLI Format - ValueError: " + str(e) + "\n")
        except Exception as e:
            self.app.stdout.write("\nException here:" + str(e) + "\n")
        if payload:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj=smgr_obj, payload=payload, method="PUT")
            smgrutils.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
        else:
            self.app.stdout.write("\nNo payload for object " + str(smgr_obj) + "\nPlease enter params\n")

    def run(self, parsed_args, remaining_args=None):
        self.take_action(parsed_args, remaining_args)
