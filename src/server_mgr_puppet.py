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
        cluster_params = eval(cluster['parameters'])
        server_params = eval(server['parameters'])
        #openstack_ip = cluster_params.get("internal_vip", None)
        openstack_ip = ''
        self_ip = server.get("ip_address", "")
        if openstack_ip is None or openstack_ip == '':
            if self_ip in role_ips_dict['openstack']:
                openstack_ip = self_ip
            else:
                openstack_ip = role_ips_dict['openstack'][0]

        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")

        subnet_address = str(IPNetwork(
            openstack_ip + "/" + subnet_mask).network)

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
        self, site_file, provision_params,
        server, cluster, cluster_servers):
        cluster_params = eval(cluster['parameters'])
        server_fqdn = provision_params['server_id'] + "." + \
            provision_params['domain']
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
        # Add keepalived (This class is no-op if vip is not configured.)
        if 'config' in server['roles'] or \
           'openstack' in server['roles']:
            data += '    include ::contrail::profile::keepalived\n'
        # Add haproxy (for config node)
        if 'config' in server['roles'] or \
           'openstack' in server['roles']:
            data += '    include ::contrail::profile::haproxy\n'
        # Add database role.
        if 'database' in server['roles']:
            data += '    include ::contrail::profile::database\n'
        # Add webui role.
        if 'webui' in server['roles']:
            data += '    include ::contrail::profile::webui\n'
        # Add openstack role.
        if 'openstack' in server['roles']:
            if cluster_params.get("internal_vip", "") != "" or \
                cluster_params.get("contrail_internal_vip", "") != "" :
                data += '    class { \'::contrail::profile::openstack_controller\': } ->\n'
                if 'config' in server['roles']:
                    data += '    class { \'::contrail::ha_config\': } ->\n'
                else:
                    data += '    class { \'::contrail::ha_config\': }\n'
            else:
                data += '    include ::contrail::profile::openstack_controller\n'
        # Add config role.
        if 'config' in server['roles']:
            if cluster_params.get("internal_vip", "") != "" or \
                cluster_params.get("contrail_internal_vip", "") != "" :
                data += '    class { \'::contrail::profile::config\': }\n'
            else:
                data += '    include ::contrail::profile::config\n'

        # Add controller role.
        if 'control' in server['roles']:
            data += '    include ::contrail::profile::controller\n'
        # Add collector role.
        if 'collector' in server['roles']:
            data += '    include ::contrail::profile::collector\n'
        # Add config provision role.
        if 'config' in server['roles']:
            data += '    class { \'::contrail::profile::provision\' : stage => \'last\' }\n'
        # Add compute role
        if 'compute' in server['roles']:
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
            "enable_ceilometer": ["enable_ceilometer", "boolean"]
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

    def initiate_esx_contrail_vm(self, provision_params):
        if 'esx_server' in provision_params.keys():
            self._smgr_log.log(self._smgr_log.DEBUG, "esx_server")
            #call scripts to provision esx
            vm_params = {}
            vm_params['vm'] = "ContrailVM"
            vm_params['vmdk'] = "ContrailVM"
            vm_params['datastore'] = provision_params['datastore']
            vm_params['eth0_mac'] = provision_params['server_mac']
            vm_params['eth0_ip'] = provision_params['server_ip']
            vm_params['eth0_pg'] = provision_params['esx_fab_port_group']
            vm_params['eth0_vswitch'] = provision_params['esx_fab_vswitch']
            vm_params['eth0_vlan'] = None
            vm_params['eth1_vswitch'] = provision_params['esx_vm_vswitch']
            vm_params['eth1_pg'] = provision_params['esx_vm_port_group']
            vm_params['eth1_vlan'] = "4095"
            vm_params['uplink_nic'] = provision_params['esx_uplink_nic']
            vm_params['uplink_vswitch'] = provision_params['esx_fab_vswitch']
            vm_params['server'] = provision_params['esx_ip']
            vm_params['username'] = provision_params['esx_username']
            vm_params['password'] = provision_params['esx_password']
            vm_params['thindisk'] =  provision_params['esx_vmdk']
            vm_params['smgr_ip'] = provision_params['smgr_ip'];
            vm_params['domain'] =  provision_params['domain']
            vm_params['vm_password'] = provision_params['password']
            vm_params['vm_server'] = provision_params['server_id']
            vm_params['vm_deb'] = provision_params['vm_deb']
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

    def generate_tor_certs(self, switch_info, provision_params):
        tor_name = switch_info['switch_name']
        tor_vendor_name = switch_info['vendor_name']
        tor_server_fqdn = provision_params['server_id'] + '.' + provision_params['domain']
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
        cluster_params = eval(cluster['parameters'])
        # By default, sequence provisioning is On.
        sequence_provisioning = provision_params['sequence_provisioning']
        sequence_provisioning_available = provision_params['sequence_provisioning_available']
        server_params = eval(server['parameters'])
        data = ''
        package_ids = [provision_params.get('package_image_id', "").encode('ascii')]
        package_types = [provision_params.get('package_type', "").encode('ascii')]
        if 'esx_server' in provision_params and 'compute' in provision_params['host_roles']:
            self.initiate_esx_contrail_vm(provision_params)
	if 'storage-compute' in provision_params['host_roles'] or 'storage-master' in provision_params['host_roles']:
            package_ids.append(provision_params.get('storage_repo_id', "").encode('ascii'))
            package_types.append("contrail-ubuntu-storage-repo".encode('ascii'))
        data += 'contrail::params::contrail_repo_name: %s\n' %(str(package_ids))
        data += 'contrail::params::contrail_repo_type: %s\n' %(str(package_types))

        data += 'contrail::params::host_ip: "%s"\n' %(
            self.get_control_ip(provision_params, server.get('ip_address', "")))

        data += 'contrail::params::contrail_version: "%s"\n' %(provision_params['package_version'])

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

        #User can pass AMQP Server List and AMQP Port for Config or Openstack nodes
        if 'contrail_amqp_ip_list' in provision_params:
            amqp_ip_list = provision_params['contrail_amqp_ip_list']
            data += 'contrail::params::contrail_amqp_ip_list: "%s"\n' % (str(contrail_amqp_ip_list))
        if 'contrail_amqp_port' in provision_params:
            data += 'contrail::params::contrail_amqp_port: "%s"\n' % (provision_params.get('contrail_amqp_port', 5672))
        if 'openstack_amqp_ip_list' in provision_params:
            amqp_ip_list = provision_params['openstack_amqp_ip_list']
            data += 'contrail::params::openstack_amqp_ip_list: "%s"\n' % (str(amqp_ip_list))
        if 'openstack_amqp_port' in provision_params:
            data += 'contrail::params::openstack_amqp_port: "%s"\n' % (provision_params.get('openstack_amqp_port', 5672))

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
        data += 'contrail::params::tor_ha_config: "%s"\n' %(str(provision_params['tor_ha_config']))
        if 'toragent' in provision_params['host_roles'] :
            tor_config = eval(provision_params.get("top_of_rack", ""))
            #self._smgr_log.log(self._smgr_log.DEBUG, "tor_config => %s" % tor_config)
            switch_list = tor_config.get('switches', "")
            if switch_list:
                data += 'contrail::params::top_of_rack:\n'
                for  switch in switch_list:
                    data += '  %s%s:\n' %(switch['switch_name'],switch['id'])
                    for key,value in switch.items():
                        #self._smgr_log.log(self._smgr_log.DEBUG, "switch key=> %s,value => %s" % (key,value))
                        data += '    %s: "%s"\n' % (key,value)
                        if key == 'ovs_protocol' and value.lower() == 'pssl':
                            self.generate_tor_certs(switch, provision_params)

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

    # Use template to prepare hiera data file for openstack modules. Revisit later to refine.
    def build_openstack_hiera_file(
        self, hiera_filename, provision_params,
        server, cluster, cluster_servers):
        mysql_allowed_hosts = []
        role_ips_dict = provision_params['roles']
        cluster_params = eval(cluster['parameters'])
        server_params = eval(server['parameters'])
        # Get all values needed to fill he template.
        self_ip = server.get("ip_address", "")
        openstack_ip = cluster_params.get("internal_vip", None)
        contrail_internal_vip = cluster_params.get("contrail_internal_vip", None)
        contrail_external_vip = cluster_params.get("contrail_external_vip", None)
        external_vip = cluster_params.get("external_vip", None)

        if contrail_internal_vip != None and contrail_internal_vip != "":
            mysql_allowed_hosts.append(contrail_internal_vip)
        if contrail_external_vip != None and contrail_external_vip != "":
            mysql_allowed_hosts.append(contrail_external_vip)
        if external_vip != None and external_vip != "":
            mysql_allowed_hosts.append(external_vip)


        os_ip_list =  [self.get_control_ip(provision_params, x["ip_address"].encode('ascii')) \
                    for x in cluster_servers if 'openstack' in set(eval(x['roles']))]

        config_ip_list =  [self.get_control_ip(provision_params, x["ip_address"].encode('ascii')) \
                    for x in cluster_servers if 'config' in set(eval(x['roles']))]

        if openstack_ip != None and openstack_ip != "":
            mysql_allowed_hosts.append(openstack_ip)
        mysql_allowed_hosts = list(set(mysql_allowed_hosts + os_ip_list + config_ip_list + role_ips_dict['config'] + role_ips_dict['openstack'] ))

        if openstack_ip is None or openstack_ip == '':
            if self_ip in role_ips_dict['openstack']:
                openstack_ip = self_ip
            else:
                openstack_ip = role_ips_dict['openstack'][0]
        
        subnet_mask = server.get("subnet_mask", "")
        if not subnet_mask:
            subnet_mask = cluster_params.get("subnet_mask", "255.255.255.0")
        mysql_root_password = cluster_params.get("mysql_root_password", "c0ntrail123")
        keystone_admin_token = (subprocess.Popen(["openssl", "rand", "-hex", "10"],stdout=subprocess.PIPE).communicate()[0]).rstrip()
        keystone_admin_password = cluster_params.get("keystone_password", "contrail123")
        heat_encryption_key = cluster_params.get("heat_encryption_key", "notgood but just long enough i think")
        subnet_address = str(IPNetwork(
            openstack_ip + "/" + subnet_mask).network)
        subnet_octets = subnet_address.split(".")
        if subnet_octets[3] == "0":
            subnet_octets[3] = "%"
            if subnet_octets[2] == "0":
                subnet_octets[2] = "%"
                if subnet_octets[1] == "0":
                    subnet_octets[1] = "%"
        #mysql_allowed_hosts = openstack_ip 
        template_vals = {
            '__openstack_ip__': openstack_ip,
            '__subnet_mask__': subnet_mask,
            '__mysql_root_password__': mysql_root_password,
            '__mysql_service_password__': mysql_root_password,
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

    def build_hiera_files(
        self, hieradata_dir, provision_params,
        server, cluster, cluster_servers):
        server_fqdn = provision_params['server_id'] + "." + \
            provision_params['domain']
        contrail_hiera_file = hieradata_dir + server_fqdn + \
            "-contrail.yaml"
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
                key = 'contrail::params::enable_' + role_step
                self._smgr_log.log(self._smgr_log.DEBUG, "role-key: %s %s" % (key, enable))
                if enable:
                    hiera_data_dict[key] = True
                else:
                    hiera_data_dict[key] = False
        data = ''
        for key, value in hiera_data_dict.iteritems():
            if isinstance(value, str):
                data = data + str(key) + ': ' + '"%s"\n' %(str(value))
            else:
                data = data + str(key) + ': ' + str(value) + '\n'
        if data:
            hiera_data_fp = open(hiera_file, 'w')
            hiera_data_fp.write(data)
            hiera_data_fp.close()
    # end modify_server_hiera_data

    def new_provision_server(
        self, provision_params, server, cluster, cluster_servers):
        server_fqdn = provision_params['server_id'] + "." + \
            provision_params['domain']
        env_name = provision_params['puppet_manifest_version']
        env_name = env_name.replace('-', '_')
        site_file = self.puppet_directory + "environments/" + \
            env_name + "/manifests/site.pp"
        hieradata_dir = self.puppet_directory + "environments/" + \
            env_name + "/hieradata/"
        # Build Hiera data for the server
        self.build_hiera_files(
            hieradata_dir, provision_params,
            server, cluster, cluster_servers)
        # Create an entry for this node in site.pp.
        # First, delete any existing entry and then add a new one.
        self.delete_node_entry(site_file, server_fqdn)
        # Now add a new node entry
        self.add_node_entry(
            site_file, provision_params, server, cluster, cluster_servers)

        # Add entry for the server to environment mapping in 
        # node_mapping.json file.
        self.update_node_map_file(provision_params['server_id'],
                                  provision_params['domain'],
                                  env_name)
    # end def new_provision_server

    # Function to remove puppet files and entries created when provisioning the server. This is called
    # when server is being reimaged. We do not want old provisioning data to be retained.
    def new_unprovision_server(self, server_id, server_domain):
        server_fqdn = server_id + "." + server_domain
        # Remove node to environment mapping from node_mapping.json file.
	node_env_dict = {}
        env_name = self.update_node_map_file(server_id, server_domain, None)
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
    # server_id and domain are required for both update and delete of an entry
    def update_node_map_file(self, server_id, server_domain, env_name):
        if not server_id or not server_domain:
            return None

        server_fqdn = server_id + "." + server_domain
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
        self, provision_params, server, cluster, cluster_servers):

        # The new way to create necessary puppet manifest files and parameters data.
        # The existing method is kept till the new method is well tested and confirmed
        # to be working.
        puppet_manifest_version = provision_params.get(
            'puppet_manifest_version', "")
        environment = puppet_manifest_version.replace('-','_')
        if self.is_new_provisioning(puppet_manifest_version):
            self.new_provision_server(
                provision_params, server, cluster, cluster_servers)
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
