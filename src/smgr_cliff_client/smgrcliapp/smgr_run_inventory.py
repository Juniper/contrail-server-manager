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
import smgr_client_def
import urllib
import logging
from cliff.command import Command


class RunInventory(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Run inventory for given server(s)"

    def get_parser(self, prog_name):
        parser = super(RunInventory, self).get_parser(prog_name)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--server_id",
                           help=("server id for the server to be provisioned"))
        group.add_argument("--cluster_id",
                           help=("cluster id for the server(s) to be provisioned"))
        group.add_argument("--tag",
                           help=("tag values for the servers to be provisioned"))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))

        self.command_dictionary["run-inventory"] = ['server_id', 'cluster_id', 'tag', 'no_confirm', 'F']

        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

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

        payload = {}
        match_key = None
        match_value = None
        if getattr(parsed_args, "server_id", None):
            match_key = 'id'
            match_value = getattr(parsed_args, "server_id", None)
        elif getattr(parsed_args, "cluster_id", None):
            match_key = 'cluster_id'
            match_value = getattr(parsed_args, "cluster_id", None)
        elif getattr(parsed_args, "tag", None):
            match_key = 'tag'
            match_value = getattr(parsed_args, "tag", None)
        else:
            pass

        if match_key:
            payload[match_key] = match_value

        if not getattr(parsed_args, "no_confirm", False):
            msg = "Run Inventory on servers matching: (%s:%s)? (y/N) :" % (
                match_key, match_value)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        if payload:
            resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port, obj="run_inventory",
                                              match_key=match_key, match_value=match_value,
                                              method="PUT")
            smgr_client_def.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgr_client_def.print_rest_response(resp)) + "\n")
