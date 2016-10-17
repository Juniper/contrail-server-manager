#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_status.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   get status of provision or reimage on servers in the server manager DB.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
import logging
from cliff.command import Command
import json


class Status(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Show a Server's Status"

    def get_parser(self, prog_name):
        parser = super(Status, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for object')

        # Subparser for server show
        parser_server = subparsers.add_parser("server", help='Show server status')
        group = parser_server.add_mutually_exclusive_group()
        group.add_argument("--server_id",
                           help=("server id for server"))
        group.add_argument("--mac",
                           help=("mac address for server"))
        group.add_argument("--ip",
                           help=("ip address for server"))
        group.add_argument("--cluster_id",
                           help=("cluster id for server(s)"))
        group.add_argument("--tag",
                           help=("tag values for the server"
                                 "in t1=v1,t2=v2,... format"))
        group.add_argument("--discovered",
                           help=("flag to get list of "
                                 "newly discovered server(s)"))
        parser_server.add_argument("--json",
                                   help="To display output in json format",
                                   action="store_true")
        self.command_dictionary["server"] = ['server_id', 'mac', 'ip', 'cluster_id', 'tag', 'discovered']
        parser_server.set_defaults(which='server')

        # Subparser for provision show
        parser_provision = subparsers.add_parser("provision", help='Show provision status')
        p_group = parser_provision.add_mutually_exclusive_group()
        p_group.add_argument("--server_id",
                           help=("server id for server"))
        p_group.add_argument("--cluster_id",
                           help=("cluster id for server(s)"))
        p_group.add_argument("--tag",
                           help=("tag values for the server"
                                 "in t1=v1,t2=v2,... format"))
        parser_provision.add_argument("--json",
                                   help="To display output in json format",
                                   action="store_true")
        self.command_dictionary["provision"] = ['server_id', 'cluster_id', 'tag']
        parser_provision.set_defaults(which='provision')

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

    def set_server_status(self, parsed_args):
        rest_api_params = dict()
        rest_api_params['object'] = 'server'
        if getattr(parsed_args, "server_id", None):
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = getattr(parsed_args, "server_id", None)
        elif getattr(parsed_args, "mac", None):
            rest_api_params['match_key'] = 'mac_address'
            rest_api_params['match_value'] = getattr(parsed_args, "mac", None)
        elif getattr(parsed_args, "ip", None):
            rest_api_params['match_key'] = 'ip_address'
            rest_api_params['match_value'] = getattr(parsed_args, "ip", None)
        elif getattr(parsed_args, "cluster_id", None):
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "tag", None):
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = getattr(parsed_args, "tag", None)
        elif getattr(parsed_args, "discovered", None):
            rest_api_params['match_key'] = 'discovered'
            rest_api_params['match_value'] = getattr(parsed_args, "discovered", None)
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params
    # end def show_server

    def set_provision_status(self, parsed_args):
        rest_api_params = dict()
        rest_api_params['object'] = 'provision'
        if getattr(parsed_args, "server_id", None):
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = getattr(parsed_args, "server_id", None)
        elif getattr(parsed_args, "cluster_id", None):
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "tag", None):
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = getattr(parsed_args, "tag", None)
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params
    # end def show_provision

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

        rest_api_params = None
        if parsed_args.which == "server":
            rest_api_params = self.set_server_status(parsed_args)
        elif parsed_args.which == "provision":
            rest_api_params = self.set_provision_status(parsed_args)
        if rest_api_params:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj=str(rest_api_params['object']+"_status"),
                                              match_key=rest_api_params['match_key'],
                                              match_value=rest_api_params['match_value'])
            json_format = getattr(parsed_args, "json", False)
            if json_format:
                self.app.stdout.write(str(smgrutils.print_rest_response(resp)) + "\n")
            else:
                table_format_output = smgrutils.convert_json_to_table(obj="server", json_resp=resp)
                self.app.stdout.write("\n" + str(smgrutils.print_rest_response(str(table_format_output))) + "\n")

