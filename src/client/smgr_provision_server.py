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
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
import smgr_client_def

def parse_arguments(args_str=None):
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Provision given server(s) for roles configured
                        list of servers can be selected from DB config or
                        in a json file or provided interactively '''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Provision given server(s) for roles configured
                        list of servers can be selected from DB config or
                        in a json file or provided interactively ''',
            prog="server-manager provision"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    parser.add_argument(
        "package_image_id", nargs='?',
        help="contrail package image id to be used for provisioning")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server_id",
                        help=("server id for the server to be provisioned"))
    group.add_argument("--cluster_id",
                        help=("cluster id for the server(s) to be provisioned"))
    group.add_argument("--tag",
                        help=("tag values for the servers to be provisioned"))
    group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    group.add_argument("--provision_params_file", "-f", 
                        help=("Optional json file containing parameters "
                             " for provisioning server"))
    group.add_argument("--interactive", "-I", action="store_true", 
                        help=("flag that user wants to enter the server "
                             " parameters for provisioning manually"))
    parser.add_argument("--no_confirm", "-F", action="store_true",
                        help=("flag to bypass confirmation message, "
                              "default = do not bypass"))
    args = parser.parse_args(args_str)
    return args

# Function to accept parameters from user and then build payload to be
# sent with REST API request for reimaging server.
def get_provision_params():
    provision_params = {}
    roles = OrderedDict ([
        ("database" , " (Comma separated list of server names for this role) : "),
        ("openstack" , " (Comma separated list of server names for this role) : "),
        ("config" , " (Comma separated list of server names for this role) : "),
        ("control" , " (Comma separated list of server names for this role) : "),
        ("collector" , " (Comma separated list of server names for this role) : "),
        ("webui" , " (Comma separated list of server names for this role) : "),
        ("compute" , " (Comma separated list of server names for this role) : "),
        ("storage-compute", " (Comma separated list of server names for this role) : "),
        ("storage-master", " (Comma separated list of server names for this role) : ")
    ])
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

    provision_params = {}
    payload = {}
    match_key = None
    match_param = None
    if args.server_id:
        match_key='id'
        match_value = args.server_id
    elif args.cluster_id:
        match_key='cluster_id'
        match_value = args.cluster_id
    elif args.tag:
        match_key='tag'
        match_value = args.tag
    elif args.where:
        match_key='where'
        match_value = args.where
    elif args.interactive:
       provision_params = get_provision_params()
    elif args.provision_params_file:
       provision_params = json.load(
           open(args.provision_params_file))
    else:
        pass

    payload['package_image_id'] = args.package_image_id
    if match_key:
        payload[match_key] = match_value
    if provision_params:
        payload['provision_parameters'] = provision_params

    if (not args.no_confirm):
        if args.package_image_id:
            pkg_id_str = args.package_image_id
        else:
            pkg_id_str = "configured package"
        if match_key:
            msg = "Provision servers (%s:%s) with %s? (y/N) :" %(
                match_key, match_value, pkg_id_str)
        else:
            msg = "Provision servers with %s? (y/N) :" %(pkg_id_str)
        user_input = raw_input(msg).lower()
        if user_input not in ["y", "yes"]:
            sys.exit()
    # end if
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    smgr_client_def.print_rest_response(resp)
# End of provision_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    provision_server(sys.argv[1:])
# End if __name__
