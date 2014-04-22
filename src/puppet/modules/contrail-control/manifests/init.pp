class contrail-control {

define control-template-scripts {
    # Ensure template param file is present with right content.
    file { "/etc/contrail/${title}" : 
        ensure  => present,
        require => Package["contrail-openstack-control"],
        content => template("contrail-control/${title}.erb"),
    }
}

define contrail-control (
        $contrail_control_ip,
        $contrail_config_ip,
        $contrail_config_port,
        $contrail_config_user,
        $contrail_config_passwd,
        $contrail_collector_ip,
        $contrail_collector_port,
        $contrail_discovery_ip,
        $hostname,
        $host_ip,
        $bgp_port,
        $cert_ops,
        $log_file,
        $contrail_log_file,
        $contrail_api_nworkers
    ) {

    # Ensure all needed packages are present
    package { 'contrail-openstack-control' : ensure => present,}

    # control venv installation
    exec { "control-venv" :
        command   => '/bin/bash -c "source ../bin/activate && pip install * && echo control-venv >> /etc/contrail/contrail-control-exec.out"',
        cwd       => '/opt/contrail/control-venv/archive',
        unless    => ["[ ! -d /opt/contrail/control-venv/archive ]",
                      "[ ! -f /opt/contrail/control-venv/bin/activate ]",
                      "grep -qx control-venv /etc/contrail/contrail-control-exec.out"],
        provider => "shell",
        require => Package['contrail-openstack-control'],
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
            require => Package['contrail-openstack-control'],
            logoutput => "true"
        }
    }

    if ($operatingsystem == "Ubuntu"){
        file {"/etc/init/supervisor-control.override": ensure => absent, require => Package['contrail-openstack-control']}
        file {"/etc/init/supervisor-dns.override": ensure => absent, require => Package['contrail-openstack-control']}
    }

    # Ensure all config files with correct content are present.
    control-template-scripts { ["control_param", "dns_param"]: }

    # Hard-coded to be taken as parameter of vnsi and multi-tenancy options need to be passed to contrail-control too.
    $router_asn = "64512"
    $mt_options = ""
    exec { "provision-control" :
        command => "/bin/bash -c \"python provision_control.py --api_server_ip $contrail_config_ip --api_server_port 8082 --host_name $hostname --host_ip $contrail_control_ip --router_asn $router_asn $mt_options && echo provision-control >> /etc/contrail/contrail-control-exec.out\"",
        cwd => "/opt/contrail/utils",
        unless  => "grep -qx provision-control /etc/contrail/contrail-control-exec.out",
        provider => shell,
        logoutput => 'true'
    }

    Package["contrail-openstack-control"]->Exec['control-venv']->Control-template-scripts["control_param"]->Control-template-scripts["dns_param"]->Exec["provision-control"]

    # Below is temporary to work-around in Ubuntu as Service resource fails
    # as upstart is not correctly linked to /etc/init.d/service-name
    if ($operatingsystem == "Ubuntu") {
        file { '/etc/init.d/supervisor-control':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisor-control"]
        }
        file { '/etc/init.d/supervisor-dns':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["supervisor-dns"]
        }
        file { '/etc/init.d/contrail-named':
            ensure => link,
            target => '/lib/init/upstart-job',
            before => Service["contrail-named"]
        }
    }
    # Ensure the services needed are running.
    service { "supervisor-control" :
        enable => true,
        require => [ Package['contrail-openstack-control'],
                     Exec['control-venv'] ],
        subscribe => File['/etc/contrail/control_param'],
        ensure => running,
    }
if ($operatingsystem == "Ubuntu") {
    service { "supervisor-dns" :
        enable => true,
        require => [ Package['contrail-openstack-control'],
                     Exec['control-venv'] ],
        subscribe => File['/etc/contrail/dns_param'],
        ensure => running,
    }
}
    service { "contrail-named" :
        enable => true,
        require => [ Package['contrail-openstack-control'],
                     Exec['control-venv'] ],
        subscribe => File['/etc/contrail/dns_param'],
        ensure => running,
    }
}
# end of user defined type contrail-control.

}
