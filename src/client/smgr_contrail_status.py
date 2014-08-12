#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_status.py
   Author : Prasad Miriyala & Bharat Putta
   Description : This program is a simple cli interface to
   get status of a server or all the servers in a Cluster.
"""
import argparse
import cgitb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import json
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
            prog="server-manager status"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    parser.add_argument("--detail", "-d", action='store_true',
                        help="Flag to indicate if details are requested")
    subparsers = parser.add_subparsers(title='objects',
                                       description='valid objects',
                                       help='help for object')

    # Subparser for server status
    parser_server = subparsers.add_parser(
        "server",help='Status server')
    group = parser_server.add_mutually_exclusive_group()
    group.add_argument("--server_id",
                        help=("server id for server"))
    parser_server.set_defaults(get_rest_params=server_rest_params)
    parser_server.set_defaults(get_status=get_server_status)


    # Subparser for cluster show
    parser_cluster = subparsers.add_parser(
        "cluster", help='Status cluster')
    parser_cluster.add_argument("--cluster_id",
                        help=("id for cluster"))
    parser_cluster.set_defaults(get_rest_params=cluster_rest_params)
    parser_cluster.set_defaults(get_status=get_cluster_status)

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

def server_rest_params(args):
    rest_api_params = {}
    rest_api_params['object'] = 'status'
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def server_status_rest_params

def cluster_rest_params(args):
    rest_api_params = {}
    rest_api_params['object'] = 'server'
    if args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def cluster_status_rest_params

def get_obj(resp):
    try:
        data = json.loads(resp)
        return data
    except ValueError:
        return {}
#end def get_obj

def get_server_status(args, smgr_ip, smgr_port):
    rest_api_params = args.get_rest_params(args)
    resp = send_REST_request(smgr_ip, smgr_port,
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      args.detail)
    if resp is not None:
        status = get_obj(resp)
        if 'server_status' not in status:
            return
        server_status = status['server_status']
        modified_status = server_status.replace('active', 'active\n') \
            .replace('failed', 'failed\n') \
            .replace('STARTIN', 'STARTIN\n') \
            .replace('BACKOFF', 'BACKOFF\n') \
            .replace( ' ==', ' ==\n') \
            .replace('NOT PRESENT', 'NOT PRESENT\n')\
            .replace('EXITED', 'EXITED\n') 
        print modified_status
#end def get_server_status

def get_cluster_status(args, smgr_ip, smgr_port):
    rest_api_params = args.get_rest_params(args)
    resp = send_REST_request(smgr_ip, smgr_port,
                             rest_api_params['object'],
                             rest_api_params['match_key'],
                             rest_api_params['match_value'],
                             args.detail)    
    servers = json.loads(resp)['server']
    for server in servers:
        server_id = server['id']
        server_resp = send_REST_request(smgr_ip, smgr_port,
                                        'status',
                                        'id',
                                        server_id.encode('ascii','ignore'),
                                        args.detail)
        if server_resp is None:
            continue
        status = get_obj(server_resp)
        if 'server_status' not in status:
            continue
        server_status = status['server_status']
        modified_status = server_status.replace('active', 'active\n') \
            .replace('failed', 'failed\n') \
            .replace('STARTIN', 'STARTIN\n') \
            .replace('BACKOFF', 'BACKOFF\n') \
            .replace( ' ==', ' ==\n') \
            .replace('NOT PRESENT', 'NOT PRESENT\n') \
            .replace('EXITED', 'EXITED\n')
        print ("Server %s status:") % (server_id)
        print modified_status
        print "\n"

#end def get_cluster_status

def show_status(args_str=None):
    parser = parse_arguments()
    args = parser.parse_args(args_str)
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
    args.get_status(args, smgr_ip, smgr_port)
# End of show_status


if __name__ == "__main__":
    cgitb.enable(format='text')
    show_status(sys.argv[1:])
# End if __name__
