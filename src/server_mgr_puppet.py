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
import openstack_hieradata
import yaml
import uuid
from server_mgr_err import *
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
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

    #API to return control interfaces IP address 
    # else return MGMT IP address
    def get_control_ip(self, provision_params, mgmt_ip):
        intf_control = {}
        """
        if 'contrail_params' in  provision_params:
            contrail_dict = eval(provision_params['contrail_params'])
            control_data_intf = contrail_dict['control_data_interface']
            if provision_params['interface_list'] and \
                     provision_params['interface_list'] [control_data_intf]:
                control_data_ip = provision_params['interface_list'] \
                                [control_data_intf] ['ip']
            if control_data_ip:
                return '"' + str(IPNetwork(control_data_ip).ip) + '"'
            else:
                return '"' + provision_params['server_ip'] + '"'
        """
        if provision_params['control_net'] [mgmt_ip]:
            intf_control = eval(provision_params['control_net'] [mgmt_ip]) 
        for intf,values in intf_control.items():
            if intf:
                return str(IPNetwork(values['ip_address']).ip)
            else:
                return provision_params['server_ip']
        return mgmt_ip
    # end get_control_ip

    def storage_get_control_network_mask(self, provision_params,
        server, cluster):
        role_ips_dict = provision_params['roles']
        cluster_params = cluster.get('parameters', {})
        server_params = server.get('parameters', {})
        #openstack_ip = cluster_params.get("internal_vip", None)
        cluster_openstack_prov_params = (
            cluster_params.get("provision", {})).get("openstack", {})
        configured_external_keystone_ip = cluster_openstack_prov_params.get("keystone_ip", None)
        openstack_ip = ''
        self_ip = server.get("ip_address", "")
        if configured_external_keystone_ip:
            openstack_ip = configured_external_keystone_ip
        elif self_ip in role_ips_dict['openstack']:
            openstack_ip = self_ip
        elif 'openstack' in role_ips_dict:
            openstack_ip = role_ips_dict['openstack'][0]
        else:
            msg = "Openstack role not defined for cluster AND External Openstack not configured in cluster parameters.\n " \
                  "The cluster needs to point to at least one Openstack node.\n"
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)

        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")
        subnet_address = ""
        intf_control = {}
        subnet_address = str(IPNetwork(
            openstack_ip + "/" + subnet_mask).network)

        if openstack_ip == configured_external_keystone_ip:
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

    def add_cluster_parameters(self, cluster_params):
        cluster_params_mapping = {
            "uuid" : ["uuid", "string"],
            "internal_vip" : ["internal_vip", "string"],
            "external_vip" : ["external_vip", "string"],
            "contrail_internal_vip" : ["contrail_internal_vip", "string"],
            "contrail_external_vip" : ["contrail_external_vip", "string"],
            "internal_virtual_router_id" : ["internal_virtual_router_id", "integer"],
            "external_virtual_router_id" : ["external_virtual_router_id", "integer"],
            "contrail_internal_virtual_router_id" : ["contrail_internal_virtual_router_id", "integer"],
            "contrail_external_virtual_router_id" : ["contrail_external_virtual_router_id", "integer"],
            "analytics_data_ttl" : ["analytics_data_ttl", "integer"],
            "analytics_config_audit_ttl" : ["analytics_config_audit_ttl", "integer"],
            "analytics_statistics_ttl" : ["analytics_statistics_ttl", "integer"],
            "analytics_flow_ttl" : ["analytics_flow_ttl", "integer"],
            "snmp_scan_frequency" : ["snmp_scan_frequency", "integer"],
            "snmp_fast_scan_frequency" : ["snmp_fast_scan_frequency", "integer"],
            "topology_scan_frequency" : ["topology_scan_frequency", "integer"],
            "analytics_syslog_port" : ["analytics_syslog_port", "integer"],
            "database_dir" : ["database_dir", "string"],
            "analytics_data_dir" : ["analytics_data_dir", "string"],
            "ssd_data_dir" : ["ssd_data_dir", "string"],
            "database_minimum_diskGB" : ["database_minimum_diskGB", "integer"],
            "enable_lbass" : ["enable_lbass", "boolean"],
            "redis_password" : ["redis_password", "string"],
            "keystone_ip" : ["keystone_ip", "string"],
            "keystone_password" : ["keystone_admin_password", "string"],
            "keystone_username" : ["keystone_admin_user", "string"],
            "keystone_tenant" : ["keystone_admin_tenant", "string"],
            "keystone_service_tenant" : ["keystone_service_tenant", "string"],
            "keystone_region_name" : ["keystone_region_name", "string"],
            "multi_tenancy" : ["multi_tenancy", "boolean"],
            "zookeeper_ip_list" : ["zookeeper_ip_list", "array"],
            "haproxy" : ["haproxy_flag", "string"],
            "hc_interval" : ["hc_interval", "integer"],
            "nfs_server" : ["nfs_server", "string"],
            "nfs_glance_path" : ["nfs_glance_path", "string"],
            "database_token" : ["database_initial_token", "integer"],
            "encapsulation_priority" : ["encap_priority", "string"],
            "router_asn" : ["router_asn", "string"],
            "external_bgp" : ["external_bgp", "string"],
            "use_certificates" : ["use_certs", "boolean"],
            "contrail_logoutput" : ["contrail_logoutput", "boolean"],
            "enable_ceilometer": ["enable_ceilometer", "boolean"],
            "xmpp_dns_auth_enable": ["xmpp_dns_auth_enable", "boolean"],
            "xmpp_auth_enable": ["xmpp_auth_enable", "boolean"],
            "contrail_amqp_ip_list": ["contrail_amqp_ip_list", "array"],
            "contrail_amqp_port": ["contrail_amqp_port", "integer"],
            "openstack_amqp_ip_list": ["openstack_amqp_ip_list", "array"],
            "openstack_amqp_port": ["openstack_amqp_port", "integer"]
        }

        data = ''
        try:
            # Go thru all the keys above and if present, add to parameter list
            for k,v in cluster_params_mapping.items():
                if k in cluster_params:
                    # if value is text, add with quotes, else without the quotes.
                    if v[1].lower() == "string":
                        data += 'contrail::params::' + v[0] + ': "' + \
                            cluster_params.get(k, "") + '"\n'
                    else:
                        data += 'contrail::params::' + v[0] + ': ' + \
                            cluster_params.get(k, "") + '\n'
                    # end if-else
            # end for
            return data
        except Exception as e:
            msg = "%s, %s, %s:%s" % (repr(e), v, k, cluster_params.get(k))
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)         
    # end add cluster_parameters

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

    def add_contrail_upgrade(
        self, server, provision_parameters):
        data = ''

        #Set the flag only when targets image_id is not equal to what it is going
        #to be provisoned with
        if server.get('provisioned_id', "") != "" and \
                  server.get('provisioned_id',"") != provision_parameters.get('package_image_id', ""):
            data += 'contrail::params::contrail_upgrade: %s\n' %(
                           True)

        return data

    def generate_tor_certs(self, switch_info, server_id, domain):
        tor_name = switch_info['switch_name']
        tor_vendor_name = switch_info['vendor_name']
        tor_server_fqdn = server_id + '.' + domain
        contrail_module_path = '/etc/contrail_smgr/puppet/ssl/'
        tor_cert_file = contrail_module_path + 'tor.' + tor_name + '.cert.pem'
        tor_key_file = contrail_module_path + 'tor.' + tor_name + '.privkey.pem'

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

    def build_contrail_hiera_file(
        self, hiera_filename, provision_params,
        server, cluster, cluster_servers):
        cluster_params = cluster.get('parameters', {})
        # By default, sequence provisioning is On.
        sequence_provisioning = provision_params['sequence_provisioning']
        sequence_provisioning_available = provision_params['sequence_provisioning_available']
        server_params = server.get('parameters', {})
        data = ''
        package_ids = [provision_params.get('package_image_id', "").encode('ascii')]
        package_types = [provision_params.get('package_type', "").encode('ascii')]
	if 'storage-compute' in provision_params['host_roles'] or 'storage-master' in provision_params['host_roles']:
            package_ids.append(provision_params.get('storage_repo_id', "").encode('ascii'))
            package_types.append("contrail-ubuntu-storage-repo".encode('ascii'))
        data += 'contrail::params::contrail_repo_name: %s\n' %(str(package_ids))
        data += 'contrail::params::contrail_repo_type: %s\n' %(str(package_types))

        data += 'contrail::params::host_ip: "%s"\n' %(
            self.get_control_ip(provision_params, server.get('ip_address', "")))

        data += 'contrail::params::contrail_version: "%s"\n' %(provision_params['package_version'])
        data += 'contrail::package_sku: "%s"\n' %(provision_params['package_sku'])

        #Upgrade Kernel
        if 'kernel_upgrade' in provision_params and \
            provision_params['kernel_upgrade'] != DEFAULT_KERNEL_UPGRADE :
            data += 'contrail::params::kernel_upgrade: "%s"\n' %(
                provision_params.get('kernel_upgrade', DEFAULT_KERNEL_UPGRADE))
        if 'kernel_version' in provision_params and \
            provision_params['kernel_version'] != DEFAULT_KERNEL_VERSION :
            data += 'contrail::params::kernel_version: "%s"\n' %(
                provision_params.get('kernel_version', DEFAULT_KERNEL_VERSION))
        if 'external_bgp' in provision_params and \
            provision_params['external_bgp'] :
            data += 'contrail::params::external_bgp: "%s"\n' %(
                provision_params.get('external_bgp', ""))
        if "uuid" in cluster_params:
            data += 'contrail::params::uuid: "%s"\n' %(
                cluster_params.get('uuid', ""))

        if 'huge_pages' in provision_params and \
            provision_params['huge_pages'] != DEFAULT_HUGE_PAGES :
            data += 'contrail::params::huge_pages: "%s"\n' %(
                provision_params.get('huge_pages', DEFAULT_HUGE_PAGES))

        if 'core_mask' in provision_params and \
            provision_params['core_mask'] != DEFAULT_CORE_MASK :
            data += 'contrail::params::core_mask: "%s"\n' %(
                provision_params.get('core_mask', DEFAULT_CORE_MASK))



        data += self.add_contrail_upgrade(server, provision_params)

        role_ips = {}
        role_ids = {}
        role_passwd = {}
        role_users = {}
        # Set enable_provision_complete flag to false
        if sequence_provisioning_available and sequence_provisioning:
            data += 'contrail::params::enable_post_provision: False\n'
            data += 'contrail::params::enable_pre_exec_vnc_galera: False\n'
            data += 'contrail::params::enable_post_exec_vnc_galera: False\n'
            data += 'contrail::params::enable_keepalived: False\n'
            data += 'contrail::params::enable_haproxy: False\n'
            data += 'contrail::params::enable_sequence_provisioning: True\n'
            data += 'contrail::params::enable_provision_started: True\n'
        for role in ['database', 'config', 'openstack',
                     'control', 'collector',
                     'webui', 'compute', 'tsn', 'toragent']:
            # Set all module enable flags to false
            if sequence_provisioning_available and sequence_provisioning:
                data += 'contrail::params::enable_%s: False\n' %(role)
            role_ips[role] = [
                self.get_control_ip(provision_params, x["ip_address"].encode('ascii')) \
                    for x in cluster_servers if role in set(eval(x['roles']))]
            data += 'contrail::params::%s_ip_list: %s\n' %(
                role, str(role_ips[role]))
            role_ids[role] = [
                x["id"].encode('ascii') for x in cluster_servers if role in set(eval(x['roles']))]
            data += 'contrail::params::%s_name_list: %s\n' %(
                role, str(role_ids[role]))
            role_passwd[role] = [
                x["password"].encode('ascii') for x in cluster_servers if role in set(eval(x['roles']))]
            data += 'contrail::params::%s_passwd_list: %s\n' %(
                role, str(role_passwd[role]))
            role_users[role] = [
                "root".encode('ascii') for x in cluster_servers if role in set(eval(x['roles']))]
            data += 'contrail::params::%s_user_list: %s\n' %(
                role, str(role_users[role]))

        if (server['id'] == role_ids['openstack'][0]) :
           data += 'contrail::params::sync_db: %s\n' %(
               "True")
        else:
           data += 'contrail::params::sync_db: %s\n' %(
               "False")
 

        # Retrieve and add all the cluster parameters specified.
        data += self.add_cluster_parameters(cluster_params)
        # Handle any other additional parameters to be added to yaml file.
        # openstack_mgmt_ip_list
        openstack_mgmt_ip_list = [x["ip_address"].encode('ascii') \
                for x in cluster_servers if "openstack" in set(eval(x['roles']))]
        data += 'contrail::params::openstack_mgmt_ip_list: %s\n' %(
            str(openstack_mgmt_ip_list))
        # host_non_mgmt_ip
        server_mgmt_ip = server.get("ip_address", "").encode('ascii')
        server_control_ip = self.get_control_ip(
            provision_params, server_mgmt_ip)
        if (server_control_ip != server_mgmt_ip):
            data += 'contrail::params::host_non_mgmt_ip: "%s"\n' %(
                server_control_ip)
            # host_non_mgmt_gateway
            control_intf_dict = provision_params.get("control_net", "")
            if control_intf_dict:
                server_control_intf = eval(control_intf_dict.get(server_mgmt_ip, ""))
                if server_control_intf:
                    intf_name, intf_details = server_control_intf.popitem()
                    data += 'contrail::params::host_non_mgmt_gateway: "%s"\n' %(
                        intf_details.get("gateway", ""))
                # end if server_control_intf
            # end if control_intf_dict
        # enf if server_control_ip...

        data += 'contrail::params::host_roles: %s\n' %(str(provision_params['host_roles']))
        if 'toragent' in provision_params['host_roles'] :
            tor_config = provision_params.get("tor_ha_config", "")
            data += 'contrail::params::tor_ha_config:\n'
            for host_tor_config in tor_config.keys():
              data += '  %s:\n' %(host_tor_config)
              switch_list = tor_config[host_tor_config].get('switches', "")
              tsn_ip = tor_config[host_tor_config].get('tsn_ip', "")
              if switch_list:
                for  switch in switch_list:
                    data += '    %s%s:\n' %(switch['switch_name'],switch['id'])
                    data += '      tsn_ip: "%s"\n' % (tsn_ip)
                    for key,value in switch.items():
                        data += '      %s: "%s"\n' % (key,value)
                        if key == 'ovs_protocol' and value.lower() == 'pssl':
                            self.generate_tor_certs(
                                switch, provision_params['server_id'],
                                provision_params['domain'])
                        #end pssl condition
                    #end key,value for loop
                #end switch for loop
              #end switch_list if condition
            #end tor_config loop
        #end toragent in host_roles

        if 'storage-compute' in provision_params['host_roles'] or 'storage-master' in provision_params['host_roles']:
            ## Storage code
            if sequence_provisioning_available and sequence_provisioning:
                data += 'contrail::params::enable_storage_master: False\n'
                data += 'contrail::params::enable_storage_compute: False\n'
            data += 'contrail::params::storage_num_osd: %s\n' %(provision_params['storage_num_osd'])
            data += 'contrail::params::storage_fsid: "%s"\n' %(provision_params['storage_fsid'])
            data += 'contrail::params::storage_num_hosts: %s\n' %(provision_params['num_storage_hosts'])
            data += 'contrail::params::storage_virsh_uuid: "%s"\n' %(provision_params['storage_virsh_uuid'])
            data += 'contrail::params::storage_monitor_secret: "%s"\n' %(provision_params['storage_mon_secret'])
            data += 'contrail::params::storage_admin_key: "%s"\n' %(provision_params['admin_key'])
            data += 'contrail::params::osd_bootstrap_key: "%s"\n' %(provision_params['osd_bootstrap_key'])
            data += 'contrail::params::storage_enabled: "%s"\n' %(provision_params['contrail-storage-enabled'])
            data += 'contrail::params::live_migration_storage_scope: "%s"\n' %(provision_params['live_migration_storage_scope'])
            data += 'contrail::params::live_migration_host: "%s"\n' %(provision_params['live_migration_host'])
            data += 'contrail::params::live_migration_ip: "%s"\n' %(provision_params['live_migration_ip'])
            data += 'contrail::params::storage_ip_list: %s\n' %(str(provision_params['storage_monitor_hosts']))

            storage_mon_hosts = ''
            for key in provision_params['storage_monitor_hosts']:
                storage_mon_hosts += '''%s, ''' % key
            data += 'contrail::params::storage_monitor_hosts: %s\n' %(str(provision_params['storage_monitor_hosts']))

            storage_hostnames = ''
            for key in provision_params['storage_hostnames']:
                storage_hostnames += ''''%s', ''' % key
            data += 'contrail::params::storage_hostnames: "[%s]"\n' %(str(storage_hostnames))

            if 'storage-master' in provision_params['host_roles']:
                storage_chassis_config = ''
                for key in provision_params['storage_chassis_config']:
                    storage_chassis_config += '''"%s", ''' % key
                if len(str(storage_chassis_config)) != 0:
                    data += 'contrail::params::storage_chassis_config: [%s]\n' %(str(storage_chassis_config))
    
            if 'storage_server_disks' in provision_params:
                storage_disks = [  x.encode('ascii') for x in provision_params['storage_server_disks']]
                data += 'contrail::params::storage_osd_disks: %s\n' %(str(storage_disks))
            else:
                data += 'contrail::params::storage_osd_disks: []\n' 
            control_network = self.storage_get_control_network_mask(provision_params, server, cluster)
            self._smgr_log.log(self._smgr_log.DEBUG, "control-net : %s" %(control_network))
            data += 'contrail::params::storage_cluster_network: %s\n' %(control_network) 

        with open(hiera_filename, "w") as site_fh:
            site_fh.write(data)
        # end with
    # end def build_contrail_hiera_file

    def add_params_from_dict(self, in_dict, package, prefix=''):
        out_dict = {}
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
                package_params = package.get("parameters", {})
                if (package_params.get('puppet_version', 0.0) < 3.0):
                    out_dict["contrail::params::" + key] = value
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
            for role in ['loadbalancer', 'database', 'config', 'openstack',
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

    # Use template to prepare hiera data file for openstack modules. Revisit later to refine.
    def build_openstack_hiera_file(
        self, hiera_filename, provision_params,
        server, cluster, cluster_servers):
        cluster_params = cluster.get('parameters', {})
        server_params = server.get('parameters', {})
        # Get all values needed to fill the template.
        self_ip = server.get("ip_address", "")

        openstack_ips = [x["ip_address"] for x in cluster_servers if "openstack" in eval(x.get('roles', '[]'))]
        cluster_openstack_prov_params = (cluster_params.get("provision", {})).get("openstack", {})
        configured_external_keystone_ip = cluster_openstack_prov_params.get("keystone_ip", None)
        if configured_external_keystone_ip:
            openstack_ip = configured_external_keystone_ip
        elif self_ip in openstack_ips:
            openstack_ip = self_ip
        elif len(openstack_ips):
            openstack_ip = openstack_ips[0]
        else:
            msg = "Openstack role not defined for cluster AND External Openstack not configured in cluster parameters.\n " \
                   "The cluster needs to point to at least one Openstack node.\n"
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            raise ServerMgrException(msg, ERR_OPR_ERROR)
        
        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")

        new_provision_params = cluster_params.get("provision", {})
        openstack_params = new_provision_params.get("openstack", {})
        if new_provision_params:
            mysql_root_password = openstack_params.get("mysql", {}).get("root_password", "")
            mysql_service_password = openstack_params.get("mysql", {}).get("service_password", "")
            keystone_admin_password = openstack_params.get("keystone", {}).get("admin_password", "")
            #Re-generate adming token if nothing was specified
            #while creation.
            #Ideally auto-generate woudl have created it.
            #But old SM-code didn't
            keystone_admin_token = openstack_params.get("keystone", {}).get("admin_token", self.random_string(12))
            heat_encryption_key = openstack_params.get("heat",{}).get("encryption_key", "")
            mysql_allowed_hosts = openstack_params.get("mysql_allowed_hosts", [])
            if not mysql_allowed_hosts:
                calc_cluster_params = cluster.get("calc_params", {})
                mysql_allowed_hosts = calc_cluster_params.get("mysql_allowed_hosts", [])
            # end if
        else:
            mysql_root_password = cluster_params.get("mysql_root_password", "")
            mysql_service_password = cluster_params.get("mysql_service_password", "")
            keystone_admin_password = cluster_params.get("keystone_password", "")
            #Re-generate adming token if nothing was specified
            #while creation.
            #Ideally auto-generate woudl have created it.
            #But old SM-code didn't
            keystone_admin_token = cluster_params.get("keystone_admin_token", self.random_string(12))
            heat_encryption_key = cluster_params.get("heat_encryption_key", "")
            # Calculate list of hosts with mysql access granted.
            mysql_allowed_hosts = []
            internal_vip = cluster_params.get("internal_vip", None)
            if internal_vip:
                mysql_allowed_hosts.append(internal_vip) 
            external_vip = cluster_params.get("external_vip", None)
            if external_vip:
                mysql_allowed_hosts.append(external_vip) 
            contrail_internal_vip = cluster_params.get("contrail_internal_vip", None)
            if contrail_internal_vip:
                mysql_allowed_hosts.append(contrail_internal_vip) 
            contrail_external_vip = cluster_params.get("contrail_external_vip", None)
            if contrail_external_vip:
                mysql_allowed_hosts.append(contrail_external_vip) 
            os_ip_list =  [self.get_control_ip(provision_params, x["ip_address"].encode('ascii')) \
                    for x in cluster_servers if 'openstack' in set(eval(x['roles']))]
            config_ip_list =  [self.get_control_ip(provision_params, x["ip_address"].encode('ascii')) \
                    for x in cluster_servers if 'config' in set(eval(x['roles']))]
            role_ips_dict = provision_params['roles']
            mysql_allowed_hosts = list(
               set(mysql_allowed_hosts + os_ip_list + config_ip_list + role_ips_dict['config'] + role_ips_dict['openstack'] ))
        # end else openstack_params
        template_vals = {
            '__openstack_ip__': openstack_ip,
            '__subnet_mask__': subnet_mask,
            '__mysql_root_password__': mysql_root_password,
            '__mysql_service_password__': mysql_service_password,
            '__keystone_admin_token__': keystone_admin_token,
            '__keystone_admin_password__': keystone_admin_password,
            '__mysql_allowed_hosts__': (', '.join("'" + item + "'" for item in mysql_allowed_hosts)),
            '__openstack_password__': keystone_admin_password,
            '__heat_encryption_key__': heat_encryption_key
        }
        data = openstack_hieradata.template.safe_substitute(template_vals)
        outfile = open(hiera_filename, 'w')
        outfile.write(data)
        outfile.close()
    # end def build_openstack_hiera_file

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
        server_fqdn = server['id'] + "." + domain
        contrail_hiera_file = hieradata_dir + server_fqdn + \
            "-contrail.yaml"
        # if cluster parameters has provision key, use new way of building Hiera file, else
        # continue with old way.
        if ("provision" in cluster_params):
            self.build_contrail_hiera_file_new(
                contrail_hiera_file, server,
                cluster, cluster_servers, package)
        else:
            self.build_contrail_hiera_file(
                contrail_hiera_file, provision_params, server,
                cluster, cluster_servers)
        openstack_hiera_file = hieradata_dir + server_fqdn + \
            "-openstack.yaml"
        self.build_openstack_hiera_file(
            openstack_hiera_file, provision_params, server,
            cluster, cluster_servers)
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
            self._smgr_log.log(self._smgr_log.DEBUG, "role-tuple: %s = %s" % (role_step_tuple[0], role_step_tuple[1]))
            if server_id == role_step_tuple[0]:
                role_step = role_step_tuple[1].replace('-', '_')
                key = 'contrail::sequencing::enable_' + role_step
                if key not in hiera_data_dict:
                    key = 'contrail::params::enable_' + role_step
                self._smgr_log.log(self._smgr_log.DEBUG, "role-key: %s %s" % (key, enable))
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
        server_fqdn = server['id'] + "." + domain
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
            self._smgr_log.log(
                self._smgr_log.DEBUG,
                "No environment for version found AND this version does not support old contrail puppet manifest (2.0 and before)")
            self._smgr_log.log(
                self._smgr_log.DEBUG,
                "Use server manager version 2.21 or earlier if you have old style contrail puppet manifests")
        # end else
    # end provision_server
# class ServerMgrPuppet

if __name__ == "__main__":
    pass
