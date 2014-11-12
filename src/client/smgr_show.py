#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_show.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   get server manager configuration objects.
   Objects can be cluster, server, or image.
   An optional parameter details is used to indicate if user
   wants to fetch details of the object.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import ConfigParser
import smgr_client_def
import json
import urllib
from smgr_monitoring import ServerMgrIPMIQuerying

mon_querying_obj = ServerMgrIPMIQuerying()

def parse_arguments():
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Show a Server Manager object'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Show a Server Manager object''',
            prog="server-manager show"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    subparsers = parser.add_subparsers(title='objects',
                                       description='valid objects',
                                       help='help for object')

    # Subparser for server show
    parser_server = subparsers.add_parser(
        "server",help='Show server')
    group = parser_server.add_mutually_exclusive_group()
    group.add_argument("--server_id",
                        help=("server id for server"))
    group.add_argument("--mac",
                        help=("mac address for server"))
    group.add_argument("--ip",
                        help=("ip address for server"))
    group.add_argument("--cluster_id",
                        help=("cluster id for server(s)"))
    group.add_argument("--tag",
                        help=("tag values for the server"
                              "in t1=v1,t2=v2,... format"))
    group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    group.add_argument("--discovered",
                        help=("flag to get list of "
                              "newly discovered server(s)"))
    server_select_group = parser_server.add_mutually_exclusive_group()
    server_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    server_select_group.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_server.set_defaults(func=show_server)

    # Subparser for cluster show
    parser_cluster = subparsers.add_parser(
        "cluster", help='Show cluster')
    cluster_group = parser_cluster.add_mutually_exclusive_group()
    cluster_group.add_argument("--cluster_id",
                        help=("cluster id for cluster"))
    cluster_group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    cluster_select_group = parser_cluster.add_mutually_exclusive_group()
    cluster_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    cluster_select_group.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_cluster.set_defaults(func=show_cluster)

    # Subparser for image show
    parser_image = subparsers.add_parser(
        "image", help='Show image')
    image_group = parser_image.add_mutually_exclusive_group()
    image_group.add_argument("--image_id",
                        help=("image id for image"))
    image_group.add_argument("--where",
                       help=("sql where statement in quotation marks"))
    image_select_group = parser_image.add_mutually_exclusive_group()
    image_select_group.add_argument("--select",
                               help=("sql select statement in quotation marks"))
    image_select_group.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_image.set_defaults(func=show_image)

    # Subparser for all show
    parser_all = subparsers.add_parser(
        "all", help='Show all configuration (servers, clusters, images, tags)')
    parser_all.add_argument(
        "--detail", "-d", action='store_true',
        help="Flag to indicate if details are requested")
    parser_all.set_defaults(func=show_all)

    # Subparser for tags show
    parser_tag = subparsers.add_parser(
        "tag", help='Show list of server tags')
    parser_tag.set_defaults(func=show_tag)

    # Common subparser for Monitoring
    monitoring_parser = subparsers.add_parser("monitoring", help="Show all monitoring information options")
    monitoring_subparser = monitoring_parser.add_subparsers()

    # Monitoring Server Fan Speed
    fan_subparser = monitoring_subparser.add_parser("fan", help="Show fan speed")
    fan_options = fan_subparser.add_mutually_exclusive_group()
    fan_options.add_argument("--server_id",
                                    help=("server id for server"))
    fan_options.add_argument("--cluster_id",
                                help=("cluster id for cluster"))
    fan_options.add_argument("--tag", help=("tag values for the server"
                                               "in t1=v1,t2=v2,... format"))
    fan_options.add_argument("--where",
                                help=("sql where statement in quotation marks"))
    fan_subparser.set_defaults(func=mon_querying_obj.show_fan_details)

    # Monitoring Server CPU Temperature
    temp_subparser = monitoring_subparser.add_parser("temperature", help="Show server CPU Temperature")
    temp_options = temp_subparser.add_mutually_exclusive_group()
    temp_options.add_argument("--server_id",
                             help=("server id for server"))
    temp_options.add_argument("--cluster_id",
                             help=("cluster id for cluster"))
    temp_options.add_argument("--tag", help=("tag values for the server"
                                            "in t1=v1,t2=v2,... format"))
    temp_options.add_argument("--where",
                             help=("sql where statement in quotation marks"))
    temp_subparser.set_defaults(func=mon_querying_obj.show_temp_details)

    # Monitoring Server Power Consumption
    power_subparser = monitoring_subparser.add_parser("power", help="Show server power consumption")
    power_options = power_subparser.add_mutually_exclusive_group()
    power_options.add_argument("--server_id",
                             help=("server id for server"))
    power_options.add_argument("--cluster_id",
                             help=("cluster id for cluster"))
    power_options.add_argument("--tag", help=("tag values for the server"
                                            "in t1=v1,t2=v2,... format"))
    power_options.add_argument("--where",
                             help=("sql where statement in quotation marks"))
    power_subparser.set_defaults(func=mon_querying_obj.show_pwr_details)

    # Monitoring all Server Environment details
    mon_all_subparser = monitoring_subparser.add_parser("all", help="Show all server environment sensor values")
    mon_all_options = mon_all_subparser.add_mutually_exclusive_group()
    mon_all_options.add_argument("--server_id",
                             help=("server id for server"))
    mon_all_options.add_argument("--cluster_id",
                             help=("cluster id for cluster"))
    mon_all_options.add_argument("--tag", help=("tag values for the server"
                                            "in t1=v1,t2=v2,... format"))
    mon_all_options.add_argument("--where",
                             help=("sql where statement in quotation marks"))
    mon_all_subparser.set_defaults(func=mon_querying_obj.show_env_details)

    # Monitoring Configuration status
    mon_status_subparser = monitoring_subparser.add_parser("status", help="Show server monitoring status")
    mon_status_subparser.set_defaults(func=mon_querying_obj.show_mon_status)

    return parser
# end def parse_arguments

def send_REST_request(ip, port, object, match_key,
                      match_value, select, detail):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" % (ip, port, object)
        args_str = ''
        if select:
            args_str += "select" + "=" \
                + urllib.quote_plus(select) + "&"
        if match_key:
            args_str += urllib.quote_plus(match_key) + "=" \
                + urllib.quote_plus(match_value)
        if detail:
            args_str += "&detail"
        if args_str != '':
            url += "?" + args_str
        conn = pycurl.Curl()
        conn.setopt(pycurl.TIMEOUT, 3)
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.HTTPGET, 1)
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None
# end def send_REST_request

def show_server(args):
    rest_api_params = {}
    rest_api_params['object'] = 'server'
    rest_api_params['select'] = args.select
    if args.server_id:
        rest_api_params['match_key'] = 'id'
        rest_api_params['match_value'] = args.server_id
    elif args.mac:
        rest_api_params['match_key'] = 'mac_address'
        rest_api_params['match_value'] = args.mac
    elif args.ip:
        rest_api_params['match_key'] = 'ip_address'
        rest_api_params['match_value'] = args.ip
    elif args.cluster_id:
        rest_api_params['match_key'] = 'cluster_id'
        rest_api_params['match_value'] = args.cluster_id
    elif args.tag:
        rest_api_params['match_key'] = 'tag'
        rest_api_params['match_value'] = args.tag
    elif args.discovered:
        rest_api_params['match_key'] = 'discovered'
        rest_api_params['match_value'] = args.discovered
    elif args.where:
        rest_api_params['match_key'] = 'where'
        rest_api_params['match_value'] = args.where
    else:
        rest_api_params['match_key'] = None
        rest_api_params['match_value'] = None
    return rest_api_params
#end def show_server

def show_cluster(args):
    if args.cluster_id:
        match_key = 'id'
        match_value = args.cluster_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'cluster',
        'match_key' : match_key,
        'match_value' : match_value,
        'select' : args.select
    }
    return rest_api_params
#end def show_cluster

def show_image(args):
    if args.image_id:
        match_key = 'id'
        match_value = args.image_id
    elif args.where:
        match_key = 'where'
        match_value = args.where
    else:
        match_key = None
        match_value = None
    rest_api_params = {
        'object' : 'image',
        'match_key' : match_key,
        'match_value' : match_value,
        'select' : args.select
    }
    return rest_api_params
#end def show_image

def show_all(args):
    rest_api_params = {
        'object' : 'all',
        'match_key' : None,
        'match_value' : None,
        'select' : None
    }
    return rest_api_params
#end def show_all

def show_tag(args):
    rest_api_params = {
        'object' : 'tag',
        'match_key' : None,
        'match_value' : None,
        'select' : None
    }
    return rest_api_params
#end def show_all

def show_config(args_str=None):
    mon_query = False
    mon_rest_api_params = None
    parser = parse_arguments()
    args = parser.parse_args(args_str)
    if args.config_file:
        config_file = args.config_file
    else:
        config_file = smgr_client_def._DEF_SMGR_CFG_FILE
    # end args.config_file
    if hasattr(args, 'detail'):
        detail = args.detail
    else:
        detail = None
    try:
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        smgr_config = dict(config.items("SERVER-MANAGER"))
        smgr_ip = smgr_config.get("listen_ip_addr", None)
        if not smgr_ip:
            sys.exit(("listen_ip_addr missing in config file"
                      "%s" %config_file))
        smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
    except Exception as e:
        sys.exit("Exception: %s : Error reading config file %s" %(e.message, config_file))
    # end except
    rest_api_params = args.func(args)
    try:
        mon_config = dict(config.items("MONITORING"))
        query_engine_port = mon_config.get("ipmi_introspect_port", None)
    except ConfigParser.NoSectionError:
        if rest_api_params['object'] == "Monitor":
            sys.exit("Monitoring hasn't been configured. Cannot use this command.")
        else:
            pass
    except Exception as e:
        if rest_api_params['object'] == "Monitor":
            sys.exit("Monitoring hasn't been configured. Cannot use this command.")
        else:
            pass
    if rest_api_params['object'] == "Monitor" and smgr_ip:
        if rest_api_params['monitoring_value'] != "Status":
            mon_query = True
            mon_rest_api_params = dict(rest_api_params)
            rest_api_params = mon_querying_obj.get_wrapper_call_params(rest_api_params)
        else:
            mon_query = False
    else:
        mon_query = False
    resp = send_REST_request(smgr_ip, smgr_port,
                      rest_api_params['object'],
                      rest_api_params['match_key'],
                      rest_api_params['match_value'],
                      rest_api_params['select'],
                      detail)
    if mon_query:
        resp = mon_querying_obj.handle_smgr_response(resp, smgr_ip, query_engine_port, mon_rest_api_params)
    smgr_client_def.print_rest_response(resp)
# End of show_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    show_config(sys.argv[1:])
# End if __name__

