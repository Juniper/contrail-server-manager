#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_delete.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   delete server manager configuration objects.
   Objects can be vns, cluster, server, or image.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO

_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 8090


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]

    # Process the arguments
    parser = argparse.ArgumentParser(
        description='''Delete a Server Manager object''',
    )
    parser.add_argument("--smgr_ip", "-i",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port", "-p",
                        help="server manager listening port number")
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       help='help for subcommand')

    # Subparser for server delete
    parser_server = subparsers.add_parser(
        "server",help='Delete server')
    group = parser_server.add_mutually_exclusive_group(required=True)
    group.add_argument("--server_id",
                        help=("server id for server to be deleted"))
    group.add_argument("--mac",
                        help=("mac address for server to be deleted"))
    group.add_argument("--ip",
                        help=("ip address for server to be deleted"))
    group.add_argument("--vns_id",
                        help=("vns id for server(s) to be deleted"))
    group.add_argument("--cluster_id",
                        help=("cluster id for server(s) to be deleted"))
    group.add_argument("--rack_id",
                        help=("rack id for server(s) to be deleted"))
    group.add_argument("--pod_id",
                        help=("pod id for server(s) to be deleted"))
    parser_server.set_defaults(func=delete_server)

    # Subparser for vns delete
    parser_vns = subparsers.add_parser(
        "vns", help='Delete vns')
    parser_vns.add_argument("vns_id",
                        help=("vns id for vns to be deleted"))
    parser_vns.set_defaults(func=delete_vns)

    # Subparser for cluster delete
    parser_cluster = subparsers.add_parser(
        "cluster", help='Delete cluster')
    parser_cluster.add_argument("cluster_id",
                        help=("cluster id for cluster to be deleted"))
    parser_cluster.set_defaults(func=delete_cluster)

    # Subparser for image delete
    parser_image = subparsers.add_parser(
        "image", help='Delete image')
    parser_image.add_argument("image_id",
                        help=("image id for image to be deleted"))
    parser_image.set_defaults(func=delete_image)
    return parser
# end def parse_arguments

def send_REST_request(ip, port, object, key, value):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s?%s=%s" %(
            ip, port, object, key, value)
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.CUSTOMREQUEST, "delete")
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None
# end def send_REST_request

def delete_server(args):
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
        rest_api_params['match_key'] = ''
        rest_api_params['match_value'] = ''
    return rest_api_params
#end def delete_server

def delete_vns(args):
    rest_api_params = {
        'object' : 'vns',
        'match_key' : 'vns_id',
        'match_value' : args.vns_id
    }
    return rest_api_params
#end def delete_vns

def delete_cluster(args):
    rest_api_params = {
        'object' : 'cluster',
        'match_key' : 'cluster_id',
        'match_value' : args.cluster_id
    }
    return rest_api_params
#end def delete_cluster

def delete_image(args):
    rest_api_params = {
        'object' : 'image',
        'match_key' : 'image_id',
        'match_value' : args.image_id
    }
    return rest_api_params
#end def delete_image

def delete_config(args_str=None):
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }
    parser = parse_arguments(args_str)
    args = parser.parse_args()
    if args.smgr_ip:
        serverMgrCfg['smgr_ip_addr'] = args.smgr_ip
    if args.smgr_port:
        serverMgrCfg['smgr_port'] = args.smgr_port
    rest_api_params = args.func(args)
    resp = send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'])
    print resp
# End of delete_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    delete_config(sys.argv[1:])
# End if __name__
