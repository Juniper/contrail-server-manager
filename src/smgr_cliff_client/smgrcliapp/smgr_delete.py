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
from smgr_client_utils import SmgrClientUtils as smgrutils
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
        group.add_argument("--discovered",
                           help=("flag to get list of "
                                 "newly discovered server(s)"))
        group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
        parser_server.set_defaults(which='server')
        self.command_dictionary["server"] = ['server_id', 'mac', 'ip', 'cluster_id', 'tag', 'where', 'discovered']

        # Subparser for cluster delete
        parser_cluster = subparsers.add_parser(
            "cluster", help='Delete cluster')
        parser_cluster_group = parser_cluster.add_mutually_exclusive_group(required=True)
        parser_cluster_group.add_argument("--cluster_id",
                                          help=("cluster id for cluster to be deleted"))
        parser_cluster_group.add_argument("--where",
                                          help=("sql where statement in quotation marks"))
        parser_cluster.set_defaults(which='cluster')
        self.command_dictionary["cluster"] = ['cluster_id', 'where', 'f', 'force']

        # Subparser for image delete
        parser_image = subparsers.add_parser(
            "image", help='Delete image')
        parser_image.add_argument("--where",
                                  help=("sql where statement in quotation marks"))
        parser_image.add_argument("--image_id",
                                  help=("image id for image to be deleted"))
        parser_image.set_defaults(which='image')
        self.command_dictionary["image"] = ['image_id', 'where']

        # Subparser for tag delete
        parser_tag = subparsers.add_parser(
            "tag", help='Delete tag')
        parser_tag.add_argument("--tags",
                                help="comma separated list of tag indexes to delete. Eg: tag1,tag5")
        parser_tag.set_defaults(which='tag')
        self.command_dictionary["tag"] = ['tags']

        # Subparser for dhcp subnet delete
        parser_dhcp_subnet = subparsers.add_parser(
            "dhcp_subnet", help='Delete dhcp subnet')
        parser_dhcp_subnet.add_argument("--subnet_address",
                                help="Address of the subnet you want to delete")
        parser_dhcp_subnet.set_defaults(which='dhcp_subnet')
        self.command_dictionary["dhcp_subnet"] = ['subnet_address']

        # Subparser for dhcp host delete
        parser_dhcp_host = subparsers.add_parser(
            "dhcp_host", help='Delete dhcp host')
        parser_dhcp_host.add_argument("--host_fqdn",
                                help="FQDN of the host you want to delete")
        parser_dhcp_host.set_defaults(which='dhcp_host')
        self.command_dictionary["dhcp_host"] = ['host_fqdn']

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
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
        elif getattr(parsed_args, "where", None):
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = getattr(parsed_args, "where", None)
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params
    # end def delete_server

    def delete_cluster(self, parsed_args):
        if getattr(parsed_args, "cluster_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "where", None):
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

    def delete_tag(self, parsed_args):
        if getattr(parsed_args, "tags", None):
            match_key = 'tag'
            match_value = getattr(parsed_args, "tags", None)
        else:
            match_key = ''
            match_value = ''
        rest_api_params = {
            'object': 'tag',
            'match_key': match_key,
            'match_value': match_value
        }
        return rest_api_params
        # end def delete_tag

    def delete_dhcp_host(self, parsed_args):
        if getattr(parsed_args, "host_fqdn", None):
            match_key = 'host_fqdn'
            match_value = getattr(parsed_args, "host_fqdn", None)
        else:
            match_key = ''
            match_value = ''
        rest_api_params = {
            'object': 'dhcp_host',
            'match_key': match_key,
            'match_value': match_value
        }
        return rest_api_params
        # end def delete_dhcp_host

    def delete_dhcp_subnet(self, parsed_args):
        if getattr(parsed_args, "subnet_address", None):
            match_key = 'subnet_address'
            match_value = getattr(parsed_args, "subnet_address", None)
        else:
            match_key = ''
            match_value = ''
        rest_api_params = {
            'object': 'dhcp_subnet',
            'match_key': match_key,
            'match_value': match_value
        }
        return rest_api_params
        # end def delete_dhcp_subnet

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
        obj = getattr(parsed_args, "which", None)
        if obj == "server":
            rest_api_params = self.delete_server(parsed_args)
        elif obj == "cluster":
            rest_api_params = self.delete_cluster(parsed_args)
        elif obj == "image":
            rest_api_params = self.delete_image(parsed_args)
        elif obj == "tag":
            rest_api_params = self.delete_tag(parsed_args)
        elif obj == "dhcp_host":
            rest_api_params = self.delete_dhcp_host(parsed_args)
        elif obj == "dhcp_subnet":
            rest_api_params = self.delete_dhcp_subnet(parsed_args)

        if rest_api_params:
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj=rest_api_params["object"],
                                              match_key=rest_api_params["match_key"],
                                              match_value=rest_api_params["match_value"],
                                              method="DELETE")
            smgrutils.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
