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
import json
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
import smgr_client_def

def parse_arguments(args_str=None):
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Reimage given server(s) with provided
                           base ISO and package. Servers can be
                           specified by providing match condition
                           to pick servers from the database.'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Reimage given server(s) with provided
                           base ISO and package. Servers can be
                           specified by providing match condition
                           to pick servers from the database.''',
            prog="server-manager reimage"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
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
    args = parser.parse_args(args_str)
    return args
# end parse arguments

def send_REST_request(ip, port, payload):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/server/reimage" %(
            ip, port)
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.POST, 1)
        conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None

def reimage_server(args_str=None):
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

    match_key = None
    match_value = None
    payload = {}
    if args.server_id:
        match_key='id'
        match_value = args.server_id
    elif args.cluster_id:
        match_key='cluster_id'
        match_value = args.cluster_id
    elif args.tag:
        match_key='tag'
        match_value = args.tag
    elif args.where:
        match_key='where'
        match_value = args.where
    else:
        pass
    
    payload['base_image_id'] = args.base_image_id
    payload['package_image_id'] = args.package_image_id
    if (args.no_reboot):
        payload['no_reboot'] = "y"
    if match_key:
        payload[match_key] = match_value

    if (not args.no_confirm):
        if args.base_image_id:
            image_str = args.base_image_id
        else:
            image_str = "configured"
        msg = "Reimage servers (%s:%s) with %s? (y/N) :" %(
            match_key, match_value, image_str)
        user_input = raw_input(msg).lower()
        if user_input not in ["y", "yes"]:
            sys.exit()
    # end if
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    smgr_client_def.print_rest_response(resp)
# End of reimage_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    reimage_server(sys.argv[1:])
# End if __name__
