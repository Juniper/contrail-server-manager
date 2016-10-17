#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_status.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   get server manager configuration objects.
   Objects can be cluster, server, or image.
   An optional parameter details is used to indicate if user
   wants to fetch details of the object.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import smgr_client_def
import json


def parse_arguments():
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Show a Server's Status'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Show a Servers status''',
            prog="server-manager status"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    subparsers = parser.add_subparsers(title='objects',
                                       description='valid objects',
                                       help='help for object')

    # Subparser for server show
    parser_server = subparsers.add_parser(
        "server",help='Show server status')
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
    group.add_argument("--discovered",
                        help=("flag to get list of "
                              "newly discovered server(s)"))
    parser_server.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_server.set_defaults(func=set_server_status)

    # Subparser for cluster show
    parser_provision = subparsers.add_parser(
        "provision",help='Show cluster provision status')
    p_group = parser_provision.add_mutually_exclusive_group()
    p_group.add_argument("--server_id",
                        help=("server id for server"))
    p_group.add_argument("--cluster_id",
                        help=("cluster id for server(s)"))
    p_group.add_argument("--tag",
                        help=("tag values for the server"
                              "in t1=v1,t2=v2,... format"))
    parser_provision.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_provision.set_defaults(func=set_provision_status)

    return parser
# end def parse_arguments

def send_REST_request(ip, port, object, match_key,
                      match_value, detail):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" % (ip, port, object)
        args_str = ''
        if match_key:
            args_str += match_key + "=" + match_value
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
    except:
        return None
# end def send_REST_request

def set_server_status(args):
    rest_api_params = {}
    rest_api_params['object'] = 'server'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.mac:
        rest_api_params['match_key'] = 'mac_address'
        rest_api_params['match_value'] = args.mac
    elif args.ip:
        rest_api_params['match_key'] = 'ip_address'
        rest_api_params['match_value'] = args.ip
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    elif args.tag:
        rest_api_params['match_key'] = 'tag'
        rest_api_params['match_value'] = args.tag
    elif args.discovered:
        rest_api_params['match_key'] = 'discovered'
        rest_api_params['match_value'] = args.discovered
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def show_server

def set_provision_status(args):
    rest_api_params = {}
    rest_api_params['object'] = 'provision'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    elif args.tag:
        rest_api_params['match_key'] = 'tag'
        rest_api_params['match_value'] = args.tag
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params

def show_status(args_str=None):
    parser = parse_arguments()
    args = parser.parse_args(args_str)
    if args.config_file:
        config_file = args.config_file
    else:
        config_file = smgr_client_def._DEF_SMGR_CFG_FILE
    # end args.config_file
    if hasattr(args, 'detail'):
        detail = args.detail
    else:
        detail = None
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
    rest_api_params = args.func(args)
    resp = send_REST_request(smgr_ip, smgr_port,
                      rest_api_params['object']+"_status",
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      detail)
    smgr_client_def.print_rest_response(resp)
# End of show_status

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    show_config(sys.argv[1:])
# End if __name__
