class contrail-compute {

# Macro to push and execute certain scripts.
define compute-scripts {
    file { "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        require => File["/etc/contrail/ctrl-details"],
    }
    exec { "setup-${title}" :
        command => "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh; echo setup-${title} >> /etc/contrail/contrail-compute-exec.out",
        require => File["/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh"],
        unless  => "grep -qx setup-${title} /etc/contrail/contrail-compute-exec.out",
        provider => shell,
        logoutput => "true"
    }
}

define compute-template-scripts {
    # Ensure template param file is present with right content.
    file { "/etc/contrail/${title}" : 
        ensure  => present,
        require => Package["contrail-openstack-vrouter"],
        content => template("contrail-compute/${title}.erb"),
    }
}

define contrail-compute-part-1 (
        $contrail_config_ip,
        $contrail_compute_ip,
        $contrail_compute_hostname,
        $contrail_collector_ip,
        $contrail_openstack_ip,
        $contrail_keystone_ip = $contrail_openstack_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_service_token,
        $contrail_physical_interface,
        $contrail_num_controls,
        $contrail_non_mgmt_ip,
        $contrail_non_mgmt_gw,
        $contrail_ks_admin_user,
        $contrail_ks_admin_passwd,
        $contrail_ks_admin_tenant,
    ) {
    # Ensure all needed packages are present
    package { 'contrail-openstack-vrouter' : ensure => present,}
    package { 'contrail-interface-name' : ensure => present,}

    # vrouter venv installation
    exec { "vrouter-venv" :
        command   => '/bin/bash -c "source ../bin/activate && pip install * && echo vrouter-venv >> /etc/contrail/contrail-compute-exec.out"',
        cwd       => '/opt/contrail/vrouter-venv/archive',
        unless    => ["[ ! -d /opt/contrail/vrouter-venv/archive ]",
                      "[ ! -f /opt/contrail/vrouter-venv/bin/activate ]",
                      "grep -qx vrouter-venv /etc/contrail/contrail-compute-exec.out"],
        provider => "shell",
        require => Package['contrail-openstack-vrouter'],
        logoutput => "true"
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
            require => Package['contrail-openstack-vrouter'],
            logoutput => "true"
        }
    }

    # flag that part 1 is completed and reboot the system
    file { "/etc/contrail/interface_renamed" :
        ensure  => present,
        mode => 0644,
        require => [ Package["contrail-openstack-vrouter"],
                     Package["contrail-interface-name"],
                     Exec["vrouter-venv"] ],
        content => "1"
    }

    # Now reboot the system
    exec { "reboot-server" :
        command   => "echo reboot-server-1 >> /etc/contrail/contrail-compute-exec.out && reboot",
        require    => File["/etc/contrail/interface_renamed"],
        unless => ["grep -qx reboot-server-1 /etc/contrail/contrail-compute-exec.out"],
        provider => "shell"
    }

    Package['contrail-openstack-vrouter'] -> Package["contrail-interface-name"] -> Exec['vrouter-venv'] -> File["/etc/contrail/interface_renamed"] -> Exec["reboot-server"]
}

define contrail-compute-part-2 (
        $contrail_config_ip,
        $contrail_compute_ip,
        $contrail_compute_hostname,
        $contrail_collector_ip,
        $contrail_openstack_ip,
        $contrail_keystone_ip = $contrail_openstack_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_service_token,
        $contrail_physical_interface,
        $contrail_num_controls,
        $contrail_non_mgmt_ip,
        $contrail_non_mgmt_gw,
        $contrail_ks_admin_user,
        $contrail_ks_admin_passwd,
        $contrail_ks_admin_tenant,
	$contrail_haproxy,
        $contrail_ks_auth_protocol="http",
        $contrail_quantum_service_protocol="http",
        $contrail_amqp_server_ip="127.0.0.1",
        $contrail_ks_auth_port="35357"
    ) {
    # Ensure all needed packages are present
    package { 'contrail-openstack-vrouter' : ensure => present,}

    if ($operatingsystem == "Ubuntu"){
        file {"/etc/init/supervisor-vrouter.override": ensure => absent, require => Package['contrail-openstack-vrouter']}
    }

    # vrouter venv installation
    exec { "vrouter-venv" :
        command   => '/bin/bash -c "source ../bin/activate && pip install * && echo vrouter-venv >> /etc/contrail/contrail-compute-exec.out"',
        cwd       => '/opt/contrail/vrouter-venv/archive',
        unless    => ["[ ! -d /opt/contrail/vrouter-venv/archive ]",
                      "[ ! -f /opt/contrail/vrouter-venv/bin/activate ]",
                      "grep -qx vrouter-venv /etc/contrail/contrail-compute-exec.out"],
        provider => "shell",
        require => Package['contrail-openstack-vrouter'],
        logoutput => "true"
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
            require => Package['contrail-openstack-vrouter'],
            logoutput => "true"
        }
    }

    #Ensure Ha-proxy cfg file is set
    if (!defined(File["/etc/haproxy/haproxy.cfg"])) and ( $contrail_haproxy == "enable" )  {
    	file { "/etc/haproxy/haproxy.cfg":
       	   ensure  => present,
           mode => 0755,
           owner => root,
           group => root,
           source => "puppet:///modules/contrail-common/$hostname.cfg"
        }
        exec { "haproxy-exec":
                command => "sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy",
                provider => shell,
                logoutput => "true",
                require => File["/etc/haproxy/haproxy.cfg"]
        }
        service { "haproxy" :
            enable => true,
            require => [File["/etc/default/haproxy"],
                        File["/etc/haproxy/haproxy.cfg"]],
            ensure => running
        }
     }

    exec { "exec-compute-qpid-rabbitmq-hostname" :
        command => "echo \"rabbit_host = $contrail_amqp_server_ip\" >> /etc/nova/nova.conf && echo exec-compute-qpid-rabbitmq-hostname >> /etc/contrail/contrail-compute-exec.out",
        unless  => ["grep -qx exec-compute-qpid-rabbitmq-hostname /etc/contrail/contrail-compute-exec.out",
                    "grep -qx \"rabbit_host = $contrail_amqp_server_ip\" /etc/nova/nova.conf"],
        provider => shell,
        logoutput => 'true'
    }

    exec { "exec-compute-neutron-admin" :
        command => "echo \"neutron_admin_auth_url = http://$contrail_keystone_ip:5000/v2.0\" >> /etc/nova/nova.conf && echo exec-compute-neutron-admin >> /etc/contrail/contrail-compute-exec.out",
        unless  => ["grep -qx exec-compute-neutron-admin /etc/contrail/contrail-compute-exec.out",
                    "grep -qx \"neutron_admin_auth_url = http://$contrail_openstack_ip/v2.0\" /etc/nova/nova.conf"],
        provider => shell,
        logoutput => 'true'
    }

    exec { "exec-compute-update-nova-conf" :
        command => "sed -i \"s/^rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g\" /etc/nova/nova.conf && echo exec-update-nova-conf >> /etc/contrail/contrail-common-exec.out",
       	unless  => ["[ ! -f /etc/nova/nova.conf ]",
                    "grep -qx exec-update-nova-conf /etc/contrail/contrail-common-exec.out"],
        provider => shell,
       	logoutput => "true"
    }
    
    # Ensure ctrl-details file is present with right content.
    if ! defined(File["/etc/contrail/ctrl-details"]) {
        $quantum_port = "9697"
     	if ($contrail_haproxy == "enable") {
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

    # Update modprobe.conf
    if inline_template('<%= operatingsystem.downcase %>') == "centos" {
        file { "/etc/modprobe.conf" : 
            ensure  => present,
            require => Package['contrail-openstack-vrouter'],
            content => template("contrail-compute/modprobe.conf.erb")
        }
    }

    # Ensure qemu.conf file is present.
    file { "/etc/libvirt/qemu.conf" : 
        ensure  => present,
    }

    # Ensure all config files with correct content are present.
    if ($contrail_haproxy == "enable") {
	$discovery_ip = "127.0.0.1"
    } else {
	$discovery_ip = $contrail_config_ip
    }

    compute-template-scripts {"vrouter_nodemgr_param":}

    if  ($contrail_non_mgmt_ip != "") and
        ($contrail_non_mgmt_ip != $contrail_compute_ip) {
        $contrail_multinet = "true"
        $contrail_vhost_ip = $contrail_non_mgmt_ip
    }
    else {
        $contrail_multinet = "false"
        $contrail_vhost_ip = $contrail_compute_ip
    }

    # Get the dev names
    $intf_array = split($interfaces, ",")
    if ($contrail_physical_interface != "") {
       if (inline_template("<%= intf_array.include?(@contrail_physical_interface) %>") == "true") {
          $contrail_dev = $contrail_physical_interface
          $contrail_compute_dev = ""
       }
       else {
           fail("Error : Interface name provided does not exist on target node")
       }
    }
    else {
        $contrail_dev = get_device_name("$contrail_vhost_ip")
        notify { "contrail device is $contrail_dev":; }
        if ($contrail_multinet == "true") {
            $contrail_compute_dev = get_device_name("$contrail_compute_ip")
        }
        else {
            $contrail_compute_dev = ""
        }
    }

    if ($contrail_dev == undef) {
        fail("contrail device is not found")
    }

    # Get Mac, netmask and gway
    if ($contrail_dev != undef and $contrail_dev != "vhost0") {
        $contrail_macaddr = inline_template("<%= scope.lookupvar('macaddress_' + @contrail_dev) %>")
        $contrail_netmask = inline_template("<%= scope.lookupvar('netmask_' + @contrail_dev) %>")
        $contrail_cidr = convert_netmask_to_cidr($contrail_netmask)

        if ($contrail_multinet == "true") {
            $contrail_gway = $contrail_non_mgmt_gw
        }
        else {
            $contrail_gway = $contrail_gateway
        }

        # Ensure all config files with correct content are present.
        compute-template-scripts { ["default_pmac",
                                    "agent_param.tmpl",
                                    "rpm_agent.conf",
				    "contrail-vrouter-agent.conf"]: 
        }

        file { "/etc/contrail/contrail_setup_utils/update_dev_net_config_files.py":
            ensure  => present,
            mode => 0755,
            owner => root,
            group => root,
            source => "puppet:///modules/contrail-compute/update_dev_net_config_files.py"
        }

        exec { "update-dev-net-config" :
            command => "/bin/bash -c \"python /etc/contrail/contrail_setup_utils/update_dev_net_config_files.py --compute_ip $contrail_compute_ip --physical_interface \'$contrail_physical_interface\' --non_mgmt_ip \'$contrail_non_mgmt_ip\' --non_mgmt_gw \'$contrail_non_mgmt_gw\' --collector_ip $contrail_collector_ip --discovery_ip $contrail_config_ip --ncontrols $contrail_num_controls --mac $contrail_macaddr && echo update-dev-net-config >> /etc/contrail/contrail-compute-exec.out\"",
            require => [ File["/etc/contrail/contrail_setup_utils/update_dev_net_config_files.py"] ],
            unless  => "grep -qx update-dev-net-config /etc/contrail/contrail-compute-exec.out",
            provider => shell,
            logoutput => 'true'
        }

        file { "/etc/contrail/contrail_setup_utils/provision_vrouter.py":
            ensure  => present,
            mode => 0755,
            owner => root,
            group => root,
            source => "puppet:///modules/contrail-compute/provision_vrouter.py"
        }
        exec { "add-vnc-config" :
            command => "/bin/bash -c \"python /etc/contrail/contrail_setup_utils/provision_vrouter.py --host_name $contrail_compute_hostname --host_ip $contrail_compute_ip --api_server_ip $contrail_config_ip --oper add --admin_user $contrail_ks_admin_user --admin_password $contrail_ks_admin_passwd --admin_tenant_name $contrail_ks_admin_tenant && echo add-vnc-config >> /etc/contrail/contrail-compute-exec.out\"",
            require => File["/etc/contrail/contrail_setup_utils/provision_vrouter.py"],
            unless  => "grep -qx add-vnc-config /etc/contrail/contrail-compute-exec.out",
            provider => shell,
            logoutput => 'true'
        }

        compute-scripts { ["compute-server-setup"]: }

        # flag that part 2 is completed and reboot the system
        file { "/etc/contrail/interface_renamed" :
            ensure  => present,
            mode => 0644,
            content => "2"
        }

        # Now reboot the system
        if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
            exec { "cp-ifcfg-file" :
                command   => "cp -f /etc/contrail/ifcfg-* /etc/sysconfig/network-scripts && echo cp-ifcfg-file >> /etc/contrail/contrail-compute-exec.out",
                require    => File["/etc/contrail/interface_renamed"],
                before => Exec["reboot-server"],
                unless  => "grep -qx cp-ifcfg-file /etc/contrail/contrail-compute-exec.out",
                provider => "shell",
                logoutput => 'true'
            }
        }
        exec { "reboot-server" :
            command   => "echo reboot-server-2 >> /etc/contrail/contrail-compute-exec.out && reboot",
            require    => File["/etc/contrail/interface_renamed"],
            unless => ["grep -qx reboot-server-2 /etc/contrail/contrail-compute-exec.out"],
            provider => "shell",
            logoutput => 'true'
        }
        Package['contrail-openstack-vrouter'] -> File["/etc/libvirt/qemu.conf"] -> Compute-template-scripts["vrouter_nodemgr_param"] -> Compute-template-scripts["default_pmac"] ->  Compute-template-scripts["agent_param.tmpl"] ->  Compute-template-scripts["rpm_agent.conf"] -> File["/etc/contrail/contrail_setup_utils/update_dev_net_config_files.py"] -> Exec["update-dev-net-config"] ->  Compute-template-scripts["contrail-vrouter-agent.conf"] -> File["/etc/contrail/contrail_setup_utils/provision_vrouter.py"] -> Exec["add-vnc-config"] -> Compute-scripts["compute-server-setup"] -> File["/etc/contrail/interface_renamed"] -> Exec["reboot-server"]
    }
    else {
        file { "/etc/contrail/contrail_setup_utils/update_dev_net_config_files.py":
            ensure  => present,
            mode => 0755,
            owner => root,
            group => root,
            source => "puppet:///modules/contrail-compute/update_dev_net_config_files.py"
        }

        exec { "update-dev-net-config" :
            command => "/bin/bash \"python /etc/contrail/contrail_setup_utils/update_dev_net_config_files.py --compute_ip $contrail_compute_ip --physical_interface \'$contrail_physical_interface\' --non_mgmt_ip \'$contrail_non_mgmt_ip\' --non_mgmt_gw \'$contrail_non_mgmt_gw\' --collector_ip $contrail_collector_ip --discovery_ip $contrail_config_ip --ncontrols $contrail_num_controls --mac $contrail_macaddr && echo update-dev-net-config >> /etc/contrail/contrail-compute-exec.out\"",
            require => [ File["/etc/contrail/contrail_setup_utils/update_dev_net_config_files.py"] ],
            unless  => "grep -qx update-dev-net-config /etc/contrail/contrail-compute-exec.out",
            provider => shell,
            logoutput => 'true'
        }
    }
}

define contrail-compute (
        $contrail_config_ip,
        $contrail_compute_ip,
        $contrail_compute_hostname,
        $contrail_collector_ip,
        $contrail_openstack_ip,
        $contrail_keystone_ip = $contrail_openstack_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_service_token,
        $contrail_physical_interface,
        $contrail_num_controls,
        $contrail_non_mgmt_ip,
        $contrail_non_mgmt_gw,
        $contrail_ks_admin_user,
        $contrail_ks_admin_user,
        $contrail_ks_admin_passwd,
        $contrail_ks_admin_tenant,
	$contrail_haproxy,
        $contrail_ks_auth_protocol="http",
        $contrail_quantum_service_protocol="http",
        $contrail_amqp_server_ip="127.0.0.1",
        $contrail_ks_auth_port="35357"
    ) {

    if ($operatingsystem == "Ubuntu") {
        if ($contrail_interface_rename_done != "2") {
            contrail-compute-part-2 { contrail-compute-2 :
                contrail_config_ip => $contrail_config_ip,
                contrail_compute_ip => $contrail_compute_ip,
                contrail_compute_hostname => $contrail_compute_hostname,
                contrail_collector_ip => $contrail_collector_ip,
                contrail_openstack_ip => $contrail_openstack_ip,
                contrail_keystone_ip => $contrail_keystone_ip,
                contrail_openstack_mgmt_ip => $contrail_openstack_mgmt_ip,
                contrail_service_token => $contrail_service_token,
                contrail_physical_interface => "",
                contrail_num_controls => $contrail_num_controls,
                contrail_non_mgmt_ip => $contrail_non_mgmt_ip,
                contrail_non_mgmt_gw => $contrail_non_mgmt_gw,
                contrail_ks_admin_user => $contrail_ks_admin_user,
                contrail_ks_admin_passwd => $contrail_ks_admin_passwd,
                contrail_ks_admin_tenant => $contrail_ks_admin_tenant,
		contrail_haproxy => $contrail_haproxy,
                contrail_ks_auth_protocol => $contrail_ks_auth_protocol,
                contrail_quantum_service_protocol => $contrail_quantum_service_protocol,
                contrail_amqp_server_ip => $contrail_amqp_server_ip,
                contrail_ks_auth_port => $contrail_ks_auth_port
            }
        }
        else {
            # Nothing for now, add code here for anything to be done after second reboot
        }
    }
    else {
        if ($contrail_interface_rename_done == "0") {
            contrail-compute-part-1 { contrail-compute-1 :
                contrail_config_ip => $contrail_config_ip,
                contrail_compute_ip => $contrail_compute_ip,
                contrail_compute_hostname => $contrail_compute_hostname,
                contrail_collector_ip => $contrail_collector_ip,
                contrail_openstack_ip => $contrail_openstack_ip,
                contrail_keystone_ip => $contrail_keystone_ip,
                contrail_openstack_mgmt_ip => $contrail_openstack_mgmt_ip,
                contrail_service_token => $contrail_service_token,
                contrail_physical_interface => $contrail_physical_interface,
                contrail_num_controls => $contrail_num_controls,
                contrail_non_mgmt_ip => $contrail_non_mgmt_ip,
                contrail_non_mgmt_gw => $contrail_non_mgmt_gw,
                contrail_ks_admin_user => $contrail_ks_admin_user,
                contrail_ks_admin_passwd => $contrail_ks_admin_passwd,
                contrail_ks_admin_tenant => $contrail_ks_admin_tenant,
            }
        }
        elsif ($contrail_interface_rename_done == "1") {
            contrail-compute-part-2 { contrail-compute-2 :
                contrail_config_ip => $contrail_config_ip,
                contrail_compute_ip => $contrail_compute_ip,
                contrail_compute_hostname => $contrail_compute_hostname,
                contrail_collector_ip => $contrail_collector_ip,
                contrail_openstack_ip => $contrail_openstack_ip,
                contrail_keystone_ip => $contrail_keystone_ip,
                contrail_openstack_mgmt_ip => $contrail_openstack_mgmt_ip,
                contrail_service_token => $contrail_service_token,
                contrail_physical_interface => "",
                contrail_num_controls => $contrail_num_controls,
                contrail_non_mgmt_ip => $contrail_non_mgmt_ip,
                contrail_non_mgmt_gw => $contrail_non_mgmt_gw,
                contrail_ks_admin_user => $contrail_ks_admin_user,
                contrail_ks_admin_passwd => $contrail_ks_admin_passwd,
                contrail_ks_admin_tenant => $contrail_ks_admin_tenant,
		contrail_haproxy => $contrail_haproxy,
                contrail_ks_auth_protocol => $contrail_ks_auth_protocol,
                contrail_quantum_service_protocol => $contrail_quantum_service_protocol,
                contrail_amqp_server_ip => $contrail_amqp_server_ip,
                contrail_ks_auth_port => $contrail_ks_auth_port
            }
        }
        else {
            # Nothing for now, add code here for anything to be done after second reboot
        }
    }
}
# end of user defined type contrail-compute.

}
