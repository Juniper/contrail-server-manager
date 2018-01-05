#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
import string
import sys
import platform
import os
import pdb
import ast
import uuid
import subprocess
from netaddr import *
from server_mgr_err import *
from server_mgr_utils import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_db import ServerMgrDb as db

dhcp_template = string.Template("""
# ******************************************************************
# Cobbler managed dhcpd.conf file
#
# generated from cobbler dhcp.conf template ($date)
# Do NOT make changes to /etc/dhcpd.conf. Instead, make your changes
# in /etc/cobbler/dhcp.template, as /etc/dhcpd.conf will be
# overwritten.
#
# ******************************************************************

ddns-update-style interim;

allow booting;
allow bootp;

ignore client-updates;
set vendorclass = option vendor-class-identifier;

$__subnet_stanza__

$__host_stanza__

#for dhcp_tag in $dhcp_tags.keys():
    ## group could be subnet if your dhcp tags line up with your subnets
    ## or really any valid dhcpd.conf construct ... if you only use the
    ## default dhcp tag in cobbler, the group block can be deleted for a
    ## flat configuration
# group for Cobbler DHCP tag: $dhcp_tag
group {
        #for mac in $dhcp_tags[$dhcp_tag].keys():
            #set iface = $dhcp_tags[$dhcp_tag][$mac]
    host $iface.name {
        hardware ethernet $mac;
        #if $iface.ip_address:
        fixed-address $iface.ip_address;
        #end if
        #if $iface.hostname:
        option host-name "$iface.hostname";
        #end if
        #if $iface.netmask:
        option subnet-mask $iface.netmask;
        #end if
        #if $iface.gateway:
        option routers $iface.gateway;
        #end if
        filename "$iface.filename";
        ## Cobbler defaults to $next_server, but some users
        ## may like to use $iface.system.server for proxied setups
        next-server $next_server;
        ## next-server $iface.next_server;
    }
        #end for
}
#end for
""")

subnet_template = string.Template("""
subnet $__subnet_address__ netmask $__subnet_mask__ {
    option routers              $__subnet_gateway__;
    option subnet-mask          $__subnet_mask__;
    option domain-name-servers  $__dns_server_list__;
    option domain-search        $__search_domains_list__;
    option domain-name          $__subnet_domain__;
    option ntp-servers          $next_server;
    $__range_dynamic_bootp_line__
    default-lease-time          $__default_lease_time__;
    max-lease-time              $__max_lease_time__;
    next-server                 $next_server;
    filename                    "/pxelinux.0";

     on commit {
         set clip = binary-to-ascii(10, 8, ".", leased-address);
         set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "commit", clip, clhw);
         set ClientHost = pick-first-value(host-decl-name,
                                           option fqdn.hostname,
                                          option host-name,
                                           "none");
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "commit", clip, clhw, ClientHost);
     }

     on release {
         set clip = binary-to-ascii(10, 8, ".", leased-address);
         set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "release", clip, clhw);
         set ClientHost = pick-first-value(host-decl-name,
                                           option fqdn.hostname,
                                           option host-name,
                                           "none");
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "release", clip, clhw, ClientHost);
     }

     on expiry {
         set clip = binary-to-ascii(10, 8, ".", leased-address);
         set clhw = binary-to-ascii(16, 8, ":", substring(hardware, 1, 6));
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "expiry", clip, clhw);
         set ClientHost = pick-first-value(host-decl-name,
                                           option fqdn.hostname,
                                           option host-name,
                                           "none");
         execute("/opt/contrail/server_manager/smgr_dhcp_event.py", "expiry", clip, clhw, ClientHost);
     }
}
""")

host_template = string.Template("""
host $__host_fqdn__ {
    hardware ethernet $__host_mac__;
    fixed-address $__host_listen_ip__;
    option host-name "$__host_name__";
    filename "/pxelinux.0";
    option ntp-servers $next_server;
    next-server $next_server;
}
""")

_DEF_SMGR_IP = '__$IPADDRESS__'
_DEF_SMGR_MAC = '__$MACADDRESS__'
_DEF_SMGR_FQDN = '__$HOSTFQDN__'
_DEF_SMGR_HOST_NAME = '__$HOSTNAME__'

_DEF_SMGR_SUBNET_ADDRESS = '__$SUBNETADDRESS__'
_DEF_SMGR_SUBNET_GATEWAY = '__$SUBNETGATEWAY__'
_DEF_SMGR_SUBNET_MASK = '__$SUBNETMASK__'
_DEF_SMGR_DOMAIN = '__$DOMAIN__'

smgr_subnet_config = {
    "subnet_address": _DEF_SMGR_SUBNET_ADDRESS,
    "subnet_mask": _DEF_SMGR_SUBNET_MASK,
    "subnet_gateway": _DEF_SMGR_SUBNET_GATEWAY,
    "subnet_domain": _DEF_SMGR_DOMAIN,
    "dns_server_list": [_DEF_SMGR_IP],
    "search_domains_list": [_DEF_SMGR_DOMAIN],
    "default_lease_time": 21600,
    "max_lease_time": 43200
}

class DHCPTemplateGenerator:

    # We auto add the DHCP subnet for the subnet that SM IP belongs to
    # This means the subnet is auto added to the cobbler dhcp template if user doesn't add it automatically

    def __init__(self, server_db, smgr_config=None):
        ''' Constructor '''
        self._serverDb = server_db
        if smgr_config and isinstance(smgr_config,dict):
            for k in smgr_config.keys():
                smgr_host_config[k] = smgr_config[k]
            self._serverDb.add_dhcp_host(smgr_host_config)
        self._serverDb.add_dhcp_subnet(smgr_subnet_config)

    def get_subnet_stanza(self):
        subnets_stanza = ""
        subnets = self._serverDb.get_dhcp_subnet()
        for dhcp_subnet in subnets:
            if "dhcp_range" in dhcp_subnet and dhcp_subnet["dhcp_range"] and len(dhcp_subnet["dhcp_range"])==2:
                range_dynamic_bootp_line = "range dynamic-bootp        " + \
                    dhcp_subnet["dhcp_range"][0] + " " + dhcp_subnet["dhcp_range"][1] + ";"
            else:
                range_dynamic_bootp_line = ""
            dhcp_subnet['search_domains_list'] = [str("\""+str(x)+"\"") for x in ast.literal_eval(dhcp_subnet['search_domains_list'])]
            dhcp_subnet['subnet_domain'] = str("\"" + dhcp_subnet['subnet_domain'] + "\"")
            subnet_stanza = subnet_template.safe_substitute({
                '__subnet_address__': dhcp_subnet['subnet_address'],
                '__subnet_mask__': dhcp_subnet['subnet_mask'],
                '__subnet_gateway__': dhcp_subnet['subnet_gateway'],
                '__subnet_domain__': dhcp_subnet['subnet_domain'],
                '__dns_server_list__': ", ".join(ast.literal_eval(dhcp_subnet['dns_server_list'])),
                '__search_domains_list__': ", ".join(dhcp_subnet['search_domains_list']),
                '__default_lease_time__': dhcp_subnet['default_lease_time'],
                '__max_lease_time__': dhcp_subnet['max_lease_time'],
                '__range_dynamic_bootp_line__': range_dynamic_bootp_line
            })
            subnets_stanza += subnet_stanza + "\n"
        return subnets_stanza

    def get_hosts_stanza(self):
        hosts_stanza = ""
        hosts = self._serverDb.get_dhcp_host()
        for dhcp_host in hosts:
            host_stanza = host_template.safe_substitute({
                '__host_fqdn__': dhcp_host['host_fqdn'],
                '__host_mac__': dhcp_host['mac_address'],
                '__host_name__': dhcp_host['host_name'],
                '__host_listen_ip__': dhcp_host['ip_address']
            })
            hosts_stanza += host_stanza + "\n"
        return hosts_stanza

    def generate_dhcp_template(self):
        try:
            subnets_stanza = ""
            hosts_stanza = ""

            subnets_stanza = self.get_subnet_stanza()
            hosts_stanza = self.get_hosts_stanza()
            dhcp_template_config = dhcp_template.safe_substitute({
                '__subnet_stanza__' : subnets_stanza,
                '__host_stanza__' : hosts_stanza
            })

            dhcp_template_file = open('/etc/cobbler/dhcp.template', 'w+')
            dhcp_template_file.write(dhcp_template_config)
            dhcp_template_file.close()

        except Exception as e:
            raise e

