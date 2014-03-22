#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_restart_server.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface that
   provides restarting server(s) via server manager. The program
   takes an optional parameter (netboot), if set the server is
   enabled for booting from net, else a local boot is performed.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import json
from collections import OrderedDict

_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 9001


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    # Process the arguments
    parser = argparse.ArgumentParser(
        description='''Reboot given server(s). Servers can be
                       specified by search in DB, or provided
                       in a file or entered interactively.'''
    )
    parser.add_argument("--smgr_ip", "-i",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port", "-p",
                        help="server manager listening port number")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--server_id",
                        help=("server id for the server to be provisioned"))
    group.add_argument("--vns_id",
                        help=("vns id for the server(s) to be provisioned"))
    group.add_argument("--cluster_id",
                        help=("cluster id for the server(s) to be provisioned"))
    group.add_argument("--rack_id",
                        help=("rack id for the server(s) to be provisioned"))
    group.add_argument("--pod_id",
                        help=("pod id for the server(s) to be provisioned"))
    group.add_argument("--restart_params_file", "-f", 
                        help=("Optional json file containing params of "
                             " servers to be restarted"))
    group.add_argument("--interactive", "-I", action="store_true", 
                        help=("flag that user wants to enter the server "
                             " IP addresses manually"))
    parser.add_argument("--net_boot", "-n", action="store_true",
                        help=("optional parameter to indicate"
                             " if server should be netbooted."))
    args = parser.parse_args()
    return args
# end def parse_arguments

# Function to accept parameters from user and then build payload to be
# sent with REST API request for reimaging server.
def get_restart_params():
    restart_params = {}
    params = OrderedDict ([
        ("server_ip" , " (Server IP Address) : "),
        ("server_passwd" , " (root password for server) : "),
        ("server_id" , " (Server id (Needed if netboot is enabled)) : "),
        ("server_domain" , " (Domain name (Needed if netboot is enabled)) : ")
    ])
    # Accept all the servers
    print "****** List of servers to be restarted ******"
    server_list = []
    while True:
        server = {}
        done = False
        for field in params:
            msg = field + params[field] 
            user_input = raw_input(msg)
            if user_input:
                server[field] = user_input
            else:
                if field == 'server_ip':
                    done = True
                    break
                # end if field ==
            # end else user_input
        # end for field in params
        if done:
            break
        server_list.append(server)
    # End while True
    restart_params['servers'] = server_list
    return restart_params
# End get_restart_params

def send_REST_request(ip, port, payload):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/server/restart" %(
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
# end def send_REST_request

def restart_server(args_str=None):
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }
    args = parse_arguments(args_str)
    if args.smgr_ip:
        serverMgrCfg['smgr_ip_addr'] = args.smgr_ip
    if args.smgr_port:
        serverMgrCfg['smgr_port'] = args.smgr_port
    restart_params = {}
    match_key = None
    match_param = None
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
       restart_params = get_restart_params()
    elif args.restart_params_file:
       restart_params = json.load(
           open(args.restart_params_file))
    else:
        pass

    payload = {}
    if match_key:
        payload[match_key] = match_value
    if restart_params:
        payload['restart_params'] = restart_params
    if (args.net_boot):
        payload['net_boot'] = "y"
 
    resp = send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      payload)
    print resp
# End of restart_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    restart_server(sys.argv[1:])
# End if __name__
