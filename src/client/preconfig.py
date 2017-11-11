#!/usr/bin/env python

import argparse
from ast import literal_eval
import json
import logging
import paramiko
import os
import re
import subprocess
import sys
from netaddr import IPNetwork

# Testbed Converter Version
__version__ = '1.0'

log = logging.getLogger('preconfig')
log.setLevel(logging.DEBUG)

class Utils(object):
    @staticmethod
    def initialize_logger(log_file='preconfig.log', log_level=40):
        log = logging.getLogger('preconfig')
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
    def parse_args(args):
        parser = argparse.ArgumentParser(description='Server Manager Lite Preconfig Utility',
                                         add_help=True)
        parser.add_argument('--version',
                            action='version',
                            version=__version__,
                            help='Print version and exit')
        parser.add_argument('-v', action='count', default=0,
                            help='Increase verbosity. -vvv prints more logs')
        parser.add_argument('--server-json',
                            required=True,
                            help='Absolute path to testbed file')
        parser.add_argument('--server-manager-ip',
                            required=True,
                            help='IP Address of Server Manager Node')
        parser.add_argument('--server-manager-repo-port',
                            default=80,
                            help='Port Number of Server Manager Node which hosts repos')
        parser.add_argument('--log-file',
                            default='preconfig.log',
                            help='Absolute path of a file for logging')
        parser.add_argument('--sku',
                            default='mitaka',
                            help='Openstack SKU that is going to be provisioned')
        parser.add_argument('--key-path',
                            default=None,
                            help='ssh private key for passwordless access to the target servers')
        cliargs = parser.parse_args(args)
        if len(args) == 0:
            parser.print_help()
            sys.exit(2)
        Utils.is_file_exists(cliargs.server_json)

        # update log level and log file
        log_level = [logging.ERROR, logging.WARN, \
                     logging.INFO, logging.DEBUG]
        cliargs.v = cliargs.v if cliargs.v <= 3 else 3
        Utils.initialize_logger(log_file=cliargs.log_file,
                                log_level=log_level[cliargs.v])
        return cliargs

    @staticmethod
    def preconfig(cliargs):
        hosts = []
        with open(cliargs.server_json, 'r') as fid:
            contents = fid.read()
        server_json = json.loads(contents)
        for host_dict in server_json['server']:
            print "Configuring  => " + host_dict['id']
            hostobj = Server(host_dict, args.server_manager_ip,
                             args.server_manager_repo_port, cliargs.key_path)
            try:
                hostobj.connect()
                if not hostobj.check_compute_provisioned():
                    hostobj.preconfig(sku=cliargs.sku)
            except:
                if "contrail-compute" in getattr(hostobj, 'roles', []):
                    srv_params = getattr(hostobj, 'parameters', {})
                    esxi_params = srv_params.get('esxi_parameters', None)
                    if esxi_params:
                        log.error('ERROR_IGNORED: Unable to connect Host (%s) ' \
                        'but ignoring it since it is on ESXI host' % (hostobj.ip))
                        pass
                    else:
                        raise RuntimeError('Connection to (%s) Failed' % hostobj.ip)
                else:
                    raise RuntimeError('Connection to (%s) Failed' % hostobj.ip)
            hosts.append(hostobj)

    @staticmethod
    def get_net_size(netmask):
        netmask_parts = netmask.split('.')
        binary_str = ''
        for octet in netmask_parts:
            binary_str += bin(int(octet))[2:].zfill(8)
        return str(len(binary_str.rstrip('0')))


class Server(object):
    def __init__(self, server_dict, server_manager_ip,
                 server_manager_repo_port=9003, keypath=None):
        self.key_path = None
        self.server_dict = server_dict
        self.server_manager_ip = server_manager_ip
        self.server_manager_repo_port = server_manager_repo_port
        self.connection = paramiko.SSHClient()
        self.connection_timeout = 5
        self.username = 'root'
        self.export_server_info()
        self.os_version = ()
        if keypath is not None:
           self.key_path = keypath
        elif server_dict.get('parameters') and server_dict['parameters'].get('auth'):
           self.key_path = server_dict['parameters']['auth'].get('ssh_private_key_path')
        elif 'password' not in server_dict:
            log.error('ERROR: Either the server key path or password has to be specified for the server %s in the json file'%(server_dict['id']))
            raise RuntimeError('Either the server key path or password has to be specified for the server %s in the json file'%(server_dict['id']))
           
        self.extra_packages_12_04 = ['puppet=3.7.3-1puppetlabs1', 'python-netaddr',
                                     'ifenslave-2.6', 'sysstat',
                                     'ethtool', 'vlan']
        self.extra_packages_14_04 = ['puppet=3.7.3-1puppetlabs1', 'python-netaddr',
                                     'ifenslave-2.6', 'sysstat',
                                     'ethtool', 'vlan', 'i40e-dkms', 'bnxt-en-dkms']
        self.extra_packages_16_04 = ['puppet=3.8.5-2', 'ruby-augeas', 'python-netaddr',
                                     'ifenslave-2.6', 'sysstat',
                                     'ethtool', 'vlan', 'i40e-dkms', 'bnxt-en-dkms']
        self.extra_packages_16_04_no_puppet = ['python-netaddr',
                                     'ifenslave-2.6', 'sysstat',
                                     'ethtool', 'vlan', 'i40e-dkms', 'bnxt-en-dkms']

    def __del__(self):
        log.info('Disconnecting...')
        self.disconnect()

    def export_server_info(self):
        for key, value in self.server_dict.items():
            setattr(self, key, value)

    def set_mgmt_interface(self):
        self.mgmt_iface = self.network['management_interface']

    def set_mgmt_ip_address(self, ):
        self.set_mgmt_interface()
        self.sm = False
        for iface_dict in self.network['interfaces']:
            if iface_dict.get('ip_address', None):
               ip = str(IPNetwork(iface_dict['ip_address']).ip)
               cidr = str(IPNetwork(iface_dict['ip_address']).prefixlen)
               if iface_dict['name'] == self.mgmt_iface:
                   self.ip, self.cidr = ip, cidr
               if ip == self.server_manager_ip:
                   self.sm = True

    def verify_self_host(self):
        ping_cmd = 'ping -q -c 1 %s > /dev/null 2>@1' %(self.id)
        host_cmd = 'grep %s /etc/hosts | grep -v "^[ ]*#"' %(self.id)
        status, old_entry = self.exec_cmd(host_cmd)
        old_entry = old_entry.strip()
        if status:
            log.info('Seems host id is not configured')
            log.info('Adding host id alias to /etc/hosts file')
            puppet_cmd = 'echo %s %s.%s %s >> /etc/hosts' % (self.ip , self.id, self.domain, self.id)
            print "HOST CMD: " + puppet_cmd
            self.exec_cmd(puppet_cmd, error_on_fail=True)
        #else:
            #log.info('Seems puppet host is already configured. ' \
                     #'Replacing with Server Manager (%s) entry' % self.server_manager_ip)
            #self.exec_cmd(r"sed -i 's/%s/%s puppet/g' /etc/hosts" % (
                              #old_entry, self.server_manager_ip),
                          #error_on_fail=True)

        log.debug('Verify PING to host after configuration')
        self.exec_cmd(ping_cmd, error_on_fail=True)

    def connect_using_key(self, ssh, ip, username, keypath):
       try:
           ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
           privatekeyfile = os.path.expanduser(keypath)
           mykey = paramiko.RSAKey.from_private_key_file(privatekeyfile)
           ssh.connect(ip, username=username, pkey = mykey)
           return ssh
       except Exception, err:
            log.error('ERROR: %s' % err)
            log.error('ERROR: Unable to connect Host (%s) with username(%s) ' \
                  'and key' % (ip, username))
            raise RuntimeError('Connection to (%s) Failed' % self.ip)

    def connect(self):
        self.set_mgmt_ip_address()
        self.connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.key_path:
                self.connect_using_key(self.connection,self.ip, self.username, self.key_path)
            else:
                self.connection.connect(self.ip, username=self.username, \
                               password=self.password, \
                               timeout=self.connection_timeout)
                log.info('Connected to Host (%s)' % self.ip)
        except Exception, err:
            log.error('ERROR: %s' % err)
            log.error('ERROR: Unable to connect Host (%s) with username(%s) ' \
                  'and password(%s)' % (self.ip, self.username, self.password))
            raise RuntimeError('Connection to (%s) Failed' % self.ip)

    def disconnect(self):
        self.connection.close()

    def local_exec_cmd(self, cmd, error_on_fail=False):
        exit_status = 0
        log.info('[localhost]: %s' % cmd)
        proc = subprocess.Popen(cmd, shell=True,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT,
                                          stdin=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            exit_status = 1
            log.error(stdout)
            log.error(stderr)
            if error_on_fail:
                raise RuntimeError('Command (%s) Failed' % cmd)
        return exit_status, stdout, stderr

    def exec_cmd(self, cmd, smLocal=False,error_on_fail=False):
        exit_status = 1
        output = None
        magic_pattern = r'001902803704605506407308209100'
        original_cmd = cmd
        cmd += ' && echo %s' % magic_pattern
        log.info('[%s]: %s' % (self.ip, original_cmd))
        log.debug('[%s]: %s' % (self.ip, cmd))
        if smLocal:
            exit_status, stdout, stderr = self.local_exec_cmd(original_cmd)
        else:
            stdin, stdout, stderr = self.connection.exec_command(cmd)
        # check stderr is pending
        if not smLocal:
            output = stdout.read()
        else:
            output = stdout
        log.debug(output)
        if (not smLocal) and output.count(magic_pattern) > 0:
            exit_status = 0
            output = re.sub(r'%s\n$' % magic_pattern, '', output, 1)

        if exit_status:
            log.warn('Cmd (%s) Failed' % cmd)
            if not smLocal:
                log.warn('%s' % stderr.read())
            else:
                log.warn('%s' % stderr)

        if error_on_fail and exit_status:
            log.error('[error_on_fail]: Cmd (%s) Failed' % original_cmd)
            raise RuntimeError('[error_on_fail]: Cmd (%s) Failed' % original_cmd)
        return exit_status, output

    def get_os_version(self):
        log.debug('Retrieve OS version')
        cmd = r'python -c "import platform; print (platform.linux_distribution())"'
        status, output = self.exec_cmd(cmd)
        if status != 0:
          cmd = r'python3 -c "import platform; print (platform.linux_distribution())"'
          status, output = self.exec_cmd(cmd)
          version_info = output
        version_info = literal_eval(output)
        return version_info

    def set_os_version(self):
        self.os_version = self.get_os_version()

    def check_compute_provisioned(self):
        # if this compute role and vhost present return true
        if "contrail-compute" in getattr(self, 'roles', []):
            cmd = 'grep -r "set vhost0 address" /etc/network/interfaces*'
            status, output = self.exec_cmd(cmd)
            if status == 0:
                return True
        return False

    def preconfig(self, sku='mitaka'):
        self.set_os_version()
        #self.preconfig_verify_domain()
        self.preconfig_hosts_file(sku)
        self.preconfig_unauthenticated_packages()
        self.preconfig_repos(sku)
        self.preconfig_1604_repos(sku)
        self.install_packages(sku)
        self.setup_interface()
        # Setup static routes if defined
        if getattr(self, 'network', None) and 'routes' in self.network and len(self.network['routes']) > 0:
            self.setup_static_routes()
        self.preconfig_ntp_config()
        if sku != 'ocata':
            self.preconfig_puppet_config()

    def verify_puppet_host(self):
        ping_cmd = r'ping -q -c 1 puppet > /dev/null 2>@1'
        puppet_cmd = r'grep puppet /etc/hosts | grep -v "^[ ]*#"'
        status, old_entry = self.exec_cmd(puppet_cmd)
        old_entry = old_entry.strip()
        if status:
            log.info('Seems puppet host is not configured')
            log.info('Adding puppet alias to /etc/hosts file')
            puppet_cmd = 'echo %s puppet >> /etc/hosts' % self.server_manager_ip
            self.exec_cmd(puppet_cmd, error_on_fail=True)
        else:
            log.info('Seems puppet host is already configured. ' \
                     'Replacing with Server Manager (%s) entry' % self.server_manager_ip)
            self.exec_cmd(r"sed -i 's/%s/%s puppet/g' /etc/hosts" % (
                              old_entry, self.server_manager_ip),
                          error_on_fail=True)

        log.debug('Verify puppet host after configuration')
        self.exec_cmd(ping_cmd, error_on_fail=True)

    def verify_setup_hostname(self):
        if not self.id:
            log.error('Hostname is not configured')
            raise RuntimeError('Hostname is not configured for (%s)' % self.ip)

    def preconfig_hosts_file(self, sku):
        if sku != 'ocata':
            self.verify_puppet_host()
        self.verify_self_host()
        self.verify_setup_hostname()

    def preconfig_verify_domain(self):
        if self.domain == "":
            log.error('Domain name is not configured. ' \
                      'All target nodes has to be setup with proper domain name')
            raise RuntimeError('Domain name is not configured for (%s)' % self.ip)

    def preconfig_unauthenticated_packages(self):
        apt_auth = r'APT::Get::AllowUnauthenticated \"true\"\;'
        status, output = self.exec_cmd('grep --quiet \"^%s\" /etc/apt/apt.conf' % apt_auth)
        if status:
            log.info('Configure Allow Unauthenticated true')
            self.exec_cmd('echo %s >> /etc/apt/apt.conf' % apt_auth, error_on_fail=True)

    def add_std_1604_repos(self):
        default_entries = [
            "deb http://archive.ubuntu.com/ubuntu xenial main universe multiverse",
            "deb http://archive.ubuntu.com/ubuntu xenial-updates main universe multiverse"
        ]
        for x in default_entries:
            cmd = "echo '%s' >> /etc/apt/sources.list" % x
            self.exec_cmd(cmd)

    def preconfig_1604_repos(self, sku):
        os_type, version, misc = self.os_version
        if os_type.lower() == 'ubuntu' and version != '16.04':
            return

        # This is required because ocata kolla-ansible requires internet repos to pull
        # in certain packages. Once these packages are made available in
        # contrail repos, this can be removed
        if sku == 'ocata':
            self.add_std_1604_repos()

        repo_entry = r'deb http://%s:%s/thirdparty_packages_ubuntu_1604/ ./' % (self.server_manager_ip, self.server_manager_repo_port)
        repo_entry_verify = r'%s.*\/thirdparty_packages_ubuntu_1604' % self.server_manager_ip
        status, output = self.exec_cmd('apt-cache policy | grep "%s"' % repo_entry_verify)
        if status:
            log.info('/etc/apt/sources.list has no thirdparty_packages 1604 '
                     'repo entry')
            log.debug('Adding Repo Entry (%s) to /etc/apt/sources.list' % repo_entry)
            self.exec_cmd('echo >> /etc/apt/sources.list', error_on_fail=True)
            self.exec_cmd(r"sed -i '1 i\%s' /etc/apt/sources.list" % repo_entry)
            self.exec_cmd('apt-get update')
            self.exec_cmd('apt-cache policy | grep "%s"' % repo_entry_verify,
                          error_on_fail=True)
        else:
            self.exec_cmd('apt-get update')

    def preconfig_repos(self, sku):
        repo_entry = r'deb http://%s:%s/thirdparty_packages/ ./' % (self.server_manager_ip, self.server_manager_repo_port)
        repo_entry_verify = r'%s.*\/thirdparty_packages' % self.server_manager_ip
        status, output = self.exec_cmd('apt-cache policy | grep "%s"' % repo_entry_verify)
        if status:
            log.info('/etc/apt/sources.list has no thirdparty_packages '
                     'repo entry')
            log.debug('Backup existing sources.list')
            self.exec_cmd(r'mv /etc/apt/sources.list '\
                          '/etc/apt/sources.list_$(date +%Y_%m_%d__%H_%M_%S).contrailbackup')
            log.debug('Adding Repo Entry (%s) to /etc/apt/sources.list' % repo_entry)
            self.exec_cmd('echo >> /etc/apt/sources.list', error_on_fail=True)
            self.exec_cmd(r"sed -i '1 i\%s' /etc/apt/sources.list" % repo_entry)
            self.exec_cmd('apt-get update')
            self.exec_cmd('apt-cache policy | grep "%s"' % repo_entry_verify,
                          error_on_fail=True)
        else:
            self.exec_cmd('apt-get update')

    def install_packages(self, sku):
        os_type, version, misc = self.os_version
        if os_type.lower() == 'ubuntu' and version == '12.04':
            packages_list = self.extra_packages_12_04
        elif os_type.lower() == 'ubuntu' and version == '14.04':
            packages_list = self.extra_packages_14_04
        elif os_type.lower() == 'ubuntu' and version == '16.04':
            if sku != 'ocata':
                packages_list = self.extra_packages_16_04
            else:
                packages_list = self.extra_packages_16_04_no_puppet
        else:
            raise RuntimeError('UnSupported OS type (%s)' % self.os_version)

        for package in packages_list:
            self.exec_cmd('DEBIAN_FRONTEND=noninteractive apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install %s' % package, error_on_fail=True)
        # remove the existing the driver to install the one you want
        self.exec_cmd('rmmod i40e')
        self.exec_cmd('modprobe i40e')
        self.exec_cmd('rmmod bnxt_en')
        self.exec_cmd('modprobe bnxt_en')
        self.exec_cmd('update-initramfs -k all -u')

    def is_already_bond_member(self, name):
        cmd = "cat /sys/class/net/" +name.strip() +"/master/bonding/slaves"
        status, output = self.exec_cmd(cmd)
        if not status:
            members_list = output.split()
            if name in members_list:
                return True
        return False

    def verify_interface_ip(self, interface, ip):
        return self.exec_cmd('ip addr show %s | grep %s' % (interface, ip), self.sm)

    def verify_static_route_ip(self, inet_prefix, device):
        return self.exec_cmd('ip route show %s | grep %s' % (inet_prefix, device), self.sm)

    def exec_setup_interface(self, iface_info, error_on_fail=True):
        iface_script_path = '/opt/contrail/bin/interface_setup.py'
        cmd = r'%s ' % iface_script_path
        if 'parent_interface' in iface_info.keys():
            device = iface_info['parent_interface']
        else:
            device = iface_info['name']
        cmd += r'--device %s ' % (device)
        ip_address = iface_info.get('ip_address', None)
        if ip_address:
            cmd += r'--ip %s ' % (ip_address)
        if 'member_interfaces' in iface_info.keys() and len(iface_info['member_interfaces']) > 0 :
            cmd += r'--members %s ' % " ".join(iface_info['member_interfaces'])
        if iface_info.get('ip_address', '') == self.ip and 'default_gateway' in iface_info.keys():
            cmd += r'--gw %s ' % iface_info['default_gateway']
        if 'mtu' in iface_info.keys():
            cmd += r'--mtu %s ' % iface_info['mtu']
        if 'vlan' in iface_info.keys():
            cmd += r'--vlan %s ' % iface_info['vlan']
        if 'bond_options' in iface_info.keys():
            cmd += r"--bond-opts '%s '" % json.dumps(iface_info['bond_options'])
        status, output = self.exec_cmd(cmd, self.sm)
        if error_on_fail and status:
            raise RuntimeError('Setup Interface failed for ' \
                               'Iface Info (%s)' % iface_info)
        return status, output

    def exec_setup_static_routes(self, interface, network, gateway, netmask, vlan, error_on_fail=True):
        iface_script_path = "/opt/contrail/bin/staticroute_setup.py"
        cmd = r'%s ' % iface_script_path
        if len(interface) > 0:
            cmd += r'--device %s ' % interface
        if len(network) > 0:
            cmd += r'--network %s ' % network
        if len(gateway) > 0:
            cmd += r'--gw %s ' % gateway
        if len(netmask) > 0:
            cmd += r'--netmask %s ' % netmask
        if len(vlan) > 0:
            cmd += r'--vlan %s ' % vlan
        status, output = self.exec_cmd(cmd)
        if error_on_fail and status:
            raise RuntimeError('Setup static routes failed for ' \
                               'Route Info (%s)' % cmd)
        return status, output

    def setup_interface(self):
        script_path = os.path.abspath(sys.argv[0])
        iface_script_path = os.path.join(os.path.dirname(script_path), 'interface_setup.py')
        if self.sm:
            self.exec_cmd('mkdir -p /opt/contrail/bin/', self.sm)
            self.exec_cmd('cp %s /opt/contrail/bin/interface_setup.py' % iface_script_path, self.sm)
            self.exec_cmd('chmod 755 /opt/contrail/bin/interface_setup.py', self.sm)
        else:
            sftp_connection = self.connection.open_sftp()
            self.exec_cmd('mkdir -p /opt/contrail/bin/')
            sftp_connection.put(iface_script_path,
                            '/opt/contrail/bin/interface_setup.py')
            self.exec_cmd('chmod 755 /opt/contrail/bin/interface_setup.py')
        for iface_info in self.network['interfaces']:
            if 'ip_address' in iface_info.keys():
                status, output = self.verify_interface_ip(iface_info['name'],
                                                          iface_info['ip_address'])
                if not status:
                    log.warn('Interface (%s) already configured with ' \
                             'IP Address (%s)' % (iface_info['name'],
                                                  iface_info['ip_address']))
                else:
                    self.exec_setup_interface(iface_info)
            elif self.is_already_bond_member(iface_info['name']):
                 log.warn('Interface (%s) already a member of the bond interfaces', \
                            (iface_info['name']))
            else:
                self.exec_setup_interface(iface_info)

    def setup_static_routes(self):
        interface =""
        network=""
        gateway=""
        netmask=""
        vlan=""
        script_path = os.path.abspath(sys.argv[0])
        staticroute_script_path = os.path.join(os.path.dirname(script_path), 'staticroute_setup.py')
        if self.sm:
            self.exec_cmd('mkdir -p /opt/contrail/bin/', self.sm)
            self.exec_cmd('cp %s /opt/contrail/bin/staticroute_setup.py' % staticroute_script_path, self.sm)
            self.exec_cmd('chmod 755 /opt/contrail/bin/staticroute_setup.py', self.sm)
        else:
            sftp_connection = self.connection.open_sftp()
            self.exec_cmd('mkdir -p /opt/contrail/bin/')
            sftp_connection.put(staticroute_script_path, '/opt/contrail/bin/staticroute_setup.py')
            self.exec_cmd('chmod 755 /opt/contrail/bin/staticroute_setup.py')
        for static_route in self.network['routes']:
            inet_prefix = str(static_route['network']) + "/" + str(Utils.get_net_size(static_route['netmask']))
            status, output = self.verify_static_route_ip(inet_prefix, static_route['interface'])
            if not status:
                log.warn('Static Route for interface (%s) already configured with ' \
                         'IP Address (%s)' % (static_route['interface'],
                                              static_route['network']))
                return
            else:
		interface += r'%s ' % (static_route['interface'])
		if 'network' in static_route.keys():
		    network += r'%s ' % static_route['network']
		if 'gateway' in static_route.keys():
		    gateway += r'%s ' % static_route['gateway']
		if 'netmask' in static_route.keys():
		    netmask += r'%s ' % static_route['netmask']
		if 'vlan' in static_route.keys():
		    vlan += r'%s ' % static_route['vlan']
        self.exec_setup_static_routes(interface, network, gateway, netmask, vlan)

    def check_ntp_status(self):
        status, output = self.exec_cmd(r'ntpq -pn | grep "%s" ' % self.server_manager_ip)
        if status:
            self.setup_ntp()

    def setup_ntp(self):
        log.debug('Install ntp package')
        self.exec_cmd('DEBIAN_FRONTEND=noninteractive apt-get -y install ntp', error_on_fail=True)
        log.debug('Setup NTP configuration')
        self.exec_cmd('ntpdate %s' % self.server_manager_ip)
        log.debug('Backup existing ntp.conf')
        self.exec_cmd(r'mv /etc/ntp.conf /etc/ntp.conf.$(date +%Y_%m_%d__%H_%M_%S).contrailbackup',
                      error_on_fail=True)
        self.exec_cmd('touch /var/lib/ntp/drift', error_on_fail=True)
        ntp_config = 'driftfile /var/lib/ntp/drift\n' \
                     'server %s\n' \
                     'restrict 127.0.0.1\n' \
                     'restrict -6 ::1\n' \
                     'includefile /etc/ntp/crypto/pw\n' \
                     'keys /etc/ntp/keys' % self.server_manager_ip
        if self.ip == self.server_manager_ip:
            ntp_config = ntp_config.replace('server %s' % self.server_manager_ip, 'server 127.127.1.0  iburst maxpoll 9')
        self.exec_cmd(r'echo "%s" >> /etc/ntp.conf' % ntp_config,
                      error_on_fail=True)

    def restart_ntp_service(self):
        self.exec_cmd('service ntp restart', error_on_fail=True)

    def preconfig_ntp_config(self):
        self.check_ntp_status()
        self.restart_ntp_service()

    def setup_puppet_configs(self):
        log.info('Setup puppet Configs')
        puppet_config = '[agent]\n' \
                        'pluginsync = true\n' \
                        'ignorecache = true\n' \
                        'usecacheonfailure = false\n' \
                        'ordering = manifest\n' \
                        'report = true\n' \
                        'stringify_facts = false\n' \
                        '[main]\n' \
                        'runinterval = 10\n' \
                        'configtimeout = 500\n'
        self.exec_cmd(r'cp /etc/puppet/puppet.conf /etc/puppet/puppet.conf.$(date +%Y_%m_%d__%H_%M_%S).contrailbackup',
                      error_on_fail=True)
        self.exec_cmd(r'echo "%s" >> /etc/puppet/puppet.conf' % puppet_config,
                      error_on_fail=True)

    def update_default_puppet(self):
        log.info('Update default puppet config file for non-server-manager node')
        self.exec_cmd(r'sed -i "s/initialize(name, path, source, ignore = nil, environment = nil, source_permissions = :ignore)/initialize(name, path, source, ignore = nil, environment = nil, source_permissions = :use)/g" /usr/lib/ruby/vendor_ruby/puppet/configurer/downloader.rb', error_on_fail=True)

    def remove_puppet_ssl(self):
        log.info('Remove puppet ssl for non-server-manager node')
        if not self.sm:
            if self.domain:
                fqdn = '%s.%s' % (self.id, self.domain)
            else:
                fqdn = self.id
            self.local_exec_cmd(r'puppet cert list %s > /dev/null 2>@1 && puppet cert clean %s > /dev/null 2>@1' % (fqdn, fqdn))
            #self.exec_cmd(r'find /var/lib/puppet/ssl -name %s*.pem -delete' % fqdn, error_on_fail=True)
            self.exec_cmd(r'rm -rf /var/lib/puppet/ssl')

    def restart_puppet_service(self):
        self.exec_cmd(r'service puppet restart', error_on_fail=True)

    def preconfig_puppet_config(self):
        self.setup_puppet_configs()
        self.remove_puppet_ssl()
        self.update_default_puppet()

if __name__ == '__main__':
    args = Utils.parse_args(sys.argv[1:])
    log.info('Executing: %s' % " ".join(sys.argv))
    Utils.preconfig(args)

