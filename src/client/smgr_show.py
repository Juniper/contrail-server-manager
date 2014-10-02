#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_show.py
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
            description='''Show a Server Manager object'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Show a Server Manager object''',
            prog="server-manager show"
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
        "server",help='Show server')
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
    parser_server.set_defaults(func=show_server)

    # Subparser for cluster show
    parser_cluster = subparsers.add_parser(
        "cluster", help='Show cluster')
    parser_cluster.add_argument("--cluster_id",
                        help=("cluster id for cluster"))
    parser_cluster.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_cluster.set_defaults(func=show_cluster)

    # Subparser for image show
    parser_image = subparsers.add_parser(
        "image", help='Show image')
    parser_image.add_argument("--image_id",
                        help=("image id for image"))
    parser_image.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_image.set_defaults(func=show_image)

    # Subparser for all show
    parser_all = subparsers.add_parser(
        "all", help='Show all configuration (servers, clusters, images, tags)')
    parser_all.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_all.set_defaults(func=show_all)

    # Subparser for tags show
    parser_tag = subparsers.add_parser(
        "tag", help='Show list of server tags')
    parser_tag.set_defaults(func=show_tag)

    #Subparser for all Env Details
    parser_env_details = subparsers.add_parser(
        "env_details", help='Show the all the Server Env Details')
    env_group = parser_env_details.add_mutually_exclusive_group()
    env_group.add_argument("--server_id",
                                     help=("server id for server"))
    env_group.add_argument("--cluster_id",
                                    help=("cluster id for cluster"))
    parser_env_details.set_defaults(func=show_env_details)

    #Subparser for Fan Details
    parser_fan_details = subparsers.add_parser(
        "fan_details", help='Show the server Fan details')
    fan_group = parser_fan_details.add_mutually_exclusive_group()
    fan_group.add_argument("--server_id",
                           help=("server id for server"))
    fan_group.add_argument("--cluster_id",
                           help=("cluster id for cluster"))
    parser_fan_details.set_defaults(func=show_fan_details)

    # Subparser for Temp Details
    parser_temp_details = subparsers.add_parser(
        "temp_details", help='Show the server Temp details')
    temp_group = parser_temp_details.add_mutually_exclusive_group()
    temp_group.add_argument("--server_id",
                           help=("server id for server"))
    temp_group.add_argument("--cluster_id",
                           help=("cluster id for cluster"))
    parser_temp_details.set_defaults(func=show_temp_details)

    # Subparser for Power Consumption
    parser_pwr_details = subparsers.add_parser(
        "power_consumption", help='Show the server Power Consumption')
    pwr_group = parser_pwr_details.add_mutually_exclusive_group()
    pwr_group.add_argument("--server_id",
                           help=("server id for server"))
    pwr_group.add_argument("--cluster_id",
                           help=("cluster id for cluster"))
    parser_pwr_details.set_defaults(func=show_pwr_details)
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
        conn.setopt(pycurl.TIMEOUT, 5)
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.HTTPGET, 1)
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None
# end def send_REST_request

def show_server(args):
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

def show_cluster(args):
    if args.cluster_id:
        match_key = 'id'
        match_value = args.cluster_id
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'cluster',
        'match_key' : match_key,
        'match_value' : match_value
    }
    return rest_api_params
#end def show_cluster

def show_image(args):
    if args.image_id:
        match_key = 'id'
        match_value = args.image_id
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'image',
        'match_key' : match_key,
        'match_value' : match_value
    }
    return rest_api_params
#end def show_image

def show_all(args):
    rest_api_params = {
        'object' : 'all',
        'match_key' : None,
        'match_value' : None
    }
    return rest_api_params
#end def show_all

def show_tag(args):
    rest_api_params = {
        'object' : 'tag',
        'match_key' : None,
        'match_value' : None
    }
    return rest_api_params
#end def show_all

def show_fan_details(args):
    rest_api_params = {}
    rest_api_params['object'] = 'Fan'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def show_fan_details

def show_temp_details(args):
    rest_api_params = {}
    rest_api_params['object'] = 'Temp'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
# end def show_temp_details

def show_pwr_details(args):
    rest_api_params = {}
    rest_api_params['object'] = 'Pwr'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
# end def show_pwr_details

def show_env_details(args):
    rest_api_params = {}
    rest_api_params['object'] = 'Env'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
# end def show_env_details

def show_config(args_str=None):
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
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      detail)
    smgr_client_def.print_rest_response(resp)
# End of show_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    show_config(sys.argv[1:])
# End if __name__
