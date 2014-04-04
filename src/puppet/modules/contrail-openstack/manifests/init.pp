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
        $contrail_config_ip,
        $contrail_compute_ip,
        $contrail_openstack_mgmt_ip,
        $contrail_service_token,
        $contrail_ks_admin_passwd,
	$contrail_haproxy,
    ) {

    # list of packages
    package { 'contrail-openstack' : ensure => present,}

    # execute Django-admin
    file { "/etc/contrail/contrail_setup_utils/django-admin.sh" : 
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        source => "puppet:///modules/contrail-openstack/django-admin.sh"
    }

    # TBD Abhay check why below command returns false
    exec { "exec-django-admin" :
        command => "/bin/bash /etc/contrail/contrail_setup_utils/django-admin.sh $operatingsystem && echo exec-django-admin >> /etc/contrail/contrail-openstack-exec.out",
        require =>  File["/etc/contrail/contrail_setup_utils/django-admin.sh"],
        unless  => "grep -qx exec-django-admin /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => 'true'
    }

    if ($operatingsystem == "Ubuntu") {

    exec { "local-settings" :
        command => "echo \"HORIZON_CONFIG[\'customization_module\'] = \'contrail_openstack_dashboard.overrides\'\" >> /etc/openstack-dashboard/local_settings.py && \
			echo \"LOGOUT_URL=\'/horizon/auth/logout/\'\" >> /etc/openstack-dashboard/local_settings.py && \
			 echo exec-local-settings >> /etc/contrail/contrail-openstack-exec.out",
        #require =>  File["/etc/openstack-dashboard/local_settings.py"],
        unless  => "grep -qx exec-local-settings /etc/contrail/contrail-openstack-exec.out",
        provider => shell,
        logoutput => 'true'
    }
}

    # Handle qpidd.conf changes
    if ($operatingsystem == "Ubuntu") {
        $conf_file = "/etc/rabbitmq/rabbitmq.config"
    }
    else {
        $conf_file = "/etc/rabbitmq/rabbitmq.config"
    }
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

    $novaconf_hostname_str = "rabbit_host"
    exec { "exec-openstack-qpid-rabbitmq-hostname" :
        command => "echo \"$novaconf_hostname_str = $contrail_openstack_ip\" >> /etc/nova/nova.conf && echo exec-openstack-qpid-rabbitmq-hostname >> /etc/contrail/contrail-openstack-exec.out",
        require =>  Package["contrail-openstack"],
        unless  => ["grep -qx exec-openstack-qpid-rabbitmq-hostname /etc/contrail/contrail-openstack-exec.out",
                    "grep -qx \"$novaconf_hostname_str = $contrail_openstack_ip\" /etc/nova/nova.conf"],
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

    # Execute keystone-server-setup script
    openstack-scripts { ["keystone-server-setup", "glance-server-setup", "cinder-server-setup", "nova-server-setup"]: }

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
#    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
#        service { "qpidd" :
#            enable => true,
#            ensure => running,
#        }
#    }
    service { "memcached" :
        enable => true,
        ensure => running,
    }
    exec { "exec-update-nova-conf" :
        command => "sed -i \"s/^rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g\" /etc/nova/nova.conf && echo exec-update-nova-conf >> /etc/contrail/contrail-common-exec.out",
        unless  => ["[ ! -f /etc/nova/nova.conf ]",
                        "grep -qx exec-update-nova-conf /etc/contrail/contrail-common-exec.out"],
        provider => shell,
        logoutput => "true"
    }

    Package['contrail-openstack']->File['/etc/contrail/contrail_setup_utils/django-admin.sh']->Exec['exec-django-admin']->File['/etc/contrail/contrail_setup_utils/api-paste.sh']->Exec['exec-api-paste']->Exec['exec-openstack-qpid-rabbitmq-hostname']->File["/etc/contrail/ctrl-details"]->File["/etc/contrail/service.token"]->Exec['exec-update-nova-conf']->Openstack-scripts["keystone-server-setup"]->Openstack-scripts["glance-server-setup"]->Openstack-scripts["cinder-server-setup"]->Openstack-scripts["nova-server-setup"]->Service['mysqld']->Service['openstack-keystone']->Service['memcached']
}
# end of user defined type contrail-openstack.

}
