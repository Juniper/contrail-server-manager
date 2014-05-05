#!/usr/bin/python

import xmltodict
import json
import argparse
import cgitb
import sys


def convert_xml_to_json(input_file, output_file):
    server_file = open(input_file, "r") 
    original_server_file = server_file.read()
    servers_dict = xmltodict.parse(original_server_file)
    servers_list = servers_dict['servers']['server']
    smgr_server_dict = {}
    smgr_server_dict['server'] = []
    for server in servers_list:
    	smgr_server = {}
	smgr_server['server_id'] = server['hostname']
	smgr_server['mac'] = server['mac']
    	smgr_server['ip'] = server['ipaddr']
    	server_params = {}
    	server_params['ifname'] = 'eth1'
    	server_params['compute_non_mgmt_ip'] = ''
    	server_params['compute_non_mgmt_gway'] = ''
    	smgr_server['server_params'] = server_params
    	smgr_server['power_address'] = server['ipmi']
    	smgr_server_dict['server'].append(smgr_server)

    servers_jdump = json.dumps(smgr_server_dict, indent=4)
    servers_list_file = open(output_file, 'w')
    servers_list_file.write(servers_jdump)
    servers_list_file.close()
# end convert_xml_to_json

def parse_args(args_str):
    conf_parser = argparse.ArgumentParser(add_help=False)
    args, remaining_argv = conf_parser.parse_known_args(args_str.split())
    parser = argparse.ArgumentParser(
        # Inherit options from config_parser
        parents=[conf_parser],
        # script description with -h/--help
        description=__doc__,
        # Don't mess with format of description
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    defaults = {
        'input_file': 'server.xml',
        'output_file': 'server.json',
        }
    parser.set_defaults(**defaults)
    parser.add_argument(
        "--input_file", "-i", help="input xml file")
    parser.add_argument(
        "--output_file", "-o", help="output json file")
    args = parser.parse_args(remaining_argv)       
    return args
# end parse_args

def main(args_str=None):
    if not args_str:
        args_str = ' '.join(sys.argv[1:])
    args = parse_args(args_str)
    convert_xml_to_json(args.input_file, args.output_file)
# end main

if __name__ == '__main__':
    cgitb.enable(format='text')
    main()
