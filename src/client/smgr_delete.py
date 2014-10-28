#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_delete.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   delete server manager configuration objects.
   Objects can be cluster, server, or image.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import smgr_client_def
import urllib

def parse_arguments():
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Delete a Server Manager object'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Delete a Server Manager object''',
            prog="server-manager delete"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    subparsers = parser.add_subparsers(title='objects',
                                       description='valid objects',
                                       help='help for object')

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
    group.add_argument("--cluster_id",
                        help=("cluster id for server(s) to be deleted"))
    group.add_argument("--tag",
                        help=("tag values for the server to be deleted "
                              "in t1=v1,t2=v2,... format"))
    group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    parser_server.set_defaults(func=delete_server)

    # Subparser for cluster delete
    parser_cluster = subparsers.add_parser(
        "cluster", help='Delete cluster')
    parser_cluster_group = parser_cluster.add_mutually_exclusive_group(required=True)
    parser_cluster_group.add_argument("--cluster_id",
                                      help=("cluster id for cluster to be deleted"))
    parser_cluster_group.add_argument("--where",
                                      help=("sql where statement in quotation marks"))
    parser_cluster.add_argument("--force", "-f", action="store_true",
                                help=("optional parameter to indicate ,"
                                      "if cluster association to be removed from server"))
    parser_cluster.set_defaults(func=delete_cluster)

    # Subparser for image delete
    parser_image = subparsers.add_parser(
        "image", help='Delete image')
    parser_image.add_argument("--where",
                              help=("sql where statement in quotation marks"))
    parser_image.add_argument("--image_id",
                        help=("image id for image to be deleted"))
    parser_image.set_defaults(func=delete_image)
    return parser
# end def parse_arguments

def send_REST_request(ip, port, object, key, value, force=False):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s?%s=%s" %(
            ip, port, object, 
            urllib.quote_plus(key), 
            urllib.quote_plus(value))
        if force:
            url += "&force"
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
    elif args.where:
        rest_api_params['match_key'] = 'where'
        rest_api_params['match_value'] = args.where
    else:
        rest_api_params['match_key'] = ''
        rest_api_params['match_value'] = ''
    return rest_api_params
#end def delete_server

def delete_cluster(args):
    if args.cluster_id:
        match_key = 'id'
        match_value = args.cluster_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = ''
        match_value = ''
    rest_api_params = {
        'object' : 'cluster',
        'match_key' : match_key,
        'match_value' : match_value
    }
    return rest_api_params
#end def delete_cluster

def delete_image(args):
    if args.image_id:
        match_key = 'id'
        match_value = args.image_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = ''
        match_value = ''
    rest_api_params = {
        'object' : 'image',
        'match_key' : match_key,
        'match_value' : match_value
    }
    return rest_api_params
#end def delete_image

def delete_config(args_str=None):
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
    rest_api_params = args.func(args)
    force = False
    if 'force' in args:
        force = args.force
    resp = send_REST_request(smgr_ip, smgr_port,
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      force)
    smgr_client_def.print_rest_response(resp)
# End of delete_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    delete_config(sys.argv[1:])
# End if __name__
