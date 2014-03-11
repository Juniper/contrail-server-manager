node 'demo1-server.demo.juniper.net' {
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
       self_ip => "10.84.51.12",
       system_name => "demo1-server",
    }

    # contrail-compute role.
    contrail-compute::contrail-compute{contrail_compute:
        contrail_config_ip => "10.84.51.13",
        contrail_compute_hostname => "demo1-server",
        contrail_compute_ip => "10.84.51.12",
        contrail_collector_ip => "10.84.51.13",
        contrail_openstack_ip => "10.84.51.13",
        contrail_openstack_mgmt_ip => "10.84.51.13",
        contrail_service_token => "contrail123",
        contrail_physical_interface => "eth0",
        contrail_num_controls => "1",
        contrail_non_mgmt_ip => "",
        contrail_non_mgmt_gw => "",
        contrail_ks_admin_user => "admin",
        contrail_ks_admin_passwd => "contrail123",
        contrail_ks_admin_tenant => "admin",
        require => Contrail-common::Contrail-common["contrail_common"]
    }

}