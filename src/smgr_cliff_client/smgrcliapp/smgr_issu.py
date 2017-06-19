#!/usr/bin/python

import argparse
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils
from cliff.command import Command
import logging
import sys

class Issu(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Perform in service software upgrade from old cluster to new cluster"


    def get_parser(self, prog_name):
        parser = super(Issu, self).get_parser(prog_name)
        parser.add_argument("--cluster_id_old",
                            help=("cluster to be upgraded"))
        parser.add_argument("--cluster_id_new",
                            help=("active cluster after the upgrade"))
        parser.add_argument("--new_image",
                            help=("contrail image cluster being upgraded to"))
        grp = parser.add_mutually_exclusive_group(required = False)
        grp.add_argument("--tag", default = None,
                            help=("compute nodes with specified tag are " +\
                                  "migrated from old cluster to new cluster."))
        grp.add_argument("--all", dest = 'compute_all', action = "store_true",
                            help=("compute nodes with specified tag are " +\
                                  "migrated from old cluster to new cluster."))
        grp.add_argument("--server_id", default = None,
                            help=("compute node specified with server_id " +\
                                  "migrated from old cluster to new cluster."))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        self.command_dictionary["issu"] = ["cluster_id_old", "cluster_id_new",
                                 "cluster_id_new", "tag", "all", "no_confirm",
                                                                 "server_id" ]
        return parser

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

        # contruct paylod for backend
        payload = {}
        payload['opcode'] = 'issu'
        payload['old_cluster'] = parsed_args.cluster_id_old
        payload['new_cluster'] = parsed_args.cluster_id_new
        payload['new_image'] = parsed_args.new_image
        if parsed_args.compute_all:
            payload['compute_tag'] = "all_computes"
        elif parsed_args.tag:
            payload['compute_tag'] = parsed_args.tag
        elif parsed_args.server_id:
            payload['compute_tag'] = "__server__id__" + parsed_args.server_id
        else:
            payload['compute_tag'] = ""

        if (not parsed_args.no_confirm):
            msg = "Upgrade cluster %s to %s, Contrail Image:%s? (y/N) :" %(
                         parsed_args.cluster_id_old, parsed_args.cluster_id_new,
                         parsed_args.new_image)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port,
                                           obj="server/provision",
                                           payload=payload, method="POST")
        self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")

class IssuFinalize(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Finalize in service software upgrade, remove old cluster references"


    def get_parser(self, prog_name):
        parser = super(IssuFinalize, self).get_parser(prog_name)
        parser.add_argument("--cluster_id_old",
                            help=("cluster to be upgraded"))
        parser.add_argument("--cluster_id_new",
                            help=("active cluster after the upgrade"))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        self.command_dictionary = ["cluster_id_old", "cluster_id_new",
                                                          "no_confirm"]
        return parser

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

        # contruct paylod for backend
        payload = {}
        payload['opcode'] = 'issu_finalize'
        payload['old_cluster'] = parsed_args.cluster_id_old
        payload['new_cluster'] = parsed_args.cluster_id_new

        if (not parsed_args.no_confirm):
            msg = "Switch from cluster %s to %s? (y/N) :" %(
                      parsed_args.cluster_id_old, parsed_args.cluster_id_new)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port,
                                           obj="server/provision",
                                           payload=payload, method="POST")
        self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")

class IssuRollback(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Move the compute node back to old cluster"


    def get_parser(self, prog_name):
        parser = super(IssuRollback, self).get_parser(prog_name)
        parser.add_argument("--cluster_id_old",
                            help=("cluster to be upgraded"))
        parser.add_argument("--cluster_id_new",
                            help=("active cluster after the upgrade"))
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
        parser.add_argument("--old_image",
                            help=("contrail image on the old cluster"))
        grp = parser.add_mutually_exclusive_group(required = False)
        grp.add_argument("--tag", default = None,
                          help=("compute nodes with specified tag are " +\
                              "migrated back to old cluster from new cluster."))
        grp.add_argument("--server_id", default = None,
                          help=("specified compute node is migrated back to " +\
                                  "old cluster from new cluster."))
        grp.add_argument("--all", dest = 'compute_all', action = "store_true",
                          help=("compute nodes with specified tag are " +\
                                  "migrated from old cluster to new cluster."))
        self.command_dictionary = ["cluster_id_old", "cluster_id_new",
                                   "no_confirm", "old_image", "tag",
                                   "server_id", "all"]
        return parser

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

        # contruct paylod for backend
        payload = {}
        payload['opcode'] = 'issu_rollback'
        payload['old_cluster'] = parsed_args.cluster_id_old
        payload['new_cluster'] = parsed_args.cluster_id_new
        payload['old_image'] = parsed_args.old_image
        if parsed_args.compute_all:
            payload['compute_tag'] = "all_computes"
        elif parsed_args.tag:
            payload['compute_tag'] = parsed_args.tag
        else:
            payload['compute_tag'] = ""
        if parsed_args.server_id:
            payload['server_id'] = parsed_args.server_id
        else:
            payload['server_id'] = ""

        if (not parsed_args.no_confirm):
            msg = "Switch from cluster %s to %s? (y/N) :" %(
                      parsed_args.cluster_id_old, parsed_args.cluster_id_new)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port,
                                           obj="server/provision",
                                           payload=payload, method="POST")

        self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")

