node 'demo2-server.demo.juniper.net' {
    # To be added if config or openstack role is configured.
    @package { 'mysql' : ensure => present,}
    @package { 'mysql-server' : ensure => present,}
    @package { 'qpid-cpp-server' : ensure => present,}
    @package { 'httpd' : ensure => present,}
    @package { 'memcached' : ensure => present,}
    @file { "/etc/qpidd.conf" : 
        ensure  => present
    }
    @service { "qpidd" :
        enable => true,
        require => Package['qpid-cpp-server'],
        subscribe => File['/etc/qpidd.conf'],
        ensure => running,
    }
    @service { "httpd" :
        enable => true,
        require => Package['httpd'],
        ensure => running,
    }
    @service { "memcached" :
        enable => true,
        require => Package['memcached'],
        ensure => running,
    }
    # To be added if config, openstack or compute role is configured.
    $contrail_service_token = "contrail123"
    $contrail_admin_token = "contrail123"
    $contrail_openstack_ip = "10.84.51.13"
    $contrail_config_ip = "10.84.51.13"
    $contrail_compute_ip = "10.84.51.12"
    $contrail_openstack_mgmt_ip = "10.84.51.13"
    @file { "/etc/contrail/ctrl-details" : 
        ensure  => present,
        content => template("contrail-common/ctrl-details.erb"),
    }
    @file { "/etc/contrail/service.token" : 
        ensure  => present,
        content => template("contrail-common/service.token.erb"),
    }
    # custom type common for all roles.
    contrail-common::contrail-common{contrail_common:
       self_ip => "10.84.51.13",
       system_name => "demo2-server",
    }

    # contrail-database role.
    contrail-database::contrail-database{contrail_database:
        contrail_database_ip => "10.84.51.13",
        contrail_cassandra_dir => "/usr/share/cassandra",
        contrail_database_dir => "/home/cassandra",
        contrail_database_initial_token => "",
        contrail_cassandra_seeds => "127.0.0.1",
        require => Contrail-common::Contrail-common["contrail_common"]
    }

    # contrail-openstack role.
    contrail-openstack::contrail-openstack{contrail_openstack:
        contrail_openstack_ip => "10.84.51.13",
        contrail_config_ip => "10.84.51.13",
        contrail_compute_ip => "10.84.51.12",
        contrail_openstack_mgmt_ip => "10.84.51.13",
        contrail_service_token => "contrail123",
        contrail_admin_token => "contrail123",
        require => Contrail-database::Contrail-database["contrail_database"]
    }

    # contrail-config role.
    contrail-config::contrail-config{contrail_config:
        contrail_openstack_ip => "10.84.51.13",
        contrail_use_certs => "False",
        contrail_multi_tenancy => "False",
        contrail_config_ip => "10.84.51.13",
        contrail_control_ip => "10.84.51.13",
        contrail_collector_ip => "10.84.51.13",
        contrail_service_token => "contrail123",
        contrail_ks_admin_user => "admin",
        contrail_ks_admin_passwd => "contrail123",
        contrail_ks_admin_tenant => "admin",
        contrail_openstack_root_passwd => "juniper2",
        contrail_cassandra_ip_list => "10.84.51.13:9160",
        require => Contrail-openstack::Contrail-openstack["contrail_openstack"]
    }

    # contrail-control role. TBD Abhay - basicauthusers.properties etc related python script revisit.
    contrail-control::contrail-control{contrail_control:
        contrail_control_ip => "10.84.51.13",
        contrail_config_ip => "10.84.51.13",
        contrail_config_port => "8443",
        contrail_config_user => "10.84.51.13",
        contrail_config_passwd => "10.84.51.13",
        contrail_collector_ip => "10.84.51.13",
        contrail_collector_port => "8086",
        contrail_discovery_ip => "10.84.51.13",
        hostname => "demo2-server",
        host_ip => "10.84.51.13",
        bgp_port => "179",
        cert_ops => "false",
        log_file => "",
        contrail_log_file => "--log-file=/var/log/contrail/control.log",
        require => Contrail-config::Contrail-config["contrail_config"]
    }

    # contrail-collector role.
    contrail-collector::contrail-collector{contrail_collector:
        contrail_config_ip => "10.84.51.13",
        contrail_collector_ip => "10.84.51.13",
        contrail_redis_master_ip => "127.0.0.1",
        contrail_redis_role => "master",
        contrail_cassandra_ip_list => "10.84.51.13:9160",
        contrail_num_collector_nodes => 1,
        require => Contrail-control::Contrail-control["contrail_control"]
    }

    # contrail-webui role.
    contrail-webui::contrail-webui{contrail_webui:
        contrail_config_ip => "10.84.51.13",
        contrail_collector_ip => "10.84.51.13",
        contrail_openstack_ip => "10.84.51.13",
        contrail_cassandra_ip_list => "['10.84.51.13']",
        require => Contrail-collector::Contrail-collector["contrail_collector"]
    }

}
