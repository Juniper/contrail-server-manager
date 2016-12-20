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
import urllib
from smgr_monitoring import ServerMgrIPMIQuerying
from smgr_inventory import ServerMgrInventory

mon_querying_obj = ServerMgrIPMIQuerying()
inv_querying_obj = ServerMgrInventory()

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
    group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    group.add_argument("--discovered",
                        help=("flag to get list of "
                              "newly discovered server(s)"))
    server_select_group = parser_server.add_mutually_exclusive_group()
    server_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    server_select_group.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")

    parser_server.add_argument(
        "--show_passwords", "-s", action='store_true',
        help=argparse.SUPPRESS)


    parser_server.set_defaults(func=show_server)

    # Subparser for inventory show
    parser_inventory = subparsers.add_parser(
        "inventory", help='Show server inventory')
    inv_group = parser_inventory.add_mutually_exclusive_group()
    inv_group.add_argument("--server_id",
                       help=("server id for server"))
    inv_group.add_argument("--cluster_id",
                           help=("cluster id for server"))
    inv_group.add_argument("--tag", help=("tag values for the server"
                                          "in t1=v1,t2=v2,... format"))
    inv_group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
    parser_inventory.set_defaults(func=inv_querying_obj.show_inv_details)

    # Subparser for cluster show
    parser_cluster = subparsers.add_parser(
        "cluster", help='Show cluster')
    cluster_group = parser_cluster.add_mutually_exclusive_group()
    cluster_group.add_argument("--cluster_id",
                        help=("cluster id for cluster"))
    cluster_group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    cluster_select_group = parser_cluster.add_mutually_exclusive_group()
    cluster_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    cluster_select_group.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")

    parser_cluster.add_argument(
        "--show_passwords", "-s", action='store_true',
        help=argparse.SUPPRESS)

    parser_cluster.set_defaults(func=show_cluster)

    # Subparser for image show
    parser_image = subparsers.add_parser(
        "image", help='Show image')
    image_group = parser_image.add_mutually_exclusive_group()
    image_group.add_argument("--image_id",
                        help=("image id for image"))
    image_group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    image_select_group = parser_image.add_mutually_exclusive_group()
    image_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    image_select_group.add_argument(
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

    # Subparser for monitoring show
    parser_monitoring = subparsers.add_parser(
        "monitoring", help='Show server inventory')
    mon_group = parser_monitoring.add_mutually_exclusive_group()
    mon_group.add_argument("--server_id",
                           help=("server id for server"))
    mon_group.add_argument("--cluster_id",
                           help=("cluster id for server"))
    mon_group.add_argument("--tag", help=("tag values for the server"
                                          "in t1=v1,t2=v2,... format"))
    mon_group.add_argument("--where",
                           help=("sql where statement in quotation marks"))
    parser_monitoring.set_defaults(func=mon_querying_obj.show_mon_details)

    # Subparser for logs show
    parser_logs = subparsers.add_parser("logs", help='Show logs from server')
    #log_group   = parser_logs.add_mutually_exclusive_group()
    parser_logs.add_argument("--server_id", help=("server id for server"))
    parser_logs.add_argument("--file_name", help=("log file on the server"))
    parser_logs.set_defaults(func=show_log)

    return parser
# end def parse_arguments

def send_REST_request(ip, port, rest_api_params, detail):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" % (ip, port, rest_api_params['object'])
        args_str = ''
        if rest_api_params["select"]:
            args_str += "select" + "=" \
                + urllib.quote_plus(rest_api_params["select"]) + "&"
        if rest_api_params["match_key"]:
            args_str += urllib.quote_plus(rest_api_params["match_key"]) + "=" \
                + urllib.quote_plus(rest_api_params["match_value"])

        if rest_api_params['object'] == 'log' and rest_api_params["file_key"]:
            args_str += "&" + urllib.quote_plus(rest_api_params["file_key"]) + "=" \
                + urllib.quote_plus(rest_api_params["file_value"])

	if 'show_passwords' in rest_api_params:
            args_str += "&show_pass=true"
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

def show_server(args):
    rest_api_params = {}
    rest_api_params['object'] = 'server'
    rest_api_params['select'] = args.select
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
    elif args.where:
        rest_api_params['match_key'] = 'where'
        rest_api_params['match_value'] = args.where
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None

    if args.show_passwords:
        rest_api_params['show_passwords'] = True

    return rest_api_params
#end def show_server

def show_cluster(args):
    if args.cluster_id:
        match_key = 'id'
        match_value = args.cluster_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'cluster',
        'match_key' : match_key,
        'match_value' : match_value,
        'select' : args.select
    }
    if args.show_passwords:
        rest_api_params['show_passwords'] = True

    return rest_api_params
#end def show_cluster

def show_image(args):
    if args.image_id:
        match_key = 'id'
        match_value = args.image_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'image',
        'match_key' : match_key,
        'match_value' : match_value,
        'select' : args.select
    }
    return rest_api_params
#end def show_image

def show_all(args):
    rest_api_params = {
        'object' : 'all',
        'match_key' : None,
        'match_value' : None,
        'select' : None
    }
    return rest_api_params
#end def show_all

def show_tag(args):
    rest_api_params = {
        'object' : 'tag',
        'match_key' : None,
        'match_value' : None,
        'select' : None
    }
    return rest_api_params
#end def show_all

def show_log(args):
    match_key   = None
    match_value = None
    file_value  = None
    file_key    = None
    if args.server_id:
        match_key = 'id'
        match_value = args.server_id
    if args.file_name:
        file_key = 'file'
        file_value = args.file_name

    rest_api_params = {
        'object' : 'log',
        'match_key' : match_key,
        'match_value' : match_value,
        'file_key' : file_key,
        'file_value' : file_value,
        'select' : None
    }
    return rest_api_params
#end def show_log

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
    except Exception as e:
        sys.exit("Exception: %s : Error reading config file %s" %(e.message, config_file))
    # end except
    rest_api_params = args.func(args)
    resp = send_REST_request(smgr_ip, smgr_port, rest_api_params, detail)
    smgr_client_def.print_rest_response(resp)
# End of show_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    show_config(sys.argv[1:])
# End if __name__

