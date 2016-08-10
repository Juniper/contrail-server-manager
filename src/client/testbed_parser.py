#!/usr/bin/env python

import ast
import argparse
from collections import defaultdict
from functools import wraps
import json
import logging
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
        parser.add_argument('--testbed',
                            required=True,
                            help='Absolute path to testbed file')
        parser.add_argument('--contrail-packages',
                            nargs='+',
                            required=True,
                            help='Absolute path to Contrail Package file, '\
                                 'Multiple files can be separated with space')
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
        if cliargs.contrail_packages:
            cliargs.contrail_packages = [('contrail_packages', pkg_file) \
                for pkg_file in Utils.get_abspath(*Utils.is_file_exists(*cliargs.contrail_packages))]

        if cliargs.contrail_storage_packages:
            cliargs.contrail_storage_packages = [('contrail_storage_packages', pkg_file) \
                for pkg_file in Utils.get_abspath(*Utils.is_file_exists(*cliargs.contrail_storage_packages))]

        if cliargs.storage_keys_ini_file:
            cliargs.storage_keys_ini_file = Utils.get_abspath(*Utils.is_file_exists(cliargs.storage_keys_ini_file))[0]

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
        testsetup = TestSetup(testbed=args.testbed, cluster_id=args.cluster_id)
        testsetup.connect()
        testsetup.update()
        server_json = ServerJsonGenerator(testsetup=testsetup,
                                          storage_packages=args.contrail_storage_packages)
        server_json.generate_json_file()
        storage_keys = Utils.get_section_from_ini_file(args.storage_keys_ini_file, 'STORAGE-KEYS')
        cluster_json = ClusterJsonGenerator(testsetup=testsetup,
                                            storage_keys=storage_keys)
        cluster_json.generate_json_file()
        package_files = args.contrail_packages + args.contrail_storage_packages
        image_json = ImageJsonGenerator(testsetup=testsetup,
                                        package_files=package_files)
        image_json.generate_json_file()

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
        self.dpdk_config = {}

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

    def set_ostype(self, ostypes):
        log.debug('Set ostype (%s) for host ID (%s)' % (ostypes, self.host_id))
        self.ostypes = ostypes

    def set_roles(self, roles):
        log.debug('Set roles (%s) for host ID (%s)' % (roles, self.host_id))
        self.roles = roles

    def set_hypervisor(self, hypervisor):
        log.debug('Set hypervisor (%s) for host ID (%s)' % (hypervisor, self.host_id))
        self.hypervisor = hypervisor

    def set_storage_node_configs(self, configs):
        log.debug('Set storage_node_configs (%s) for host ID (%s)' % (configs, self.host_id))
        self.storage_node_configs = configs

    def set_dpdk_configs(self, configs):
        log.debug('Set dpdk_config (%s) for host ID (%s)' % (configs, self.host_id))
        self.dpdk_config = configs

    def set_vrouter_module_params(self, params):
        log.debug('Set vrouter_module_params (%s) for host ID (%s)' % (params, self.host_id))
        self.vrouter_module_params = params

    def set_virtual_gateway(self, configs):
        log.debug('Set vgw (%s) for host ID (%s)' % (configs, self.host_id))
        self.vgw = configs

    def set_bond_info(self, bond_info):
        log.debug('Set bond (%s) for host ID (%s)' % (bond_info, self.host_id))
        self.bond = bond_info

    def set_control_data(self, control_data):
        log.debug('Set control_data (%s) for host ID (%s)' % (control_data, self.host_id))
        self.control_data = control_data

    def set_static_route(self, static_route):
        log.debug('Set static_route (%s) for host ID (%s)' % (static_route, self.host_id))
        self.static_route = static_route

    def set_tor_agent(self, configs):
        log.debug('Set tor_agent (%s) for host ID (%s)' % (configs, self.host_id))
        self.tor_agent = configs

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

    def update(self):
        self.update_hosts()
        self.update_testbed()

    def update_hosts(self):
        for host_obj in self.hosts.values():
            host_obj.update()

    def update_testbed(self):
        self.set_testbed_ostype()
        self.set_host_params()
        self.update_host_ostypes()
        self.update_host_roles()
        self.update_tor_agent_info()
        #self.update_host_hypervisor()
        #self.update_host_bond_info()
        #self.update_host_control_data()
        #self.update_host_static_route()
        #self.update_host_vrouter_params()
        self.update_hosts_dpdk_info()

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

    def get_roles(self):
        host_dict = defaultdict(list)
        for role, hosts in self.roledefs.items():
            if role == 'build' or role == 'all':
                log.debug('Discarding role (%s)' % role)
                continue
            for host in hosts:
                host_dict[host].append(role)
        return host_dict

    def update_host_roles(self):
        host_dict = self.get_roles()
        for host_id, roles in host_dict.items():
            log.debug('Replacing cfgm role with config role name')
            if roles.count('cfgm') > 0:
                roles.remove('cfgm')
                roles.append('config')
            self.hosts[host_id].set_roles(roles)

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
            # we know roledefs never contain host definitions
            if dict_obj == 'hosts' or dict_obj == 'roledefs':
                continue
            for key in self.__dict__[dict_obj].keys():
              if key in self.hosts.keys():
                  if getattr(self.hosts[key], dict_obj, None) is None:
                      setattr(self.hosts[key], dict_obj, self.__dict__[dict_obj][key])

    @is_defined('ostypes')
    def update_host_ostypes(self):
        for host_id, os_type in self.ostypes.items():
            self.hosts[host_id].set_ostype(os_type)

    @is_defined('hypervisor')
    def update_host_hypervisor(self):
        for host_id, hypervisor in self.hypervisor.items():
            self.hosts[host_id].set_hypervisor(hypervisor)

    @is_defined('bond')
    def update_host_bond_info(self):
        for host_id, bond_info in self.bond.items():
            self.hosts[host_id].set_bond_info(bond_info)

    @is_defined('control_data')
    def update_host_control_data(self):
        for host_id, control_data in self.control_data.items():
            self.hosts[host_id].set_control_data(control_data)

    @is_defined('static_route')
    def update_host_static_route(self):
        for host_id, static_route in self.static_route.items():
            self.hosts[host_id].set_static_route(static_route)

    @is_defined('storage_node_config')
    def update_storage_node_configs(self):
        for host_id, config in self.storage_node_config.items():
            self.hosts[host_id].set_storage_node_configs(config)

    @is_defined('vgw')
    def update_virtual_gateway(self):
        for host_id, config in self.vgw.items():
            self.hosts[host_id].set_virtual_gateway(config)

    @is_defined('tor_agent')
    def update_tor_agent_info(self):
        for host_id, config in self.tor_agent.items():
            self.hosts[host_id].set_tor_agent(config)

    @is_defined('dpdk')
    def update_hosts_dpdk_info(self):
        for host_id, dpdk_info in self.dpdk.items():
            self.hosts[host_id].set_dpdk_configs(dpdk_info)

    @is_defined('vrouter_module_params')
    def update_host_vrouter_params(self):
        for host_id, vrouter_params in self.vrouter_module_params.items():
            self.hosts[host_id].set_vrouter_module_params(vrouter_params)


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

    def get_destination_variable_to_set(self, source_variable_name, destination_variable_top, translation_dict):
        if source_variable_name in translation_dict:
            name_format_dict = translation_dict[source_variable_name]
            destination_variable_name = name_format_dict["newname"]
            split_dest_v_name = destination_variable_name.split('.')
            tmp_dict = destination_variable_top
            for level in split_dest_v_name[:-1]:
                if level not in tmp_dict.keys():
                    tmp_dict[str(level)] = {}
                tmp_dict = tmp_dict[str(level)]
            tmp_dict[str(split_dest_v_name[-1])] = ""
            return tmp_dict, split_dest_v_name[-1], name_format_dict["newformat"]

    def set_if_defined(self, source_variable_name,
                       destination_variable, **kwargs):

        destination_variable_name = kwargs.get('destination_variable_name',
                                               source_variable_name)
        source_variable = kwargs.get('source_variable', self.testsetup)
        function = kwargs.get('function', getattr)
        to_string = kwargs.get('to_string', True)
        to_lower = kwargs.get('to_lower', False)
        is_boolean = kwargs.get('is_boolean', False)
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
                else:
                    value = str(value)

            destination_variable[destination_variable_name] = value

    def generate(self):
        log.debug('Generate Json with Dict data: %s' % self.dict_data)
        log.info('Generating Json File (%s)...' % self.jsonfile)
        with open(self.jsonfile, 'w') as fid:
            fid.write('%s\n' % json.dumps(self.dict_data, sort_keys=True,
                                          indent=4, separators=(',', ': ')))

class ServerJsonGenerator(BaseJsonGenerator):
    def __init__(self, testsetup, **kwargs):
        kwargs.update([('name', kwargs.get('name', 'server'))])
        super(ServerJsonGenerator, self).__init__(testsetup=testsetup, **kwargs)
        self.dict_data = {"server": []}

    def _initialize(self, hostobj):
        # set kernel upgrade 'yes' by default
        kernel_upgrade_flag = self.testsetup.testbed.env.get('kernel_upgrade', True)
        if kernel_upgrade_flag:
            kernel_upgrade = 'yes'
        else:
            kernel_upgrade = 'no'
        server_dict = {"id": hostobj.hostname,
                       "roles": hostobj.roles,
                       "cluster_id": self.cluster_id,
                       "password": hostobj.password,
                       "domain": hostobj.domain_name,
                       "parameters": {
                           "kernel_upgrade" : kernel_upgrade,
                            },
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
        server_dict['parameters']['provision']['contrail']['storage'] = {}
        server_dict['parameters']['provision']['contrail']['compute'] = {}
        static_route_list = []
        if getattr(hostobj, 'static_route', None) is not None:
            for staticroute in hostobj.static_route:
                static_route_dict = {}
                self.set_if_defined('gw', static_route_dict, source_variable=staticroute, function=dict.get, destination_variable_name='gateway')
                self.set_if_defined('intf', static_route_dict, source_variable=staticroute, function=dict.get, destination_variable_name='interface')
                self.set_if_defined('ip', static_route_dict, source_variable=staticroute, function=dict.get, destination_variable_name='network')
                self.set_if_defined('netmask', static_route_dict, source_variable=staticroute, function=dict.get, destination_variable_name='netmask')
                static_route_list.append(static_route_dict)
            if len(static_route_list) > 0:
                network_dict = server_dict["network"]
                network_dict["routes"] = static_route_list
        #Get the top of rack entries from testbed.py and append it to the server_dict dictionary
        if getattr(hostobj, 'tor_agent', None) is not None:
            tor_dict = {}
            switch_list = []
            #Go through the list of tor agents
            for toragent in hostobj.tor_agent:
                switchdict = {}
                #Get the host for which tor is applicable
                if toragent['tor_tsn_ip'] == hostobj.ip:
                    #Convert the key entries so that SM json likes it
                    self.set_if_defined('tor_agent_id', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='id')
                    self.set_if_defined('tor_ip', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='ip_address')
                    self.set_if_defined('tor_tunnel_ip', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='tunnel_ip_address')
                    self.set_if_defined('tor_type', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='type')
                    self.set_if_defined('tor_ovs_port', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='ovs_port')
                    self.set_if_defined('tor_ovs_protocol', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='ovs_protocol')
                    self.set_if_defined('tor_name', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='switch_name')
                    self.set_if_defined('tor_vendor_name', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='vendor_name')
                    self.set_if_defined('tor_product_name', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='product_name')
                    self.set_if_defined('tor_agent_http_server_port', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='http_server_port')
                    self.set_if_defined('tor_agent_ovs_ka', switchdict, source_variable=toragent, function=dict.get, destination_variable_name='keepalive_time')
                    switch_list.append(switchdict)
            if len(switch_list) > 0:
                switch_dict = defaultdict(list)
                for switches in switch_list:
                    switch_dict["switches"].append(switches)
                tor_dict["top_of_rack"] = dict(switch_dict)
                server_dict.update(tor_dict)
        return server_dict

    def update_bond_details(self, server_dict, hostobj):
        bond_dict = {"name": hostobj.bond['name'],
                     "type": 'bond',
                     "bond_options": {},
                     }
        if 'member' in hostobj.bond.keys():
            bond_dict['member_interfaces'] = hostobj.bond['member']
        if 'mode' in hostobj.bond.keys():
            bond_dict['bond_options']['mode'] = hostobj.bond['mode']
        if 'xmit_hash_policy' in hostobj.bond.keys():
            bond_dict['bond_options']['xmit_hash_policy'] = hostobj.bond['xmit_hash_policy']
        return bond_dict

    def update_static_route_info(self, server_dict, hostobj):
        if getattr(hostobj, 'static_route', None) is None:
            return server_dict
        server_dict['static_routes'] = hostobj.static_route
        return server_dict

    def update_control_data_info(self, server_dict, hostobj):
        if getattr(hostobj, 'control_data', None) is None:
            return server_dict
        server_dict['contrail'] = {"control_data_interface": hostobj.control_data['device']}
        if hostobj.control_data['device'].startswith('bond'):
            control_data_dict = self.update_bond_details(server_dict, hostobj)
        else:
            control_data_dict = {"name": hostobj.control_data['device']}
        control_data_dict["ip_address"] = hostobj.control_data['ip']
        self.set_if_defined('gw', control_data_dict,
                            source_variable=hostobj.control_data,
                            function=dict.get,
                            destination_variable_name='default_gateway')
        self.set_if_defined('vlan', control_data_dict,
                            source_variable=hostobj.control_data,
                            function=dict.get)

        server_dict['network']['interfaces'].append(control_data_dict)
        return server_dict

    def update_network_details(self, server_dict, hostobj):
        server_dict = self.update_control_data_info(server_dict, hostobj)
        server_dict = self.update_static_route_info(server_dict, hostobj)
        return server_dict

    def update_parameters_info(self, server_dict, hostobj):
        # disks
        if getattr(hostobj, 'storage_node_config', None):
            if 'disks' in hostobj.storage_node_config.keys() and \
               'journal' in  hostobj.storage_node_config.keys():
                journal = hostobj.storage_node_config['journal'][0]
                disks = hostobj.storage_node_config['disks']
                server_dict['parameters']['provision']['contrail']['storage']['storage_osd_disks'] = ["%s:%s" % (disk, journal) \
                    for disk in hostobj.storage_node_config['disks'] \
                    for journal in hostobj.storage_node_config['journal']]
            elif 'disks' in hostobj.storage_node_config.keys():
                server_dict['parameters']['provision']['contrail']['storage']['storage_osd_disks'] = hostobj.storage_node_config['disks']
            else:
                log.warn("No disks defined in storage_node_config")
            if 'chassis' in hostobj.storage_node_config.keys():
                server_dict['parameters']['provision']['contrail']['storage']['storage_chassis_id'] = hostobj.storage_node_config['chassis']
        if getattr(hostobj, 'roles', None) and self.storage_package_files:
            if 'storage-master' in hostobj.roles or \
               'storage-compute' in hostobj.roles:
               package_type, package_file = self.storage_package_files[0]
               version = ImageUtils.get_version(package_file, self.testsetup.os_type)
               image_id = ImageUtils.get_image_id(version, package_type)
               server_dict['parameters']['provision']['contrail']['storage']['storage_repo_id'] = image_id
        return server_dict


    def update_dpdk_info(self, server_dict, hostobj):
        server_dict['parameters']['provision']['contrail']['compute']['dpdk'] = {}
        if hostobj.dpdk_config and \
            hostobj.dpdk_config.get('huge_pages', ''):
            server_dict['parameters']['provision']['contrail']['compute']['dpdk']['huge_pages'] = hostobj.dpdk_config['huge_pages']
        if hostobj.dpdk_config and \
            hostobj.dpdk_config.get('coremask', ''):
            server_dict['parameters']['provision']['contrail']['compute']['dpdk']['core_mask'] = hostobj.dpdk_config['coremask']
        return server_dict

    def update(self):
        for host_id in self.testsetup.hosts:
            hostobj = self.testsetup.hosts[host_id]
            server_dict = self._initialize(hostobj)
            server_dict = self.update_network_details(server_dict, hostobj)
            server_dict = self.update_parameters_info(server_dict, hostobj)
            server_dict = self.update_dpdk_info(server_dict, hostobj)
            self.dict_data['server'].append(server_dict)

    def generate_json_file(self):
        self.update()
        self.generate()

class ClusterJsonGenerator(BaseJsonGenerator):
    def __init__(self, testsetup, **kwargs):
        kwargs.update([('name', kwargs.get('name', 'cluster'))])
        super(ClusterJsonGenerator, self).__init__(testsetup=testsetup, **kwargs)
        self.storage_keys = kwargs.get('storage_keys', None)
        self.dict_data = {"cluster": []}

    def _initialize(self):
        translation_dict = {}
        with open('/opt/contrail/server_manager/client/parameter-translation-dict.json') as json_file:
            translation_dict = json.load(json_file)
        cluster_dict = {"id": self.cluster_id, "parameters": {}}
        cluster_dict['parameters']['provision'] = {}
        for allowed_key in translation_dict:
            if "." in allowed_key:
                sub_dict_name = str(allowed_key).split('.')[0]
                sub_dict_key = str(allowed_key).split('.')[1]
                source_variable = getattr(self.testsetup, sub_dict_name, None)
            else:
                sub_dict_name = None
                sub_dict_key = None
                source_variable = self.testsetup
            if allowed_key in self.testsetup.testbed.__dict__.keys() \
                    or allowed_key in self.testsetup.testbed.env.keys() \
                    or (sub_dict_key and source_variable and sub_dict_key in dict(source_variable)):
                dest_var, dest_var_name, data_format = self.get_destination_variable_to_set(
                    allowed_key, cluster_dict['parameters']['provision'], translation_dict)
                to_lower = False
                if sub_dict_key:
                    source_variable_name = sub_dict_key
                    function_to_use=dict.get
                else:
                    function_to_use=getattr
                    source_variable_name = allowed_key
                if data_format == "boolean":
                    is_boolean = True
                else:
                    is_boolean = False
                self.set_if_defined(source_variable_name, dest_var, source_variable=source_variable,
                                    destination_variable_name=str(dest_var_name), to_lower=to_lower,
                                    is_boolean=is_boolean, function=function_to_use)
        return cluster_dict

    def generate_json_file(self):
        cluster_dict = self._initialize()
        self.dict_data['cluster'].append(cluster_dict)
        self.generate()

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

    def get_package_type(self, package_file, package_type):
        package_type = package_type.replace('_', '-').replace('-packages', '')
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

    def _initialize(self, package_file, package_type):
        version = ImageUtils.get_version(package_file, self.testsetup.os_type)
        image_id = ImageUtils.get_image_id(version, package_type)
        image_dict = {
            "id": image_id,
            "category": self.get_category(package_file),
            "version": version,
            "type": self.get_package_type(package_file, package_type),
            "path": package_file,
        }
        log.debug('Created Basic image_dict: %s' % image_dict)
        return image_dict

    def generate_json_file(self):
        for package_type, package_file in self.package_files:
            image_dict = self._initialize(package_file, package_type)
            self.dict_data['image'].append(image_dict)
            self.generate()

if __name__ == '__main__':
    args = Utils.parse_args(sys.argv[1:])
    log.info('Executing: %s' % " ".join(sys.argv))
    Utils.converter(args)
