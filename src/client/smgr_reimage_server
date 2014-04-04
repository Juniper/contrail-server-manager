#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_reimage_server.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface that
   provides reimaging a server with given iso and repo.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import json
from collections import OrderedDict
import ConfigParser

_DEF_SMGR_PORT = 9001
_DEF_SMGR_CFG_FILE = "/etc/contrail_smgr/smgr_client_config.ini"

def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    # Process the arguments
    parser = argparse.ArgumentParser(
        description='''Reimage given server(s) with provided
                       base ISO and repository. Servers can be
                       specified by search in DB, or provided
                       in a file or entered interactively.'''
    )
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--ip_port", "-i",
                        help=("ip addr & port of server manager "
                              "<ip-addr>[:<port>] format, default port "
                              " 9001"))
    group1.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              _DEF_SMGR_CFG_FILE)))
    parser.add_argument("base_image_id",
                        help="image id for base image to be used")
    parser.add_argument("--repo_image_id", "-r",
                        help=("Optional contrail repo to be copied"
                             " on reimaged server"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server_id",
                        help=("server id for the server to be reimaged"))
    group.add_argument("--vns_id",
                        help=("vns id for the server(s) to be reimaged"))
    group.add_argument("--cluster_id",
                        help=("cluster id for the server(s) to be reimaged"))
    group.add_argument("--rack_id",
                        help=("rack id for the server(s) to be reimaged"))
    group.add_argument("--pod_id",
                        help=("pod id for the server(s) to be reimaged"))
    group.add_argument("--reimage_params_file", "-f", 
                        help=("Optional json file containing parameters "
                             " for reimaging servers"))
    group.add_argument("--interactive", "-I", action="store_true", 
                        help=("flag that user wants to enter the server "
                             " parameters for reimaging manually"))
    args = parser.parse_args()
    return args

# Function to accept parameters from user and then build payload to be
# sent with REST API request for reimaging server.
def get_reimage_params():
    server_list = []
    fields = OrderedDict ([
        ("server_id" , " (Server Name/Id) <Enter> to end : "),
        ("server_ip" , " (Server IP Address) : "),
        ("server_mac" , " (Server MAC Address) : "),
        ("server_mask" , " (Server subnet mask) : "),
        ("server_gway" , " (Server default gateway) : "),
        ("server_domain" , " (Server domain name) : "),
        ("server_passwd" , " (root password (default C0ntrail123)) : "),
        ("server_ifname" , " (Server Interface name (default eth0)) : ")
    ])
    print "******** List of servers to be reimaged ********"
    while True:
        server = {}
        done = False
        for field in fields:
            msg = field + fields[field] 
            user_input = raw_input(msg)
            if user_input:
                server[field] = user_input
            else:
                if field == 'server_id':
                    done = True
                    break
                # end if field ==
            # end else user_input
        # end for field in fields
        if done:
            break;
        server_list.append(server)
        print "****** Next Server details ******"
    # end while True
    reimage_params = {"servers" : server_list}
    return reimage_params
# End get_reimage_params

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

    reimage_params = {}
    match_key = None
    match_value = None
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
    elif args.interactive:
       reimage_params = get_reimage_params()
    elif args.reimage_params_file:
       reimage_params = json.load(
           open(args.reimage_params_file))
    else:
        pass
    
    payload = {}
    payload['base_image_id'] = args.base_image_id
    payload['repo_image_id'] = args.repo_image_id
    if match_key:
        payload[match_key] = match_value
    if reimage_params:
        payload['reimage_params'] = reimage_params
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    print resp
# End of reimage_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    reimage_server(sys.argv[1:])
# End if __name__
