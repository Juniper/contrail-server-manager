class contrail-common {

# Macro to ensure that a line is either presnt or absent in file.
define line($file, $line, $ensure = 'present') {
    case $ensure {
        default : { err ( "unknown ensure value ${ensure}" ) }
        present: {
            exec { "/bin/echo '${line}' >> '${file}'":
                unless => "/bin/grep -qFx '${line}' '${file}'",
                logoutput => "true"
            }
        }
        absent: {
            exec { "/bin/grep -vFx '${line}' '${file}' | /usr/bin/tee '${file}' > /dev/null 2>&1":
              onlyif => "/bin/grep -qFx '${line}' '${file}'",
                logoutput => "true"
            }

            # Use this resource instead if your platform's grep doesn't support -vFx;
            # note that this command has been known to have problems with lines containing quotes.
            # exec { "/usr/bin/perl -ni -e 'print unless /^\\Q${line}\\E\$/' '${file}'":
            #     onlyif => "/bin/grep -qFx '${line}' '${file}'",
            #     logoutput => "true"
            # }
        }
    }
}
# End of macro line

#source ha proxy files
define haproxy-cfg($server_id) {
    file { "/etc/haproxy/haproxy.cfg":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        source => "puppet:///modules/contrail-common/$server_id.cfg"
    }
	exec { "haproxy-exec":
		command => "sudo sed -i 's/ENABLED=.*/ENABLED=1/g' /etc/default/haproxy; chkconfig haproxy on; service haproxy restart",
		provider => shell,
		logoutput => "true",
		require => File["/etc/haproxy/haproxy.cfg"]
	}
}

# macro to perform common functions
define contrail-common (
        $self_ip,
        $system_name
    ) {
    host { "$system_name" :
        ensure => present,
        ip => "$self_ip"
    }

    # Disable SELINUX on boot, if not already disabled.
    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
        exec { "selinux-dis-1" :
            command   => "sed -i \'s/SELINUX=.*/SELINUX=disabled/g\' config",
            cwd       => '/etc/selinux',
            onlyif    => '[ -d /etc/selinux ]',
            unless    => "grep -qFx 'SELINUX=disabled' '/etc/selinux/config'",
            provider  => shell,
            logoutput => "true"
        }

        # disable selinux runtime
        exec { "selinux-dis-2" :
            command   => "setenforce 0 || true",
            unless    => "getenforce | grep -qi disabled",
            provider  => shell,
            logoutput => "true"
        }

        # Disable iptables
        service { "iptables" :
            enable => false,
            ensure => stopped
        }
    }

    if ($operatingsystem == "Ubuntu") {
        # disable firewall
        exec { "disable-ufw" :
            command   => "ufw disable",
            unless    => "ufw status | grep -qi inactive",
            provider  => shell,
            logoutput => "true"
        }
        # Create symbolic link to chkconfig. This does not exist on Ubuntu.
        file { '/sbin/chkconfig':
            ensure => link,
            target => '/bin/true'
        }
    }

    # Flush ip tables.
    exec { 'iptables --flush': provider => shell, logoutput => true }

    # Remove any core limit configured
    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {
        exec { 'daemon-core-file-unlimited':
            command   => "sed -i \'/DAEMON_COREFILE_LIMIT=.*/d\' /etc/sysconfig/init; echo DAEMON_COREFILE_LIMIT=\"\'unlimited\'\" >> /etc/sysconfig/init",
            unless    => "grep -qx \"DAEMON_COREFILE_LIMIT='unlimited'\" /etc/sysconfig/init",
            provider => shell,
            logoutput => "true"
        }
    }
    if ($operatingsystem == "Ubuntu") {
        exec { "core-file-unlimited" :
            command   => "ulimit -c unlimited",
            unless    => "ulimit -c | grep -qi unlimited",
            provider  => shell,
            logoutput => "true"
        }
    }

    # Core pattern
    exec { 'core_pattern_1':
        command   => 'echo \'kernel.core_pattern = /var/crashes/core.%e.%p.%h.%t\' >> /etc/sysctl.conf',
        unless    => "grep -q 'kernel.core_pattern = /var/crashes/core.%e.%p.%h.%t' /etc/sysctl.conf",
        provider => shell,
        logoutput => "true"
    }

    # Enable ip forwarding in sysctl.conf for vgw
    exec { 'enable-ipf-for-vgw':
        command   => "sed -i \"s/net.ipv4.ip_forward.*/net.ipv4.ip_forward = 1/g\" /etc/sysctl.conf",
        unless    => ["[ ! -f /etc/sysctl.conf ]",
                      "grep -qx \"net.ipv4.ip_forward = 1\" /etc/sysctl.conf"],
        provider => shell,
        logoutput => "true"
    }

    # 
    exec { 'sysctl -e -p' : provider => shell, logoutput => on_failure }
    file { "/var/crashes":
        ensure => "directory",
    }

    # Make sure our scripts directory is present
    file { "/etc/contrail":
        ensure => "directory",
    }
    file { "/etc/contrail/contrail_setup_utils":
        ensure => "directory",
        require => File["/etc/contrail"]
    }

    # Enable kernel core.
    file { "/etc/contrail/contrail_setup_utils/enable_kernel_core.py":
        ensure  => present,
        mode => 0755,
        owner => root,
        group => root,
        source => "puppet:///modules/contrail-common/enable_kernel_core.py"
    }

    # enable kernel core , below python code has bug, for now ignore by executing echo regardless and thus returning true for cmd.
    # need to revisit afterwards.
    exec { "enable-kernel-core" :
        #command => "python /etc/contrail/contrail_setup_utils/enable_kernel_core.py && echo enable-kernel-core >> /etc/contrail/contrail-common-exec.out",
        command => "python /etc/contrail/contrail_setup_utils/enable_kernel_core.py; echo enable-kernel-core >> /etc/contrail/contrail-common-exec.out",
        require => File["/etc/contrail/contrail_setup_utils/enable_kernel_core.py" ],
        unless  => "grep -qx enable-kernel-core /etc/contrail/contrail-common-exec.out",
        provider => shell,
        logoutput => "true"
    }


    if ($operatingsystem == "Ubuntu"){

        exec { "exec-update-neutron-conf" :
            command => "sed -i \"s/^rpc_backend = nova.openstack.common.rpc.impl_qpid/#rpc_backend = nova.openstack.common.rpc.impl_qpid/g\" /etc/neutron/neutron.conf && echo exec-update-neutron-conf >> /etc/contrail/contrail-common-exec.out",
            unless  => ["[ ! -f /etc/neutron/neutron.conf ]",
                        "grep -qx exec-update-neutron-conf /etc/contrail/contrail-common-exec.out"],
            provider => shell,
            logoutput => "true"
        }
    }

    if ($operatingsystem == "Centos" or $operatingsystem == "Fedora") {

        exec { "exec-update-quantum-conf" :
            command => "sed -i \"s/rpc_backend\s*=\s*quantum.openstack.common.rpc.impl_qpid/#rpc_backend = quantum.openstack.common.rpc.impl_qpid/g\" /etc/quantum/quantum.conf && echo exec-update-quantum-conf >> /etc/contrail/contrail-common-exec.out",
            unless  => ["[ ! -f /etc/quantum/quantum.conf ]",
                        "grep -qx exec-update-quantum-conf /etc/contrail/contrail-common-exec.out"],
            provider => shell,
            logoutput => "true"
        }
    

    }

}

}
