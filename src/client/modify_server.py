#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : modify_server.py
   Author : Abhay Joshi
   Description : Small python script to add server to server manager.
                 It makes httpie calls to invoke the REST API to
                 server manager.
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


def get_role_params_from_user():
    params = {}
    while True:
        param_name = raw_input("Param Name:")
        if not param_name:
            break
        param_value = raw_input("Param Value:")
        params[param_name] = param_value
    return params


def get_role_details_from_user():
    role = {}
    role_id = raw_input("Node Name (Press enter to end):")
    if not role_id:
        return None
    role['role_id'] = role_id
    role['role_params'] = get_role_params_from_user()
    return role


def get_server_details_from_user(server_id):
    """ Only to be changed parameters should be specified here """
    server = {}
    server['server_id'] = server_id
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
    cluster_id = raw_input("Name of cluster where server is to be added:")
    if cluster_id:
        server['cluster_id'] = cluster_id
    roles = []
    while True:
        role = get_role_details_from_user()
        if not role:
            break
        roles.append(role)
    # end while True
    if roles:
        server['roles'] = roles
    return server


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("-c", "--config_file",
                             help=("Specify config file with"
                                   " the parameter values."),
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
        description=''' Add a server to server manager DB. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the server"
                              " manager is serving REST requests."))
    parser.add_argument("-f", "--file_name",
                        help=("Name of the file cotaining json"
                              " description of the server"), metavar="FILE")
    args = parser.parse_args(remaining_args)
    return args


def modify_server(args_str=None):
    args = parse_arguments(args_str)
    if args.file_name:
        file_name = args.file_name
    else:
        server_id = raw_input("Name of server to be modified:")
        if not server_id:
            return
        print "****** Current Server Information ***********"
        cmd = "http -b --timeout 240 GET http://%s:%s/server?server_id=%s" \
            % (args.smgr_ip_addr,
               args.smgr_port,
               server_id)
        subprocess.call(cmd, shell=True)
        server_def = get_server_details_from_user(server_id)
        temp = tempfile.NamedTemporaryFile()
        file_name = temp.name
        temp.seek(0)
        json.dump(server_def, temp)
        temp.flush()
    cmd = "http -b --timeout 240 POST http://%s:%s/server < %s" \
        % (args.smgr_ip_addr,
           args.smgr_port,
           file_name)
    subprocess.call(cmd, shell=True)
# End of modify_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    modify_server(sys.argv[1:])
# End if __name__
