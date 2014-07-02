class contrail-database {

define database-scripts {
    file { "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
    }
    exec { "setup-${title}" :
        command => "/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh; echo setup-${title} >> /etc/contrail/contrail-compute-exec.out",
        require => File["/opt/contrail/contrail_installer/contrail_setup_utils/${title}.sh"],
        unless  => "grep -qx setup-${title} /etc/contrail/contrail-compute-exec.out",
        provider => shell,
        logoutput => "true"
    }
}

define database-template-scripts {

    # Ensure template param file is present with right content.
    file { "/etc/contrail/${title}" : 
        ensure  => present,
	before => Service["supervisord-contrail-database"],
        content => template("contrail-database/${title}.erb"),
    }
}

define contrail-database (
        $contrail_database_ip,
        $contrail_database_dir,
        $contrail_database_initial_token,
        $contrail_cassandra_seeds,
        $system_name,
        $contrail_config_ip,
        $contrail_zookeeper_ip_list,
        $contrail_cfgm_index,
    ) {

    # Ensure all needed packages are present
    package { 'contrail-openstack-database' : ensure => present,}
    # The above wrapper package should be broken down to the below packages
    # For Debian/Ubuntu - cassandra (>= 1.1.12) , contrail-setup, supervisor
    # For Centos/Fedora - contrail-api-lib, contrail-database, contrail-setup, openstack-quantum-contrail, supervisor

    exec { "exec-config-host-entry" :
        command   => 'echo \"$contrail_config_ip   $system_name\" >> /etc/hosts && echo exec-config-host-entry >> /etc/contrail/contrail-database-exec.out',
        unless    => ["grep -q $contrail_config_ip /etc/hosts",
                      "grep -qx exec-config-host-entry /etc/contrail/contrail-database-exec.out"],
        provider => "shell",
        require => Package['contrail-openstack-database'],
        logoutput => "true"
    }

    if ($operatingsystem == "Ubuntu"){
        file {"/etc/init/supervisord-contrail-database.override": ensure => absent, require => Package['contrail-openstack-database']}
    }

    # database venv installation
    exec { "database-venv" :
        command   => '/bin/bash -c "source ../bin/activate && pip install * && echo database-venv >> /etc/contrail/contrail-database-exec.out"',
        cwd       => '/opt/contrail/database-venv/archive',
        unless    => [ "[ ! -d /opt/contrail/database-venv/archive ]",
                       "[ ! -f /opt/contrail/database-venv/bin/activate ]",
                       "grep -qx database-venv /etc/contrail/contrail-database-exec.out"],
        require   => Package['contrail-openstack-database'],
        provider => "shell",
        logoutput => "true"
    }

    # Ensure that config file and env file are present
    if ($operatingsystem == "Ubuntu") {
        $contrail_cassandra_dir = "/etc/cassandra"
    }
    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
        $contrail_cassandra_dir = "/etc/cassandra/conf"
    }
    file { "$contrail_database_dir" : 
        ensure  => directory,
        require => Package['contrail-openstack-database']
    }

    file { "$contrail_cassandra_dir/cassandra.yaml" : 
        ensure  => present,
        require => [ Package['contrail-openstack-database'] ],
        content => template("contrail-database/cassandra.yaml.erb"),
    }
    file { "$contrail_cassandra_dir/cassandra-env.sh" : 
        ensure  => present,
        require => [ Package['contrail-openstack-database'] ],
        content => template("contrail-database/cassandra-env.sh.erb"),
    }

    # Below is temporary to work-around in Ubuntu as Service resource fails
    # as upstart is not correctly linked to /etc/init.d/service-name
    if ($operatingsystem == "Ubuntu") {
        file { '/etc/init.d/supervisord-contrail-database':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisord-contrail-database"]
        }
    }
    # Ensure the services needed are running.
    service { "supervisord-contrail-database" :
        enable => true,
        require => [ Package["contrail-openstack-database"],
                     Exec['database-venv'] ],
        subscribe => [ File["$contrail_cassandra_dir/cassandra.yaml"],
                       File["$contrail_cassandra_dir/cassandra-env.sh"] ],
        ensure => running,
    }

    # -CHHANDAK
    # set high session timeout to survive glance led disk activity
    file { "/etc/contrail/contrail_setup_utils/config-zk-files-setup.sh":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        require => Package["contrail-openstack-database"],
        source => "puppet:///modules/contrail-database/config-zk-files-setup.sh"
    }
    $contrail_zk_ip_list_for_shell = inline_template('<%= contrail_zookeeper_ip_list.map{ |ip| "#{ip}" }.join(" ") %>')
    $contrail_zk_exec_cmd = "/bin/bash /etc/contrail/contrail_setup_utils/config-zk-files-setup.sh $operatingsystem $contrail_cfgm_index $contrail_zk_ip_list_for_shell && echo setup-config-zk-files-setup >> /etc/contrail/contrail-config-exec.out"
    notify { "contrail contrail_zk_exec_cmd is $contrail_zk_exec_cmd":; } 
    exec { "setup-config-zk-files-setup" :
        command => $contrail_zk_exec_cmd,
        require => File["/etc/contrail/contrail_setup_utils/config-zk-files-setup.sh"],
        unless  => "grep -qx setup-config-zk-files-setup /etc/contrail/contrail-config-exec.out",
        provider => shell,
        logoutput => "true"
    }
    database-scripts { ["database-server-setup"]: }
    # End Here

    database-template-scripts { ["contrail-nodemgr-database.conf", "database_nodemgr_param"]: }

    # Execute config-server-setup scripts
    #config-scripts { ["database-server-setup"] }

 }
	
# end of user defined type contrail-database.

}
