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
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command


class Add(Command):
    log = logging.getLogger(__name__)
    command_dictionary = dict()
    multilevel_param_classes = dict()
    mandatory_params = {}
    mandatory_params_args = {}
    smgr_objects = list()
    smgr_ip = None
    smgr_port = None
    smgrutils_obj = smgrutils()
    object_dict = smgrutils_obj.get_object_dict()

    def get_command_options(self):
        return self.command_dictionary

    def get_mandatory_options(self):
        return self.mandatory_params_args

    def get_description(self):
        return "Add an Object to Server Manager Database"

    def get_parser(self, prog_name):

        self.smgr_objects = ["config", "server", "cluster", "image", "tag", "dhcp_host", "dhcp_subnet"]
        self.mandatory_params["server"] = ['id', 'mac_address', 'ip_address', 'subnet_mask', 'gateway']
        self.mandatory_params["cluster"] = ['id']
        self.mandatory_params["image"] = ['id', 'category', 'version', 'type', 'path']
        self.mandatory_params["tag"] = []
        self.mandatory_params["config"] = ['file_name']
        self.mandatory_params["dhcp_subnet"] = ['subnet_address','subnet_mask','subnet_domain','subnet_gateway','dns_server_list','search_domains_list']
        self.mandatory_params["dhcp_host"] = ['host_fqdn','mac_address','ip_address','host_name']
        self.multilevel_param_classes["server"] = ["network", "parameters", "contrail"]
        self.multilevel_param_classes["cluster"] = ["parameters"]
        self.multilevel_param_classes["image"] = ["parameters"]
        self.multilevel_param_classes["dhcp_host"] = []
        self.multilevel_param_classes["dhcp_subnet"] = []
        parser = super(Add, self).get_parser(prog_name)
        # Process the arguments

        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for objects',
                                           dest='object')

        # Subparser for combined config edit
        parser_config = subparsers.add_parser(
            "config", help='Create server cluster and image from JSON')
        parser_config.add_argument(
            "--file_name", "-f",
            help="json file containing server cluster and image param values", dest="file_name", default=None)

        # Subparser for server edit
        parser_server = subparsers.add_parser(
            "server", help='Create server')
        parser_server.add_argument(
            "--file_name", "-f",
            help="json file containing server param values", dest="file_name", default=None)
        for param in self.object_dict["server"]:
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
            "--tags", help="Comma separated list of tag_number=tag_name pairs.", default=None)
        parser_tag.add_argument(
            "--file_name", "-f",
            help="json file containing tag values", dest="file_name", default=None)

        # Subparser for cluster edit
        parser_cluster = subparsers.add_parser(
            "cluster", help='Create cluster')
        for param in self.object_dict["cluster"]:
            if param not in self.multilevel_param_classes["cluster"]:
                parser_cluster.add_argument(
                    "--" + str(param),
                    help="Parameter " + str(param) + " for the cluster being added",
                    default=None
                )
        parser_cluster.add_argument(
            "--file_name", "-f",
            help="json file containing cluster param values", dest="file_name", default=None)

        # Subparser for image edit
        parser_image = subparsers.add_parser(
            "image", help='Create image')
        for param in self.object_dict["image"]:
            if param not in self.multilevel_param_classes["image"]:
                parser_image.add_argument(
                    "--" + str(param),
                    help="Parameter " + str(param) + " for the image being added",
                    default=None
                )
        parser_image.add_argument(
            "--file_name", "-f",
            help="json file containing image param values", dest="file_name", default=None)

        # Subparser for DHCP host edit
        parser_dhcp_host = subparsers.add_parser(
            "dhcp_host", help='Create DHCP Host')
        parser_dhcp_host.add_argument(
            "--file_name", "-f",
            help="json file containing dhcp_host param values", dest="file_name", default=None)
        for param in self.object_dict["dhcp_host"]:
            parser_dhcp_host.add_argument(
                "--" + str(param),
                help="Parameter " + str(param) + " for the image being added",
                default=None
            )

        # Subparser for DHCP subnet edit
        parser_dhcp_subnet = subparsers.add_parser(
            "dhcp_subnet", help='Create DHCP Subnet')
        parser_dhcp_subnet.add_argument(
            "--file_name", "-f",
            help="json file containing dhcp_subnet param values", dest="file_name", default=None)
        for param in self.object_dict["dhcp_subnet"]:
            parser_dhcp_subnet.add_argument(
                "--" + str(param),
                help="Parameter " + str(param) + " for the image being added",
                default=None
            )

        for obj in self.smgr_objects:
            self.command_dictionary[str(obj)] = ['f', 'file_name']
            if obj == "tag":
                self.command_dictionary[str(obj)] += ['tags']
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
        for key, value in config_ini_object_defaults.iteritems():
            if key in self.object_dict[obj]:
                default_object[key] = value
            elif key in self.object_dict[obj]["parameters"]:
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

    def verify_added_tags(self, smgr_obj, obj_payload):
        existing_tags = smgrutils.send_REST_request(
            self.smgr_ip, self.smgr_port,
            obj="tag", detail=True, method="GET")
        tag_dict = json.loads(existing_tags)
        rev_tag_dict = dict((v, k) for k, v in tag_dict.iteritems())
        allowed_tags = self.object_dict["tag"].keys()
        if smgr_obj == "tag":
            for tag_idx in obj_payload:
                if tag_idx not in allowed_tags:
                    self.app.print_error_message_and_quit("\nThe tag " + str(tag_idx) +
                                                          " is not a valid tag index. Please use tags1-7\n\n")
        elif smgr_obj == "server":
            added_tag_dict = obj_payload["tag"]
            added_tags = added_tag_dict.keys()
            for tag in added_tags:
                if tag not in rev_tag_dict:
                    self.app.print_error_message_and_quit("\nThe tag " + str(tag) +
                                                          " has been added to server config but hasn't been"
                                                          " added as a user defined tag. Add this tag first\n\n")

    def pairwise(self, iterable):
        a = iter(iterable)
        return izip(a, a)

    def process_val(self, val_set):
        return_dict = dict()
        if '[' in val_set and ']' in val_set:
            list_str = str(val_set)
            val_list = str(list_str)
            return val_list
        elif "," in val_set and "=" in val_set:
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
        top_level_object_params = self.object_dict[obj].keys()
        multilevel_obj_params = self.multilevel_param_classes[obj]
        for arg in vars(parsed_args):
            if arg in top_level_object_params and arg not in multilevel_obj_params and getattr(parsed_args, arg, None):
                obj_payload[arg] = self.process_val(getattr(parsed_args, arg, None))
                if arg == "roles" and isinstance(obj_payload[arg], str):
                    role_list = list()
                    role_list.append(obj_payload[arg])
                    obj_payload[arg] = role_list
        if remaining_args:
            self.parse_remaining_args(obj, obj_payload, multilevel_obj_params, remaining_args)
        return obj_payload

    def add_tag(self, parsed_args, remaining_args=None):
        tag_payload = {}
        allowed_tags = self.object_dict["tag"].keys()
        if hasattr(parsed_args, "tags"):
            add_tag_dict = self.process_val(getattr(parsed_args, "tags", None))
            tag_payload = {k: v for k, v in add_tag_dict.iteritems() if k in allowed_tags}
        return tag_payload

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
                if smgr_obj == "tag":
                    self.verify_added_tags(smgr_obj, payload)
                elif smgr_obj == "config":
                    for obj in payload.keys():
                        for obj_payload in payload[obj]:
                            if "id" not in obj_payload:
                                self.app.print_error_message_and_quit("No id specified for object %s being added\n" % (obj))
                else:
                    for obj_payload in payload[str(smgr_obj)]:
                        if "tag" in obj_payload and smgr_obj == "server":
                            self.verify_added_tags(smgr_obj, obj_payload)
                        if "id" not in obj_payload and (smgr_obj != "tag" and smgr_obj != "dhcp_host" and smgr_obj != "dhcp_subnet"):
                            self.app.print_error_message_and_quit("No id specified for object being added\n")
            elif not (getattr(parsed_args, "id", None) or getattr(parsed_args, "mac_address", None)) \
                    and smgr_obj != "tag" and smgr_obj != "dhcp_subnet":
                # Check if parsed args has id for object
                self.app.print_error_message_and_quit("\nYou need to specify the id or mac_address to add an object"
                                                      " (Arguement --id/--mac_address).\n")
            elif smgr_obj not in self.smgr_objects:
                self.app.print_error_message_and_quit(
                    "\nThe object: " + str(smgr_obj) + " is not a valid one.\n")
            elif smgr_obj == "tag":
                payload = self.add_tag(parsed_args, remaining_args)
                self.verify_added_tags(smgr_obj, payload)
            else:
                payload = {}
                payload[smgr_obj] = list()
                # Collect object payload from parsed_args and remaining args
                payload[smgr_obj].append(self.add_object(smgr_obj, parsed_args, remaining_args))
                # Verify tags and mandatory params added for given object
                for obj_payload in payload[smgr_obj]:
                    if "tag" in obj_payload and smgr_obj == "server":
                        self.verify_added_tags(smgr_obj, obj_payload)
                    mandatory_params_set = set(self.mandatory_params[smgr_obj])
                    added_params_set = set(obj_payload.keys())
                    if mandatory_params_set.difference(added_params_set):
                        self.app.stdout.write("\nMandatory parameters for object " + str(smgr_obj) + " not entered\n")
                        self.app.print_error_message_and_quit("\nList of missing mandatory parameters are: " + str(list(
                            mandatory_params_set.difference(added_params_set))) + "\n")
            # Merge obj_payload with ini defaults, in code defaults (same func)
            self.merge_with_defaults(smgr_obj, payload)
        except ValueError as e:
            self.app.stdout.write("\nError in CLI Format - ValueError: " + str(e) + "\n")
            self.app.stdout.write("\nError Message: " + str(e.message) + "\n")
            self.app.stdout.write("\nPayload: " + str(payload) + "\n")
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
