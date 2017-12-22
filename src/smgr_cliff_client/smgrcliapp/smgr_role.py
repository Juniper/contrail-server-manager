#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_role.py
   Author : Siva Gurumurthy
   Description : Command support to add and delete roles
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


class Role(Command):
    log = logging.getLogger(__name__)
    smgr_ip = None
    smgr_port = None

    def get_description(self):
        return "add and delete the given role for the specified server(s)"

    def get_parser(self, prog_name):
        parser = super(Role, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(help='operations on role', dest='command')
        add_parser = subparsers.add_parser("add") 
        del_parser = subparsers.add_parser("delete") 
        add_parser.add_argument( "role_list",help="list of roles that need to be added")
        del_parser.add_argument( "role_list",help="list of roles that need to be deleted")
        for subparser in  [add_parser, del_parser]:
            subparser.add_argument("--server_list",
                           help=("server id(s) for the server to be provisioned"), required=True)
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
        role_list = getattr(parsed_args, "role_list", None).split(',')
        self.validate_roles(role_list)
        payload['role_list'] = role_list
        payload['id'] = getattr(parsed_args, "server_list", None).split(',')
        payload['oper'] = getattr(parsed_args, "command", None)

        # end if
        if payload:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj="provision_role",payload=payload, method="POST")
            if "Error" not in resp:
                self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
            else:
                self.app.stdout.write("\nError Returned:\n" + str(smgrutils.print_rest_response(resp)))
