#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : delete_config.py
   Author : Abhay Joshi
   Description : Small python script to delete configuration of a cluster from
                 server manager.It makes httpie calls to invoke the REST API to
                 server manager.
"""
import subprocess
import argparse
import pdb
import sys
import ConfigParser

_DEF_SMGR_CFG_FILE = './smgr.ini'
_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 8090


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("-c", "--config_file",
                             help=("Specify config file with the"
                                   "parameter values."),
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
        description=''' Delete a given cluster. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the server"
                              " manager is serving REST requests."))
    parser.add_argument("element",
                        help=("name of the config element to be"
                              " deleted (server/cluster/image/role)"))
    parser.add_argument("match_key",
                        help=("key to be used to identify"
                              " record to be deleted."))
    parser.add_argument("match_value",
                        help=("value to be used to"
                              " identify record to be deleted."))
    args = parser.parse_args(remaining_args)
    return args


def delete_config(args_str=None):
    args = parse_arguments(args_str)
    if (args.element.lower() not in ("cluster", "server", "role", "image")):
        print "Incorrect config element specified"
        exit()
    cmd = "http -b DELETE http://%s:%s/%s?%s=%s" \
        % (args.smgr_ip_addr, args.smgr_port,
           args.element, args.match_key, args.match_value)
    subprocess.call(cmd, shell=True)
# End of delete_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    delete_config(sys.argv[1:])
# End if __name__
