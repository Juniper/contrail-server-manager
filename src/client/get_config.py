#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : get_config.py
   Author : Abhay Joshi
   Description : Small python script to get configuration from server manager.
                 It makes httpie calls to invoke the
                 REST API to server manager.
"""
import subprocess
import argparse
import pdb
import sys
import ConfigParser

_DEF_SMGR_CFG_FILE = './smgr.ini'
_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 9001


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("-c", "--config_file",
                             help=("Specify config file with"
                                   " the parameter values."), metavar="FILE")
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
        description=''' Get configuration elements from the server. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("element",
                        help=("Config element for which config is requested"
                              " (all/server/cluster/image/role)"))
    parser.add_argument("--match_key",
                        help="key to be used for filtering config provided.")
    parser.add_argument("--match_value",
                        help="value to be used for filtering config provided.")
    parser.add_argument("--detail", action="store_true",
                        help="flag to state if config details are requested")
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the server"
                              " manager is serving REST requests."))
    args = parser.parse_args(remaining_args)
    return args


def get_config(args_str=None):
    args = parse_arguments(args_str)
    if (args.element.lower() not in ("all", "cluster", "server", "role",
       "image")):
        print "Incorrect config element specified"
        exit()
    cmd = "http -b GET http://%s:%s/%s" \
        % (args.smgr_ip_addr, args.smgr_port, args.element)
    param = "?"
    if (args.match_key and args.match_value):
        cmd += '%s%s=%s' % (param, args.match_key, args.match_value)
        param = "\&"
    if args.detail:
        cmd += '%sdetail' % (param)
    subprocess.call(cmd, shell=True)
# End of get_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    get_config(sys.argv[1:])
# End if __name__
