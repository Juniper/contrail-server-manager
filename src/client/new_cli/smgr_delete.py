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
    parser.add_argument("object", choices = ['server',
                                             'cluster',
                                             'vns',
                                             'image'],
                        help=("Object to be deleted"))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--server_id",
                        help=("server id for server to get info"))
    group.add_argument("--vns_id",
                        help=("vns id for vns or server(s) to get info"))
    group.add_argument("--cluster_id",
                        help=("cluster id for cluster or server(s) to get info about"))
    group.add_argument("--rack_id",
                        help=("rack id for server(s) to get info"))
    group.add_argument("--pod_id",
                        help=("pod id for server(s) to get info"))
    args = parser.parse_args()
    return args


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


def delete_config(args_str=None):
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }
    args = parse_arguments(args_str)
    if args.smgr_ip:
        serverMgrCfg['smgr_ip_addr'] = args.smgr_ip
    if args.smgr_port:
        serverMgrCfg['smgr_port'] = args.smgr_port
    object = args.object
    if args.server_id:
        match_key='server_id'
        match_value = args.server_id
    elif args.vns_id:
        match_key='vns_id'
        match_value = args.vns_id
    elif args.cluster_id:
        match_key='cluster_id'
        match_value = args.cluster_id
    elif args.rack_id:
        match_key='rack_id'
        match_value = args.rack_id
    elif args.pod_id:
        match_key='pod_id'
        match_value = args.pod_id
    else:
        match_key = None
        match_value = None
    resp = send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      object, match_key, match_value)
    print resp
# End of delete_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    delete_config(sys.argv[1:])
# End if __name__
