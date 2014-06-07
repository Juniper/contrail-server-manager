#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_show.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   get server manager configuration objects.
   Objects can be vns, cluster, server, or image.
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
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--ip_port", "-i",
                        help=("ip addr & port of server manager "
                              "<ip-addr>[:<port>] format, default port "
                              " 9001"))
    group1.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              _DEF_SMGR_CFG_FILE)))
    parser.add_argument("--detail", "-d", action='store_true',
                        help="Flag to indicate if details are requested")
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
    group.add_argument("--vns_id",
                        help=("vns id for server(s)"))
    group.add_argument("--cluster_id",
                        help=("cluster id for server(s)"))
    group.add_argument("--rack_id",
                        help=("rack id for server(s)"))
    group.add_argument("--pod_id",
                        help=("pod id for server(s)"))
    parser_server.set_defaults(func=show_server)

    # Subparser for vns show
    parser_vns = subparsers.add_parser(
        "vns", help='Show vns')
    parser_vns.add_argument("--vns_id",
                        help=("vns id for vns"))
    parser_vns.set_defaults(func=show_vns)

    # Subparser for cluster show
    parser_cluster = subparsers.add_parser(
        "cluster", help='Show cluster')
    parser_cluster.add_argument("--cluster_id",
                        help=("cluster id for cluster"))
    parser_cluster.set_defaults(func=show_cluster)

    # Subparser for image show
    parser_image = subparsers.add_parser(
        "image", help='Show image')
    parser_image.add_argument("--image_id",
                        help=("image id for image"))
    parser_image.set_defaults(func=show_image)

    # Subparser for all show
    parser_all = subparsers.add_parser(
        "all", help='Show all configuration (servers,vns,clusters, images)')
    parser_all.set_defaults(func=show_all)
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
        conn.setopt(pycurl.TIMEOUT, 1)
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
        rest_api_params['match_key'] = 'server_id'
        rest_api_params['match_value'] = args.server_id
    elif args.mac:
        rest_api_params['match_key'] = 'mac'
        rest_api_params['match_value'] = args.mac
    elif args.ip:
        rest_api_params['match_key'] = 'ip'
        rest_api_params['match_value'] = args.ip
    elif args.vns_id:
        rest_api_params['match_key'] = 'vns_id'
        rest_api_params['match_value'] = args.vns_id
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    elif args.rack_id:
        rest_api_params['match_key'] = 'rack_id'
        rest_api_params['match_value'] = args.rack_id
    elif args.pod_id:
        rest_api_params['match_key'] = 'pod_id'
        rest_api_params['match_value'] = args.pod_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def show_server

def show_vns(args):
    if args.vns_id:
        match_key = 'vns_id'
        match_value = args.vns_id
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'vns',
        'match_key' : match_key,
        'match_value' : match_value
    }
    return rest_api_params
#end def show_vns

def show_cluster(args):
    if args.cluster_id:
        match_key = 'cluster_id'
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
        match_key = 'image_id'
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

def show_config(args_str=None):
    parser = parse_arguments()
    args = parser.parse_args(args_str)
    if args.ip_port:
        smgr_ip, smgr_port = args.ip_port.split(":")
        if not smgr_port:
            smgr_port = _DEF_SMGR_PORT
    else:
        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        # end args.config_file
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not smgr_ip:
                sys.exit(("listen_ip_addr missing in config file"
                          "%s" %config_file))
            smgr_port = smgr_config.get("listen_port", _DEF_SMGR_PORT)
        except:
            sys.exit("Error reading config file %s" %config_file)
        # end except
    # end else args.ip_port
    rest_api_params = args.func(args)
    resp = send_REST_request(smgr_ip, smgr_port,
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      args.detail)
    print resp
# End of show_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    show_config(sys.argv[1:])
# End if __name__
