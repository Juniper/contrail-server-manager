#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_cli.py
   Author : Nitish Krishna
   Description : This file provides implementation of Server Manager CLI as part of Cliff framework
"""
import logging
import sys
import readline
from StringIO import StringIO
import pycurl
import json
import urllib
import smgr_client_def
import ConfigParser
from cliff.app import App
from cliff.complete import CompleteCommand
from commandmanager import CommandManager


class ServerManagerCLI(App):
    log = logging.getLogger(__name__)
    smgr_port = None
    smgr_ip = None
    config_file = None

    def __init__(self):
        super(ServerManagerCLI, self).__init__(
            description='Server Manager CLI',
            version='0.1',
            command_manager=CommandManager('smgrcli.app')
        )
        self.command_manager.add_command_group('smgr.cli.common')

    def initialize_app(self, argv):
        self.log.debug('initialize_app')
        self.config_file = getattr(argv, "config_file", smgr_client_def._DEF_SMGR_CFG_FILE)
        config = None
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([self.config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            self.smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not self.smgr_ip:
                self.stdout.write("listen_ip_addr missing in config file %s" % self.config_file)
            self.smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
            if not self.smgr_port:
                self.stdout.write("listen_port missing in config file %s" % self.config_file)
        except Exception as e:
            self.stdout.write("Exception: %s : Error reading config file %s" % (e.message, self.config_file))

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
        #self.stdout.write("List of added commands = " + str(self.command_manager.get_added_commands()) + "\n")
        self.interpreter.cmdloop()
        return 0

    def get_smgr_details(self):
        return {
            "smgr_ip": self.smgr_ip,
            "smgr_port": self.smgr_port
        }

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


def main(argv=sys.argv[1:]):
    myapp = ServerManagerCLI()
    return myapp.run(argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
