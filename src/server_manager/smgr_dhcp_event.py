#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_dhcp_event.py
   Author : Abhay Joshi
   Description : Small python script that gets called from DHCP server to
   notify of new IP address assignment or removal to hosts. This
   script takes that information and does update to the DB for the
   corresponding server.
"""
import argparse
import pdb
import sys
import pycurl

# The following 2 variable settings are important. These specify the IP address
# and port where the below DHCP hook, that gets called from dhcpd, will send
# REST request to server manager. The IP address field is replaced with host ip
# as part of install process. The port number, if changed from default value (9001)
# needs to be changed here too.
_DEF_SMGR_IP_ADDR = '__$IPADDRESS__'
_DEF_SMGR_PORT = 9001

IP_ADDRESS_KEY = "ip_address"
MAC_ADDRESS_KEY = "mac_address"


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]

    # Process the arguments
    parser = argparse.ArgumentParser(
        description=''' Add a server to server manager DB. ''',
    )
    parser.add_argument("action",
                        help="action is one of commit release or expiry.")
    parser.add_argument("server_ip",
                        help="IP address of the server.")
    parser.add_argument("server_mac",
                        help="mac_address of the server.")
    args = parser.parse_args()
    return args


def send_REST_request(ip, port, action, payload):
    try:
        url = "http://%s:%s/dhcp_event?action=%s" % (ip, port, action)
        headers = ["Content-Type:application/json"]

        conn = pycurl.Curl()
        conn.setopt(pycurl.TIMEOUT, 1)
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.POST, 1)
        conn.setopt(pycurl.POSTFIELDS, payload)
        conn.perform()
    except:
        return


def dhcp_event(args_str=None):
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }
    args = parse_arguments(args_str)
    if args.action.lower() == "commit":
        smgr_action = "add"
    else:
        smgr_action = "delete"
    server_def = '{"%s":"%s", "%s":"%s"}' \
                 % (IP_ADDRESS_KEY, args.server_ip, \
                    MAC_ADDRESS_KEY, args.server_mac)
    send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      smgr_action, server_def)
# End of dhcp_event

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    dhcp_event(sys.argv[1:])
# End if __name__
