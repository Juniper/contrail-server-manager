#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : upload_image.py
   Author : Abhay Joshi
   Description : Small python script to upload image to server manager.
        It makes httpie calls to invoke the REST API to server manager.
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
        description=''' Add a image to server manager DB. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the"
                              " server manager is serving REST requests."))
    parser.add_argument("image_id",
                        help="Name of the new image")
    parser.add_argument("image_version",
                        help="version number of the image")
    parser.add_argument(
        "image_type",
        help="type of the image (fedora/centos/ubuntu/contrail-ubuntu-repo)")
    parser.add_argument("file_name",
                        help="complete path for the file")
    args = parser.parse_args(remaining_args)
    return args


def upload_image(args_str=None):
    args = parse_arguments(args_str)
    cmd = "http --timeout 300 -f PUT http://%s:%s/image/upload image_id=%s \
               image_version=\'%s\' image_type=%s file_name@%s" \
    % (args.smgr_ip_addr, args.smgr_port, args.image_id,
        args.image_version, args.image_type, args.file_name)
    subprocess.call(cmd, shell=True)
# End of upload_image

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    upload_image(sys.argv[1:])
# End if __name__
