#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_provision_server.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface that
   provides provisioning a server for the roles configured. The
   SM prepares puppet manifests that define the role(s) being
   configured on receiving this REST API request.
"""
import argparse
import pdb
import sys
import pycurl
import logging
from StringIO import StringIO
import json
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command


class Provision(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Provision a Server or a Set of Servers with a chosen Contrail Package from Server Manager Database"

    def get_parser(self, prog_name):
        parser = super(Provision, self).get_parser(prog_name)
        parser.add_argument(
            "package_image_id", nargs='?',
            help="contrail package image id to be used for provisioning")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--server_id",
                           help=("server id for the server to be provisioned"))
        group.add_argument("--cluster_id",
                           help=("cluster id for the server(s) to be provisioned"))
        group.add_argument("--tag",
                           help=("tag values for the servers to be provisioned"))
        group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
        group.add_argument("--provision_params_file", "-f",
                           help=("Optional json file containing parameters "
                                 " for provisioning server"))
        group.add_argument("--interactive", "-I", action="store_true",
                           help=("flag that user wants to enter the server "
                                 " parameters for provisioning manually"))
        parser.add_argument("--contrail_image_id",
                           help=("image_id for the contrail-install-package.deb"
                           " package"))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        parser.add_argument("--no_run", "-r", action="store_true",
                            help=("flag to build only inventory, no execute, "
                                  "default = execute"))
        parser.add_argument("--tasks",
                            help=("tags that user will specify to run only "
                                  "specific ansible tasks - "
                                  "[openstack_bootstrap,openstack_deploy,"
                                  "openstack_destroy,openstack_post_deploy,"
                                  "contrail_deploy]"))
        self.command_dictionary["provision"] = ["server_id", "cluster_id", "tag", "where",
                                                "interactive",
                                                "contrail_image_id", "tasks"
                                                "no_confirm",
                                                "provision_params_file", "f",
                                                "F", "I", "no_run", "r"]
        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

    # Function to accept parameters from user and then build payload to be
    # sent with REST API request for reimaging server.
    def get_provision_params(self):
        provision_params = {}
        roles = OrderedDict([
            ("database", " (Comma separated list of server names for this role) : "),
            ("openstack", " (Comma separated list of server names for this role) : "),
            ("config", " (Comma separated list of server names for this role) : "),
            ("control", " (Comma separated list of server names for this role) : "),
            ("collector", " (Comma separated list of server names for this role) : "),
            ("webui", " (Comma separated list of server names for this role) : "),
            ("compute", " (Comma separated list of server names for this role) : "),
            ("storage-compute", " (Comma separated list of server names for this role) : "),
            ("storage-master", " (Comma separated list of server names for this role) : ")
        ])
        # Accept all the role definitions
        role_dict = {}
        for field in roles:
            msg = field + roles[field]
            user_input = raw_input(msg)
            if user_input:
                role_dict[field] = user_input.split(",")
        # end for field in params
        provision_params['roles'] = role_dict
        return provision_params
        # End get_provision_params

    def take_action(self, parsed_args):
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

        provision_params = {}
        payload = {}
        match_key = None
        match_value = None
        match_param = None
        contrail_img_id = None
        tasks = None
        if getattr(parsed_args, "server_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "server_id", None)
        elif getattr(parsed_args, "cluster_id", None):
            match_key = 'cluster_id'
            match_value = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "tag", None):
            match_key = 'tag'
            match_value = getattr(parsed_args, "tag", None)
        elif getattr(parsed_args, "where", None):
            match_key = 'where'
            match_value = getattr(parsed_args, "where", None)
        elif getattr(parsed_args, "interactive", None):
            provision_params = self.get_provision_params()
        elif getattr(parsed_args, "provision_params_file", None):
            provision_params = json.load(open(getattr(parsed_args, "provision_params_file", None)))
        else:
            pass

        if getattr(parsed_args, "contrail_image_id", None):
            contrail_img_id = getattr(parsed_args, "contrail_image_id", None)
        payload['package_image_id'] = getattr(parsed_args, "package_image_id", None)
        if contrail_img_id != None:
            payload['contrail_image_id'] = contrail_img_id
        if match_key and match_value:
            payload[match_key] = match_value
        if provision_params:
            payload['provision_parameters'] = provision_params

        if getattr(parsed_args, "tasks", None):
            tasks =  getattr(parsed_args, "tasks", None)
        if tasks != None:
            payload['tasks'] = tasks

	if getattr(parsed_args, "no_run", None):
            payload['no_run'] = 1;

        if not getattr(parsed_args, "no_confirm", None):
            if getattr(parsed_args, "package_image_id", None):
                pkg_id_str = getattr(parsed_args, "package_image_id", None)
            else:
                pkg_id_str = "configured package"
            if match_key:
                if tasks:
                    msg = "Provision servers (%s:%s) with %s and tasks %s? (y/N) :" % (
                        match_key, match_value, pkg_id_str, tasks)
                else:
                    msg = "Provision servers (%s:%s) with %s? (y/N) :" % (
                    match_key, match_value, pkg_id_str)
            else:
                msg = "Provision servers with %s? (y/N) :" % (pkg_id_str)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        if payload:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj="server/provision",
                                               payload=payload, method="POST")
            self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
            #  End of provision_server
