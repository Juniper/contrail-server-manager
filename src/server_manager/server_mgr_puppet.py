#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import sys
import re
import datetime
import commands
import json
import pdb
import subprocess
from netaddr import *
import string
import textwrap
import shutil
import random 
import tempfile
import re
import yaml
import uuid
from server_mgr_err import *
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import SMProvisionLogger as ServerMgrProvlogger
from server_mgr_exception import ServerMgrException as ServerMgrException
from esxi_contrailvm import ContrailVM as ContrailVM
from contrail_defaults import *


class ServerMgrPuppet:
    _node_env_map_file = "puppet/node_mapping.json"

    def __init__(self, smgr_base_dir, puppet_dir):
        self._smgr_log = ServerMgrlogger()
        self._smgr_log.log(self._smgr_log.DEBUG, "ServerMgrPuppet Init")


        self.smgr_base_dir = smgr_base_dir
        self.puppet_directory = puppet_dir
        if not os.path.exists(os.path.dirname(puppet_dir)):
            os.makedirs(os.path.dirname(puppet_dir))
    # end __init__

    def storage_get_control_network_mask(self, provision_params,
        server, cluster):
        role_ips_dict = provision_params['roles']
        cluster_params = cluster.get('parameters', {})
        server_params = server.get('parameters', {})
        #openstack_ip = cluster_params.get("internal_vip", None)
        cluster_openstack_prov_params = (
            cluster_params.get("provision", {})).get("openstack", {})
        configured_external_openstack_ip = cluster_openstack_prov_params.get("external_openstack_ip", None)
        openstack_ip = ''
        self_ip = server.get("ip_address", "")
        if configured_external_openstack_ip:
            openstack_ip = configured_external_openstack_ip
        elif 'openstack' in role_ips_dict and len(role_ips_dict['openstack']) and self_ip not in role_ips_dict['openstack']:
            openstack_ip = role_ips_dict['openstack'][0]
        else:
            openstack_ip = self_ip

        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")
        subnet_address = ""
        intf_control = {}
        subnet_address = str(IPNetwork(
            openstack_ip + "/" + subnet_mask).network)

        if openstack_ip == configured_external_openstack_ip:
            return '"' + str(IPNetwork(subnet_address).network) + '/' + str(IPNetwork(subnet_address).prefixlen) + '"'

        self._smgr_log.log(self._smgr_log.DEBUG, "control-net : %s" % str( provision_params['control_net']))
        if provision_params['control_net'] [openstack_ip]:
            intf_control = eval(provision_params['control_net'] [openstack_ip])
            self._smgr_log.log(self._smgr_log.DEBUG, "openstack-control-net : %s" % str(intf_control ))

        for intf,values in intf_control.items():
            if intf:
                self._smgr_log.log(self._smgr_log.DEBUG, "ip_address : %s" % values['ip_address'])
                return '"' + str(IPNetwork(values['ip_address']).network) + '/'+ str(IPNetwork(values['ip_address']).prefixlen) + '"'
            else:
                self._smgr_log.log(self._smgr_log.DEBUG, "server_ip : %s" % values['server_ip'])
                return '"' + str(IPNetwork(provision_params['server_ip']).network) + '/'+ str(IPNetwork(provision_params['server_ip']).prefixlen) + '"'

        return '"' + str(IPNetwork(subnet_address).network) + '/'+ str(IPNetwork(subnet_address).prefixlen) + '"'

    def delete_node_entry(self, site_file, server_fqdn):
        tempfd, temp_file = tempfile.mkstemp()
        fh = os.fdopen(tempfd, "w")
        node_found = False
        brace_count = 0
        with open(site_file, "r") as site_fh:
            for line in site_fh:
                tokens = line.strip().split()
                if ((len(tokens) >= 2) and
                    (tokens[0] == "node") and
                    ((re.findall(r"['\"](.*?)['\"]", tokens[1]))[0] == server_fqdn)):
                    node_found = True
                #end if tokens...
                if not node_found:
                    fh.write(line)
                else:
                    # skip comments
                    if tokens[0].startswith("#"):
                        continue
                    # Skip lines till closing brace
                    if "{" in line:
                        brace_count += 1
                    if "}" in line:
                        brace_count -= 1
                    if brace_count == 0:
                        node_found = False
                # end else not node_found
            # end for
        # end with
        fh.close()
        shutil.copy(temp_file, site_file)
        os.chmod(site_file, 0644)
        os.remove(temp_file)
    # end def delete_node_entry

    def add_node_entry(
        self, site_file, server_fqdn,
        server, cluster, cluster_servers, puppet_version):
        cluster_params = cluster.get('parameters', {})
        data = ''
        data += "node \'%s\' {\n" %server_fqdn
        # Add Stage relationships
        data += '    stage{ \'first\': }\n'
        data += '    stage{ \'last\': }\n'
        data += '    stage{ \'compute\': }\n'
        data += '    stage{ \'pre\': }\n'
        data += '    stage{ \'post\': }\n'
        if 'tsn' in server['roles']:
            data += '    stage{ \'tsn\': }\n'
        if 'toragent' in server['roles']:
            data += '    stage{ \'toragent\': }\n'
        if 'storage-compute' in server['roles'] or 'storage-master' in server['roles']:
            data += '    stage{ \'storage\': }\n'
        data += '    Stage[\'pre\']->Stage[\'first\']->Stage[\'main\']->Stage[\'last\']->Stage[\'compute\']->'
        if 'tsn' in server['roles']:
            data += 'Stage[\'tsn\']->'
        if 'toragent' in server['roles']:
            data += 'Stage[\'toragent\']->'
        if 'storage-compute' in server['roles'] or 'storage-master' in server['roles']:
            data += 'Stage[\'storage\']->'
        data += 'Stage[\'post\']\n'

        # Add pre role
        data += '    class { \'::contrail::provision_start\' : state => \'provision_started\', stage => \'pre\' }\n'
        # Add common role
        data += '    class { \'::sysctl::base\' : stage => \'first\' }\n'
        data += '    class { \'::apt\' : stage => \'first\' }\n'
        data += '    class { \'::contrail::profile::common\' : stage => \'first\' }\n'
        #Include all roles manifest,Each manifest will execute only if that host
        #is configured to have a role.
        #Uninstall manifest will get executed when host_roles doesnt have that
        #role and contrail_roles[] facts has that role.
        #This implies that a role which is not configured is present on
        #the target and uninstall manifest will get executed.

        # Add keepalived (This class is no-op if vip is not configured.)
        data += '    include ::contrail::profile::keepalived\n'
        # Add haproxy (for config node)
        data += '    include ::contrail::profile::haproxy\n'
        # Add database role.
        data += '    include ::contrail::profile::database\n'
        # Add webui role.
        data += '    include ::contrail::profile::webui\n'
        # Add openstack role.
        data += '    include ::contrail::profile::openstack_controller\n'
        # Add ha_config role.
        data += '    include ::contrail::ha_config\n'
        # Add config provision role.
        data += '    include ::contrail::profile::config\n'
        # Add controller role.
        data += '    include ::contrail::profile::controller\n'
        # Add collector role.
        data += '    include ::contrail::profile::collector\n'
        # Add config provision role.
        if ((puppet_version < 3.0) and ('config' in server['roles'])):
            data += '    class { \'::contrail::profile::provision\' : stage => \'last\' }\n'
        # Add compute role
        data += '    class { \'::contrail::profile::compute\' : stage => \'compute\' }\n'

        # Add Tsn Role
        if 'tsn' in server['roles']:
            data += '    class { \'::contrail::profile::tsn\' :  stage => \'tsn\' }\n'
        # Add Toragent Role
        if 'toragent' in server['roles']:
            data += '    class { \'::contrail::profile::toragent\' :  stage => \'toragent\' }\n'
        # Add Storage Role
        if 'storage-compute' in server['roles'] or 'storage-master' in server['roles']:
            data += '    class { \'::contrail::profile::storage\' :  stage => \'storage\' }\n'
        # Add post role
        data += '    class { \'::contrail::provision_complete\' : state => \'post_provision_completed\', stage => \'post\' }\n'

        data += "}\n"
        with open(site_file, "a") as site_fh:
            site_fh.write(data)
        os.chmod(site_file, 0644)
        # end with
    # end def add_node_entry

    def add_node_entry_new(
        self, site_file, server_fqdn):
        data = "node \'%s\' {\n" %server_fqdn
        data += "   class { '::contrail::contrail_all': }\n"
        data += "}\n"
        with open(site_file, "a") as site_fh:
            site_fh.write(data)
        # end with
        os.chmod(site_file, 0644)
    # end def add_node_entry_new

    def initiate_esx_contrail_vm(self, server, esx_server):
        self._smgr_log.log(self._smgr_log.DEBUG, "esx_server")
        #call scripts to provision esx
        server_params = server.get("parameters", {})
        vm_params = {}
        vm_params['vm'] = "ContrailVM"
        vm_params['vmdk'] = "ContrailVM"
        vm_params['datastore'] = server_params.get('datastore', "/vmfs/volumes/datastore1")
        vm_params['eth0_mac'] = server.get('mac_address', '')
        vm_params['eth0_ip'] = server.get('ip_address', '')
        vm_params['eth0_pg'] = server_params.get('esx_fab_port_group', '')
        vm_params['eth0_vswitch'] = server_params.get('esx_fab_vswitch', '')
        vm_params['eth0_vlan'] = None
        vm_params['eth1_vswitch'] = server_params.get('esx_vm_vswitch', '')
        vm_params['eth1_pg'] = server_params.get('esx_vm_port_group', '')
        vm_params['eth1_vlan'] = "4095"
        vm_params['uplink_nic'] = server_params.get('esx_uplink_nic', '')
        vm_params['uplink_vswitch'] = server_params.get('esx_fab_vswitch', '')
        vm_params['server'] = esx_server.get('esx_ip', '')
        vm_params['username'] = 'root'
        vm_params['password'] = esx_server.get('esx_password', '')
        vm_params['thindisk'] =  server_params.get('esx_vmdk', '')
        vm_params['smgr_ip'] = server_params.get('smgr_ip', '');
        vm_params['domain'] =  server_params.get('domain', '')
        vm_params['vm_password'] = server_params.get('password', '')
        vm_params['vm_server'] = server_params.get('id', '')
        vm_params['vm_deb'] = server_params.get('vm_deb', '')
        out = ContrailVM(vm_params)
        self._smgr_log.log(self._smgr_log.DEBUG, "ContrilVM:" %(out))
    # end initiate_esx_contrail_vm

    def generate_tor_certs(self, switch_info, server_id, domain):
        tor_name = switch_info['name']
        tor_agent_id = switch_info['agent_id']
        tor_vendor_name = switch_info['vendor_name']
        tor_server_fqdn = server_id + '.' + domain
        contrail_module_path = '/etc/contrail_smgr/puppet/ssl/tor/'
        tor_cert_file = contrail_module_path + 'tor.' + str(tor_agent_id) + '.cert.pem'
        tor_key_file = contrail_module_path + 'tor.' + str(tor_agent_id) + '.privkey.pem'

        self._smgr_log.log(self._smgr_log.DEBUG, 'module path => %s' % contrail_module_path)
        if os.path.exists(tor_cert_file) and os.path.exists(tor_key_file):
            self._smgr_log.log(self._smgr_log.DEBUG, 'cert exists for %s host %s' % (tor_name, tor_server_fqdn))
            return
        cert_cmd ='openssl req -new -x509 -days 3650 -sha256 -newkey rsa:4096'\
            + ' -nodes -text -subj "/C=US/ST=Global/L=' + tor_name + '/O=' \
            + tor_vendor_name + '/CN=' + tor_server_fqdn + '" -keyout ' \
            + tor_key_file + ' -out ' + tor_cert_file

        if not os.path.exists(contrail_module_path):
            os.makedirs(contrail_module_path)
        self._smgr_log.log(self._smgr_log.DEBUG, 'ssl_cmd => %s' % cert_cmd)

        subprocess.check_call(cert_cmd, shell=True)

    # Function to change key name from new param key name to pre-3.0 puppet hiera names. 
    def xlate_key_to_pre_3_0(self, long_key, key):
        xlate_dict = {
            "contrail::analytics::analytics_ip_list"	: "collector_ip_list",
            "contrail::analytics::analytics_name_list"	: "collector_name_list",
            "contrail::analytics::data_ttl" 		: "analytics_data_ttl",
            "contrail::analytics::config_audit_ttl"	: "analytics_config_audit_ttl",
            "contrail::analytics::statistics_ttl"	: "analytics_statistics_ttl",
            "contrail::analytics::flow_ttl"		: "analytics_flow_ttl",
            "contrail::analytics::syslog_port"		: "analytics_syslog_port",
            "contrail::analytics::directory"		: "database_dir",
            "contrail::analytics::data_directory"	: "analytics_data_dir",
            "contrail::analytics::ssd_data_directory"	: "ssd_data_dir",
            "contrail::database::directory"		: "database_dir",
            "contrail::database::minimum_diskGB"	: "database_minimum_diskGB",
            "contrail::database::initial_token"		: "database_initial_token",
            "contrail::database::ip_port"		: "database_ip_port",
            "openstack::keystone::admin_password"	: "keystone_admin_password",
            "openstack::keystone::admin_user"		: "keystone_admin_user",
            "openstack::keystone::admin_tenant"		: "keystone_admin_tenant",
            "openstack::keystone::service_tenant"	: "keystone_service_tenant",
            "openstack::keystone::admin_token"		: "keystone_service_token",
            "openstack::keystone::auth_protocol"	: "keystone_auth_protocol",
            "openstack::keystone::auth_port"		: "keystone_auth_port",
            "openstack::keystone::insecure_flag"	: "keystone_insecure_flag",
            "openstack::region"				: "keystone_region_name",
            "contrail::ha::haproxy_enable"		: "haproxy_flag",
            "openstack::neutron::port"			: "quantum_port",
            "openstack::neutron::service_protocol"	: "neutron_service_protocol",
            "openstack::amqp::server_ip"		: "amqp_server_ip",
            "contrail::config::zookeeper_ip_port"	: "zk_ip_port",
            "contrail::config::healthcheck_interval"	: "hc_interval",
            "contrail::vmware::ip"			: "vmware_ip",
            "contrail::vmware::username"		: "vmware_username",
            "contrail::vmware::password"		: "vmware_password",
            "contrail::vmware::vswitch"			: "vmware_vswitch",
            "openstack::mysql::root_password"		: "mysql_root_password",
            "contrail::control::encapsulation_priority"	: "encap_priority",
            "contrail::vgw::public_subnet"		: "vgw_public_subnet",
            "contrail::vgw::public_vn_name"		: "vgw_public_vn_name",
            "contrail::vgw::public_interface"		: "vgw_public_interface",
            "contrail::vgw::public_gateway_routes"	: "vgw_public_gateway_routes",
            "contrail::storage::storage_name_list"	: "storage_hostnames"
        }
        return xlate_dict.get(long_key, key)
    # end of function to xlate key to pre_3_0

    def add_params_from_dict(self, in_dict, package, prefix=''):
        out_dict = {}
        package_params = package.get("parameters", {})
        if not(isinstance(in_dict, dict)):
            return out_dict
        for key, value in in_dict.iteritems():
            new_prefix = str("::".join(x for x in (prefix, key) if x))
            if (isinstance(value, dict) and
                (not value.pop("literal", False))):
                out_dict.update(self.add_params_from_dict(
                    value, package, new_prefix))
            else:
                # For pre3.0 contrail, we need to generate hiera data
                # in contrail::params::... format too. This code should
                # be removed when we stop supporting old format contrail (pre-3.0)
                if (package_params.get('puppet_version', 0.0) < 3.0):
                    out_dict["contrail::params::" + self.xlate_key_to_pre_3_0(new_prefix, key)] = value
                out_dict[new_prefix] = value
        return out_dict
    # end add_params_from_dict

    def add_cluster_provisioning_params(self, cluster, package):
        cluster_parameters = cluster.get("parameters", {})
        provision_params = cluster_parameters.get("provision", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_cluster_provisioning_params

    def add_server_provisioning_params(self, server, package):
        server_parameters = server.get("parameters", {})
        provision_params = server_parameters.get("provision", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_server_provisioning_params

    def add_package_provisioning_params(self, package):
        package_parameters = package.get("parameters", {})
        provision_params = package_parameters.get("provision", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_package_provisioning_params

    def add_cluster_calculated_params(self, cluster, package):
        provision_params = cluster.get("calc_params", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_cluster_calculated_params

    def add_server_calculated_params(self, server, package):
        provision_params = server.get("calc_params", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_server_calculated_params

    def add_package_calculated_params(self, package):
        provision_params = package.get("calc_params", {})
        return self.add_params_from_dict(provision_params, package)
    # end of add_package_calculated_params

    def add_sequencing_params(self, cluster, package):
        cluster_params = cluster.get('parameters', {})
        package_params = package.get('parameters', {})
        sequence_provisioning_available = package_params.get(
            'sequence_provisioning_available', False)
        sequence_provisioning = cluster_params.get(
            'sequence_provisioning', True)
        if (package_params.get('puppet_version', 0.0) >= 3.0):
            key = "sequencing"
        else:
            key = "params"
        sequencing_params = {}
        if sequence_provisioning_available and sequence_provisioning:
            sequencing_params['contrail'] = {}
            sequencing_params['contrail'][key] = {}
            sequencing_params['contrail'][key]['enable_post_provision'] = False
            sequencing_params['contrail'][key]['enable_pre_exec_vnc_galera'] = False
            sequencing_params['contrail'][key]['enable_post_exec_vnc_galera'] = False
            sequencing_params['contrail'][key]['enable_keepalived'] = False
            sequencing_params['contrail'][key]['enable_haproxy'] = False
            sequencing_params['contrail'][key]['enable_sequence_provisioning'] = True
            sequencing_params['contrail'][key]['enable_provision_started'] = True
            sequencing_params['contrail'][key]['enable_storage_master'] = False
            sequencing_params['contrail'][key]['enable_storage_compute'] = False
            for role in ['global_controller', 'loadbalancer', 'database', 'config', 'openstack',
                         'control', 'collector',
                         'webui', 'compute', 'tsn', 'toragent']:
                sequencing_params['contrail'][key][
                    'enable_'+role] = False
        return self.add_params_from_dict(sequencing_params, package)
    # end add_sequencing_params

    def build_contrail_hiera_file_new(
        self, hiera_filename, server,
        cluster, cluster_servers, package):
        cluster_params = cluster.get('parameters', {})
        # By default, sequence provisioning is On.
        server_params = server.get('parameters', {})
        hiera_params = {}
        hiera_params.update(self.add_cluster_calculated_params(cluster, package))
        hiera_params.update(self.add_server_calculated_params(server, package))
        hiera_params.update(self.add_package_calculated_params(package))
        hiera_params.update(self.add_cluster_provisioning_params(cluster, package))
        hiera_params.update(self.add_server_provisioning_params(server, package))
        hiera_params.update(self.add_package_provisioning_params(package))
        hiera_params.update(self.add_sequencing_params(
            cluster, package))
        # Dump the hiera_params in yaml file.
        data = yaml.dump(hiera_params, default_style='\'', indent=4)
        with open(hiera_filename, "w") as hiera_fh:
            hiera_fh.write(data)
    # end def build_contrail_hiera_file_new

    #generate random string
    def random_string(self, string_length=10):
        """Returns a random string of length string_length."""
        random = str(uuid.uuid4()) # Convert UUID format to a Python string.
        random = random.upper() # Make all characters uppercase.
        random = random.replace("-","") # Remove the UUID '-'.
        return random[0:string_length] # Return the random string.

    def build_hiera_files(
        self, hieradata_dir, provision_params,
        server, cluster, cluster_servers, package, serverDb):
        server_params = server.get("parameters", {})
        cluster_params = cluster.get("parameters", {})
        domain = server.get('domain', '')
        if not domain:
            domain = cluster_params.get('domain', '')
        server_fqdn = server['host_name'] + "." + domain
        contrail_hiera_file = hieradata_dir + server_fqdn + \
            "-contrail.yaml"
        # if cluster parameters has provision key, use new way of building Hiera file, else
        # continue with old way.
        if ("provision" in cluster_params):
            self.build_contrail_hiera_file_new(
                contrail_hiera_file, server,
                cluster, cluster_servers, package)
        # Check and add contrail-defaults.yaml
        contrail_defaults_file = hieradata_dir + "contrail-defaults.yaml"
        contrail_defaults_source = "/etc/contrail_smgr/contrail-defaults.yaml"
        if not os.path.exists(contrail_defaults_file) and os.path.exists(contrail_defaults_source):
            shutil.copy(contrail_defaults_source, contrail_defaults_file)

    # end def build_hieradata_files

    def modify_server_hiera_data(self, server_id, hiera_file, role_steps_list,
                                 enable=True):
        if not server_id or not hiera_file or not role_steps_list:
            return
        try:
            hiera_data_fp = open(hiera_file, 'r')
        except:
            return
        hiera_data_dict = yaml.load(hiera_data_fp)
        hiera_data_fp.close()
        if not hiera_data_dict:
            return
        for role_step_tuple in role_steps_list:
            if server_id == role_step_tuple[0]:
                role_step = role_step_tuple[1].replace('-', '_')
                key = 'contrail::sequencing::enable_' + role_step
                if key not in hiera_data_dict:
                    key = 'contrail::params::enable_' + role_step
                hiera_data_dict[key] = enable
        data = yaml.dump(hiera_data_dict, default_style='\'', indent=4)
        with open(hiera_file, "w") as hiera_fh:
            hiera_fh.write(data)
    # end modify_server_hiera_data

    def new_provision_server(
        self, provision_params, server, cluster, cluster_servers, package, serverDb):
        server_params = server.get("parameters", {})
        cluster_params = cluster.get("parameters", {})
        package_params = package.get("parameters", {})
        domain = server.get('domain', '')
        if not domain:
            domain = cluster_params.get('domain', '')
        server_fqdn = server['host_name'] + "." + domain
        env_name = package_params.get('puppet_manifest_version',"")
        env_name = env_name.replace('-', '_')
        site_file = self.puppet_directory + "environments/" + \
            env_name + "/manifests/site.pp"
        hieradata_dir = self.puppet_directory + "environments/" + \
            env_name + "/hieradata/"
        # Start contail VM if running compute on esx_server.
        if 'compute' in eval(server['roles']):
            esx_server_id = server_params.get('esx_server', None)
            if esx_server_id:
                esx_servers = serverDb.get_server(
                    {'id' : server_params['esx_server']}, detail=True)
                esx_server = esx_servers[0]
                if esx_server:
                    self.initiate_esx_contrail_vm(server, esx_server)
        # Build Hiera data for the server
        self.build_hiera_files(
            hieradata_dir, provision_params,
            server, cluster, cluster_servers, package, serverDb)
        # Create an entry for this node in site.pp.
        # First, delete any existing entry and then add a new one.
        self.delete_node_entry(site_file, server_fqdn)
        # Now add a new node entry
        puppet_version = package_params.get("puppet_version", 0.0)
        if (puppet_version >= 3.0):
            self.add_node_entry_new(
                site_file, server_fqdn)
        else:
            self.add_node_entry(
                site_file, server_fqdn, server,
                cluster, cluster_servers, puppet_version)

        # Add entry for the server to environment mapping in 
        # node_mapping.json file.
        self.update_node_map_file(server_fqdn, env_name)
    # end def new_provision_server

    # Function to remove puppet files and entries created when provisioning the server. This is called
    # when server is being reimaged. We do not want old provisioning data to be retained.
    def new_unprovision_server(self, server_id, server_domain):
        server_fqdn = server_id + "." + server_domain
        # Remove node to environment mapping from node_mapping.json file.
	node_env_dict = {}
        env_name = self.update_node_map_file(server_fqdn, None)
        if env_name is None:
            return
        # Remove server node entry from site.pp.
        site_file = self.puppet_directory + "environments/" + \
            env_name + "/manifests/site.pp"
        try:
            self.delete_node_entry(site_file, server_fqdn)
	except:
	    pass
        # Remove Hiera Data files for the server.
        hiera_datadir = self.puppet_directory + "environments/" + \
            env_name + "/hieradata/"
        try:
            os.remove(hiera_datadir + server_fqdn + "-contrail.yaml")
            os.remove(hiera_datadir + server_fqdn + "-openstack.yaml")
	except:
	    pass
    # end new_unprovision_server()

    # env_name empty string or None is to remove the entry from the map file.
    # env_name value specified will be updated to the map file.
    # env_name could be valid one or invalid manifest.
    #        invalid valid manifest is used to turn off the agent puppet run
    # server_fqdn is required for both update and delete of an entry
    def update_node_map_file(self, server_fqdn, env_name):
        if not server_fqdn:
            return None

        node_env_map_file = self.smgr_base_dir+self._node_env_map_file
        
        try:
            with open(node_env_map_file, "r") as env_file:
                node_env_dict = json.load(env_file)
            # end with
        except:
            msg = "Not able open environment map file %s" % (node_env_map_file)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return None

        if env_name:
            node_env_dict[server_fqdn] = env_name
            msg = "Add/Modify map file with env_name %s for server %s" % (env_name, server_fqdn)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
        else:
            env_name = node_env_dict.pop(server_fqdn, None)
            msg = "Remove server from map file for server %s" % (server_fqdn)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
            if not env_name:
                return env_name

        try:
            with open(node_env_map_file, "w") as env_file:
                json.dump(node_env_dict, env_file, sort_keys = True,
                          indent = 4)
            # end with
        except:
            msg = "Not able open environment map file %s for update" % (node_env_map_file)
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return None
        return env_name
    # end update_node_map_file

    def is_new_provisioning(self, puppet_manifest_version):
        environment = puppet_manifest_version.replace('-','_')
        if ((environment != "") and
            (os.path.isdir(
                    "/etc/puppet/environments/" + environment))):
            return True
        return False
    # end is_new_provisioning

    def provision_server(
        self, provision_params, server,
        cluster, cluster_servers, package,
        serverDb):

        # The new way to create necessary puppet manifest files and parameters data.
        # The existing method is kept till the new method is well tested and confirmed
        # to be working.
        self._sm_prov_log = ServerMgrProvlogger(cluster['id'])
        package_params = package.get("parameters", {})
        puppet_manifest_version = package_params.get(
            'puppet_manifest_version', "")
        environment = puppet_manifest_version.replace('-','_')
        if self.is_new_provisioning(puppet_manifest_version):
            self.new_provision_server(
                provision_params, server,
                cluster, cluster_servers, package, serverDb)
        else:
            # old puppet manifests not supported anymore, log message
            # and return
            self._sm_prov_log.log(
                "debug",
                "No environment for version found AND this version does not support old contrail puppet manifest (2.0 and before)")
            self._smgr_log.log(
                self._smgr_log.DEBUG,
                "No environment for version found AND this version does not support old contrail puppet manifest (2.0 and before)")
            self._sm_prov_log.log(
                "debug",
                "Use server manager version 2.21 or earlier if you have old style contrail puppet manifests")
            self._smgr_log.log(
                self._smgr_log.DEBUG,
                "Use server manager version 2.21 or earlier if you have old style contrail puppet manifests")
        # end else
    # end provision_server
# class ServerMgrPuppet

if __name__ == "__main__":
    pass
