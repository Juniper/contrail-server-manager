#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_edit.py
   Author : Nitish Krishna
   Description : This program is a simple cli interface to
   edit server manager configuration objects.
   Objects can be cluster or server.
"""
import logging
import pdb
import sys
import ast
from itertools import izip
import json
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command


class Edit(Command):
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
        return "Edit an existing Object in Server Manager Database"

    def get_parser(self, prog_name):

        self.smgr_objects = ["server", "cluster", "tag"]
        self.mandatory_params["server"] = ['id', 'ip_address', 'subnet_mask', 'gateway']
        self.mandatory_params["cluster"] = ['id']
        self.mandatory_params["tag"] = []
        self.multilevel_param_classes["server"] = ["network", "parameters", "contrail"]
        self.multilevel_param_classes["cluster"] = ["parameters"]

        parser = super(Edit, self).get_parser(prog_name)
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
                    help="Parameter " + str(param) + " for the cluster being edited",
                    default=None
                )
        parser_cluster.add_argument(
            "--file_name", "-f",
            help="json file containing cluster param values", dest="file_name", default=None)

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

    def verify_edited_tags(self, obj, obj_payload):
        existing_tags = smgrutils.send_REST_request(
            self.smgr_ip, self.smgr_port,
            obj="tag", detail=True, method="GET")
        tag_dict = json.loads(existing_tags)
        tag_dict_idx_list = [str(key) for key in tag_dict.keys()]
        rev_tag_dict = dict((v, k) for k, v in tag_dict.iteritems())
        allowed_tag_indices = self.object_dict["tag"].keys()
        if obj == "tag":
            for tag_idx in obj_payload:
                if tag_idx not in allowed_tag_indices:
                    self.app.print_error_message_and_quit("\nThe tag index " + str(tag_idx) +
                                                          " is not a valid tag index. Please use tags1-7\n\n")
                elif tag_idx not in tag_dict_idx_list:
                    self.app.print_error_message_and_quit("\nThe tag " + str(tag_idx) +
                                                          " with this index hasn't been added, it cannot be edited."
                                                          "Use the add tag command to add a tag to this index.\n"
                                                          "List is" + str(tag_dict_idx_list) + "\n")
        elif obj == "server":
            edited_tag_dict = obj_payload["tag"]
            edited_tags = edited_tag_dict.keys()
            for tag in edited_tags:
                if tag not in rev_tag_dict:
                    self.app.print_error_message_and_quit("\nThe tag " + str(tag) +
                                                          " has been added to server config but hasn't been"
                                                          " added as a user defined tag. Add this tag first\n\n")

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

    def edit_object(self, obj, parsed_args, remaining_args=None):
        obj_payload = {}
        top_level_object_params = self.object_dict[obj].keys()
        multilevel_obj_params = self.multilevel_param_classes[obj]
        for arg in vars(parsed_args):
            if arg in top_level_object_params and arg not in multilevel_obj_params and getattr(parsed_args, arg, None):
                obj_payload[arg] = self.process_val(getattr(parsed_args, arg, None))
        if remaining_args:
            self.parse_remaining_args(obj, obj_payload, multilevel_obj_params, remaining_args)
        return obj_payload

    def edit_tag(self, parsed_args, remaining_args=None):
        tag_payload = {}
        allowed_tags = self.object_dict["tag"].keys()
        if hasattr(parsed_args, "tags"):
            edit_tag_dict = self.process_val(getattr(parsed_args, "tags", None))
            tag_payload = {k: v for k, v in edit_tag_dict.iteritems() if k in allowed_tags}
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
        if not smgr_obj:
            self.app.print_error_message_and_quit("\nNo object entered for editing\n")
        payload = None

        try:
            if getattr(parsed_args, "file_name", None) and smgr_obj in self.smgr_objects:
                payload = json.load(open(parsed_args.file_name))
                if smgr_obj == "tag":
                    self.verify_edited_tags(smgr_obj, payload)
                else:
                    for obj_payload in payload[str(smgr_obj)]:
                        if "tag" in obj_payload and smgr_obj == "server":
                            self.verify_edited_tags(smgr_obj, obj_payload)
                        if "id" not in obj_payload and smgr_obj != "tag":
                            self.app.print_error_message_and_quit("No id specified for object being edited")
            elif not (getattr(parsed_args, "id", None) or getattr(parsed_args, "mac_address", None)) \
                    and smgr_obj != "tag":
                # 1. Check if parsed args has id for object
                self.app.print_error_message_and_quit(
                    "\nYou need to specify the id or mac_address to edit an object (Arguement --id/--mac_address).\n")
            elif smgr_obj not in self.smgr_objects:
                self.app.print_error_message_and_quit(
                    "\nThe object: " + str(smgr_obj) + " is not a valid one.\n")
            elif smgr_obj == "tag":
                payload = self.edit_tag(parsed_args, remaining_args)
                self.verify_edited_tags(smgr_obj, payload)
            else:
                payload = {}
                # 2. Check that id exists for this added object
                resp = smgrutils.send_REST_request(
                    self.smgr_ip, self.smgr_port,
                    obj=smgr_obj, detail=True, method="GET")
                existing_objects_dict = json.loads(resp)
                existing_objects = existing_objects_dict[smgr_obj]
                obj_id_list = list()
                edited_obj_id = getattr(parsed_args, "id", None)
                for ex_obj in existing_objects:
                    obj_id_list.append(ex_obj["id"])
                    if edited_obj_id == ex_obj["id"]:
                        edited_obj_config = ex_obj
                if edited_obj_id not in obj_id_list:
                    self.app.print_error_message_and_quit(
                        "\n" + str(smgr_obj) + " with this id doesn't already exist. You need to add it first.\n")
                payload[smgr_obj] = list()
                # 3. Collect object payload from parsed_args and remaining args
                payload[smgr_obj].append(self.edit_object(smgr_obj, parsed_args, remaining_args))
                # 4. Verify tags and mandatory params added for given object
                for obj_payload in payload[smgr_obj]:
                    if "tag" in obj_payload and smgr_obj == "server":
                        self.verify_edited_tags(smgr_obj, obj_payload)
        except ValueError as e:
            self.app.print_error_message_and_quit("\nError in CLI Format - ValueError: " + str(e) + "\n")
        except Exception as e:
            self.app.print_error_message_and_quit("\nException here:" + str(e) + "\n")
        if payload:
            resp = smgrutils.send_REST_request(
                self.smgr_ip, self.smgr_port, obj=smgr_obj, payload=payload, method="PUT")
            smgrutils.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
        else:
            self.app.stdout.write("\nNo payload for object " + str(smgr_obj) + "\nPlease enter params\n")

    def run(self, parsed_args, remaining_args=None):
        self.take_action(parsed_args, remaining_args)
