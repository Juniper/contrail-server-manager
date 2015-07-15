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
import pycurl
from StringIO import StringIO
import json
import readline
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
import smgr_client_def
from cliff.command import Command

# Below array of dictionary's is used by add_payload
# function to add payload when user choses to input
# object parameter values manually instead of providing a
# json file.
object_dict = {
    "cluster" : OrderedDict ([
        ("id", "Specify unique id for this cluster"),
        ("email", "Email id for notifications"),
        ("base_image_id", "Base image id"),
        ("package_image_id", "Package id"),
        ("parameters", OrderedDict ([
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
    "server": OrderedDict ([ 
        ("id", "server id value"),
        ("host_name", "host name of the server"),
        ("ip_address", "server ip address"),
        ("mac_address", "server mac address"),
        ("roles", "comma-separated list of roles for this server"),
        ("parameters", OrderedDict([
            ("interface_name", "Ethernet Interface name"),
            ("partition", "Use this partition and create lvm"),
            ("disks", "Storage OSDs (default none)")])),
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
    "image" : OrderedDict ([
        ("id", "Specify unique image id for this image"),
        ("version", "Specify version for this image"),
        ("category", "image/package"),
        ("type",
         "ubuntu/centos/redhat/esxi5.1/esxi5.5/contrail-ubuntu-package/contrail-centos-package/contrail-storage-ubuntu-package"),
        ("path", "complete path where image file is located on server"),
        ("parameters", OrderedDict([
            ("kickstart", "kickstart file for base image"),
            ("kickseed", "kickseed file for base image")])),
    ]),
    "tag" : OrderedDict ([
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


# End of add_config
class Add(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Add an Object to Server Manager Database"

    def get_parser(self, prog_name):
        parser = super(Add, self).get_parser(prog_name)
        # Process the arguments

        """
        parser.add_argument("--config_file", "-c",
                            help=("Server manager client config file "
                                  " (default - %s)" % (
                                      smgr_client_def._DEF_SMGR_CFG_FILE)))
        """
        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for objects',
                                           dest='object')

        # Subparser for server add
        parser_server = subparsers.add_parser(
            "server", help='Create server')
        parser_server.add_argument(
            "--file_name", "-f",
            help="json file containing server param values", default=None)
        self.command_dictionary["server"] = ['f', 'file_name']

        # Subparser for server tags add
        parser_tag = subparsers.add_parser(
            "tag", help='Create tags')
        parser_tag.add_argument(
            "--file_name", "-f",
            help="json file containing tag values", default=None)
        self.command_dictionary["tag"] = ['f', 'file_name']

        # Subparser for cluster add
        parser_cluster = subparsers.add_parser(
            "cluster", help='Create cluster')
        parser_cluster.add_argument(
            "--file_name", "-f",
            help="json file containing cluster param values", default=None)
        self.command_dictionary["cluster"] = ['f', 'file_name']

        # Subparser for image add
        parser_image = subparsers.add_parser(
            "image", help='Create image')
        parser_image.add_argument(
            "--file_name", "-f",
            help="json file containing image param values", default=None)
        self.command_dictionary["image"] = ['f', 'file_name']

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser
    # end def parse_arguments

    def input_default(self, prompt, default):
        return raw_input("%s [%s]" % (prompt, default)) or default

    def rlinput(self, prompt, prefill=''):
        readline.set_startup_hook(lambda: readline.insert_text(prefill))
        try:
            return raw_input(prompt)
        finally:
            readline.set_startup_hook()

    def object_exists(self, obj, object_id_key, object_id_value, payload):
        return_val = False
        # post a request for each object
        resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port,
                                 obj=obj, payload=payload, match_key=object_id_key,
                                 match_value=object_id_value, detail=True, method="GET")
        if resp:
            smgr_object_dict = json.loads(resp)
            if len(smgr_object_dict[obj]):
                return True

        return False

    # end object_exists

    def get_object_config_ini_entries(self, obj, config):
        config_object_defaults = None
        try:
            config_object_defaults = config.items(obj.upper())
            return config_object_defaults
        except ConfigParser.NoSectionError:
            return config_object_defaults

    # end get_object_config_ini_entries

    def get_default_object(self, obj, config):
        # get current tag settings
        payload = {}
        resp = self.app.send_REST_request(
            self.smgr_ip, self.smgr_port,
            obj="tag", payload=payload, detail=True, method="GET")
        tag_dict = json.loads(resp)
        rev_tag_dict = dict((v, k) for k, v in tag_dict.iteritems())
        default_object = {}
        config_object_defaults = self.get_object_config_ini_entries(obj, config)
        if not config_object_defaults:
            return default_object
        default_object["parameters"] = {}
        default_object["tag"] = {}
        for key, value in config_object_defaults:
            if key in object_dict[obj]:
                default_object[key] = value
            elif key in object_dict[obj]["parameters"]:
                default_object["parameters"][key] = value
            elif key in rev_tag_dict:
                default_object["tag"][key] = value
        return default_object

    # end get_default_object

    def merge_with_defaults(self, object_item, payload, config):
        if object_item not in payload or not payload[object_item]:
            return
        default_object = self.get_default_object(object_item, config)
        for i in range(len(payload[object_item])):
            obj = payload[object_item][i]
            obj_id = "id"
            if obj_id not in obj or not obj[obj_id]:
                continue
            if self.object_exists(object_item, "id", str(obj[obj_id]), {}):
                continue
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

    # Function to accept parameters from user and then build payload to be
    # sent with REST API request for creating the object.
    def add_payload(self, object_item, default_object):
        payload = {}
        objects = []
        # get current tag settings
        resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port, obj="tag",
                                          payload=payload, detail=True, method="GET")
        tag_dict = json.loads(resp)
        rev_tag_dict = dict((v, k) for k, v in tag_dict.iteritems())

        while True:
            temp_dict = {}
            fields_dict = object_dict[object_item]
            obj_id = "id"
            msg = obj_id + ":"
            user_input = raw_input(msg)

            temp_dict[obj_id] = user_input
            if not user_input:
                print "Empty id is not valid"
                return None
            # post a request for each object
            resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port,
                                          obj=object_item, payload=payload, match_key=obj_id,
                                     match_value=user_input, detail=True, method="GET")
            smgr_object_dict = json.loads(resp)
            obj_keys = object_item + "_keys"
            non_mutable_fields = eval(object_dict[obj_keys])

            #If object is present, then we can let the user
            #pick the field to be modified
            #else its a new field and user has to go through each fields
            if len(smgr_object_dict[object_item]):
                obj = smgr_object_dict[object_item][0]

                if obj[obj_id] != user_input:
                    print "Server-manager doesn't return the object"
                    return None

                #print "Display Fields"
                data = ''
                i = 0
                index_dict = {}
                server_tags = obj.get("tag", {})
                #form the fields to be displayed with index
                for key in fields_dict:
                    value = fields_dict[key]
                    if (key in ["tag1", "tag2", "tag3",
                                "tag4", "tag5", "tag6",
                                "tag7"]):
                        tag = tag_dict.get(key, None)
                        if not tag:
                            continue
                        data += str(i) + ". %s : %s \n" % (
                            tag, server_tags.get(tag, ''))
                        index_dict[i] = tag
                        i += 1
                    elif (key != ("parameters")):
                        index_dict[i] = key
                        if key in non_mutable_fields:
                            data += str(i) + ". %s : %s *\n" % (key, obj[key])
                        elif key == "roles":
                            data += str(i) + ". %s : %s \n" % (
                                key, ','.join(obj[key]))
                        else:
                            data += str(i) + ". %s : %s \n" % (key, obj[key])
                        i += 1
                    else:
                        if ("parameters" in obj) and obj["parameters"]:
                            smgr_params = obj["parameters"].copy()
                        else:
                            smgr_params = {}
                        for param in value:
                            data += str(i) + ". %s : %s \n" % (
                                param, smgr_params.get(param, ""))
                            index_dict[i] = param
                            i += 1
                #display them
                print data
                params_dict = {}
                tags = {}
                #Prompt if users wants to modify a field in
                # the existing object or continue
                # adding a new object
                while True:
                    user_selection = raw_input("Enter Field index to Modify, C to"
                                               " continue with next Object :")
                    if user_selection.strip() == 'C':
                        #print 'send output'
                        temp_dict["parameters"] = params_dict
                        temp_dict["tag"] = tags
                        break

                    else:
                        try:
                            user_int = int(user_selection.strip())
                            if user_int > len(index_dict):
                                print "Invalid Input"
                                continue
                        except ValueError:
                            print "Invalid Input"
                            continue

                        key_selected = index_dict[eval(user_selection)]
                        object_params = object_dict[object_item]["parameters"]
                        if key_selected in rev_tag_dict:
                            msg = key_selected + ":"
                            user_input = self.rlinput(msg, server_tags.get(key_selected, ''))
                            tags[key_selected] = user_input
                        elif key_selected in object_params.keys():
                            msg = key_selected + ":"
                            value = smgr_params.get(key_selected, "")
                            if key_selected != 'disks':
                                user_input = self.rlinput(
                                    msg, smgr_params.get(key_selected, ''))
                            elif key_selected == 'disks' and 'storage-compute' in object_dict["roles"]:
                                disks = raw_input(msg)
                                if disks:
                                    disk_list = disks.split(',')
                                    user_input = [str(d) for d in disk_list]
                                else:
                                    user_input = None
                            params_dict[key_selected] = user_input
                        elif key_selected == "roles":
                            msg = key_selected + ":"
                            user_input = self.rlinput(msg,
                                                 ','.join(obj[key_selected]))
                            temp_dict[key_selected] = user_input.replace(' ', '').split(",")
                        else:
                            msg = index_dict[eval(user_selection)] + ":"
                            user_input = self.rlinput(msg, obj[index_dict[eval(user_selection)]])
                            temp_dict[key_selected] = user_input
            #Add a new object
            else:
                obj_id = "id"
                tag = {}
                for key in fields_dict:
                    if key == obj_id:
                        continue
                    value = fields_dict[key]
                    if (key in ["tag1", "tag2", "tag3",
                                "tag4", "tag5", "tag6",
                                "tag7"]):
                        msg = tag_dict.get(key, None)
                        if not msg:
                            continue
                        if value:
                            msg += " (%s) " % (value)
                        msg += ": "
                        default_tag = default_object.get("tag", {})
                        default_value = default_tag.get(tag_dict[key], "")
                        user_input = self.rlinput(msg, default_value)
                        if user_input:
                            tag[tag_dict[key]] = user_input
                        temp_dict['tag'] = tag
                    elif (key != ("parameters")):
                        msg = key
                        if value:
                            msg += " (%s) " % (value)
                        msg += ": "
                        default_value = default_object.get(key, "")
                        user_input = self.rlinput(msg, default_value)
                        if user_input:
                            # Special case for roles -
                            # store as a list
                            if key == "roles":
                                #add rlinput at user_input for populating with
                                #defaults
                                temp_dict[key] = user_input.replace(' ', '').split(",")
                            else:
                                temp_dict[key] = user_input
                    #normal fields
                    else:
                        param_dict = {}
                        for param in value:
                            pvalue = value[param]
                            msg = param
                            if pvalue:
                                msg += " (%s) " % (pvalue)
                            msg += ": "
                            #user_input = raw_input(msg)
                            if default_object.has_key("parameters"):
                                default_value = default_object["parameters"].get(param, "")
                            else:
                                default_value = ""
                            user_input = ""
                            if ((param == 'disks') and ('roles' in temp_dict) and
                                    ('storage-compute' in temp_dict["roles"])):
                                disks = raw_input(msg)
                                if disks:
                                    disk_list = disks.split(',')
                                    user_input = [str(d) for d in disk_list]
                                else:
                                    user_input = None
                            else:
                                user_input = self.rlinput(msg, default_value)
                            if user_input:
                                param_dict[param] = user_input
                        temp_dict[key] = param_dict
                        # End if (key != ("parameters"))
                        # End for key, value in fields_dict
            objects.append(temp_dict)
            choice = raw_input("More %s(s) to input? (y/N)" % (object_item))
            if ((not choice) or
                    (choice.lower() != "y")):
                break
        # End while True
        payload[object_item] = objects
        return payload

    # End add_payload

    # Function to accept parameters from user and then build payload to be
    # sent with REST API request for creating the object of type tag.A
    # This function is kept separate as processing is quite different from
    # other objects.
    def add_tag_payload(self, object_item):
        payload = {}
        fields_dict = object_dict[object_item]
        # post a request for each object
        resp = self.app.send_REST_request(
            self.smgr_ip, self.smgr_port, obj=object_item, payload=payload,
            detail=False, method="GET")
        payload = json.loads(resp)
        while True:
            i = 0
            for key in fields_dict.iterkeys():
                value = payload.get(
                    key, '<UNDEFINED>')
                data = str(i) + ". %s : %s" % (
                    key, value)
                print data
                i += 1
            # end for
            user_input = raw_input(
                "Enter index=<tag_value>, "
                "empty value to delete tag, Q to end :")
            if user_input.upper() == "Q":
                break
            try:
                user_data = [x.strip() for x in user_input.split('=')]
                index = int(user_data[0])
                if index >= len(fields_dict):
                    print "Invalid Index"
                    continue
                value = user_data[1]
                if value:
                    payload[fields_dict.keys()[index]] = value
                else:
                    payload.pop(fields_dict.keys()[index], None)
            except:
                print "Invalid input <tag-index>=<tag-value>"
                continue
        # end while
        return payload

    # End add_tag_payload

    def take_action(self, parsed_args):

        config_file = getattr(parsed_args, "config_file", smgr_client_def._DEF_SMGR_CFG_FILE)
        config = None
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            self.smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not self.smgr_ip:
                self.app.stdout.write("listen_ip_addr missing in config file"
                                      "%s" % config_file)
            self.smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
        except Exception as e:
            self.app.stdout.write("Exception: %s : Error reading config file %s" % (e.message, config_file))

        obj = getattr(parsed_args, "object", None)
        payload = None
        try:
            if getattr(parsed_args, "file_name", None):
                payload = json.load(open(parsed_args.file_name))
                self.merge_with_defaults(obj, payload, config)
            else:
                # Accept parameters and construct json.
                if obj == 'tag':
                    payload = self.add_tag_payload(obj)
                else:
                    default_object = self.get_default_object(obj, config)
                    payload = self.add_payload(obj, default_object)
        except ValueError as e:
            self.app.stdout.write("\nError in JSON Format - ValueError: " + str(e) + "\n")
        except Exception as e:
            self.app.stdout.write("\nException here:" + str(e) + "\n")
        if payload:
            resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port, obj=obj, payload=payload)
            smgr_client_def.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgr_client_def.print_rest_response(resp)) + "\n")


