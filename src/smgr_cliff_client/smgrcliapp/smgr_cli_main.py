#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_cli.py
   Author : Nitish Krishna
   Description : This file provides implementation of Server Manager CLI as part of Cliff framework
"""
import logging
import sys
import os
from StringIO import StringIO
import pycurl
import json
import urllib
import smgr_client_def
import argparse
import ConfigParser
import getopt
from cliff.app import App
from commandmanager import CommandManager
from cliff.help import HelpAction
from prettytable import PrettyTable
import ast


class ServerManagerCLI(App):
    log = logging.getLogger(__name__)
    smgr_port = None
    smgr_ip = None
    default_config = dict()
    defaults_file = None

    def __init__(self):
        super(ServerManagerCLI, self).__init__(
            description='Server Manager CLI',
            version='0.1',
            command_manager=CommandManager('smgrcli.app')
        )
        self.command_manager.add_command_group('smgr.cli.common')

    def build_option_parser(self, description, version,
                            argparse_kwargs=None):
        argparse_kwargs = argparse_kwargs or {}
        parser = argparse.ArgumentParser(
            description=description,
            add_help=False,
            **argparse_kwargs
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s {0}'.format(version),
        )
        parser.add_argument(
            '-v', '--verbose',
            action='count',
            dest='verbose_level',
            default=self.DEFAULT_VERBOSE_LEVEL,
            help='Increase verbosity of output. Can be repeated.',
        )
        parser.add_argument(
            '--log-file',
            action='store',
            default=None,
            help='Specify a file to log output. Disabled by default.',
        )
        parser.add_argument(
            '-q', '--quiet',
            action='store_const',
            dest='verbose_level',
            const=0,
            help='suppress output except warnings and errors',
        )
        if self.deferred_help:
            parser.add_argument(
                '-h', '--help',
                dest='deferred_help',
                action='store_true',
                help="show this help message and exit",
            )
        else:
            parser.add_argument(
                '-h', '--help',
                action=HelpAction,
                nargs=0,
                default=self,  # tricky
                help="show this help message and exit",
            )
        parser.add_argument(
            '--debug',
            default=False,
            action='store_true',
            help='show tracebacks on errors',
        )
        parser.add_argument(
            '--smgr_ip',
            default=None,
            help='The IP Address on which server-manager is listening.'
                 'Default is 127.0.0.1'
        )
        parser.add_argument(
            '--smgr_port',
            default=None,
            help='The port on which server-manager is listening.'
                 'Default is 9001'
        )
        parser.add_argument(
            '--defaults_file',
            default='/tmp/sm-client-config.ini',
            help='The ini file that specifies the default parameter values for Objects like Cluster, Server, etc.'
                 'Default is /tmp/sm-client-config.ini'
        )
        return parser

    def initialize_app(self, argv):
        self.log.debug('initialize_app')
        self.defaults_file = getattr(self.options, "defaults_file", "/tmp/sm-client-config.ini")

        try:
            config = ConfigParser.SafeConfigParser()
            config.read([self.defaults_file])
            self.default_config["server"] = dict(config.items("SERVER"))
            self.default_config["cluster"] = dict(config.items("CLUSTER"))
            self.default_config["tag"] = dict(config.items("TAG"))
            env_smgr_ip = os.environ.get('SMGR_IP')
            if getattr(self.options, "smgr_ip", None):
                self.smgr_ip = getattr(self.options, "smgr_ip", None)
            elif env_smgr_ip:
                self.smgr_ip = env_smgr_ip
            else:
                self.report_missing_config("smgr_ip")

            env_smgr_port = os.environ.get('SMGR_PORT')
            if getattr(self.options, "smgr_port", None):
                self.smgr_port = getattr(self.options, "smgr_port", None)
            elif env_smgr_port:
                self.smgr_port = env_smgr_port
            else:
                self.report_missing_config("smgr_port")
                
        except Exception as e:
            self.stdout.write("Exception: %s : Error reading config file %s" % (e.message, self.defaults_file))

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('got an error: %s', err)

    def interact(self):
        # Defer importing .interactive as cmd2 is a slow import
        from interactive import SmgrInteractiveApp
        self.interpreter = SmgrInteractiveApp(self, self.command_manager, None, None)
        self.interpreter.cmdloop()
        return 0

    def report_missing_config(self, param):
        msg = "ERROR: You must provide a config parameter " + str(param) + " via either --" + str(param) + \
              " or env[" + str(param).upper() + "]\n"
        self.stdout.write(msg)
        sys.exit(0)

    def get_smgr_config(self):
        return {
            "smgr_ip": self.smgr_ip,
            "smgr_port": self.smgr_port
        }

    def get_default_config(self):
        return self.default_config

    def send_REST_request(self, ip, port, obj=None, rest_api_params=None,
                          payload=None, match_key=None, match_value=None, detail=False, force=False, method="PUT"):
        try:
            args_str = ""
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = ""
            if method == "PUT" and obj:
                url = "http://%s:%s/%s" % (
                    ip, port, obj)
            elif method == "GET":
                if rest_api_params:
                    url = "http://%s:%s/%s" % (ip, port, rest_api_params['object'])
                    if rest_api_params["select"]:
                        args_str += "select" + "=" \
                                    + urllib.quote_plus(rest_api_params["select"]) + "&"
                    if rest_api_params["match_key"] and rest_api_params["match_value"]:
                        args_str += urllib.quote_plus(rest_api_params["match_key"]) + "=" + \
                                    urllib.quote_plus(rest_api_params["match_value"])

                elif obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += match_key + "=" + match_value
                if force:
                    args_str += "&force"
                if detail:
                    args_str += "&detail"
                if args_str != '':
                    url += "?" + args_str
            elif method == "DELETE":
                if obj:
                    url = "http://%s:%s/%s" % (ip, port, obj)
                if match_key and match_value:
                    args_str += match_key + "=" + match_value
                if force:
                    args_str += "&force"
                if args_str != '':
                    url += "?" + args_str
            else:
                return None
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, url)
            conn.setopt(pycurl.HTTPHEADER, headers)
            if method == "PUT" and payload and obj != "image/upload":
                conn.setopt(pycurl.POST, 1)
                conn.setopt(pycurl.POSTFIELDS, '%s' % json.dumps(payload))
                conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
            elif method == 'PUT' and payload and obj == "image/upload":
                conn.setopt(pycurl.POST, 1)
                conn.setopt(pycurl.HTTPPOST, payload.items())
                conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
            elif method == "GET":
                conn.setopt(pycurl.HTTPGET, 1)
            elif method == "DELETE":
                conn.setopt(pycurl.CUSTOMREQUEST, "delete")
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.TIMEOUT, 30)
            conn.perform()
            return response.getvalue()
        except Exception as e:
            return "Error: " + str(e)
            # end def send_REST_request

    def convert_json_to_list(self, obj, json_resp):
        return_list = list()
        data_dict = dict(json_resp)
        if len(data_dict.keys()) == 1 and obj in['server', 'cluster', 'image', 'mac', 'ip']:
            key, value = data_dict.popitem()
            dict_list = eval(str(value))
            for d in dict_list:
                d = dict(d)
                id_key, id_value = d.popitem()
                return_list.append(id_value)
        elif obj == 'tag':
            for key in data_dict:
                return_list.append(data_dict[key])
        return return_list

    def convert_json_to_table(self, obj, json_resp, select_item=None):
        if obj != "monitoring" and obj != "inventory":
            data_dict = dict(ast.literal_eval(str(json_resp)))
            return_table = None
            if len(data_dict.keys()) == 1:
                obj_type, obj_value = data_dict.popitem()
                dict_list = eval(str(obj_value))
                if obj_type == "server":
                    return_table = PrettyTable(["id", "ip_address", "mac_address"])
                    return_table.align["id"] = "l"
                    for d in dict_list:
                        d = dict(d)
                        return_table.add_row([d["id"], d["ip_address"], d["mac_address"]])
                elif obj_type == "cluster" or obj_type == "image":
                    return_table = PrettyTable(["id"])
                    return_table.align["id"] = "l"
                    for d in dict_list:
                        d = dict(d)
                        return_table.add_row([d["id"]])
                elif obj_type == "tag":
                    return_table = PrettyTable(["Tag No.", "Tag"])
                    return_table.align["Tag"] = "l"
                    for key in data_dict:
                        if str(key).startswith("tag"):
                            tag_no = key[3]
                            tag = data_dict[key]
                            return_table.add_row([tag_no, tag])
        else:
            dict_list = list(ast.literal_eval(json_resp))
            server_dict = dict(dict_list[0])
            data_dict = None
            error_msg = "Incorrect Select clause chosen"

            if "ServerMonitoringInfo" in server_dict and select_item in server_dict["ServerMonitoringInfo"]:
                data_item = server_dict["ServerMonitoringInfo"][select_item]
                if isinstance(data_item, dict):
                    data_dict = data_item
                elif isinstance(data_item, list):
                    data_dict = data_item[0]
                else:
                    return error_msg
            elif "ServerInventoryInfo" in server_dict and select_item in server_dict["ServerInventoryInfo"]:
                data_item = server_dict["ServerInventoryInfo"][select_item]
                if isinstance(data_item, dict):
                    data_dict = data_item
                elif isinstance(data_item, list):
                    data_dict = data_item[0]
                else:
                    return error_msg
            else:
                return error_msg
            key_list = list()
            key_list.append("server_name")
            for key, val in sorted(dict(data_dict).iteritems()):
                key_list.append(key)
            return_table = PrettyTable(key_list)
            for server_dict in dict_list:
                server_dict = dict(server_dict)
                server_id = server_dict["name"]
                if select_item in ["disk_usage_stats", "disk_usage_totals", "network_info_stats", "network_info_totals",
                                   "sensor_stats"] and "ServerMonitoringInfo" in server_dict:
                    data_dict_list = list(server_dict["ServerMonitoringInfo"][select_item])
                    for data_dict in data_dict_list:
                        data_dict = dict(data_dict)
                        val_list = list()
                        val_list.append(server_id)
                        for key, val in sorted(data_dict.iteritems()):
                            val_list.append(val)
                        return_table.add_row(val_list)
                elif select_item in ["chassis_state", "resource_info_stats"] and "ServerMonitoringInfo" in server_dict:
                    data_dict = dict(server_dict["ServerMonitoringInfo"][select_item])
                    val_list = list()
                    val_list.append(server_id)
                    for key, val in sorted(data_dict.iteritems()):
                        val_list.append(val)
                    return_table.add_row(val_list)
                elif select_item in ["cpu_info_state", "mem_state", "eth_controller_state"] \
                        and "ServerInventoryInfo" in server_dict:
                    data_dict = dict(server_dict["ServerInventoryInfo"][select_item])
                    val_list = list()
                    val_list.append(server_id)
                    for key, val in sorted(data_dict.iteritems()):
                        val_list.append(val)
                    return_table.add_row(val_list)
                elif select_item in ["interface_infos", "fru_infos"] and "ServerInventoryInfo" in server_dict:
                    data_dict_list = list(server_dict["ServerInventoryInfo"][select_item])
                    for data_dict in data_dict_list:
                        data_dict = dict(data_dict)
                        val_list = list()
                        val_list.append(server_id)
                        for key, val in sorted(data_dict.iteritems()):
                            val_list.append(val)
                        return_table.add_row(val_list)
                else:
                    return error_msg
        return return_table


def main(argv=sys.argv[1:]):
    myapp = ServerManagerCLI()
    return myapp.run(argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
