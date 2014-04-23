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

class ServerMgrPuppet:
    _puppet_site_file_name = "site.pp"
    _site_manifest_file = ''

    def pupp_create_site_manifest_file(self):
        self._site_manifest_file = self.puppet_directory + "manifests/" + \
            self._puppet_site_file_name
        if os.path.isfile(self._site_manifest_file):
            return
        fp = open(self._site_manifest_file, 'w')
        if not fp:
            assert 0, "puppet site config file create failed"
        fp.close()
    # end pupp_create_site_manifest_file

    def pupp_create_server_manifest_file(self, provision_params):
        server_manifest_file = self.puppet_directory + "manifests/" + \
            provision_params['server_id'] + "." + \
            provision_params['domain'] + ".pp"
        if not os.path.exists(os.path.dirname(server_manifest_file)):
            os.makedirs(os.path.dirname(server_manifest_file))
        if os.path.exists(server_manifest_file):
            os.remove(server_manifest_file)
        fp = open(server_manifest_file, 'w')
        if not fp:
            assert 0, "puppet server config file create failed"
        fp.close()
        return server_manifest_file
    # end pupp_create_server_manifest_file

    def pupp_copy_common_files(self, puppet_dir):
        puppet_source_dir = self.smgr_base_dir + "puppet/modules"
        # remove all old contrail module files.
        dirlist = [
            "contrail-common", "contrail-database", "contrail-openstack",
            "contrail-compute", "contrail-config", "contrail-webui",
            "contrail-collector", "contrail-control"]
        for dir in dirlist:
            tmp_dir = puppet_dir + "modules/" + dir
            subprocess.call(["rm", "-rf", tmp_dir])
        # Now copy all new module files
        subprocess.call(["cp", "-rf", puppet_source_dir, puppet_dir])
    # end pupp_copy_common_files

    def __init__(self, smgr_base_dir, puppet_dir):
        self.smgr_base_dir = smgr_base_dir
        self.puppet_directory = puppet_dir
        if not os.path.exists(os.path.dirname(puppet_dir)):
            os.makedirs(os.path.dirname(puppet_dir))

        # Check and create puppet main site file
        self.pupp_create_site_manifest_file()

        # Copy all static files (templates, module manifests, custom functions,
        # customer facts etc) to puppet file-structure
        self.pupp_copy_common_files(self.puppet_directory)
    # end __init__

    def puppet_add_script_end_role(self, provision_params, last_res_added=None):
#        pdb.set_trace()
	if 'execute_script' in provision_params.keys():
            script_data = eval(provision_params["execute_script"])
            script_name = script_data["script_name"]
	    script_args = script_data["args"]
	    print "Executing Custom script"
            data = '''    # Execute Script for all roles.
    	contrail-common::contrail-exec-script{%s:
       	    script_name => "%s",
       	    args => "%s",
            require => %s
    	}\n\n''' % (script_name.replace('.','_'),
		script_name,
                script_args.replace('"','\''), last_res_added)
        return data



    def puppet_add_common_role(self, provision_params, last_res_added=None):
        data = '''    # custom type common for all roles.
    contrail-common::contrail-common{contrail_common:
       self_ip => "%s",
       system_name => "%s",
    }\n\n''' % (provision_params["server_ip"],
                provision_params["server_id"])
        return data
    # end puppet_add_common_role

    def puppet_add_database_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
        if provision_params['server_ip'] in provision_params['roles']['config']:
            config_server = provision_params['server_ip']
        else:
            config_server = provision_params['roles']['config'][0]

        cassandra_seeds = ["\"%s\""%(x) for x in \
            provision_params['roles']['database']]
        data += '''    # contrail-database role.
    contrail-database::contrail-database{contrail_database:
        contrail_database_ip => "%s",
        contrail_database_dir => "%s",
        contrail_database_initial_token => "%s",
        contrail_cassandra_seeds => [%s],
        system_name => "%s",
        contrail_config_ip => "%s", 
        require => %s
    }\n\n''' % (provision_params["server_ip"],
                provision_params["database_dir"],
                provision_params["db_initial_token"],
                ','.join(cassandra_seeds),
                provision_params["server_id"],
                config_server, last_res_added)
        return data
    # end puppet_add_database_role

    def puppet_add_openstack_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
#	if provision_params['haproxy'] == 'enable':
 #           data += '''         #Source HA Proxy CFG
  #      contrail-common::haproxy-cfg{haproxy_cfg:
   #         server_id => "%s"}\n\n
#''' % (server["server_id"])


        if (provision_params['openstack_mgmt_ip'] == ''):
            contrail_openstack_mgmt_ip = provision_params["server_ip"]
        else:
            contrail_openstack_mgmt_ip = provision_params['openstack_mgmt_ip']
        if provision_params['server_ip'] in provision_params['roles']['config']:
            config_server = provision_params['server_ip']
        else:
            config_server = provision_params['roles']['config'][0]

        if provision_params['server_ip'] in provision_params['roles']['compute']:
            compute_server = provision_params['server_ip']
        else:
            compute_server = provision_params['roles']['compute'][0]


        data += '''    # contrail-openstack role.
    contrail-openstack::contrail-openstack{contrail_openstack:
        contrail_openstack_ip => "%s",
        contrail_config_ip => "%s",
        contrail_compute_ip => "%s",
        contrail_openstack_mgmt_ip => "%s",
        contrail_service_token => "%s",
        contrail_ks_admin_passwd => "%s",
	contrail_haproxy => "%s",
        require => %s
    }\n\n''' % (provision_params["server_ip"], config_server,
                compute_server, contrail_openstack_mgmt_ip,
                provision_params["service_token"],
                provision_params["ks_passwd"], provision_params["haproxy"],
		last_res_added)


        if provision_params["haproxy"] == "enable":
			create_openstack_ha_proxy(provision_params)

        return data
    # end puppet_add_openstack_role



    def create_config_ha_proxy(self, provision_params):
        smgr_dir = "/etc/puppet/modules/contrail-common/files/"
        staging_dir = "/etc/puppet/modules/contrail-common/files/"
        cfg_ha_proxy_tmpl = string.Template("""
#contrail-config-marker-start
listen contrail-config-stats :5937
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

frontend quantum-server *:9696
    default_backend    quantum-server-backend

frontend  contrail-api *:8082
    default_backend    contrail-api-backend

frontend  contrail-discovery *:5998
    default_backend    contrail-discovery-backend

backend quantum-server-backend
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9697 check

backend contrail-api-backend
    balance     roundrobin
$__contrail_api_backend_servers__
    #server  10.84.14.2 10.84.14.2:9100 check
    #server  10.84.14.2 10.84.14.2:9101 check

backend contrail-discovery-backend
    balance     roundrobin
$__contrail_disc_backend_servers__
    #server  10.84.14.2 10.84.14.2:9110 check
    #server  10.84.14.2 10.84.14.2:9111 check
#contrail-config-marker-end
""")
    #ha proxy for cfg
        config_role_list = provision_params['roles']['config']
        q_listen_port = 9697
        q_server_lines = ''
        api_listen_port = 9100
        api_server_lines = ''
        disc_listen_port = 9110
        disc_server_lines = ''
        smgr_dir = "/etc/puppet/modules/contrail-common/files/"
        staging_dir = "/etc/puppet/modules/contrail-common/files/"
        #TODO
        nworkers = 1
        for config_host in config_role_list:
             host_ip = config_host
             n_workers = 1
             q_server_lines = q_server_lines + \
                             '    server %s %s:%s check\n' \
                             %(host_ip, host_ip, str(q_listen_port))
             for i in range(nworkers):
                api_server_lines = api_server_lines + \
                 '    server %s %s:%s check\n' \
                 %(host_ip, host_ip, str(api_listen_port + i))
                disc_server_lines = disc_server_lines + \
                 '    server %s %s:%s check\n' \
                 %(host_ip, host_ip, str(disc_listen_port + i))

        for config_host in config_role_list:
             haproxy_config = cfg_ha_proxy_tmpl.safe_substitute({
             '__contrail_quantum_servers__': q_server_lines,
             '__contrail_api_backend_servers__': api_server_lines,
             '__contrail_disc_backend_servers__': disc_server_lines,
             '__contrail_hap_user__': 'haproxy',
             '__contrail_hap_passwd__': 'contrail123',
             })

        ha_proxy_cfg = staging_dir + provision_params['server_id'] + ".cfg"
        shutil.copy2(smgr_dir + "haproxy.cfg", ha_proxy_cfg)
        cfg_file = open(ha_proxy_cfg, 'a')
        cfg_file.write(haproxy_config)
        cfg_file.close()

    def puppet_add_zk_role(self, provision_params, last_res_added):
	data = ''
	config_servers = provision_params['roles']['config']
	zk_servers = provision_params['roles']['zookeeper']

	cfgm_ip_list = ["\"%s\""%(x) for x in config_servers]
	zoo_ip_list = ["\"%s\""%(x) for x in zk_servers]
	zk_ip_list = cfgm_ip_list + zoo_ip_list

 	contrail_zk_index = len(config_servers) + zk_servers.index(
            provision_params["server_ip"])+1

        data = '''    # Execute Script for all roles.
        contrail-common::contrail-cfg-zk{contrail_cfg_zk:
            zk_ip_list => [%s],
            zk_index => "%s",
            require => %s
        }\n\n''' % (','.join(zk_ip_list),
                contrail_zk_index, last_res_added)
        return data


    def puppet_add_config_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
#	if 'haproxy' in config_role_params.dict() \
#		 and config_role_params['haproxy'] == 'enable':


	if provision_params['server_ip'] in provision_params['roles']['compute']:
	    compute_server = provision_params['server_ip']
        else:
            compute_server = provision_params['roles']['compute'][0]

        config_servers = provision_params['roles']['config']
	zk_servers = provision_params['roles']['zookeeper']

        cfgm_ip_list = ["\"%s\""%(x) for x in config_servers]
	zoo_ip_list = ["\"%s\""%(x) for x in zk_servers]
	zk_ip_list = cfgm_ip_list + zoo_ip_list

        contrail_cfgm_index = config_servers.index(
            provision_params["server_ip"])+1
        cassandra_ip_list = ["\"%s\""%(x) for x in \
            provision_params['roles']['database']]
        openstack_server = provision_params['roles']['openstack'][0]
        control_ip_list = provision_params['roles']['control']
        if (provision_params['openstack_mgmt_ip'] == ''):
            contrail_openstack_mgmt_ip = provision_params['roles']['openstack'][0]
        else:
            contrail_openstack_mgmt_ip = provision_params['openstack_mgmt_ip']
        collector_servers = provision_params['roles']['collector']
        if (provision_params["server_ip"] in collector_servers):
           collector_server = provision_params['server_ip']
        else:
            hindex = config_servers.index(provision_params['server_ip'])
            hindex = hindex % len(collector_servers)
            collector_server = collector_servers[hindex]
        nworkers = 1
        sctl_lines = ''
        for worker_id in range(int(nworkers)):
            sctl_line = 'supervisorctl -s http://localhost:9004 ' + \
                        '${1} `basename ${0}:%s`' %(worker_id)
            sctl_lines = sctl_lines + sctl_line

        data += '''    # contrail-config role.
    contrail-config::contrail-config{contrail_config:
        contrail_openstack_ip => "%s",
        contrail_openstack_mgmt_ip => "%s",
        contrail_compute_ip => "%s",
        contrail_use_certs => "%s",
        contrail_multi_tenancy => "%s",
        contrail_config_ip => "%s",
        contrail_control_ip_list => "%s",
        contrail_collector_ip => "%s",
        contrail_service_token => "%s",
        contrail_ks_admin_user => "%s",
        contrail_ks_admin_passwd => "%s",
        contrail_ks_admin_tenant => "%s",
        contrail_openstack_root_passwd => "%s",
        contrail_cassandra_ip_list => [%s],
        contrail_cassandra_ip_port => "9160",
        contrail_zookeeper_ip_list => [%s],
        contrail_zk_ip_port => "2181",
        contrail_redis_ip => "%s",
        contrail_cfgm_index => "%s",
        contrail_api_nworkers => "%s",
        contrail_supervisorctl_lines => '%s',
	contrail_haproxy => "%s",
        contrail_uuid => "%s",
	contrail_rmq_master => "%s",
	contrail_rmq_is_master => "%s",
		contrail_region_name => "%s",
		contrail_router_asn => "%s",
		contrail_encap_priority => "%s",
        require => %s
    }\n\n''' % (openstack_server, contrail_openstack_mgmt_ip, compute_server,
		provision_params["use_certs"], provision_params["multi_tenancy"],
        provision_params["server_ip"], ','.join(control_ip_list),
        collector_server, provision_params["service_token"],
        provision_params["ks_user"], provision_params["ks_passwd"],
        provision_params["ks_tenant"], provision_params["openstack_passwd"],
        ','.join(cassandra_ip_list), ','.join(zk_ip_list),
        config_servers[0], contrail_cfgm_index,
        nworkers, sctl_lines, "enable",
	provision_params['uuid'], provision_params['rmq_master'],
	provision_params['is_rmq_master'], provision_params['region_name'],
	provision_params['router_asn'], provision_params['encap_priority'],
	last_res_added)
	#add Ha Proxy
	self.create_config_ha_proxy(provision_params)


#        data += '''         #Source HA Proxy CFG
#        contrail-common::haproxy-cfg{haproxy_cfg:
#            server_id => "%s",
#	    require => Contrail-config::Contrail-config[\"contrail_config\"]
#	}\n
#''' % (provision_params['server_id'])


        return data
    # end puppet_add_config_role

    def puppet_add_control_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
    	if provision_params['server_ip'] in provision_params['roles']['config']:
            config_server = provision_params['server_ip']
        else:
            config_server = provision_params['roles']['config'][0]

        collector_servers = provision_params['roles']['collector']
        control_servers = provision_params['roles']['control']
        if (provision_params["server_ip"] in collector_servers):
           collector_server = provision_params['server_ip']
        else:
            hindex = control_servers.index(provision_params['server_ip'])
            hindex = hindex % len(collector_servers)
            collector_server = collector_servers[hindex]
        nworkers = 1
        data += '''    # contrail-control role.
    contrail-control::contrail-control{contrail_control:
        contrail_control_ip => "%s",
        contrail_config_ip => "%s",
        contrail_config_port => "8443",
        contrail_config_user => "%s",
        contrail_config_passwd => "%s",
        contrail_collector_ip => "%s",
        contrail_collector_port => "8086",
        contrail_discovery_ip => "%s",
        hostname => "%s",
        host_ip => "%s",
        bgp_port => "179",
        cert_ops => "false",
        log_file => "",
        contrail_log_file => "--log-file=/var/log/contrail/control.log",
        contrail_api_nworkers => "%s",
        require => %s
    }\n\n''' % (
        provision_params["server_ip"], config_server,
        provision_params["server_ip"], provision_params["server_ip"],
        collector_server, config_server,
        provision_params["server_id"], provision_params["server_ip"],
        nworkers, last_res_added)

        return data
    # end puppet_add_control_role

    def puppet_add_collector_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
        config_server = provision_params['roles']['config'][0]
        cassandra_ip_list = ["\"%s\""%(x) for x in \
            provision_params['roles']['database']]
        collector_servers = provision_params['roles']['collector']
        redis_master_ip = collector_servers[0]
        if (redis_master_ip == provision_params["server_ip"]):
            redis_role = "master"
        else:
            redis_role = "slave"
        data += '''    # contrail-collector role.
    contrail-collector::contrail-collector{contrail_collector:
        contrail_config_ip => "%s",
        contrail_collector_ip => "%s",
        contrail_redis_master_ip => "%s",
        contrail_redis_role => "%s",
        contrail_cassandra_ip_list => [%s],
        contrail_cassandra_ip_port => "9160",
        contrail_num_collector_nodes => %s,
        contrail_analytics_data_ttl => %s,
        require => %s
    }\n\n''' % (config_server, provision_params["server_ip"],
                redis_master_ip, redis_role,
                ','.join(cassandra_ip_list),
                len(collector_servers), 
                provision_params["analytics_data_ttl"],
                last_res_added)
        return data
    # end puppet_add_collector_role

    def puppet_add_webui_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
    	if provision_params['server_ip'] in provision_params['roles']['config']:
            config_server = provision_params['server_ip']
        else:
            config_server = provision_params['roles']['config'][0]

        webui_ips = provision_params['roles']['webui']
        collector_servers = provision_params['roles']['collector']
        if (provision_params["server_ip"] in collector_servers):
           collector_server = provision_params['server_ip']
        else:
            hindex = webui_ips.index(provision_params["server_ip"])
            hindex = hindex % len(collector_servers)
            collector_server = collector_servers[hindex]
        openstack_server = provision_params['roles']['openstack'][0]
        cassandra_ip_list = ["\"%s\""%(x) for x in \
            provision_params['roles']['database']]
        data += '''    # contrail-webui role.
    contrail-webui::contrail-webui{contrail_webui:
        contrail_config_ip => "%s",
        contrail_collector_ip => "%s",
        contrail_openstack_ip => "%s",
        contrail_cassandra_ip_list => [%s],
        require => %s
    }\n\n''' % (
        config_server, collector_server, openstack_server,
        ','.join(cassandra_ip_list), last_res_added)
        return data
    # end puppet_add_webui_role

    #Function to create haproxy cfg file for compute nodes
    def create_compute_ha_proxy(self, provision_params):

        smgr_dir = "/etc/contrail/"
        staging_dir = "/etc/puppet/modules/contrail-common/files/"

        compute_haproxy_template = string.Template("""
#contrail-compute-marker-start
listen contrail-compute-stats :5938
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__contrail_disc_stanza__

$__contrail_quantum_stanza__

$__contrail_qpid_stanza__

$__contrail_glance_api_stanza__

#contrail-compute-marker-end
""")


        ds_stanza_template = string.Template("""
$__contrail_disc_frontend__

backend discovery-server-backend
    balance     roundrobin
$__contrail_disc_servers__
    #server  10.84.14.2 10.84.14.2:5998 check
""")

        q_stanza_template = string.Template("""
$__contrail_quantum_frontend__

backend quantum-server-backend
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9696 check
""")

        g_api_stanza_template = string.Template("""
$__contrail_glance_api_frontend__

backend glance-api-backend
    balance     roundrobin
$__contrail_glance_apis__
    #server  10.84.14.2 10.84.14.2:9292 check
""")

        ds_frontend = textwrap.dedent("""\
        frontend discovery-server 127.0.0.1:5998
            default_backend discovery-server-backend
        """)

        q_frontend = textwrap.dedent("""\
        frontend quantum-server 127.0.0.1:9696
            default_backend quantum-server-backend
        """)

        g_api_frontend = textwrap.dedent("""\
        frontend glance-api 127.0.0.1:9292
            default_backend glance-api-backend
        """)

        haproxy_config = ''

        # if this compute is also config, skip quantum and discovery
        # stanza as they would have been generated in config context
        ds_stanza = ''
        q_stanza = ''

        config_ip_list = provision_params['roles']['config']
        openstack_ip_list = provision_params['roles']['openstack']
        compute_ip = provision_prams['server_ip']

        if compute_ip not in config_ip_list:
            # generate discovery service stanza
            ds_server_lines = ''
            for config_ip in config_ip_list:
                host_ip = config_ip

                ds_server_lines = ds_server_lines + \
                '    server %s %s:5998 check\n' %(host_ip, host_ip)

                ds_stanza = ds_stanza_template.safe_substitute({
                    '__contrail_disc_frontend__': ds_frontend,
                    '__contrail_disc_servers__': ds_server_lines,
                    })

            # generate  quantum stanza
            q_server_lines = ''
            for config_ip in config_ip_list:
                host_ip = config_ip

                q_server_lines = q_server_lines + \
                '    server %s %s:9696 check\n' %(host_ip, host_ip)

                q_stanza = q_stanza_template.safe_substitute({
                    '__contrail_quantum_frontend__': q_frontend,
                    '__contrail_quantum_servers__': q_server_lines,
                    })

        # if this compute is also openstack, skip glance-api stanza
        # as that would have been generated in openstack context
        g_api_stanza = ''
        if compute_ip not in openstack_ip_list:
            # generate a glance-api stanza
            g_api_server_lines = ''
            for openstack_ip in openstack_ip_list:
                host_ip = openstack_ip

                g_api_server_lines = g_api_server_lines + \
                '    server %s %s:9292 check\n' %(host_ip, host_ip)

                g_api_stanza = g_api_stanza_template.safe_substitute({
                    '__contrail_glance_api_frontend__': g_api_frontend,
                    '__contrail_glance_apis__': g_api_server_lines,
                    })
                # HACK: for now only one openstack
                break

        compute_haproxy = compute_haproxy_template.safe_substitute({
               '__contrail_hap_user__': 'haproxy',
            '__contrail_hap_passwd__': 'contrail123',
            '__contrail_disc_stanza__': ds_stanza,
            '__contrail_quantum_stanza__': q_stanza,
            '__contrail_glance_api_stanza__': g_api_stanza,
            '__contrail_qpid_stanza__': '',
            })

        ha_proxy_cfg = staging_dir + compute_host_string + ".cfg"

        shutil.copy2(smgr_dir + "haproxy.cfg", ha_proxy_cfg)
        cfg_file = open(ha_proxy_cfg, 'a')
        cfg_file.write(compute_haproxy)
        cfg_file.close()

    #Function to create haproxy cfg for openstack nodes
    def create_openstack_ha_proxy(self, roles, server_index, servers):
        smgr_dir = "/etc/contrail/"
        staging_dir = "/etc/puppet/modules/contrail-common/files/"
        openstack_haproxy_template = string.Template("""
#contrail-openstack-marker-start
listen contrail-openstack-stats :5936
   mode http
   stats enable
   stats uri /
   stats auth $__contrail_hap_user__:$__contrail_hap_passwd__

$__contrail_quantum_stanza__

#contrail-openstack-marker-end
""")

        q_stanza_template = string.Template("""
$__contrail_quantum_frontend__

backend quantum-server-backend
    balance     roundrobin
$__contrail_quantum_servers__
    #server  10.84.14.2 10.84.14.2:9696 check
""")

        q_frontend = textwrap.dedent("""\
        frontend quantum-server 127.0.0.1:9696
            default_backend quantum-server-backend
        """)

        config_ip_list = provision_params['roles']['config']
        openstack_ip_list = provision_params['roles']['openstack']	
        openstack_ip = provision_prams['server_ip']


        # for all openstack, set appropriate haproxy stanzas
        for openstack_ip in openstack_ip_list:
            haproxy_config = ''

            # if this openstack is also config, skip quantum stanza
            # as that would have been generated in config context
            q_stanza = ''
            if openstack_ip not in openstack_ip_list:
                # generate a quantum stanza
                q_server_lines = ''
                for config_ip in config_ip_list:
                    host_ip = config_ip

                    q_server_lines = q_server_lines + \
                    '    server %s %s:9696 check\n' %(host_ip, host_ip)

                    q_stanza = q_stanza_template.safe_substitute({
                        '__contrail_quantum_frontend__': q_frontend,
                        '__contrail_quantum_servers__': q_server_lines,
                        })

            # ...generate new ones
            openstack_haproxy = openstack_haproxy_template.safe_substitute({
                '__contrail_hap_user__': 'haproxy',
                '__contrail_hap_passwd__': 'contrail123',
                '__contrail_quantum_stanza__': q_stanza,
                })

            ha_proxy_cfg = staging_dir + openstack_host_string + ".cfg"

            shutil.copy2(smgr_dir + "haproxy.cfg", ha_proxy_cfg)
            cfg_file = open(ha_proxy_cfg, 'a')
            cfg_file.write(openstack_haproxy)
            cfg_file.close()

    def puppet_add_compute_role(self, provision_params, last_res_added):
        # Get all the parameters needed to send to puppet manifest.
        data = ''
        control_servers = provision_params['roles']['control']

    	if provision_params['server_ip'] in provision_params['roles']['config']:
            config_server = provision_params['server_ip']
        else:
            config_server = provision_params['roles']['config'][0]

    	if provision_params['server_ip'] in provision_params['roles']['collector']:
            collector_server = provision_params['server_ip']
        else:
            collector_server = provision_params['roles']['collector'][0]

    	if provision_params['server_ip'] in provision_params['roles']['openstack']:
            openstack_server = provision_params['server_ip']
        else:
            openstack_server = provision_params['roles']['openstack'][0]

        if (provision_params['openstack_mgmt_ip'] == ''):
            contrail_openstack_mgmt_ip = provision_params['roles']['openstack'][0]
        else:
            contrail_openstack_mgmt_ip = provision_params['openstack_mgmt_ip']
#	if provision_params['haproxy'] == 'enable':
#            data += '''         #Source HA Proxy CFG
#        contrail-common::haproxy-cfg{haproxy_cfg:
#            server_id => "%s"}\n\n
#''' % (server["server_id"])
        data += '''    # contrail-compute role.
    contrail-compute::contrail-compute{contrail_compute:
        contrail_config_ip => "%s",
        contrail_compute_hostname => "%s",
        contrail_compute_ip => "%s",
        contrail_collector_ip => "%s",
        contrail_openstack_ip => "%s",
        contrail_openstack_mgmt_ip => "%s",
        contrail_service_token => "%s",
        contrail_physical_interface => "%s",
        contrail_num_controls => "%s",
        contrail_non_mgmt_ip => "%s",
        contrail_non_mgmt_gw => "%s",
        contrail_ks_admin_user => "%s",
        contrail_ks_admin_passwd => "%s",
        contrail_ks_admin_tenant => "%s",
		contrail_haproxy => "%s",

        require => %s
    }\n\n''' % (
        config_server, provision_params["server_id"],
        provision_params["server_ip"], collector_server,
        openstack_server, contrail_openstack_mgmt_ip,
        provision_params["service_token"],
        provision_params["phy_interface"],
        len(control_servers), provision_params["compute_non_mgmt_ip"],
        provision_params["compute_non_mgmt_gway"],
        provision_params["ks_user"], provision_params["ks_passwd"],
        provision_params["ks_tenant"], provision_params["haproxy"],
	    last_res_added)


        if provision_params["haproxy"] == "enable":
            create_compute_ha_proxy(provision_params)

        return data
    # end puppet_add_compute_role

    _roles_function_map = {
        "common": puppet_add_common_role,
        "database": puppet_add_database_role,
        "openstack": puppet_add_openstack_role,
        "config": puppet_add_config_role,
        "control": puppet_add_control_role,
        "collector": puppet_add_collector_role,
        "webui": puppet_add_webui_role,
        "zookeeper": puppet_add_zk_role,
        "compute": puppet_add_compute_role
    }

    def provision_server(self, provision_params):
        # Create a new site file for this server
        server_manifest_file = self.pupp_create_server_manifest_file(
            provision_params)
        data = '''node '%s.%s' {\n''' % (
            provision_params["server_id"],
            provision_params["domain"])
        # Always call common function for all the roles
        data += self._roles_function_map["common"](self, provision_params)
        last_res_added =\
            "Contrail-common::Contrail-common[\"contrail_common\"]"

        # Iterate thru all the roles defined for this server and
        # call functions to add the necessary puppet lines in server.pp file.
        # list array used to ensure that the role definitions are added
        # in a particular order
        roles = ['database', 'openstack', 'config', 'control',
                 'collector', 'webui', 'zookeeper', 'compute']
        for role in roles:
            if provision_params['server_ip'] in \
                provision_params['roles'][role]:
                data += self._roles_function_map[role](
                    self, provision_params, last_res_added)
#		if role == "config":
#		    last_res_added =  "Contrail-common::Haproxy-cfg[\"haproxy_cfg\"]"
  		if role == "zookeeper":
		    last_res_added =  "Contrail-common::Contrail-cfg-zk[\"contrail_cfg_zk\"]"
		else:
                    last_res_added = (
                        "Contrail-%s::Contrail-%s[\"contrail_%s\"]")\
                        % (role, role, role)


	#Call stuff to be added at end
	if provision_params['execute_script']:
	    data += self.puppet_add_script_end_role(provision_params,
						 last_res_added)

        data += '''}'''
        # write the data to manifest file for this server.
        with open(server_manifest_file, 'w') as f:
            f.write(data)
        # Now add an entry in site manifest file for this server
        server_line = "import \'%s\'\n" % (
            os.path.basename(server_manifest_file))
        with open(self._site_manifest_file, 'a+') as f:
            lines = f.readlines()
            if not server_line in lines:
                f.write(server_line)
    # end provision_server
# class ServerMgrPuppet

if __name__ == "__main__":
    pass
