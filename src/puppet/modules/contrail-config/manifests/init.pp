class contrail-config {

# Macro to push and execute certain scripts.
define config-scripts {
    file { "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        require => [File["/etc/contrail/ctrl-details"],Config-template-scripts["schema_transformer.conf"],Config-template-scripts["svc_monitor.conf"]]
    }
    exec { "setup-${title}" :
        command => "/bin/bash /opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh $operatingsystem && echo setup-${title} >> /etc/contrail/contrail-config-exec.out",
        require => File["/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh"],
        unless  => "grep -qx setup-${title} /etc/contrail/contrail-config-exec.out",
        provider => shell
    }
}

# Macro to setup the configuration files from templates.
define config-template-scripts {
    # Ensure template param file is present with right content.
    file { "/etc/contrail/${title}" : 
        ensure  => present,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/${title}.erb"),
    }
}

# Main module code
define contrail-config (
        $contrail_config_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_compute_ip,
        $contrail_control_ip_list,
	$contrail_control_name_list,
        $contrail_collector_ip,
        $contrail_cassandra_ip_list,
        $contrail_cassandra_ip_port,
        $contrail_openstack_ip,
        $contrail_keystone_ip = $contrail_openstack_ip,
        $contrail_use_certs,
        $contrail_service_token,
        $contrail_ks_admin_user,
        $contrail_ks_admin_passwd,
        $contrail_ks_admin_tenant,
        $contrail_openstack_root_passwd,
        $contrail_multi_tenancy,
        $contrail_zookeeper_ip_list,
        $contrail_zk_ip_port,
        $contrail_redis_ip,
        $contrail_cfgm_index,
        $contrail_api_nworkers,
        $contrail_supervisorctl_lines,
	$contrail_haproxy,
	$contrail_uuid,
	$contrail_rmq_master,
	$contrail_rmq_is_master,
	$contrail_region_name,
	$contrail_router_asn,
	$contrail_encap_priority,
	$contrail_bgp_params,
        $contrail_ks_insecure_flag=false,
        $contrail_hc_interval="5",
        $contrail_ks_auth_protocol="http",
        $contrail_quantum_service_protocol="http",
        $contrail_ks_auth_port="35357"
    ) {

    if $contrail_use_certs == "yes" {
        $contrail_ifmap_server_port = '8444'
    }
    else {
        $contrail_ifmap_server_port = '8443'
    }

    if $contrail_multi_tenancy == "True" {
        $contrail_memcached_opt = "memcache_servers=127.0.0.1:11211"
    }
    else {
        $contrail_memcached_opt = ""
    }

    # Ensure all needed packages are present
    package { 'contrail-openstack-config' : ensure => present,}
    # The above wrapper package should be broken down to the below packages
    # For Debian/Ubuntu - supervisor, contrail-nodemgr, contrail-lib, contrail-config, neutron-plugin-contrail, neutron-server, python-novaclient,
    #                     python-keystoneclient, contrail-setup, haproxy, euca2ools, rabbitmq-server, python-qpid, python-iniparse, python-bottle,
    #                     zookeeper, ifmap-server, ifmap-python-client, contrail-config-openstack
    # For Centos/Fedora - contrail-api-lib contrail-api-extension, contrail-config, openstack-quantum-contrail, python-novaclient, python-keystoneclient >= 0.2.0,
    #                     python-psutil, mysql-server, contrail-setup, python-zope-interface, python-importlib, euca2ools, m2crypto, openstack-nova,
    #                     java-1.7.0-openjdk, haproxy, rabbitmq-server, python-bottle, contrail-nodemgr

    # enable haproxy in haproxy config file for ubuntu.
    if ($operatingsystem == "Ubuntu") {

        if ! defined(File["/etc/haproxy/haproxy.cfg"]) {
            file { "/etc/haproxy/haproxy.cfg":
                ensure  => present,
                mode => 0755,
                owner => root,
                group => root,
                source => "puppet:///modules/contrail-common/$hostname.cfg"
            }
            exec { "haproxy-exec":
                command => "sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy && echo haproxy-exec >> /etc/contrail/contrail-config-exec.out",
                require => File["/etc/haproxy/haproxy.cfg"],
                unless  => "grep -qx haproxy-exec /etc/contrail/contrail-config-exec.out",
                provider => shell,
                logoutput => "true"
            }
            service { "haproxy" :
                enable => true,
                require => File["/etc/haproxy/haproxy.cfg"],
                ensure => running
            }
        }

        file {"/etc/init/supervisor-config.override": ensure => absent, require => Package['contrail-openstack-config']}
        file {"/etc/init/neutron-server.override": ensure => absent, require => Package['contrail-openstack-config']}
   }

    # api venv installation
    if ! defined(Exec["api-venv"]) {
        exec { "api-venv" :
            command   => '/bin/bash -c "source ../bin/activate && pip install * && echo api-venv >> /etc/contrail/contrail-config-exec.out"',
            cwd       => "/opt/contrail/api-venv/archive",
            unless    => ["[ ! -d /opt/contrail/api-venv/archive ]",
                          "[ ! -f /opt/contrail/api-venv/bin/activate ]",
                          "grep -qx api-venv /etc/contrail/contrail-config-exec.out"],
            provider => "shell",
            require => Package['contrail-openstack-config'],
            logoutput => "true"
        }
    }
    
    # Ensure ctrl-details file is present with right content.
    if ! defined(File["/etc/contrail/ctrl-details"]) {
        $quantum_port = "9697"
        #$contrail_compute_ip = ''
        #$contrail_openstack_mgmt_ip = ''
     	if $contrail_haproxy == "enable" {
		$quantum_ip = "127.0.0.1"
        } else {
		$quantum_ip = $contrail_config_ip
	}
        file { "/etc/contrail/ctrl-details" :
            ensure  => present,
            content => template("contrail-common/ctrl-details.erb"),
        }
    }
    # Ensure service.token file is present with right content.
    if ! defined(File["/etc/contrail/service.token"]) {
        file { "/etc/contrail/service.token" :
            ensure  => present,
            content => template("contrail-common/service.token.erb"),
        }
    }

    if ! defined(Exec["neutron-conf-exec"]) {
        exec { "neutron-conf-exec":
            command => "sudo sed -i 's/rpc_backend\s*=\s*neutron.openstack.common.rpc.impl_qpid/#rpc_backend = neutron.openstack.common.rpc.impl_qpid/g' /etc/neutron/neutron.conf && echo neutron-conf-exec >> /etc/contrail/contrail-openstack-exec.out",
            onlyif => "test -f /etc/neutron/neutron.conf",
            unless  => "grep -qx neutron-conf-exec /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => "true"
        }
    }

    if ! defined(Exec["quantum-conf-exec"]) {
        exec { "quantum-conf-exec":
            command => "sudo sed -i 's/rpc_backend\s*=\s*quantum.openstack.common.rpc.impl_qpid/#rpc_backend = quantum.openstack.common.rpc.impl_qpid/g' /etc/quantum/quantum.conf && echo quantum-conf-exec >> /etc/contrail/contrail-openstack-exec.out",
            onlyif => "test -f /etc/quantum/quantum.conf",
            unless  => "grep -qx quantum-conf-exec /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => "true"
        }
    }

    # Ensure ifmap.properties file is present with right content.
    #file { "/etc/ifmap-server/ifmap.properties" : 
    #    ensure  => present,
    #    require => Package["contrail-openstack-config"],
    #    content => template("contrail-config/ifmap.properties.erb"),
    #}

    # Ensure log4j.properties file is present with right content.
    file { "/etc/ifmap-server/log4j.properties" : 
        ensure  => present,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/log4j.properties.erb"),
    }

    # Ensure authorization.properties file is present with right content.
    file { "/etc/ifmap-server/authorization.properties" : 
        ensure  => present,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/authorization.properties.erb"),
    }

    # Ensure basicauthusers.proprties file is present with right content.
    file { "/etc/ifmap-server/basicauthusers.properties" : 
        ensure  => present,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/basicauthusers.properties.erb"),
    }

    # Ensure publisher.properties file is present with right content.
    file { "/etc/ifmap-server/publisher.properties" : 
        ensure  => present,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/publisher.properties.erb"),
    }

    # Ensure all config files with correct content are present.
    config-template-scripts { ["api_server.conf",
                               "schema_transformer.conf",
                               "svc_monitor.conf",
                               "discovery.conf",
                               "vnc_api_lib.ini",
                               "contrail_plugin.ini"]: }

    # Supervisor contrail-api.ini
    $contrail_api_port_base = '910'
    if ($operatingsystem == "Ubuntu") {
        file { "/etc/contrail/supervisord_config_files/contrail-api.ini" : 
            ensure  => present,
            require => Package["contrail-openstack-config"],
            content => template("contrail-config/contrail-api.ini.erb"),
        }
    }
    else {
        file { "/etc/contrail/supervisord_config_files/contrail-api.ini" : 
            ensure  => present,
            require => Package["contrail-openstack-config"],
            content => template("contrail-config/contrail-api-centos.ini.erb"),
        }
    }

    # initd script wrapper for contrail-api 
    file { "/etc/init.d/contrail-api" : 
        ensure  => present,
        mode => 0777,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/contrail-api.svc.erb"),
    }

    exec { "create-contrail-plugin-neutron":
        command => "cp /etc/contrail/contrail_plugin.ini /etc/neutron/plugins/opencontrail/ContrailPlugin.ini",
        require => File["/etc/contrail/contrail_plugin.ini"],
        onlyif => "test -d /etc/neutron/",
        provider => shell,
        logoutput => "true"
    }
    exec { "create-contrail-plugin-quantum":
        command => "cp /etc/contrail/contrail_plugin.ini /etc/quantum/plugins/contrail/contrail_plugin.ini",
        require => File["/etc/contrail/contrail_plugin.ini"],
        onlyif => "test -d /etc/quantum/",
        provider => shell,
        logoutput => "true"
    }

    # Supervisor contrail-discovery.ini
    $contrail_disc_port_base = '911'
    $contrail_disc_nworkers = '1'
    if ($operatingsystem == "Ubuntu") {
        file { "/etc/contrail/supervisord_config_files/contrail-discovery.ini" : 
            ensure  => present,
            require => Package["contrail-openstack-config"],
            content => template("contrail-config/contrail-discovery.ini.erb"),
        }
    }
    else {
        file { "/etc/contrail/supervisord_config_files/contrail-discovery.ini" : 
            ensure  => present,
            require => Package["contrail-openstack-config"],
            content => template("contrail-config/contrail-discovery-centos.ini.erb"),
        }
    }

    # initd script wrapper for contrail-discovery 
    file { "/etc/init.d/contrail-discovery" : 
        ensure  => present,
        mode => 0777,
        require => Package["contrail-openstack-config"],
        content => template("contrail-config/contrail-discovery.svc.erb"),
    }

    # set high session timeout to survive glance led disk activity
    file { "/etc/contrail/contrail_setup_utils/config-zk-files-setup.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        require => Package["contrail-openstack-config"],
        source => "puppet:///modules/contrail-config/config-zk-files-setup.sh"
    }
    $contrail_zk_ip_list_for_shell = inline_template('<%= contrail_zookeeper_ip_list.map{ |ip| "#{ip}" }.join(" ") %>')
    exec { "setup-config-zk-files-setup" :
        command => "/bin/bash /etc/contrail/contrail_setup_utils/config-zk-files-setup.sh $operatingsystem $contrail_cfgm_index $contrail_zk_ip_list_for_shell && echo setup-config-zk-files-setup >> /etc/contrail/contrail-config-exec.out",
        require => File["/etc/contrail/contrail_setup_utils/config-zk-files-setup.sh"],
        unless  => "grep -qx setup-config-zk-files-setup /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }

    # Handle rabbitmq.config changes
    $conf_file = "/etc/rabbitmq/rabbitmq.config"
    if ! defined(File["/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh"]) {
        file { "/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh" : 
            ensure  => present,
            mode => 0755,
            owner => root,
            group => root,
            require => Package['contrail-openstack-config'],
            source => "puppet:///modules/contrail-openstack/cfg-qpidd-rabbitmq.sh"
        }
    }
    if ! defined(Exec["exec-cfg-qpidd-rabbitmq"]) {
        exec { "exec-cfg-qpidd-rabbitmq" :
            command => "/bin/bash /etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh $conf_file && echo exec-cfg-qpidd-rabbitmq >> /etc/contrail/contrail-openstack-exec.out",
            require =>  File["/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh"],
            unless  => "grep -qx exec-qpidd-rabbitmq /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => 'true'
        }
    }

    # run setup-pki.sh script
    if $contrail_use_certs == true {
        file { "/etc/contrail_setup_utils/setup-pki.sh" : 
            ensure  => present,
            mode => 0755,
            user => root,
            group => root,
            source => "puppet:///modules/contrail-config/setup-pki.sh"
        }
        exec { "setup-pki" :
            command => "/etc/contrail_setup_utils/setup-pki.sh /etc/contrail/ssl; echo setup-pki >> /etc/contrail/contrail-config-exec.out",
            require => File["/etc/contrail_setup_utils/setup-pki.sh"],
            unless  => "grep -qx setup-pki /etc/contrail/contrail-config-exec.out",
            provider => shell,
            logoutput => "true"
        }
    }

    # Execute config-server-setup scripts
    config-scripts { ["config-server-setup", "quantum-server-setup"]: }

    # Need to run python script to setup quantum in keystone on openstack node TBD Abhay
    file { "/opt/contrail/contrail_installer/contrail_setup_utils/setup-quantum-in-keystone.py":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
    }
    exec { "setup-quantum-in-keystone" :
        command => "python /opt/contrail/contrail_installer/contrail_setup_utils/setup-quantum-in-keystone.py --ks_server_ip $contrail_openstack_ip --quant_server_ip $contrail_config_ip --tenant $contrail_ks_admin_tenant --user $contrail_ks_admin_user --password $contrail_ks_admin_passwd --svc_password $contrail_service_token --region_name $contrail_region_name && echo setup-quantum-in-keystone >> /etc/contrail/contrail-config-exec.out",
        require => [ File["/opt/contrail/contrail_installer/contrail_setup_utils/setup-quantum-in-keystone.py"] ],
        unless  => "grep -qx setup-quantum-in-keystone /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }

###############################

    File["/etc/contrail/ctrl-details"]->File["/etc/contrail/service.token"]->Config-template-scripts["api_server.conf"]->File["/etc/contrail/contrail_plugin.ini"]->Config-template-scripts["schema_transformer.conf"]->Config-template-scripts["svc_monitor.conf"]->Config-template-scripts["discovery.conf"]->Config-template-scripts["vnc_api_lib.ini"]

    # Initialize the multi tenancy option will update latter based on vns argument
    if ($contrail_multi_tenancy == "True") {
	$mt_options = "admin,$contrail_ks_admin_passwd,$contrail_ks_admin_tenant"
    } else {
        $mt_options = "None" 
    } 

    # Hard-coded to be taken as parameter of vnsi and multi-tenancy options need to be passed to contrail-control too.
    $router_asn = "64512"

    file { "/etc/contrail/contrail_setup_utils/exec_provision_control.py" :
        ensure  => present,
        mode => 0755,
    #    user => root,
        group => root,
        source => "puppet:///modules/contrail-config/exec_provision_control.py"
    }
    $contrail_host_ip_list_for_shell = inline_template('<%= contrail_control_ip_list.map{ |ip| "#{ip}" }.join(",") %>')
    $contrail_host_name_list_for_shell = inline_template('<%= contrail_control_name_list.map{ |name| "#{name}" }.join(",") %>')
    exec { "exec-provision-control" :
        command => "python  exec_provision_control.py --api_server_ip $contrail_config_ip --api_server_port 8082 --host_name_list $contrail_host_name_list_for_shell --host_ip_list $contrail_host_ip_list_for_shell --router_asn $router_asn --mt_options $mt_options && echo exec-provision-control >> /etc/contrail/contrail-config-exec.out",
        cwd => "/etc/contrail/contrail_setup_utils/",
        unless  => "grep -qx exec-provision-control /etc/contrail/contrail-config-exec.out",
        provider => shell,
	require => [ File["/etc/contrail/contrail_setup_utils/exec_provision_control.py"] ],
        logoutput => 'true'
    }
    
    file { "/etc/contrail/contrail_setup_utils/setup_external_bgp.py" :
            ensure  => present,
            mode => 0755,
            group => root,
            source => "puppet:///modules/contrail-config/setup_external_bgp.py"
    }

   exec { "provision-external-bgp" :
        command => "python /etc/contrail/contrail_setup_utils/setup_external_bgp.py --bgp_params \"$contrail_bgp_params\" --api_server_ip $contrail_config_ip --api_server_port 8082 --router_asn $contrail_router_asn --mt_options \"$mt_options\" && echo provision-external-bgp >> /etc/contrail/contrail-config-exec.out",
        require => [ File["/etc/contrail/contrail_setup_utils/setup_external_bgp.py"] ],
        unless  => "grep -qx provision-external-bgp /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }

    exec { "provision-metadata-services" :
        command => "python /opt/contrail/utils/provision_linklocal.py --admin_user $contrail_ks_admin_user --admin_password $contrail_ks_admin_passwd --linklocal_service_name metadata --linklocal_service_ip 169.254.169.254 --linklocal_service_port 80 --ipfabric_service_ip $contrail_openstack_ip --ipfabric_service_port 8775 --oper add && echo provision-metadata-services >> /etc/contrail/contrail-config-exec.out",
        require => [ File["/etc/haproxy/haproxy.cfg"] ],
        unless  => "grep -qx provision-metadata-services /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }

    exec { "provision-encap-type" :
        command => "python /opt/contrail/utils/provision_encap.py --admin_user $contrail_ks_admin_user --admin_password $contrail_ks_admin_passwd --encap_priority $contrail_encap_priority --oper add && echo provision-encap-type >> /etc/contrail/contrail-config-exec.out",
        require => [ File["/etc/haproxy/haproxy.cfg"],  ],
        unless  => "grep -qx provision-encap-type /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }


    Exec["haproxy-exec"]->Exec["setup-config-zk-files-setup"]->Config-scripts["config-server-setup"]->Config-scripts["quantum-server-setup"]->Exec["setup-quantum-in-keystone"]->Exec["provision-metadata-services"]->Exec["provision-encap-type"]->Exec["exec-provision-control"]->Exec["provision-external-bgp"]

    # Below is temporary to work-around in Ubuntu as Service resource fails
    # as upstart is not correctly linked to /etc/init.d/service-name
    if ($operatingsystem == "Ubuntu") {
        file { '/etc/init.d/supervisor-config':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisor-config"]
        }
    }
    service { "supervisor-config" :
        enable => true,
        require => [ Package['contrail-openstack-config'],
                     Exec['api-venv'] ],
        ensure => running,
    }
}
# end of user defined type contrail-config.

}
