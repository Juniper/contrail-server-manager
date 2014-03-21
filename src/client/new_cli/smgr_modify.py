#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_modify.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   modify server manager configuration objects.
   Objects can be vns, cluster, server, or image.
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

# Below array of dictionary's is used by create_payload
# function to create payload when user choses to input
# object parameter values manually instead of providing a
# json file.
object_dict = {
    "vns" : OrderedDict ([
        ("vns_id", "vns_id for vns to be modfied"),
        ("vns_params", OrderedDict ([
             ("router_asn", "Router asn value"),
             ("mask", "Subnet mask"),
             ("gway", "Default gateway for servers in this cluster"),
             ("passwd", "Default password for servers in this cluster"),
             ("domain", "Default domain for servers in this cluster"),
             ("database_dir", "home directory for cassandra"),
             ("db_initial_token", "initial database token"),
             ("openstack_mgmt_ip", "openstack management ip"),
             ("use_certs", "whether to use certificates for auth (True/False)"),
             ("multi_tenancy", "Openstack multitenancy (True/False)"),
             ("service_token", "Service token for openstack access"),
             ("ks_user", "Keystone user name"),
             ("ks_passwd", "keystone password"),
             ("ks_tenant", "keystone tenant name"),
             ("openstack_passwd", "open stack password"),
             ("analytics_data_ttl", "analytics data TTL")]))
    ]),
    "server": OrderedDict ([ 
        ("server_id", "server id of the server to be modified"),
        ("ip", "server ip address"),
        ("roles", "comma-separated list of roles for this server"),
        ("server_params", OrderedDict([
            ("ifname", "Ethernet Interface name"),
            ("compute_non_mgmt_ip", "compute node non mgmt ip (default none)"),
            ("compute_non_mgmt_gway", "compute node non mgmt gway (default none)")])),
        ("mask", "subnet mask (default use value from vns table)"),
        ("gway", "gateway (default use value from vns table)"),
        ("domain", "domain name (default use value from vns table)"),
        ("passwd", "root password (default use value from vns table)"),
    ]),
    "image" : OrderedDict ([
        ("image_id", "Image id of image to be modified"),
        ("image_version", "Specify version for this image"),
    ]),
    "cluster" : OrderedDict ([
        ("cluster_id", "cluster id of cluster to be modified"),
    ])
}

def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]

    # Process the arguments
    parser = argparse.ArgumentParser(
        description='''Modify a Server Manager object''',
    )
    parser.add_argument("--smgr_ip", "-i",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port", "-p",
                        help="server manager listening port number")
    subparsers = parser.add_subparsers(title='subcommands',
                                       description='valid subcommands',
                                       help='help for subcommand',
                                       dest='object')

    # Subparser for server modify
    parser_server = subparsers.add_parser(
        "server",help='Modify server')
    parser_server.add_argument(
        "--file_name", "-f",
        help="json file containing server param values")

    # Subparser for vns modify
    parser_vns = subparsers.add_parser(
        "vns", help='Modify vns')
    parser_vns.add_argument(
        "--file_name", "-f",
        help="json file containing vns param values")

    # Subparser for cluster modify
    parser_cluster = subparsers.add_parser(
        "cluster", help='Modify cluster')
    parser_cluster.add_argument(
        "--file_name", "-f",
        help="json file containing cluster param values")

    # Subparser for image modify
    parser_image = subparsers.add_parser(
        "image", help='Modify image')
    parser_image.add_argument(
        "--file_name", "-f",
        help="json file containing image param values")

    args = parser.parse_args()
    return args

def send_REST_request(ip, port, object, payload):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" %(
            ip, port, object)
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

# Function to accept parameters from user and then build payload to be
# sent with REST API request for creating the object.
def create_payload(object):
    payload = {}
    objects = []
    while True:
        temp_dict = {}
        fields_dict = object_dict[object]
        for key in fields_dict:
            value = fields_dict[key]
            if (key != (object+"_params")):
                msg = key
                if value:
                    msg += " (%s) " %(value)
                msg += ": "
                user_input = raw_input(msg)
                if user_input:
                    # Special case for roles -
                    # store as a list
                    if key == "roles":
                        temp_dict[key] = user_input.strip().split(",")
                    else:
                        temp_dict[key] = user_input
            else:
                param_dict = {}
                for param in value:
                    pvalue = value[param]
                    msg = param
                    if pvalue:
                        msg += " (%s) " %(pvalue)
                    msg += ": "
                    user_input = raw_input(msg)
                    if user_input:
                        param_dict[param] = user_input
                if param_dict:
                    temp_dict[key] = param_dict
            # End if (key != (object+"_params"))
        # End for key, value in fields_dict 
        objects.append(temp_dict)
        choice = raw_input("More %s(s) to input? (y/N)" %(object))
        if ((not choice) or
            (choice.lower() != "y")):
            break;
    # End while True
    payload[object] = objects
    return payload
# End create_payload

def modify_config(args_str=None):
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
    if args.file_name:
        payload = json.load(open(args.file_name))
    else:
        # Accept parameters and construct json.
        payload = create_payload(object)
    
    resp = send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      object, payload)
    print resp
# End of modify_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    modify_config(sys.argv[1:])
# End if __name__
