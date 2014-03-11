class contrail-webui {

define contrail-webui (
        $contrail_config_ip,
        $contrail_collector_ip,
        $contrail_openstack_ip,
        $contrail_cassandra_ip_list
    ) {
    # Ensure all needed packages are present
    package { 'contrail-openstack-webui' : ensure => present,}

    # Ensure global config js file is present.
    file { "/etc/contrail/config.global.js" : 
        ensure  => present,
        require => Package["contrail-openstack-webui"],
        content => template("contrail-webui/config.global.js.erb"),
    }

    # Below is temporary to work-around in Ubuntu as Service resource fails
    # as upstart is not correctly linked to /etc/init.d/service-name
    if ($operatingsystem == "Ubuntu") {
        file { '/etc/init.d/supervisor-webui':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisor-webui"]
        }
    }
    # Ensure the services needed are running.
    service { "supervisor-webui" :
        enable => true,
        subscribe => File['/etc/contrail/config.global.js'],
        ensure => running,
    }
}
# end of user defined type contrail-webui.

}
