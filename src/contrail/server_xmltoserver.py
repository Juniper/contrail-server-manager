#!/usr/bin/env python

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
	smgr_server['id'] = server['hostname']
        network = {}
        network['interfaces'] = []
        interface = {}
        interface['ip_address'] = server['ipaddr'] + '/24'
        interface['mac_addres'] = server['mac']
        interface['name'] = 'eth1'
        interface['type'] = 'physical'
        ip_addr_list = server['ipaddr'].split('.')
        ip_addr_list[3] = '254'
        interface['default_gateway'] = '.'.join(ip_addr_list)
        interface['dhcp'] = True
        network['interfaces'].append(interface)
        network['management_interface'] = interface['name']
        contrail = {}
        contrail['control_data_interface'] = interface['name']
        tag = {}
        tag['datacenter'] = 'contrail_lab'
        tag['floor'] = 'floor_6'
        tag['row'] = 'row_' + server['row']
        tag['rack'] = 'rack_' + server['rack']
        tag['userid'] = server['reserved']
        smgr_server['network'] = network
        smgr_server['contrail'] = contrail
        smgr_server['tag'] = tag
        smgr_server['password'] = 'c0ntrail123'
        smgr_server['domain'] = 'contrail.juniper.net'
    	smgr_server['ipmi_address'] = server['ipmi']
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
