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
            description='''Reboot given server(s). Servers can be
                           specified by providing match condition
                           to pick servers from the database.'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Reboot given server(s). Servers can be
                           specified by providing match condition
                           to pick servers from the database.''',
            prog="server-manager restart"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--server_id",
                        help=("server id for the server to be restarted"))
    group.add_argument("--cluster_id",
                        help=("cluster id for the server(s) to be restarted"))
    group.add_argument("--tag",
                        help=("tag values for the servers to be restarted"
                              "in t1=v1,t2=v2,... format"))
    group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    parser.add_argument("--net_boot", "-n", action="store_true",
                        help=("optional parameter to indicate"
                             " if server should be netbooted."))
    parser.add_argument("--no_confirm", "-F", action="store_true",
                        help=("flag to bypass confirmation message, "
                              "default = do not bypass"))
    args = parser.parse_args(args_str)
    return args
# end def parse_arguments

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
    match_key = None
    match_param = None
    payload = {}
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
    else:
        pass

    if match_key:
        payload[match_key] = match_value
    if (args.net_boot):
        payload['net_boot'] = "y"

    if (not args.no_confirm):
        msg = "Restart servers (%s:%s)? (y/N) :" %(
            match_key, match_value)
        user_input = raw_input(msg).lower()
        if user_input not in ["y", "yes"]:
            sys.exit()
    # end if
 
    resp = send_REST_request(smgr_ip, smgr_port,
                             payload)
    print resp
# End of restart_server

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    restart_server(sys.argv[1:])
# End if __name__
