#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_reimage_server.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface that
   provides reimaging a server with given iso and package.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import logging
import json
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command


class Reimage(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Reimage a Server or a Set of Servers with a base OS image from Server Manager Database"

    def get_parser(self, prog_name):
        parser = super(Reimage, self).get_parser(prog_name)
        parser.add_argument("base_image_id", nargs='?',
                            help="image id for base image to be used")
        parser.add_argument("--package_image_id", "-p",
                            help=("Optional contrail package to be used"
                                  " on reimaged server"))
        parser.add_argument("--no_reboot", "-n", action="store_true",
                            help=("optional parameter to indicate"
                                  " that server should NOT be rebooted"
                                  " following the reimage setup."))

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--server_id",
                           help=("server id for the server to be reimaged"))
        group.add_argument("--cluster_id",
                           help=("cluster id for the server(s) to be reimaged"))
        group.add_argument("--tag",
                           help=("tag values for the servers to be reimaged"
                                 "in t1=v1,t2=v2,... format"))
        group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        self.command_dictionary["reimage"] = ["package_image_id", "no_reboot",
                                              "server_id", "cluster_id", "tag", "where", "no_confirm"]
        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]
        return parser
        # end parse arguments

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

        match_key = None
        match_value = None
        payload = {}
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
        else:
            pass

        payload['base_image_id'] = getattr(parsed_args, "base_image_id", None)
        payload['package_image_id'] = getattr(parsed_args, "package_image_id", None)

        if getattr(parsed_args, "no_reboot", None):
            payload['no_reboot'] = "y"
        if match_key:
            payload[match_key] = match_value

        if not getattr(parsed_args, "no_confirm", None):
            if getattr(parsed_args, "base_image_id", None):
                image_str = getattr(parsed_args, "base_image_id", None)
            else:
                image_str = "configured"
            msg = "Reimage servers (%s:%s) with %s? (y/N) :" % (
                match_key, match_value, image_str)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        if payload:
            #self.app.print_error_message_and_quit("Payload = " + str(payload) + "\n\n")
            resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port, obj="server/reimage",
                                               payload=payload, method="POST")
            self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")
        # End of reimage_server
