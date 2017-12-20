#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_run_inventory.py
   Author : Nitish Krishna
   Description : TBD
"""
import argparse
import pdb
import sys
import json

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
import urllib
import logging
from cliff.command import Command


class ProvisionRole(Command):
    log = logging.getLogger(__name__)
    smgr_ip = None
    smgr_port = None

    def get_description(self):
        return "Provision the given role in the given server(s)"

    def get_parser(self, prog_name):
        parser = super(ProvisionRole, self).get_parser(prog_name)
        parser.add_argument(
            "package_image_id", nargs='?',
            help="contrail package image id to be used for provisioning")
        parser.add_argument("--role",
                           help=("name of the role to be provisioned"), required=True)
        parser.add_argument("--server_id_list",
                           help=("server id(s) for the server to be provisioned"), required=True)
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        return parser

    def validate_roles(self, roles):
        valid_roles = ['contrail-compute']
        for item in roles:
           if item not in valid_roles:
               sys.exit("Exception: %s : Please specify a valid role")

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

        payload = {}
        match_key = None
        match_value = None
        payload['package_image_id'] = getattr(parsed_args, "package_image_id", None)
        if getattr(parsed_args, "role", None):
            match_value = getattr(parsed_args, "role", None).split(',')
            self.validate_roles(match_value)
            payload['role'] = match_value
        if getattr(parsed_args, "server_id_list", None):
            match_value = getattr(parsed_args, "server_id_list", None).split(',')
            payload['id'] = match_value
        else:
            pass

        if not getattr(parsed_args, "no_confirm", False):
            msg = "Provision role  on given servers: (%s:%s)? (y/N) :" % (
                match_key, match_value)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if
        if payload:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj="provision_role",
                                               payload=payload, method="POST")
            if "Error" not in resp:
                self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
            else:
                self.app.stdout.write("\nError Returned:\n" + str(smgrutils.print_rest_response(resp)))
