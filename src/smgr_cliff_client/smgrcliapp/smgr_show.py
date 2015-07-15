#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_monitoring.py
   Author : Nitish Krishna
   Description : TBD
"""

import logging
import os
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import smgr_client_def
import json
import urllib
from smgr_monitoring import ServerMgrIPMIQuerying
from smgr_inventory import ServerMgrInventory

mon_querying_obj = ServerMgrIPMIQuerying()
inv_querying_obj = ServerMgrInventory()

from cliff.command import Command


class Show(Command):

    log = logging.getLogger(__name__)
    command_dictionary = {}

    def get_command_options(self):
        return self.command_dictionary

    def send_REST_request(self, ip, port, rest_api_params, detail):
        try:
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = "http://%s:%s/%s" % (ip, port, rest_api_params['object'])
            args_str = ''
            if rest_api_params["select"]:
                args_str += "select" + "=" \
                            + urllib.quote_plus(rest_api_params["select"]) + "&"
            if rest_api_params["match_key"]:
                args_str += urllib.quote_plus(rest_api_params["match_key"]) + "=" \
                            + urllib.quote_plus(rest_api_params["match_value"])
            if detail:
                args_str += "&detail"
            if args_str != '':
                url += "?" + args_str
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, url)
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.perform()
            return response.getvalue()
        except Exception as e:
            return "Error: " + str(e)
            # end def send_REST_request

    def get_description(self):
        return "Show Details about Objects in Server Manager Database"

    def get_parser(self, prog_name):
        parser = super(Show, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for object')
        # Subparser for server show
        parser_server = subparsers.add_parser(
            "server", help='Show server')

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
        group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
        group.add_argument("--discovered",
                           help=("flag to get list of "
                                 "newly discovered server(s)"))
        server_select_group = parser_server.add_mutually_exclusive_group()
        server_select_group.add_argument("--select",
                                         help=("sql select statement in quotation marks"))
        server_select_group.add_argument(
            "--detail", "-d", action='store_true',
            help="Flag to indicate if details are requested")
        parser_server.set_defaults(which='server')
        self.command_dictionary["server"] = ['server_id', 'mac', 'ip', 'cluster_id', 'tag',
                                             'where', 'discovered', 'select', 'detail']

        # Subparser for image show
        parser_image = subparsers.add_parser(
            "image", help='Show image')
        image_group = parser_image.add_mutually_exclusive_group()
        image_group.add_argument("--image_id",
                                 help=("image id for image"))
        image_group.add_argument("--where",
                                 help=("sql where statement in quotation marks"))
        image_select_group = parser_image.add_mutually_exclusive_group()
        image_select_group.add_argument("--select",
                                        help=("sql select statement in quotation marks"))
        image_select_group.add_argument(
            "--detail", "-d", action='store_true',
            help="Flag to indicate if details are requested")
        parser_image.set_defaults(which='image')
        self.command_dictionary["image"] = ['image_id', 'where', 'select', 'detail']

        # Subparser for inventory show
        parser_inventory = subparsers.add_parser(
            "inventory", help='Show server inventory info')
        inv_group = parser_inventory.add_mutually_exclusive_group()
        inv_group.add_argument("--server_id",
                               help=("server id for server"))
        inv_group.add_argument("--cluster_id",
                               help=("cluster id for server"))
        inv_group.add_argument("--tag", help=("tag values for the server"
                                              "in t1=v1,t2=v2,... format"))
        inv_group.add_argument("--where",
                               help=("sql where statement in quotation marks"))
        parser_inventory.set_defaults(which='inventory')
        self.command_dictionary["inventory"] = ['server_id', 'cluster_id', 'tag', 'where']

        # Subparser for cluster show
        parser_cluster = subparsers.add_parser(
            "cluster", help='Show cluster')
        cluster_group = parser_cluster.add_mutually_exclusive_group()
        cluster_group.add_argument("--cluster_id",
                                   help=("cluster id for cluster"))
        cluster_group.add_argument("--where",
                                   help=("sql where statement in quotation marks"))
        cluster_select_group = parser_cluster.add_mutually_exclusive_group()
        cluster_select_group.add_argument("--select",
                                          help=("sql select statement in quotation marks"))
        cluster_select_group.add_argument(
            "--detail", "-d", action='store_true',
            help="Flag to indicate if details are requested")
        parser_cluster.set_defaults(which='cluster')
        self.command_dictionary["cluster"] = ['cluster_id', 'where', 'select', 'detail']

        # Subparser for all show
        parser_all = subparsers.add_parser(
            "all", help='Show all configuration (servers, clusters, images, tags)')
        parser_all.add_argument(
            "--detail", "-d", action='store_true',
            help="Flag to indicate if details are requested")
        parser_all.set_defaults(which='all')
        self.command_dictionary["all"] = ['detail']

        # Subparser for tags show
        parser_tag = subparsers.add_parser(
            "tag", help='Show list of server tags')
        parser_tag.set_defaults(which='tag')
        self.command_dictionary["tag"] = []

        # Subparser for monitoring show
        parser_monitoring = subparsers.add_parser(
            "monitoring", help='Show server monitoring info')
        mon_group = parser_monitoring.add_mutually_exclusive_group()
        mon_group.add_argument("--server_id",
                               help=("server id for server"))
        mon_group.add_argument("--cluster_id",
                               help=("cluster id for server"))
        mon_group.add_argument("--tag", help=("tag values for the server"
                                              "in t1=v1,t2=v2,... format"))
        mon_group.add_argument("--where",
                               help=("sql where statement in quotation marks"))
        parser_monitoring.set_defaults(which='monitoring')
        self.command_dictionary["monitoring"] = ['server_id', 'cluster_id', 'tag', 'where']

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

    def show_image(self, parsed_args):
        rest_api_params = {}
        rest_api_params['object'] = 'image'
        rest_api_params['select'] = getattr(parsed_args, "select", None)

        if getattr(parsed_args, "image_id", None):
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = getattr(parsed_args, "image_id", None)
        elif getattr(parsed_args, "where", None):
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = getattr(parsed_args, "where", None)
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    def show_server(self, parsed_args):
        rest_api_params = {}
        rest_api_params['object'] = 'server'
        rest_api_params['select'] = getattr(parsed_args, "select", None)

        if getattr(parsed_args, "server_id", None):
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = getattr(parsed_args, "server_id", None)
        elif getattr(parsed_args, "cluster_id", None):
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = getattr(parsed_args, "cluster_id", None)
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params

    def show_cluster(self, parsed_args):
        if getattr(parsed_args, "cluster_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "where", None):
            match_key = 'where'
            match_value = getattr(parsed_args, "where", None)
        else:
            match_key = None
            match_value = None
        rest_api_params = {
            'object': 'cluster',
            'match_key': match_key,
            'match_value': match_value,
            'select': getattr(parsed_args, "select", None)
        }
        return rest_api_params

    # end def show_cluster

    def show_all(args):
        rest_api_params = {
            'object': 'all',
            'match_key': None,
            'match_value': None,
            'select': None
        }
        return rest_api_params

    # end def show_all

    def show_tag(args):
        rest_api_params = {
            'object': 'tag',
            'match_key': None,
            'match_value': None,
            'select': None
        }
        return rest_api_params

    #end def show_all

    def take_action(self, parsed_args):

        config_file = getattr(parsed_args, "config_file", smgr_client_def._DEF_SMGR_CFG_FILE)
        # end args.config_file

        detail = getattr(parsed_args, 'detail', None)
        rest_api_params = {}

        # end except
        if parsed_args.which == "server":
            rest_api_params = self.show_server(parsed_args)
        elif parsed_args.which == "image":
            rest_api_params = self.show_image(parsed_args)
        elif parsed_args.which == "cluster":
            rest_api_params = self.show_cluster(parsed_args)
        elif parsed_args.which == 'tag':
            rest_api_params = self.show_tag()
        elif parsed_args.which == 'all':
            rest_api_params = self.show_all()
        elif parsed_args.which == 'monitoring':
            rest_api_params = mon_querying_obj.show_mon_details(parsed_args)
        elif parsed_args.which == 'inventory':
            rest_api_params = inv_querying_obj.show_inv_details(parsed_args)

        try:
            config = ConfigParser.SafeConfigParser()
            config.read([config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not smgr_ip:
                self.app.stdout.write("listen_ip_addr missing in config file"
                                      "%s" % config_file)
            smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
        except Exception as e:
            self.app.stdout.write("Exception: %s : Error reading config file %s" % (e.message, config_file))
            sys.exit("Exception: %s : Error reading config file %s" % (e.message, config_file))
        resp = self.app.send_REST_request(smgr_ip, smgr_port, rest_api_params=rest_api_params,
                                          detail=detail, method='GET')
        self.app.stdout.write("\n" + str(smgr_client_def.print_rest_response(resp)) + "\n")

        """command_list = [n for n, v in self.app.command_manager]
        self.app.stdout.write("\n" + str(command_list) + "\n")
        display_option_list = [v for n, v in self.app.command_manager if n == "display"]
        self.app.stdout.write("\n" + str(display_option_list) + "\n")"""
