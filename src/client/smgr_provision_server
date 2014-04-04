#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_provision_server.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface that
   provides provisioning a server for the roles configured. The
   SM prepares puppet manifests that define the role(s) being
   configured on receiving this REST API request.
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
        description='''Provision given server(s) for roles configured
                    list of servers can be selected from DB config or
                    in a json file or provided interactively '''
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
    group = parser.add_mutually_exclusive_group(required=True)
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
    group.add_argument("--provision_params_file", "-f", 
                        help=("Optional json file containing parameters "
                             " for provisioning server"))
    group.add_argument("--interactive", "-I", action="store_true", 
                        help=("flag that user wants to enter the server "
                             " parameters for provisioning manually"))
    args = parser.parse_args()
    return args

# Function to accept parameters from user and then build payload to be
# sent with REST API request for reimaging server.
def get_provision_params():
    provision_params = {}
    params = OrderedDict ([
        ("domain" , " (Domain name) : "),
        ("database_dir" , " (Datbase directory - default /home/cassandra) : "),
        ("db_initial_token" , " (Database initial token - default none) : "),
        ("openstack_mgmt_ip" , " (Openstack node mgmt IP address - default server IP) : "),
        ("use_certs" , " (Openstack use certificates (True/False) - default false) : "),
        ("multi_tenancy" , " (Openstack multi tenancy (True/False) - default false) : "),
        ("service_token" , " (Service Token for openstack) : "),
        ("ks_user" , " (Keystone username - default admin) : "),
        ("ks_passwd" , " (Keystone password - default contrail123) : "),
        ("ks_tenant" , " (Keystone Tenant - default admin) : "),
        ("openstack_passwd" , " (Openstack node password - default contrail123) : "),
        ("analytics_data_ttl" , " (Analytics data TTL - Default 168) : ")
    ])
    servers = OrderedDict ([
        ("server_id" , " (Server Name - <Enter> to end) : "),
        ("server_ip" , " (Server IP) : "),
        ("ifname" , " (physical interface name for compute - default eth0) : "),
        ("compute_non_mgmt_ip" , " (Compute node non mgmt IP - default none) : "),
        ("compute_non_mgmt_gway" , " (Compute node non mgmt gway - default none) : ")
    ])
    roles = OrderedDict ([
        ("database" , " (Comma separated list of server names for this role) : "),
        ("openstack" , " (Comma separated list of server names for this role) : "),
        ("config" , " (Comma separated list of server names for this role) : "),
        ("control" , " (Comma separated list of server names for this role) : "),
        ("collector" , " (Comma separated list of server names for this role) : "),
        ("webui" , " (Comma separated list of server names for this role) : "),
        ("compute" , " (Comma separated list of server names for this role) : ")
    ])
    # Accept all the vns level parameter values
    param_dict = {}
    print "****** VNS Params to be provided ******"
    for field in params:
       msg = field + params[field] 
       user_input = raw_input(msg)
       if user_input:
           param_dict[field] = user_input
    # end for field in params
    provision_params['params'] = param_dict

    # Accept all the servers
    print "****** List of servers to be provisioned ******"
    server_list = []
    while True:
        server = {}
        done = False
        for field in servers:
            msg = field + servers[field] 
            user_input = raw_input(msg)
            if user_input:
                server[field] = user_input
            else:
                if field == 'server_id':
                    done = True
                    break
                # end if field ==
            # end else user_input
        # end for field in params
        if done:
            break
        server_list.append(server)
    # End while True
    provision_params['servers'] = server_list

    # Accept all the role definitions
    print "****** List of role definitions ******"
    role_dict = {}
    for field in roles:
        msg = field + roles[field] 
        user_input = raw_input(msg)
        if user_input:
            role_dict[field] = user_input.split(",")
    # end for field in params
    provision_params['roles'] = role_dict
    return provision_params
# End get_provision_params

def send_REST_request(ip, port, payload):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/server/provision" %(
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

def provision_server(args_str=None):
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

    provision_params = {}
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
       provision_params = get_provision_params()
    elif args.provision_params_file:
       provision_params = json.load(
           open(args.provision_params_file))
    else:
        pass

    payload = {}
    if match_key:
        payload[match_key] = match_value
    if provision_params:
        payload['provision_params'] = provision_params
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    print resp
# End of provision_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    provision_server(sys.argv[1:])
# End if __name__
