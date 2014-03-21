#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : add_cluster.py
   Author : Abhay Joshi
   Description : Small python script to add cluster to server manager.
        It makes httpie calls to invoke the REST API to server manager.
"""
import subprocess
import argparse
import pdb
import tempfile
import json
import sys
import ConfigParser

_DEF_SMGR_CFG_FILE = './smgr.ini'
_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 9001


def get_role_details_from_user():
    role = {}
    # Additional role table parameters would be added here.
    role_id = raw_input("Node Name (Press enter to end) : ")
    if not role_id:
        return None
    role['role_id'] = role_id
    return role


def get_role_params_from_user():
    params = {}
    while True:
        param_name = raw_input("Param Name : ")
        if not param_name:
            break
        param_value = raw_input("Param Value : ")
        params[param_name] = param_value
    return params


def get_server_role_details_from_user():
    role = {}
    role_id = raw_input("Node Name (Press enter to end) : ")
    if not role_id:
        return None
    role['role_id'] = role_id
    role['role_params'] = get_role_params_from_user()
    return role


def get_image_details_from_user():
    image = {}
    image_id = raw_input("Image Id (Press enter to end) : ")
    if not image_id:
        return image
    image['image_id'] = image_id
    image_version = raw_input("Image version : ")
    image['image_version'] = image_version
    image_type = raw_input("Image type : ")
    image['image_type'] = image_type
    image_path = raw_input("Image path : ")
    image['image_path'] = image_path
    return image


def get_server_details_from_user():
    server = {}
    server_id = raw_input("Server Name (Press enter to end) : ")
    if not server_id:
        return None
    server['name'] = server_id
    server_mac = raw_input("Server MAC Address : ")
    if not server_mac:
        return None
    server['mac'] = server_mac
    server_passwd = raw_input("Server password : ")
    server['passwd'] = server_passwd
    server_dhcp = raw_input("DHCP/STATIC? : ")
    server['dhcp'] = server_dhcp
    if server_dhcp.lower() == "dhcp":
        server['ip'] = ''
        server['mask'] = ''
        server['gway'] = ''
    else:
        server_ip = raw_input("Server IP Address : ")
        server['ip'] = server_ip
        server_mask = raw_input("Server network mask : ")
        server['mask'] = server_mask
        server_gway = raw_input("Server gateway : ")
        server['gway'] = server_gway
        server_domain = raw_input("Server domain : ")
        server['domain'] = server_domain
    roles = []
    while True:
        role = get_server_role_details_from_user()
        if not role:
            break
        roles.append(role)
    # end while True
    server['roles'] = roles
    return server


def get_cluster_details_from_user():
    cluster = {}
    cluster_id = raw_input("Cluster Name : ")
    if not cluster_id:
        return {}
    cluster['name'] = cluster_id
    return cluster


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("-c", "--config_file",
                             help=("Specify config file "
                                   "with the parameter values."),
                             metavar="FILE")
    cargs, remaining_args = conf_parser.parse_known_args(args_str)
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }

    if cargs.config_file:
        config_file = cargs.config_file
    else:
        config_file = _DEF_SMGR_CFG_FILE

    config = ConfigParser.SafeConfigParser()
    config.read([config_file])
    for key in serverMgrCfg.keys():
        serverMgrCfg[key] = dict(config.items("SERVER-MANAGER"))[key]
    # Now Process rest of the arguments
    parser = argparse.ArgumentParser(
        description=''' Add a cluster to server manager DB. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("element",
                        help=("description of jason file about what element"
                              " to add (all/cluster/server/image/role)"))
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the server "
                              "manager is serving REST requests."))
    parser.add_argument("-f", "--file_name",
                        help=("Optional file cotaining json "
                              "description of the element(s)"),
                        metavar="FILE")
    args = parser.parse_args(remaining_args)
    return args


def add_config(args_str=None):
    args = parse_arguments(args_str)
    if (args.element.lower() not in
       ("all", "cluster", "server", "image", "role")):
        print "Incorrect element value"
        return
    if args.file_name:
        file_name = args.file_name
    else:
        element = args.element.lower()
        if element == "cluster":
            json_def = get_cluster_details_from_user()
        elif element == "server":
            json_def = get_server_details_from_user()
        elif element == "image":
            json_def = get_image_details_from_user()
        elif element == "role":
            json_def = get_role_details_from_user()
        else:
            print "Manual config add possible for individual elements only"
            return
        temp = tempfile.NamedTemporaryFile()
        file_name = temp.name
        temp.seek(0)
        json.dump(json_def, temp)
        temp.flush()
    cmd = "http -b --timeout 240 PUT http://%s:%s/%s < %s" \
        % (args.smgr_ip_addr,
           args.smgr_port,
           args.element,
           file_name)
    subprocess.call(cmd, shell=True)
# End of add_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    add_config(sys.argv[1:])
# End if __name__
