#!/usr/bin/python

import argparse
import smgr_client_def
from smgr_provision_server import *
import ConfigParser

def parse_arguments(args_str=None):
    parser = argparse.ArgumentParser(
        description='''Perform in service software upgrade from old 
                       cluster to new cluster''',
        prog="server-manager issu"
    )
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    parser.add_argument("--cluster_id_old",
                        help=("cluster to be upgraded"))
    parser.add_argument("--cluster_id_new",
                        help=("active cluster after the upgrade"))
    #parser.add_argument("--old_version",
    #                    help=("version of the cluster being upgraded"))
    parser.add_argument("--new_image",
                        help=("contrail image cluster being upgraded to"))
    parser.add_argument("--no_confirm", "-F", action="store_true",
                        help=("flag to bypass confirmation message, "
                              "default = do not bypass"))
    args = parser.parse_args(args_str)
    return args

def do_issu(args_str=None):
    args = parse_arguments(args_str)
    if args.config_file:
        config_file = args.config_file
    else:
        config_file = smgr_client_def._DEF_SMGR_CFG_FILE
    # end args.config_file
    try:
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        smgr_config = dict(config.items("SERVER-MANAGER"))
        smgr_ip = smgr_config.get("listen_ip_addr", None)
        if not smgr_ip:
            sys.exit(("listen_ip_addr missing in config file"
                      "%s" %config_file))
        smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
    except:
        sys.exit("Error reading config file %s" %config_file)
    # end except

    # contruct paylod for backend
    payload = {}
    payload['opcode'] = 'issu'
    payload['old_cluster'] = args.cluster_id_old
    payload['new_cluster'] = args.cluster_id_new
    #payload['old_version'] = args.old_version
    payload['new_image'] = args.new_image

    if (not args.no_confirm):
        msg = "Upgrade cluster %s to %s:Version:%s? (y/N) :" %(
                                    args.cluster_id_old, args.cluster_id_new,
                                    args.new_image)
        user_input = raw_input(msg).lower()
        if user_input not in ["y", "yes"]:
            sys.exit()
    # end if
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    smgr_client_def.print_rest_response(resp)
# End of provision_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    do_issu(sys.argv[1:])
# End if __name__
