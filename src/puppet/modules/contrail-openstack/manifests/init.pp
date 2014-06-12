class contrail-openstack {

define openstack-scripts {
    file { "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
    }
    exec { "setup-${title}" :
        command => "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh $operatingsystem && echo setup-${title} >> /etc/contrail/contrail-openstack-exec.out",
        require => [ File["/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh"],
                     File["/etc/contrail/ctrl-details"] ],
        unless  => "grep -qx setup-${title} /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => "true"
    }
}

define contrail-openstack (
        $contrail_openstack_ip,
        $contrail_keystone_ip = $contrail_openstack_ip,
        $contrail_config_ip,
        $contrail_compute_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_service_token,
        $contrail_ks_admin_passwd,
	$contrail_haproxy,
        $contrail_amqp_server_ip="127.0.0.1",
        $contrail_ks_auth_protocol="http",
        $contrail_quantum_service_protocol="http",
        $contrail_ks_auth_port="35357"
    ) {

    # list of packages
    package { 'contrail-openstack' : ensure => present,}
    # The above wrapper package should be broken down to the below packages
    # For Debian/Ubuntu - python-contrail, openstack-dashboard, contrail-openstack-dashboard, glance, keystone, nova-api, nova-common,
    #                     nova-conductor, nova-console, nova-objectstore, nova-scheduler, cinder-api, cinder-common, cinder-scheduler,
    #                     mysql-server, contrail-setup, memcached, nova-novncproxy, nova-consoleauth, python-m2crypto, haproxy,
    #                     rabbitmq-server, apache2, libapache2-mod-wsgi, python-memcache, python-iniparse, python-qpid, euca2ools
    # For Centos/Fedora - contrail-api-lib, openstack-dashboard, contrail-openstack-dashboard, openstack-glance, openstack-keystone,
    #                     openstack-nova, openstack-cinder, mysql-server, contrail-setup, memcached, openstack-nova-novncproxy,
    #                     python-glance, python-glanceclient, python-importlib, euca2ools, m2crypto, qpid-cpp-server,
    #                     haproxy, rabbitmq-server


    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
        exec { "dashboard-local-settings-1" :
            command => "sudo sed -i 's/ALLOWED_HOSTS =/#ALLOWED_HOSTS =/g' /etc/openstack_dashboard/local_settings && echo dashboard-local-settings-1 >> /etc/contrail/contrail-openstack-exec.out",
            require =>  package["contrail-openstack"],
            onlyif => "test -f /etc/openstack_dashboard/local_settings",
            unless  => "grep -qx dashboard-local-settings-1 /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => 'true'
        }
        exec { "dashboard-local-settings-2" :
            command => "sudo sed -i 's/ALLOWED_HOSTS =/#ALLOWED_HOSTS =/g' /etc/openstack-dashboard/local_settings && echo dashboard-local-settings-2 >> /etc/contrail/contrail-openstack-exec.out",
            require =>  package["contrail-openstack"],
            onlyif => "test -f /etc/openstack-dashboard/local_settings",
            unless  => "grep -qx dashboard-local-settings-2 /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => 'true'
        }
    }

    exec { "update-nova-conf-file" :
        command => "sudo sed -i 's/rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g' /etc/nova/nova.conf && echo update-nova-conf-file >> /etc/contrail/contrail-openstack-exec.out",
        require =>  package["contrail-openstack"],
        onlyif => "test -f /etc/nova/nova.conf",
        unless  => "grep -qx update-nova-conf-file /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => 'true'
    }

    exec { "update-cinder-conf-file" :
        command => "sudo sed -i 's/rpc_backend = cinder.openstack.common.rpc.impl_qpid/#rpc_backend = cinder.openstack.common.rpc.impl_qpid/g' /etc/cinder/cinder.conf && echo update-cinder-conf-file >> /etc/contrail/contrail-openstack-exec.out",
        require =>  package["contrail-openstack"],
        onlyif => "test -f /etc/cinder/cinder.conf",
        unless  => "grep -qx update-cinder-conf-file /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => 'true'
    }

    # Handle rabbitmq.conf changes
    $conf_file = "/etc/rabbitmq/rabbitmq.config"
    if ! defined(File["/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh"]) {
        file { "/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh" : 
            ensure  => present,
            mode => 0755,
            owner => root,
            group => root,
            source => "puppet:///modules/contrail-openstack/cfg-qpidd-rabbitmq.sh"
        }
    }
    if ! defined(Exec["exec-cfg-qpidd-rabbitmq"]) {
        exec { "exec-cfg-qpidd-rabbitmq" :
            command => "/bin/bash /etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh $operatingsystem $conf_file && echo exec-cfg-qpidd-rabbitmq >> /etc/contrail/contrail-openstack-exec.out",
            require =>  File["/etc/contrail/contrail_setup_utils/cfg-qpidd-rabbitmq.sh"],
            unless  => "grep -qx exec-cfg-qpidd-rabbitmq /etc/contrail/contrail-openstack-exec.out",
            provider => shell,
            logoutput => 'true'
        }
    }

    file { "/etc/contrail/contrail_setup_utils/api-paste.sh" : 
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        source => "puppet:///modules/contrail-openstack/api-paste.sh"
    }
    exec { "exec-api-paste" :
        command => "/bin/bash /etc/contrail/contrail_setup_utils/api-paste.sh && echo exec-api-paste >> /etc/contrail/contrail-openstack-exec.out",
        require =>  File["/etc/contrail/contrail_setup_utils/api-paste.sh"],
        unless  => "grep -qx exec-api-paste /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => 'true'
    }

    exec { "exec-openstack-qpid-rabbitmq-hostname" :
        command => "echo \"rabbit_host = $contrail_amqp_server_ip\" >> /etc/nova/nova.conf && echo exec-openstack-qpid-rabbitmq-hostname >> /etc/contrail/contrail-openstack-exec.out",
        require =>  Package["contrail-openstack"],
        unless  => ["grep -qx exec-openstack-qpid-rabbitmq-hostname /etc/contrail/contrail-openstack-exec.out",
                    "grep -qx \"rabbit_host = $contrail_amqp_server_ip\" /etc/nova/nova.conf"],
        provider => shell,
        logoutput => 'true'
    }
    
    # Ensure ctrl-details file is present with right content.
    if ! defined(File["/etc/contrail/ctrl-details"]) {
        $quantum_port = "9697"
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

    # Execute keystone-server-setup script
    openstack-scripts { ["keystone-server-setup", "glance-server-setup", "cinder-server-setup", "nova-server-setup"]: }

    if (!defined(File["/etc/haproxy/haproxy.cfg"])) and ( $contrail_haproxy == "enable" )  {
    	file { "/etc/haproxy/haproxy.cfg":
       	   ensure  => present,
           mode => 0755,
           owner => root,
           group => root,
           source => "puppet:///modules/contrail-common/$hostname.cfg"
        }
        exec { "haproxy-exec":
                command => "sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy;",
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

    # repeat keystone setup (workaround for now) Needs to be fixed .. Abhay
    if ($operatingsystem == "Ubuntu") {
	    exec { "setup-keystone-server-2setup" :
		    command => "/opt/contrail/contrail_installer/contrail_setup_utils/keystone-server-setup.sh $operatingsystem && echo setup-keystone-server-2setup >> /etc/contrail/contrail-openstack-exec.out",
		    require => [ File["/opt/contrail/contrail_installer/contrail_setup_utils/keystone-server-setup.sh"],
		    File["/etc/contrail/ctrl-details"],
		    Openstack-scripts['nova-server-setup'] ],
		    unless  => "grep -qx setup-keystone-server-2setup /etc/contrail/contrail-openstack-exec.out",
		    provider => shell,
		    logoutput => "true",
		    before => Service['mysqld']
	    }
# Below is temporary to work-around in Ubuntu as Service resource fails
# as upstart is not correctly linked to /etc/init.d/service-name
	    file { '/etc/init.d/mysqld':
		    ensure => link,
			   target => '/lib/init/upstart-job',
			   before => Service["mysqld"]
	    }
	    file { '/etc/init.d/openstack-keystone':
		    ensure => link,
			   target => '/lib/init/upstart-job',
			   before => Service["openstack-keystone"]
	    }
    }
    # Ensure the services needed are running.
    service { "mysqld" :
        enable => true,
        require => [ Package['contrail-openstack'] ],
        ensure => running,
    }

    service { "openstack-keystone" :
        enable => true,
        require => [ Package['contrail-openstack'],
                     Openstack-scripts["nova-server-setup"] ],
        ensure => running,
    }
    service { "memcached" :
        enable => true,
        ensure => running,
    }

    Package['contrail-openstack']->File['/etc/contrail/contrail_setup_utils/api-paste.sh']->Exec['exec-api-paste']->Exec['exec-openstack-qpid-rabbitmq-hostname']->File["/etc/contrail/ctrl-details"]->File["/etc/contrail/service.token"]->Openstack-scripts["keystone-server-setup"]->Openstack-scripts["glance-server-setup"]->Openstack-scripts["cinder-server-setup"]->Openstack-scripts["nova-server-setup"]->Service['mysqld']->Service['openstack-keystone']->Service['memcached']
}
# end of user defined type contrail-openstack.

}
