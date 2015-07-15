#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_delete.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   delete server manager configuration objects.
   Objects can be cluster, server, or image.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import smgr_client_def
import urllib
import logging
from cliff.command import Command


class Delete(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Delete a Server Manager object"

    def get_parser(self, prog_name):
        parser = super(Delete, self).get_parser(prog_name)
        subparsers = parser.add_subparsers(title='objects',
                                           description='valid objects',
                                           help='help for object')

        # Subparser for server delete
        parser_server = subparsers.add_parser(
            "server", help='Delete server')
        group = parser_server.add_mutually_exclusive_group(required=True)
        group.add_argument("--server_id",
                           help=("server id for server to be deleted"))
        group.add_argument("--mac",
                           help=("mac address for server to be deleted"))
        group.add_argument("--ip",
                           help=("ip address for server to be deleted"))
        group.add_argument("--cluster_id",
                           help=("cluster id for server(s) to be deleted"))
        group.add_argument("--tag",
                           help=("tag values for the server to be deleted "
                                 "in t1=v1,t2=v2,... format"))
        group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
        parser_server.set_defaults(which='server')
        self.command_dictionary["server"] = ['server_id', 'mac', 'ip', 'cluster_id', 'tag', 'where']

        # Subparser for cluster delete
        parser_cluster = subparsers.add_parser(
            "cluster", help='Delete cluster')
        parser_cluster_group = parser_cluster.add_mutually_exclusive_group(required=True)
        parser_cluster_group.add_argument("--cluster_id",
                                          help=("cluster id for cluster to be deleted"))
        parser_cluster_group.add_argument("--where",
                                          help=("sql where statement in quotation marks"))
        parser_cluster.add_argument("--force", "-f", action="store_true",
                                    help=("optional parameter to indicate ,"
                                          "if cluster association to be removed from server"))
        parser_cluster.set_defaults(which='cluster')
        self.command_dictionary["cluster"] = ['cluster_id', 'where', 'f', 'force']

        # Subparser for image delete
        parser_image = subparsers.add_parser(
            "image", help='Delete image')
        parser_image.add_argument("--where",
                                  help=("sql where statement in quotation marks"))
        parser_image.add_argument("--image_id",
                                  help=("image id for image to be deleted"))
        self.command_dictionary["image"] = ['image_id', 'where']
        parser_image.set_defaults(which='image')

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = []
            new_dict[key].append([str("--" + s) for s in self.command_dictionary[key] if len(s) > 1])
            new_dict[key].append([str("-" + s) for s in self.command_dictionary[key] if len(s) == 1])
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

    def delete_server(self, parsed_args):
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
    # end def delete_server

    def delete_cluster(self, parsed_args):
        if getattr(parsed_args, "cluster_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "server_id", None):
            match_key = 'where'
            match_value = getattr(parsed_args, "where", None)
        else:
            match_key = ''
            match_value = ''
        rest_api_params = {
            'object': 'cluster',
            'match_key': match_key,
            'match_value': match_value
        }
        return rest_api_params
    # end def delete_cluster

    def delete_image(self, parsed_args):
        if getattr(parsed_args, "image_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "image_id", None)
        elif getattr(parsed_args, "where", None):
            match_key = 'where'
            match_value = getattr(parsed_args, "where", None)
        else:
            match_key = ''
            match_value = ''
        rest_api_params = {
            'object': 'image',
            'match_key': match_key,
            'match_value': match_value
        }
        return rest_api_params
        #end def delete_image

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

        rest_api_params = None
        obj = getattr(parsed_args, "which", None)
        if obj == "server":
            rest_api_params = self.delete_server(parsed_args)
        elif obj == "cluster":
            rest_api_params = self.delete_cluster(parsed_args)
        elif obj == "image":
            rest_api_params = self.delete_image(parsed_args)

        force = False
        if hasattr(parsed_args, "force"):
            force = getattr(parsed_args, "force")
        if rest_api_params:
            resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port, obj=rest_api_params["object"],
                                              match_key=rest_api_params["match_key"],
                                              match_value=rest_api_params["match_value"],
                                              force=force,
                                              method="DELETE")
            smgr_client_def.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgr_client_def.print_rest_response(resp)) + "\n")
