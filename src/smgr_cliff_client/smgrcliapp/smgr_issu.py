#!/usr/bin/python

import argparse
import ConfigParser
from smgr_client_utils import SmgrClientUtils as smgrutils

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
        parser.add_argument("--no_confirm", "-F", action="store_true",
                            help=("flag to bypass confirmation message, "
                                  "default = do not bypass"))
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
        else:
            payload['compute_tag'] = None

        if (not parsed_args.no_confirm):
            msg = "Upgrade cluster %s to %s, Contrail Image:%s? (y/N) :" %(
                         parsed_args.cluster_id_old, parsed_args.cluster_id_new,
                         parsed_args.new_image)
            user_input = raw_input(msg).lower()
            if user_input not in ["y", "yes"]:
                sys.exit()
        # end if

        resp = smgrutils.send_REST_request(self.smgr_ip, self.smgr_port,
                                 payload)
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
                                           payload)
        self.app.stdout.write("\n" + str(smgrutils.print_rest_response(resp)) + "\n")

