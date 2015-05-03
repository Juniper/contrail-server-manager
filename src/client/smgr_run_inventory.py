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
import requests
import json

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
import smgr_client_def
import urllib


def parse_arguments(args_str=None):
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Run inventory for given server(s)'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Run inventory for given server(s)''',
            prog="server-manager run_inventory"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" % (
                                  smgr_client_def._DEF_SMGR_CFG_FILE)))
    parser.add_argument(
        "package_image_id", nargs='?',
        help="contrail package image id to be used for provisioning")
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
    args = parser.parse_args(args_str)
    return args
# End get_provision_params


def send_REST_request(ip, port, payload):
    try:
        url = "http://%s:%s/run_inventory" % (ip, port)
        args_str = ''
        match_key, match_value = payload.popitem()
        if match_key and match_value:
            args_str += urllib.quote_plus(str(match_key)) + "=" \
                        + urllib.quote_plus(str(match_value))
        if args_str != '':
            url += "?" + args_str
        headers = {'content-type': 'application/json'}
        resp = requests.post(url, headers=headers, timeout=30)
        return resp.text
    except Exception as e:
        return None


def run_inventory(args_str=None):
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
                      "%s" % config_file))
        smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
    except:
        sys.exit("Error reading config file %s" % config_file)
    # end except

    payload = {}
    match_key = None
    if args.server_id:
        match_key = 'id'
        match_value = args.server_id
    elif args.cluster_id:
        match_key = 'cluster_id'
        match_value = args.cluster_id
    elif args.tag:
        match_key = 'tag'
        match_value = args.tag
    else:
        pass

    if match_key:
        payload[match_key] = match_value

    if (not args.no_confirm):
        msg = "Run Inventory on servers matching: (%s:%s)? (y/N) :" % (
            match_key, match_value)
        user_input = raw_input(msg).lower()
        if user_input not in ["y", "yes"]:
            sys.exit()
    # end if

    resp = send_REST_request(smgr_ip, smgr_port, payload)
    smgr_client_def.print_rest_response(resp)

# End of run_inventory

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')
    run_inventory(sys.argv[1:])
# End if __name__

