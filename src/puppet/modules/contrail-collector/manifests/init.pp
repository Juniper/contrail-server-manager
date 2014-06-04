class contrail-collector {

define collector-template-scripts {
    # Ensure template param file is present with right content.
    file { "/etc/contrail/${title}" : 
        ensure  => present,
        require => Package["contrail-openstack-analytics"],
        content => template("contrail-collector/${title}.erb"),
    }
}

define contrail-collector (
        $contrail_config_ip,
        $contrail_collector_ip,
        $contrail_redis_master_ip,
        $contrail_redis_role,
        $contrail_cassandra_ip_list,
        $contrail_cassandra_ip_port,
        $contrail_num_collector_nodes,
        $contrail_analytics_data_ttl
    ) {

    # Ensure all needed packages are present
    package { 'contrail-openstack-analytics' : ensure => present,}
    # The above wrapper package should be broken down to the below packages
    # For Debian/Ubuntu - supervisor, python-contrail, contrail-analytics, contrail-setup, contrail-nodemgr
    # For Centos/Fedora - contrail-api-pib, contrail-analytics, contrail-setup, contrail-nodemgr

    if ($operatingsystem == "Ubuntu"){
        file {"/etc/init/supervisor-analytics.override": ensure => absent, require => Package['contrail-openstack-analytics']}
    }

    # analytics venv installation
    exec { "analytics-venv" :
        command   => '/bin/bash -c "source ../bin/activate && pip install * && echo analytics-venv >> /etc/contrail/contrail-collector-exec.out"',
        cwd       => '/opt/contrail/analytics-venv/archive',
        unless    => ["[ ! -d /opt/contrail/analytics-venv/archive ]",
                      "[ ! -f /opt/contrail/analytics-venv/bin/activate ]",
                      "grep -qx analytics-venv /etc/contrail/contrail-collector-exec.out"],
        provider => "shell",
        require => Package['contrail-openstack-analytics'],
        logoutput => "true"
    }

    # Ensure all config files with correct content are present.
    collector-template-scripts { ["contrail-analytics-api.conf" , "collector.conf", "query-engine.conf"]: }

    # The below commented code is not used in latest fab. Need to check with analytics team and then remove
    # if not needed.
    # if ($contrail_num_collector_nodes > 0) {
    #     if ($contrail_num_collector_nodes > 1) {
    #         $sentinel_quoram = $contrail_num_collector_nodes - 1
    #     }
    #     else {
    #         $sentinel_quoram = 1
    #     }
    #     file { "/etc/contrail/sentinel.conf" : 
    #         ensure  => present,
    #         require => Package["contrail-openstack-analytics"],
    #         content => template("contrail-collector/sentinel.conf.erb"),
    #     }
    #     if ($contrail_redis_role == "slave") {
    #         file { "/etc/contrail/redis-uve.conf" : 
    #             ensure  => present,
    #             require => Package["contrail-openstack-analytics"],
    #             content => template("contrail-collector/redis-uve.conf.erb"),
    #         }
    #     }
    # }
    # end commented out code.

    # Below is temporary to work-around in Ubuntu as Service resource fails
    # as upstart is not correctly linked to /etc/init.d/service-name
    if ($operatingsystem == "Ubuntu") {
        file { '/etc/init.d/supervisor-analytics':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisor-analytics"]
        }
    }
    # Ensure the services needed are running.
    service { "supervisor-analytics" :
        enable => true,
        require => [ Package['contrail-openstack-analytics'],
                     Exec['analytics-venv'] ],
        subscribe => [ File['/etc/contrail/collector.conf'],
                       File['/etc/contrail/query-engine.conf'],
                       File['/etc/contrail/contrail-analytics-api.conf'] ],
        ensure => running,
    }
}
# end of user defined type contrail-collector.

}
