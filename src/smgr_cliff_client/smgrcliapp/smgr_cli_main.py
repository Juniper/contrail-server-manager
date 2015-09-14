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
import argparse
import ConfigParser
import inspect
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

    def run_subcommand(self, argv):
        try:
            subcommand = self.command_manager.find_command(argv)
        except ValueError as err:
            if self.options.debug:
                raise
            else:
                self.LOG.error(err)
            return 2
        cmd_factory, cmd_name, sub_argv = subcommand
        kwargs = {}
        if 'cmd_name' in inspect.getargspec(cmd_factory.__init__).args:
            kwargs['cmd_name'] = cmd_name
        cmd = cmd_factory(self, self.options, **kwargs)
        err = None
        result = 1
        try:
            self.prepare_to_run_command(cmd)
            full_name = (cmd_name
                         if self.interactive_mode
                         else ' '.join([self.NAME, cmd_name])
            )
            cmd_parser = cmd.get_parser(full_name)
            parsed_args, remainder = cmd_parser.parse_known_args(sub_argv)
            if remainder:
                result = cmd.run(parsed_args, remainder)
            else:
                result = cmd.run(parsed_args)
        except Exception as err:
            if self.options.debug:
                self.LOG.exception(err)
            else:
                self.LOG.error(err)
            try:
                self.clean_up(cmd, result, err)
            except Exception as err2:
                if self.options.debug:
                    self.LOG.exception(err2)
                else:
                    self.LOG.error('Could not clean up: %s', err2)
            if self.options.debug:
                raise
        else:
            try:
                self.clean_up(cmd, result, None)
            except Exception as err3:
                if self.options.debug:
                    self.LOG.exception(err3)
                else:
                    self.LOG.error('Could not clean up: %s', err3)
        return result

    def report_missing_config(self, param):
        msg = "ERROR: You must provide a config parameter " + str(param) + " via either --" + str(param) + \
              " or env[" + str(param).upper() + "]\n"
        self.print_error_message_and_quit(msg)

    def print_error_message_and_quit(self, msg):
        self.stdout.write(msg)
        sys.exit(0)

    def get_smgr_config(self):
        return {
            "smgr_ip": self.smgr_ip,
            "smgr_port": self.smgr_port
        }

    def get_default_config(self):
        return self.default_config


def main(argv=sys.argv[1:]):
    myapp = ServerManagerCLI()
    return myapp.run(argv)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
