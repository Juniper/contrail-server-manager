#!/usr/bin/env python

import ast
import argparse
from collections import defaultdict
from functools import wraps
import json
import logging
import pdb
import paramiko
import os
import re
import shutil
import socket
import sys
import ConfigParser
from tempfile import mkdtemp
from collections import defaultdict

# Testbed Converter Version
__version__ = '1.0'
# Default translation dictionaries
DEF_TRANS_DICT='/opt/contrail/contrail_server_manager/container-parameter-translation-dict.json'
DEF_TESTBED_FORMAT_DICT='/opt/contrail/contrail_server_manager/testbed-format-translator.json'
# List of parameters that need to be recalculated in specific ways before being put into Server/Cluster JSONs
recalculate_list=["ext_routers","tor_agent","control_data"]

log = logging.getLogger('testbed_parser')
log.setLevel(logging.DEBUG)

class Utils(object):
    @staticmethod
    def initialize_logger(log_file='testbed_parser.log', log_level=40):
        log = logging.getLogger('testbed_parser')
        file_h = logging.FileHandler(log_file)
        file_h.setLevel(logging.DEBUG)
        stream_h = logging.StreamHandler(sys.stdout)
        stream_h.setLevel(log_level)
        long_format = '[%(asctime)-15s: %(filename)s:%(lineno)s:%(funcName)s: %(levelname)s] %(message)s'
        short_format = '[%(asctime)-15s: %(funcName)s] %(message)s'
        file_formatter = logging.Formatter(long_format)
        stream_formatter = logging.Formatter(short_format)
        file_h.setFormatter(file_formatter)
        stream_h.setFormatter(stream_formatter)
        log.addHandler(file_h)
        log.addHandler(stream_h)

    @staticmethod
    def is_file_exists(*filenames):
        for filename in filenames:
            filename = os.path.abspath(os.path.expanduser(filename))
            if not os.path.isfile(filename):
                raise RuntimeError('file (%s) does not exists' %filename)
        return filenames

    @staticmethod
    def get_abspath(*filenames):
        return [os.path.abspath(os.path.expanduser(filename)) for filename in filenames]

    @staticmethod
    def parse_args(args):
        parser = argparse.ArgumentParser(description='TestBed Conversion Utility',
                                         add_help=True)
        parser.add_argument('--version',
                            action='version',
                            version=__version__,
                            help='Print version and exit')
        parser.add_argument('-v', action='count', default=0,
                            help='Increase verbosity. -vvv prints more logs')
        parser.add_argument('--testbed', '-t',
                            required=True,
                            help='Absolute path to testbed file')
        parser.add_argument('--translation-dict',
                            help='Absolute path to parameter translation dictionary file')
        parser.add_argument('--testbed-format-translation-dict',
                            help='Absolute path to testbed format translation dictionary file')
        parser.add_argument('--contrail-packages',
                            nargs='+',
                            help='Absolute path to Contrail Package file, '\
                                 'Multiple files can be separated with space')
        parser.add_argument('--contrail-cloud-package', '-c',
                            nargs='+',
                            help='Absolute path to Contrail Docker Cloud Package file')
        parser.add_argument('--contrail-storage-packages',
                            nargs='+',
                            default=[],
                            help='Absolute path to Contrail Storage Package file, '\
                                 'Multiple files can be separated with space')
        parser.add_argument('--storage-keys-ini-file',
                            default=None,
                            help='Provide storage keys for storage cluster creation')
        parser.add_argument('--cluster-id',
                            action='store',
                            default=None,
                            help='Provide Cluster ID of the cluster')
        parser.add_argument('--log-file',
                            default='test_parser.log',
                            help='Absolute path of a file for logging')
        cliargs = parser.parse_args(args)
        if len(args) == 0:
            parser.print_help()
            sys.exit(2)
        if cliargs.contrail_cloud_package:
            cliargs.contrail_cloud_package = [('contrail_cloud_package', pkg_file) \
                for pkg_file in Utils.get_abspath(*Utils.is_file_exists(*cliargs.contrail_cloud_package))]

        if cliargs.contrail_packages:
            cliargs.contrail_packages = [('contrail_packages', pkg_file) \
                for pkg_file in Utils.get_abspath(*Utils.is_file_exists(*cliargs.contrail_packages))]

        if cliargs.contrail_storage_packages:
            cliargs.contrail_storage_packages = [('contrail_storage_packages', pkg_file) \
                for pkg_file in Utils.get_abspath(*Utils.is_file_exists(*cliargs.contrail_storage_packages))]

        if cliargs.storage_keys_ini_file:
            cliargs.storage_keys_ini_file = Utils.get_abspath(*Utils.is_file_exists(cliargs.storage_keys_ini_file))[0]

        if not (cliargs.contrail_cloud_package or cliargs.contrail_packages):
            log.error('ERROR: Missing Contrail Image argument')
            log.error('ERROR: Please add contrail image argument using --contrail-packages for contrail-install-package or -c for contrail-cloud-docker package')
            raise RuntimeError('Testbed parsing failed')

        # update log level and log file
        log_level = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
        cliargs.v = cliargs.v if cliargs.v <= 3 else 3
        Utils.initialize_logger(log_file=cliargs.log_file, log_level=log_level[cliargs.v])
        return cliargs

    @staticmethod
    def get_section_from_ini_file(file_name, section):
        section_items = {}
        if not file_name:
            return section_items
        ini_config = ConfigParser.SafeConfigParser()
        ini_config.read(file_name)
        if section in ini_config.sections():
            section_items = dict(ini_config.items(section))
        return section_items

    @staticmethod
    def converter(args):
        translation_dict = args.translation_dict
        testbed_format_translation_dict = args.testbed_format_translation_dict
        if not translation_dict:
            translation_dict = DEF_TRANS_DICT
        if not testbed_format_translation_dict:
            testbed_format_translation_dict = DEF_TESTBED_FORMAT_DICT
        with open(testbed_format_translation_dict) as json_file:
            testbed_format_translation_dict = json.load(json_file)
        testsetup = TestSetup(testbed=args.testbed, cluster_id=args.cluster_id)
        testsetup.connect()
        testsetup.update(testbed_format_translation_dict)
        server_json = ServerJsonGenerator(testsetup=testsetup,
                                          storage_packages=args.contrail_storage_packages)
        server_json_dict = server_json.generate_json_dict(translation_dict,testbed_format_translation_dict)
        storage_keys = Utils.get_section_from_ini_file(args.storage_keys_ini_file, 'STORAGE-KEYS')
        cluster_json = ClusterJsonGenerator(testsetup=testsetup,
                                            storage_keys=storage_keys)
        cluster_json_dict = cluster_json.generate_json_dict(translation_dict, testbed_format_translation_dict)
        cloud_package=False
        if args.contrail_packages or args.contrail_cloud_package:
            if args.contrail_packages:
                package_files = args.contrail_packages + args.contrail_storage_packages
            elif args.contrail_cloud_package:
                package_files = args.contrail_cloud_package
                cloud_package=True
            image_json = ImageJsonGenerator(testsetup=testsetup,
                                            package_files=package_files)
            image_json_dict = image_json.generate_json_dict(cloud_package)
        combined_json_dict = {}
        if "cluster" in cluster_json_dict:
            combined_json_dict["cluster"] = cluster_json_dict["cluster"]
        if "server" in server_json_dict:
            combined_json_dict["server"] = server_json_dict["server"]
        if "image" in image_json_dict:
            combined_json_dict["image"] = image_json_dict["image"]
        image_json.generate()
        cluster_json.generate()
        server_json.generate()
        server_json.generate('./combined.json', combined_json_dict)

class Host(object):
    def __init__(self, ip, username, password, **kwargs):
        self.connection = paramiko.SSHClient()
        self.iface_data_raw = ''
        self.iface_data_all = ''
        self.route_data_raw = ''
        self.ip = ip
        self.username = username
        self.password = password
        self.host_id = '%s@%s' % (username, ip)
        self.timeout = kwargs.get('timeout', 5)

    def __del__(self):
        log.info('Disconnecting...')
        self.disconnect()

    def connect(self):
        self.connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.connection.connect(self.ip, username=self.username, \
                                    password=self.password, \
                                    timeout=self.timeout)
            log.info('Connected to Host (%s)' % self.ip)
        except Exception, err:
            log.error('ERROR: %s' % err)
            log.error('ERROR: Unable to connect Host (%s) with username(%s) ' \
                  'and password(%s)' % (self.ip, self.username, self.password))
            raise RuntimeError('Connection to (%s) Failed' % self.ip)


    def disconnect(self):
        self.connection.close()

    def exec_cmd(self, cmd):
        stdin, stdout, stderr = self.connection.exec_command(cmd)
        # check stderr is pending
        return stdout.read()

    def retrieve_iface_info(self):
        cmd = 'ip address list'
        log.debug('Execute: %s' % cmd)
        output = self.exec_cmd(cmd)
        return output.strip()

    def retrieve_route_info(self):
        cmd = 'ip route list'
        log.debug('Execute: %s' % cmd)
        output = self.exec_cmd(cmd)
        return output.strip()

    def retrieve_hostname(self):
        cmd = 'hostname -s'
        log.debug('Execute: %s' % cmd)
        output = self.exec_cmd(cmd)
        return output.strip()

    def retrieve_domain_name(self):
        cmd = 'hostname -d'
        log.debug('Execute: %s' % cmd)
        output = self.exec_cmd(cmd)
        return output.strip()

    def retrieve_ostype(self):
        cmd = "python -c 'from platform import linux_distribution; " \
              "print linux_distribution()'"
        log.debug('Execute: %s' % cmd)
        output = self.exec_cmd(cmd)
        if output == "" :
          cmd = r'python3 -c "import platform; print (platform.linux_distribution())"'
          output = self.exec_cmd(cmd)
        return output.strip()

    def parse_iface_info(self, iface_data=None):
        parsed_data = {}
        pattern = r'^\d+\:\s+\w+\:\s+'
        iface_pattern = r'^\d+\:\s+(\w+)\:\s+(.*)'
        iface_data = iface_data or self.retrieve_iface_info()

        iters = re.finditer(pattern, iface_data, re.M|re.DOTALL)
        indices = [match.start() for match in iters]
        matched = map(iface_data.__getslice__, indices, indices[1:] + [len(iface_data)])
        for match in matched:
            if_match = re.search(iface_pattern, match, re.M|re.DOTALL)
            if if_match:
                parsed_data[if_match.groups()[0]] = if_match.groups()[1]
        return parsed_data

    def parse_route_info(self, route_data=None):
        route_data = route_data or self.retrieve_route_info()
        return route_data.split('\r\n')

    def get_actual_ostype(self):
        version_raw = self.retrieve_ostype()
        dist, version, extra = ast.literal_eval(version_raw)
        return dist, version, extra

    def set_actual_ostype(self):
        dist, version, extra = self.get_actual_ostype()
        if 'red hat' in dist.lower():
            dist = 'redhat'
        elif 'centos linux' in dist.lower():
            dist = 'centoslinux'
        self.actual_ostype = (dist.lower(), version, extra)

    def get_mac_from_ifconfig(self, iface_data=None):
        mac = ''
        if iface_data is None:
            iface_data = self.iface_data_raw
        ether_pattern = re.compile(r'\bether\s([^\s]+)\b')
        ether_match = ether_pattern.search(iface_data)
        if ether_match:
            mac = ether_match.groups()[0]
        return mac

    def get_mac_from_if_name(self, interface, iface_data=None):
        mac = ''
        if iface_data is None:
            iface_info = self.parse_iface_info()
            if interface and interface in iface_info.keys():
                iface_data = iface_info[str(interface)]
        ether_pattern = re.compile(r'\bether\s([^\s]+)\b')
        ether_match = ether_pattern.search(iface_data)
        if ether_match:
            mac = ether_match.groups()[0]
        return mac

    def get_ip_from_ifconfig(self, iface_data=None):
        ip_net = []
        if iface_data is None:
            iface_data = self.iface_data_raw
        inet_pattern = re.compile(r'\binet\s([^\s]+)\b')
        inet_match = inet_pattern.search(iface_data)
        if inet_match:
            ip_net = inet_match.groups()[0].split('/')
        return ip_net

    def get_interface_details_from_ip(self, ip=None):
        interface = matched_data = ''
        if ip is None:
            ip = self.ip
        iface_info = self.parse_iface_info()
        for iface, iface_data in iface_info.items():
            if re.search(r'\binet\s+%s' % ip, iface_data):
                matched_data = iface_data
                interface = iface
        return interface, matched_data

    def set_route_data(self):
        self.route_data_raw = self.parse_route_info()

    def get_default_gateway(self, route_data=None):
        if route_data is None:
            route_data = self.parse_route_info()
        pattern = re.compile(r'\bdefault\s+via\s+([^\s]+)\b')
        for route_info in route_data:
            match = pattern.search(route_info)
            if match:
                gw = match.groups()[0]
        return gw

    def get_if_dhcp_enabled(self):
        pass

    def get_hostname(self):
        return self.retrieve_hostname()

    def get_domain_name(self):
        return self.retrieve_domain_name()

    def set_interface_details_from_ip(self, ip=None):
        if ip is None:
            ip = self.ip
        self.interface, self.iface_data_raw = self.get_interface_details_from_ip(ip)

    def set_route_data(self):
        self.route_data_raw = self.get_route_data()

    def set_ip_from_ifconfig(self, iface_data=None):
        self.ip_net = self.get_ip_from_ifconfig(iface_data)

    def set_mac_from_ifconfig(self, iface_data=None):
        self.mac = self.get_mac_from_ifconfig(iface_data)

    def set_default_gateway(self):
        self.default_gateway = self.get_default_gateway()

    def set_domain_name(self):
        self.domain_name = self.get_domain_name()

    def set_if_dhcp_enabled(self):
        pass

    def set_group_param(self, group_param,group_param_value):
        log.debug('Set group_param (%s) for host ID (%s)' % (group_param, self.host_id))
        self.__dict__[str(group_param)] = group_param_value

    def set_server_specific_params(self, server_specific_param, param_value):
        log.debug('Set host specific parameter (%s) for host ID (%s)' % (server_specific_param, self.host_id))
        self.__dict__[str(server_specific_param)] = param_value

    def set_hostname(self):
        log.debug('Retrieve hostname for host ID (%s)' % self.host_id)
        self.hostname = self.get_hostname()
        log.debug('Set hostname (%s) for host ID (%s)' % (self.hostname, self.host_id))

    def update(self):
        self.set_actual_ostype()
        self.set_interface_details_from_ip()
        self.set_ip_from_ifconfig()
        self.set_mac_from_ifconfig()
        self.set_hostname()
        self.set_if_dhcp_enabled()
        self.set_domain_name()
        self.set_default_gateway()

class Testbed(object):
    def __init__(self, testbed):
        self.testbed_file = testbed
        self.testbed = None
        self.fab_replacer = 'try:\n'\
                            '    from fabric.api import env\n' \
                            'except:\n' \
                            '    class TestbedEnv(dict):\n' \
                            '        def __getattr__(self, key):\n' \
                            '            try:\n' \
                            '                return self[key]\n' \
                            '            except:\n' \
                            '                raise AttributeError(key)\n' \
                            '        def __setattr__(self, key, value):\n' \
                            '            self[key] = value\n' \
                            '    env = TestbedEnv()'
        self.import_testbed()

    def import_testbed(self):
        log.debug('Handling fab imports')
        pattern = re.compile(r'\bfrom\s+fabric.api\s+import\s+env\b')
        tempdir = mkdtemp()
        sys.path.insert(0, tempdir)

        with open(os.path.join(tempdir, '__init__.py'), 'w') as fid:
            fid.write('\n')

        with open(self.testbed_file, 'r') as fid:
            testbed_contents = fid.read()
        new_contents = pattern.sub(self.fab_replacer, testbed_contents)
        with open(os.path.join(tempdir, 'testbed.py'), 'w') as fid:
            fid.write(new_contents)
        log.debug('Replaced fab imports with Attribute Dict to provide env variable')

        try:
            self.testbed = __import__('testbed')
        except Exception, err:
            log.error(err)
            raise RuntimeError('Error while importing testbed file (%s)' % self.testbed_file)
        finally:
            shutil.rmtree(tempdir)


class TestSetup(Testbed):
    def __init__(self, testbed, cluster_id=None):
        super(TestSetup, self).__init__(testbed=testbed)
        self.cluster_id = cluster_id
        self.host_ids = []
        self.hosts = defaultdict(dict)
        self.import_testbed_variables()
        self.import_testbed_env_variables()
        self.set_host_ids()
        self.all_server_params = set()
        self.all_cluster_params = set()
        self.set_hosts()

    def get_host_ip_from_hostid(self, host_id):
        username, host_ip = host_id.split('@')
        # Quick check for IPv4 address
        if not re.match(r'^([\d]{1,3}\.){3}[\d]{1,3}$', host_ip.strip()):
            log.debug('Retrieve IP address of host (%s)' % host_ip)
            host_ip = socket.gethostbyname(host_ip)
        return username, host_ip

    def set_hosts(self):
        for host_id in self.host_ids:
            username, host_ip = self.get_host_ip_from_hostid(host_id)
            password = self.passwords.get(host_id, None)
            if password is None:
                raise RuntimeError('No Password defined for Host ID (%s)' % host_id)
            self.hosts[host_id] = Host(host_ip, username=username, password=password)

    def get_host_ids(self):
        return self.testbed.env.roledefs['all']

    def set_host_ids(self):
        self.host_ids = self.get_host_ids()

    def connect(self):
        for host_obj in self.hosts.values():
            log.debug('Connecting host (%s) ...' % host_obj.ip)
            host_obj.connect()

    def update(self,testbed_format_translation_dict):
        self.update_hosts()
        self.update_testbed(testbed_format_translation_dict)

    def update_hosts(self):
        for host_obj in self.hosts.values():
            host_obj.update()

    def update_testbed(self, testbed_format_translation_dict):
        self.set_testbed_ostype()
        self.set_host_params()
        all_host_params = set(self.__dict__.keys())
        for host in self.hosts.keys():
            all_host_params.update(self.hosts[host].__dict__.keys())
        server_specific_params = all_host_params.intersection(set(testbed_format_translation_dict["server_params"]))
        server_dict_params = all_host_params.intersection(set(testbed_format_translation_dict["server_dict_params"]))
        server_group_params = all_host_params.intersection(set(testbed_format_translation_dict["server_group_params"]))
        server_dict_list_params = all_host_params.intersection(set(testbed_format_translation_dict["server_dict_list_params"]))
        server_nested_dict_params = all_host_params.intersection(set(testbed_format_translation_dict["server_nested_dict_params"]))
        all_server_params = server_specific_params.union(server_dict_params).union(server_dict_list_params).union(server_nested_dict_params)
        self.update_server_specific_params(all_server_params)
        self.update_server_group_params(server_group_params)
        self.all_server_params = all_server_params.union(server_group_params)
        self.server_specific_params = server_specific_params
        self.server_dict_params = server_dict_params
        self.server_dict_list_params = server_dict_list_params
        self.server_nested_dict_params = server_nested_dict_params


    def import_testbed_variables(self):
        for key, value in self.testbed.__dict__.items():
            if key.startswith('__') and key.endswith('__'):
                continue
            setattr(self, key, value)

    def import_testbed_env_variables(self):
        for key, value in self.testbed.env.items():
            if key == 'hosts':
                continue
            setattr(self, key, value)

    def is_defined(variable):
        def _is_defined(function):
            @wraps(function)
            def wrapped(self, *args, **kwargs):
                try:
                    getattr(self, variable)
                    return function(self, *args, **kwargs)
                except:
                    return
            return wrapped
        return _is_defined

    def get_testbed_ostype(self):
        hostobj = self.hosts.values()[0]
        return hostobj.actual_ostype

    def set_testbed_ostype(self):
        self.os_type = self.get_testbed_ostype()

    def set_host_params(self):
        '''Set hostobj params  with its params defined in testbed.py only if
           they're not initialized already
        '''
        dict_objs = [key for key in self.__dict__.keys() if isinstance(self.__dict__[key], dict)]
        for dict_obj in dict_objs:
            # skip adding hosts attribue to hosts
            if dict_obj == 'hosts':
                continue
            for key in self.__dict__[dict_obj].keys():
              if key in self.hosts.keys():
                  if getattr(self.hosts[key], dict_obj, None) is None:
                      setattr(self.hosts[key], dict_obj, self.__dict__[dict_obj][key])

    def update_server_specific_params(self, all_server_params):
        for specific_param in all_server_params:
            if specific_param in self.__dict__.keys():
                for host_id, param_value in self.__dict__.get(specific_param).iteritems():
                    if host_id != 'all':
                        self.hosts[host_id].set_server_specific_params(specific_param,param_value)

    def update_server_group_params(self, server_group_params):
        for server_group_param in server_group_params:
            host_dict = self.get_group_dict(server_group_param)
            for host_id, param_value in host_dict.items():
                if server_group_param == "roledefs":
                    server_group_param = "roles"
                    if param_value.count('cfgm') > 0:
                        log.debug('Replacing cfgm role with config role name')
                        param_value.remove('cfgm')
                        param_value.append('config')
                self.hosts[host_id].set_group_param(server_group_param,param_value)

    def get_group_dict(self, server_group_param):
        host_dict = defaultdict(list)
        for group_param, hosts in self.__dict__[server_group_param].items():
            if group_param == 'build' or group_param == 'all':
                log.debug('Discarding role (%s)' % group_param)
                continue
            for host in hosts:
                host_dict[host].append(group_param)
        return host_dict


class BaseJsonGenerator(object):
    def __init__(self, **kwargs):
        self.testsetup = kwargs.get('testsetup', None)
        name = kwargs.get('name', 'contrail')
        abspath = kwargs.get('abspath', None)
        self.package_files = kwargs.get('package_files', None)
        self.storage_package_files = kwargs.get('storage_packages', None)
        self.jsonfile = abspath or '%s.json' % name
        self.cluster_id = self.testsetup.cluster_id or "cluster"
        self.dict_data = {}

    def get_destination_struct_to_set(self, source_variable_name, destination_variable_top, translation_dict):
        if source_variable_name in translation_dict:
            name_format_dict = translation_dict[source_variable_name]
            dest_format = name_format_dict.get("dest_format","dict")
            tmp_dict = destination_variable_top
            if dest_format == "list":
                destination_variable_name = name_format_dict.get("dest_path",destination_variable_top)
                param_path = name_format_dict["name"]
            elif dest_format == "nested_dict" or dest_format == "dict":
                destination_variable_name = name_format_dict.get("dest_path",destination_variable_top)
                param_path = name_format_dict["name"]
            else:
                return None, None, None
            split_dest_v_name = destination_variable_name.split('.')
            for level in split_dest_v_name[:-1]:
                if level not in tmp_dict.keys():
                    tmp_dict[str(level)] = {}
                tmp_dict = tmp_dict[str(level)]
            if dest_format == "list":
                if str(split_dest_v_name[-1]) not in tmp_dict:
                    tmp_dict[str(split_dest_v_name[-1])] = []
                return tmp_dict[str(split_dest_v_name[-1])], param_path, name_format_dict["format"]
            elif dest_format == "nested_dict" or dest_format == "dict":
                return tmp_dict, str(split_dest_v_name[-1]), name_format_dict["format"]


    def get_destination_variable_to_set(self, source_variable_name, destination_variable_top, translation_dict):
        if source_variable_name in translation_dict:
            name_format_dict = translation_dict[source_variable_name]
            tmp_dict = destination_variable_top
            dest_format = name_format_dict.get("dest_format","dict")
            destination_variable_name = name_format_dict["name"]
            split_dest_v_name = destination_variable_name.split('.')
            for level in split_dest_v_name[:-1]:
                if level not in tmp_dict.keys():
                    tmp_dict[str(level)] = {}
                tmp_dict = tmp_dict[str(level)]
            tmp_dict[str(split_dest_v_name[-1])] = ""
            return tmp_dict, split_dest_v_name[-1], name_format_dict["format"]

    def set_if_defined(self, source_variable_name,
                       destination_variable, **kwargs):

        destination_variable_name = kwargs.get('destination_variable_name',
                                               source_variable_name)
        source_variable = kwargs.get('source_variable', self.testsetup)
        function = kwargs.get('function', getattr)
        to_string = kwargs.get('to_string', True)
        to_lower = kwargs.get('to_lower', False)
        is_boolean = kwargs.get('is_boolean', False)
        is_list = kwargs.get('is_list', False)
        log.debug('Adding Variable (%s)' % destination_variable_name)
        log.debug('Source Variable: (%s) Destination Variable: (%s) ' \
                  'Source Variable Name (%s) Destination Variable Name (%s) ' \
                  'Function (%s) ' % (
            source_variable, destination_variable, source_variable_name,
            destination_variable_name, function))
        value = function(source_variable, source_variable_name, None)
        log.debug('Retrieved Value (%s)' % value)
        if value is not None:
            if to_string:
                if to_lower:
                    value = str(value).lower()
                elif is_boolean:
                    value = (str(value).lower() == "true")
                elif is_list:
                    value = eval(str(value))
                else:
                    value = str(value)

            destination_variable[destination_variable_name] = value

    def get_source_format(self, param, source_dict):
        if isinstance(source_dict[param],dict):
            if isinstance(source_dict[param].itervalues().next(),dict):
                return "nested_dict", source_dict[param]
            return "dict", source_dict[param]
        elif isinstance(source_dict[param],list) and len(source_dict[param]) and isinstance(source_dict[param][0],dict):
            return "list", source_dict[param]
        else:
            return "str", source_dict[param]

    def get_dest_format(self, key, translation_dict):
        if key in translation_dict.keys():
            name_format_dict = translation_dict[key]
            dest_format = name_format_dict.get("dest_format","dict")
            dest_path = name_format_dict.get("dest_path", None)
            return dest_format, dest_path
        else:
            return None, None

    def translate_key(self, dest_dict, key, translation_dict, source_dict):
        if key not in translation_dict.keys():
            # Cannot be translated
            return
        if "." in key:
            sub_dict_name = str(key).split('.')[0]
            sub_dict_key = str(key).split('.')[1]
            source_variable = source_dict.get(sub_dict_name, None)
        elif key in source_dict:
            sub_dict_name = None
            sub_dict_key = None
            source_variable = source_dict
        else:
            # Cannot be translated
            return

        if key in source_dict \
                or (sub_dict_key and source_variable and sub_dict_key in source_variable):
            dest_var, dest_var_name, data_format = self.get_destination_variable_to_set(
                key, dest_dict, translation_dict)
            if not dest_var:
                return
        else:
            return
        function_to_use=dict.get
        if sub_dict_key:
            source_variable_name = sub_dict_key
        else:
            source_variable_name = key
        if data_format == "boolean":
            is_boolean = True
        else:
            is_boolean = False
        if data_format == "list":
            is_list = True
        elif data_format == "dict":
            is_list = True
        else:
            is_list = False
        to_lower = False
        self.set_if_defined(source_variable_name, dest_var, source_variable=source_variable,
                        destination_variable_name=str(dest_var_name), to_lower=to_lower,
                        is_boolean=is_boolean, is_list=is_list, function=function_to_use)

    def process_key_translation(self, dest_format, dest_path, key, item_to_process, dest_dict, translation_dict, source_dict):
        if dest_format == "dict":
            dict_format_key_list = [str(key)+"."+str(k) for k in item_to_process.keys()]
            for k in dict_format_key_list:
                self.translate_key(dest_dict, k, translation_dict, source_dict)
        elif dest_format == "nested_dict":
            dest_dict, primary_key_name, data_format = self.get_destination_struct_to_set(
                str(key)+"."+str(item_to_process.keys()[0]), dest_dict, translation_dict)
            if dest_dict == None:
                return
            new_dest_dict = {}
            dict_format_key_list = [str(key)+"."+str(k) for k in item_to_process.keys()]
            dict_format_key_list.remove(str(key)+"."+str(primary_key_name))
            for k in dict_format_key_list:
                self.translate_key(new_dest_dict, k, translation_dict, {key: item_to_process})
            dest_dict[str(item_to_process[primary_key_name])] = new_dest_dict
        elif dest_format == "list":
            dest_list, dest_var, data_format = self.get_destination_struct_to_set(
                str(key)+"."+str(item_to_process.keys()[0]), dest_dict, translation_dict)
            if dest_list == None:
                return
            new_dest_dict = {}
            dest_path_key_list = [str(key)+"."+str(k) for k in item_to_process.keys()]
            for k in dest_path_key_list:
                self.translate_key(new_dest_dict, k, translation_dict, source_dict)
            dest_list.append(new_dest_dict)

    def process_key_list(self, dest_dict, key_list, translation_dict, source_dict):
        key_list_to_process = key_list.intersection(set(source_dict.keys()))
        for key in key_list_to_process:
            source_format, item_to_process = self.get_source_format(key, source_dict)
            if source_format == "str":
                self.translate_key(dest_dict, key, translation_dict, source_dict)
            elif source_format == "dict":
                dest_format,dest_path = self.get_dest_format(str(key)+"."+str(item_to_process.keys()[0]), translation_dict)
                if dest_format == None:
                    return
                self.process_key_translation(dest_format, dest_path, key, item_to_process, dest_dict, translation_dict, source_dict)
            elif source_format == "nested_dict":
                dest_format,dest_path = self.get_dest_format(str(key)+"."+str(item_to_process.values()[0].keys()[0]), translation_dict)
                if dest_format == None:
                    return
                dest_dict, primary_key_name, data_format = self.get_destination_struct_to_set(
                    str(key)+"."+str(item_to_process.values()[0].keys()[0]), dest_dict, translation_dict)
                for primary_key in item_to_process.keys():
                    dest_dict[str(primary_key)] = {}
                    self.process_key_translation(dest_format, dest_path, key, item_to_process[primary_key], dest_dict[str(primary_key)], translation_dict, {key: item_to_process[primary_key]})
            elif source_format == "list":
                for cfg_dict in item_to_process:
                    dest_format,dest_path = self.get_dest_format(str(key)+"."+str(cfg_dict.keys()[0]), translation_dict)
                    self.process_key_translation(dest_format, dest_path, key, cfg_dict, dest_dict, translation_dict, {key: cfg_dict})

    def generate(self, json_path=None, json_data=None):
        if not json_path:
            json_path = self.jsonfile
        if not json_data:
            json_data = self.dict_data
        log.debug('Generate Json with Dict data: %s' % json_data)
        log.info('Generating Json File (%s)...' % json_path)
        with open(json_path, 'w') as fid:
            fid.write('%s\n' % json.dumps(json_data, sort_keys=True,
                                          indent=4, separators=(',', ': ')))

    def recalculate_control_data_interface(self, cfg_dict, source_dict, host_ip):
        interface_list = cfg_dict['network']['interfaces']
        control_data_source_dict = source_dict['control_data']
        bond_dict = None
        control_data_dict = None
        vlan_flag = False
        if isinstance(interface_list, list) and isinstance(interface_list[0], dict):
            for intf_dict in interface_list:
                if intf_dict["name"].startswith('bond') and "member_interfaces" in intf_dict:
                    bond_dict = intf_dict
                    bond_dict["type"]="bond"
                if "ip_address" in intf_dict and intf_dict["name"]==control_data_source_dict["device"]:
                    control_data_dict = intf_dict
                    cfg_dict['contrail'] = {"control_data_interface": control_data_dict["name"]}
                    if "vlan" in intf_dict:
                        vlan_flag = True
        if bond_dict and control_data_dict["name"].startswith('bond'):
            for k in bond_dict.keys():
                control_data_dict[k] = bond_dict[k]
            member_interfaces = bond_dict["member_interfaces"]
            for member_interface in member_interfaces:
                member_intf_dict = {}
                member_intf_dict["name"] = member_interface
                host_ids = self.testsetup.get_host_ids()
                for host_id in host_ids:
                    if host_ip == self.testsetup.get_host_ip_from_hostid(str(host_id))[1]:
                        host_id_to_process = host_id
                member_intf_dict["mac_address"] = self.testsetup.hosts[host_id_to_process].get_mac_from_if_name(member_interface)
                interface_list.append(member_intf_dict)
            interface_list.remove(bond_dict)
            # The bond dict should come after memeber interface dict in list of interfaces
            interface_list.remove(control_data_dict)
            interface_list.append(control_data_dict)
        if vlan_flag and control_data_dict:
            vlan_intf_dict = {}
            vlan_intf_dict["type"] = "vlan"
            vlan_intf_dict["ip_address"] = control_data_dict.pop('ip_address')
            vlan_intf_dict["parent_interface"] = control_data_dict['name']
            vlan_intf_dict["name"] = "vlan" + str(control_data_dict['vlan'])
            vlan_intf_dict["vlan"] = control_data_dict.pop('vlan')
            self.set_if_defined('default_gateway', vlan_intf_dict,
                                source_variable=control_data_dict,
                                function=dict.get,
                                destination_variable_name='default_gateway')
            control_data_dict.pop("default_gateway")
            cfg_dict['contrail'] = {"control_data_interface": vlan_intf_dict["name"]}
            cfg_dict['network']['interfaces'].append(vlan_intf_dict)

    def recalculate_external_router_list(self, cfg_dict):
        ext_routers_dict = {}
        if "contrail_4" not in cfg_dict['parameters']['provision']:
            return
        source_tuple_list = cfg_dict['parameters']['provision']['contrail_4']['controller_config']['external_routers_list']
        if isinstance(source_tuple_list,list):
            for source_tuple in source_tuple_list:
                if len(source_tuple) == 2:
                    ext_routers_dict[source_tuple[0]] = source_tuple[1]
            cfg_dict['parameters']['provision']['contrail_4']['controller_config']['external_routers_list'] = ext_routers_dict

    def verify_tor_tsn_ip(self, cfg_dict, source_dict, host_ip):
        tor_switches = cfg_dict['top_of_rack']['switches']
        control_data_ip = None
        control_data_source_dict = source_dict.get('control_data',None)
        if control_data_source_dict:
            control_data_ip = control_data_source_dict['ip'].split('/')[0].strip()
        for switch in tor_switches:
            if "tsn_ip" in switch and (switch["tsn_ip"]==control_data_ip or switch["tsn_ip"]==host_ip):
                continue
            else:
                tor_switches.remove(switch)
                log.error('ERROR: Tor Switch with name %s has a TSN_IP %s which does not match ' \
                  'any IP address of the compute server %s %s ' % (switch["name"], switch["tsn_ip"], host_ip, control_data_ip))
                raise Exception('Failed to add ToR Switch %s' % (switch["name"]))

    def recalculate_params(self, cfg_dict, params_to_recalculate, source_dict, host_ip):
        if "ext_routers" in params_to_recalculate:
            self.recalculate_external_router_list(cfg_dict)
        if "control_data" in params_to_recalculate and "network" in cfg_dict:
            self.recalculate_control_data_interface(cfg_dict, source_dict, host_ip)
        if "tor_agent" in params_to_recalculate and "top_of_rack" in cfg_dict:
            self.verify_tor_tsn_ip(cfg_dict, source_dict, host_ip)

class ServerJsonGenerator(BaseJsonGenerator):
    def __init__(self, testsetup, **kwargs):
        kwargs.update([('name', kwargs.get('name', 'server'))])
        super(ServerJsonGenerator, self).__init__(testsetup=testsetup, **kwargs)
        self.dict_data = {"server": []}

    def _initialize(self, hostobj, translation_dict, testbed_format_dict):
        if 'tsn' in hostobj.roles:
            tsn_mode_flag = True
            hostobj.roles.remove('tsn')
        else:
            tsn_mode_flag = False
        server_dict = {"id": hostobj.hostname,
                       "roles": hostobj.roles,
                       "cluster_id": self.cluster_id,
                       "password": hostobj.password,
                       "domain": hostobj.domain_name,
                       "parameters": {},
                       "network": {
                           "management_interface": hostobj.interface,
                           "provisioning": "kickstart",
                           "interfaces": [
                                {
                                "default_gateway": hostobj.default_gateway,
                                "ip_address": "%s/%s" % (hostobj.ip, hostobj.ip_net[1]),
                                "mac_address": hostobj.mac,
                                "name": hostobj.interface,
                                }  ]
                            }
                        }

        server_dict['parameters']['provision'] = {}
        server_dict['parameters']['provision']['contrail'] = {}
        server_dict['parameters']['provision']['contrail_4'] = {}
        if tsn_mode_flag:
            server_dict['parameters']['provision']['contrail_4']['tsn_mode'] = True
        with open(translation_dict) as json_file:
            translation_dict = json.load(json_file)

        all_host_params = self.testsetup.all_server_params
        source_dict = {}
        for key in all_host_params:
            if key in self.testsetup.testbed.env.keys() and \
              str(hostobj.host_id) in self.testsetup.testbed.env[key]:
                source_dict[key]=self.testsetup.testbed.env[key][str(hostobj.host_id)]
            elif key in self.testsetup.testbed.__dict__.keys() and \
              str(hostobj.host_id) in self.testsetup.testbed.__dict__[key]:
                source_dict[key]=self.testsetup.testbed.__dict__[key][str(hostobj.host_id)]
        self.process_key_list(server_dict, self.testsetup.server_specific_params, translation_dict, source_dict)
        self.process_key_list(server_dict, self.testsetup.server_dict_params, translation_dict, source_dict)
        self.process_key_list(server_dict, self.testsetup.server_dict_list_params, translation_dict, source_dict)
        self.process_key_list(server_dict, self.testsetup.server_nested_dict_params, translation_dict, source_dict)
        if len(set(recalculate_list).intersection(all_host_params)):
            self.recalculate_params(server_dict, set(recalculate_list).intersection(all_host_params), source_dict, hostobj.ip)
        return server_dict

    def update(self, translation_dict, testbed_format_dict):
        for host_id in self.testsetup.hosts:
            hostobj = self.testsetup.hosts[host_id]
            server_dict = self._initialize(hostobj, translation_dict, testbed_format_dict)
            self.dict_data['server'].append(server_dict)

    def generate_json_dict(self, translation_dict, testbed_format_dict):
        self.update(translation_dict, testbed_format_dict)
        return self.dict_data

class ClusterJsonGenerator(BaseJsonGenerator):
    def __init__(self, testsetup, **kwargs):
        kwargs.update([('name', kwargs.get('name', 'cluster'))])
        super(ClusterJsonGenerator, self).__init__(testsetup=testsetup, **kwargs)
        self.storage_keys = kwargs.get('storage_keys', None)
        self.dict_data = {"cluster": []}

    def _initialize(self, translation_dict, testbed_format_translation_dict):
        with open(translation_dict) as json_file:
            translation_dict = json.load(json_file)
        cluster_dict = {"id": self.cluster_id, "parameters": {}}
        cluster_dict['parameters']['provision'] = {}
        #TODO: Instead of translation_dict here, use list of all added params from what host_obj has for cluster wide params

        testbed_param_list = set(self.testsetup.testbed.__dict__.keys() + self.testsetup.testbed.env.keys())
        cluster_specific_params = testbed_param_list.intersection(set(testbed_format_translation_dict["cluster_params"]))
        cluster_dict_params = testbed_param_list.intersection(set(testbed_format_translation_dict["cluster_dict_params"]))
        all_cluster_dict_params = cluster_specific_params.union(cluster_dict_params)
        source_dict = {}
        for param in all_cluster_dict_params:
            if param in self.testsetup.testbed.__dict__.keys():
                source_dict[param] = self.testsetup.testbed.__dict__[param]
            elif param in self.testsetup.testbed.env.keys():
                source_dict[param] = self.testsetup.testbed.env[param]

        self.process_key_list(cluster_dict, all_cluster_dict_params, translation_dict, source_dict)
        if len(set(recalculate_list).intersection(all_cluster_dict_params)):
            self.recalculate_params(cluster_dict, set(recalculate_list).intersection(all_cluster_dict_params), source_dict, None)
        return cluster_dict

    def generate_json_dict(self,translation_dict,testbed_format_dict):
        cluster_dict = self._initialize(translation_dict, testbed_format_dict)
        self.dict_data['cluster'].append(cluster_dict)
        return self.dict_data

class ImageUtils(object):
    @staticmethod
    def get_version(package_file, os_type):
        version = ''
        # only rpm or deb version can be retrieved
        if not (package_file.endswith('.rpm') or package_file.endswith('.deb') or package_file.endswith('.tgz')):
            return ""
        if os_type[0] in ['centos', 'fedora', 'redhat', 'centoslinux']:
            cmd = "rpm -qp --queryformat '%%{VERSION}-%%{RELEASE}\\n' %s" % package_file
        elif os_type[0] in ['ubuntu']:
            package_name = os.path.basename(package_file)
            if package_name.endswith('.tgz'):
                exp = re.compile("[0-9].*")
                for m in exp.finditer(package_name):
                   match_index = m.span()[0]
                version = package_name[match_index:-4]
            else:
                cmd = "dpkg-deb -f %s Version" % package_file
                pid = os.popen(cmd)
                version = pid.read().strip()
                pid.flush()
        else:
            raise Exception("ERROR: UnSupported OS Type (%s)" % os_type)
        return version

    @staticmethod
    def get_image_id(image_id, package_type):
        replacables = ['.', '-', '~']
        for r_item, item  in zip(['_'] * len(replacables), replacables):
            image_id = image_id.replace(item, r_item)
        image_id = package_type + '_' + image_id
        return "image_%s" % image_id

class ImageJsonGenerator(BaseJsonGenerator):
    def __init__(self, testsetup, package_files, **kwargs):
        kwargs.update([('name', kwargs.get('name', 'image'))])
        super(ImageJsonGenerator, self).__init__(testsetup=testsetup,
                                                 package_files=package_files,
                                                 **kwargs)
        self.dict_data = {"image": []}
        self.package_types = {'deb': 'package', 'rpm': 'package',
                             'iso': 'image', 'tgz': 'package',
                             'tar.gz': 'tgz'}

    def get_category(self, package_file):
        category = 'package'
        ext = filter(package_file.endswith, self.package_types.keys())
        if ext:
            category = self.package_types.get(ext[0], category)
        return category

    def get_package_type(self, package_file, package_type, cloud_package):
        package_type = package_type.replace('_', '-').replace('-packages', '')
        if cloud_package:
            return 'contrail-ubuntu-package'
        if package_file.endswith('.rpm'):
            dist = 'centos'
        elif package_file.endswith('.deb') or package_file.endswith('.tgz'):
            dist = 'ubuntu'
        else:
            log.debug('Only deb or rpm packages are supported. Received (%s)' % package_file)
            raise RuntimeError('UnSupported Package (%s)' % package_file)
        return "%s-%s-%s" %(package_type, dist, 'package')

    def get_md5(self, package_file):
        pid = os.popen('md5sum %s' % package_file)
        md5sum = pid.read().strip()
        return md5sum.split()[0]

    def _initialize(self, package_file, package_type, cloud_package):
        version = ImageUtils.get_version(package_file, self.testsetup.os_type)
        image_id = ImageUtils.get_image_id(version, package_type)
        image_dict = {
            "id": image_id,
            "category": self.get_category(package_file),
            "version": version,
            "type": self.get_package_type(package_file, package_type,cloud_package),
            "path": package_file,
        }
        log.debug('Created Basic image_dict: %s' % image_dict)
        return image_dict

    def generate_json_dict(self,cloud_package=False):
        for package_type, package_file in self.package_files:
            image_dict = self._initialize(package_file, package_type, cloud_package)
            if cloud_package:
                image_dict["parameters"] = { "contrail-container-package": True }
            else:
                image_dict["parameters"] = {}
            self.dict_data['image'].append(image_dict)
            return self.dict_data

if __name__ == '__main__':
    args = Utils.parse_args(sys.argv[1:])
    log.info('Executing: %s' % " ".join(sys.argv))
    Utils.converter(args)
