#!/usr/bin/python
#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

import sys
import argparse
import ConfigParser
import commands
import itertools

#from provision_bgp import BgpProvisioner


class ExecControlProvisioner(object):

    def __init__(self, args_str=None):
        self._args = None
        if not args_str:
            args_str = ' '.join(sys.argv[1:])
        self._parse_args(args_str)

        api_server_port="8082"
        contrail_config_ip='127.0.0.1'
        host_ip_list= self._args.host_ip_list.split(",")
        host_name_list= self._args.host_name_list.split(",")
        if  self._args.mt_options != "None":
            multi_tenancy_list= self._args.mt_options.split(",")
            mt_options= "--admin_user %s --admin_password %s --admin_tenant_name %s" %(multi_tenancy_list[0],multi_tenancy_list[1],multi_tenancy_list[2])
        else :
            mt_options = ""
      
        for control_ip,hostname in itertools.izip(host_ip_list, host_name_list):
            output= commands.getstatusoutput('python /opt/contrail/utils/provision_control.py --api_server_ip %s --api_server_port %s --host_name %s  --host_ip %s --router_asn %s %s --oper add' %(contrail_config_ip, api_server_port, hostname, control_ip, self._args.router_asn, mt_options))
    # end __init__

    def _parse_args(self, args_str):
        '''
        Eg. python provision_control.py --host_name_list ['a3s30.contrail.juniper.net','a3s31.contrail.juniper.net']
                                        --host_ip_list ['10.1.1.1','10.1.1.2']
                                        --router_asn 64512
                                        --api_server_ip 127.0.0.1
                                        --api_server_port 8082
                                        --oper <add | del>
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument("-c", "--conf_file",
                                 help="Specify config file", metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str.split())

        defaults = {
            'router_asn': '64512',
            'api_server_ip': '127.0.0.1',
            'api_server_port': '8082',
            'oper': 'add',
        }

        if args.conf_file:
            config = ConfigParser.SafeConfigParser()
            config.read([args.conf_file])
            defaults.update(dict(config.items("DEFAULTS")))

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**defaults)

        parser.add_argument(
            "--host_name_list", help="List of hostname names of control-node")
        parser.add_argument("--host_ip_list", help="List of IP address of control-nodes")
        parser.add_argument(
            "--router_asn", help="AS Number the control-node is in")
        parser.add_argument(
            "--api_server_ip", help="IP address of api server")
        parser.add_argument(
            "--mt_options", help="Multi tenancy option")
        parser.add_argument("--api_server_port", help="Port of api server")
        parser.add_argument(
            "--oper", default='add',
            help="Provision operation to be done(add or del)")

        self._args = parser.parse_args(remaining_argv)

    # end _parse_args

# end class ControlProvisioner


def main(args_str=None):
    ExecControlProvisioner(args_str)
# end main

if __name__ == "__main__":
    main()
