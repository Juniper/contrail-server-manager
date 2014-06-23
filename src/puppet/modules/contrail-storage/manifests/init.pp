class contrail-storage {

define contrail-storage (
	$contrail_storage_fsid,
	$contrail_storage_mon_secret,
	$contrail_storage_auth_type = 'cephx',
	$contrail_storage_mon_hosts,
	$contrail_mon_addr = $ipaddress,
	$contrail_mon_port  = 6789,
	$contrail_storage_hostname = $hostname
    ) {
        package { 'contrail-storage-packages' : ensure => present,}
        package { 'contrail-storage' : ensure => present,}

	notify { "hotname : $contrail_storage_hostname":; }
	notify { "hotname : $contrail_mon_addr":; }
	notify { "BLKID FACT ${contrail_storage_hostname}: ${contrail_mon_addr}": }

    	file { "/etc/ceph/ceph.conf" : 
        	ensure  => present,
	        content => template("contrail-storage/ceph.conf.erb"),
    	}
	contrail_storage_monitor{'config_monitor':
		contrail_storage_mon_secret => $contrail_storage_mon_secret,
		contrail_storage_mon_hostname => $contrail_storage_hostname
	}
    }

define contrail_storage_monitor(
	$contrail_storage_mon_secret,
	$contrail_storage_mon_hostname
	) {

	notify { "BLKID FACT1 ${contrail_storage_mon_hostname}: ${contrail_storage_mon_secret}": }
  exec { 'ceph-mon-keyring':
    command => "/usr/bin/ceph-authtool /var/lib/ceph/tmp/keyring.mon.${contrail_storage_mon_hostname} \
	--create-keyring \
	--name=mon. \
	--add-key='${contrail_storage_mon_secret}' \
	--cap mon 'allow *'",
    creates => "/var/lib/ceph/tmp/keyring.mon.${contrail_storage_mon_hostname}",
    before  => Exec['ceph-mon-mkfs'],
  }

  file { "/var/lib/ceph/mon/ceph-${contrail_storage_mon_hostname}":
    ensure  => 'directory',
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
  }

  exec { 'ceph-mon-mkfs':
    command => "/usr/bin/ceph-mon --mkfs -i ${contrail_storage_mon_hostname} \
	--keyring /var/lib/ceph/tmp/keyring.mon.${contrail_storage_mon_hostname}",
    creates => "/var/lib/ceph/mon/${contrail_storage_mon_hostname}/keyring",
  }


  service { "ceph-mon.${contrail_storage_mon_hostname}":
    ensure   => running,
    provider => $::ceph::params::service_provider,
    start    => "service ceph start mon.${contrail_storage_mon_hostname}",
    stop     => "service ceph stop mon.${contrail_storage_mon_hostname}",
    status   => "service ceph status mon.${contrail_storage_mon_hostname}",
    require  => Exec['ceph-mon-mkfs'],
  }

  exec { 'ceph-admin-key':
    command => "/usr/bin/ceph-authtool /etc/ceph/keyring \
	--create-keyring \
	--name=client.admin \
	--add-key \
	$(ceph --name mon. --keyring /var/lib/ceph/mon/ceph-${contrail_storage_mon_hostname}/keyring \
	  auth get-or-create-key client.admin \
	    mon 'allow *' \
	    osd 'allow *' \
	    mds allow)",
    creates => '/etc/ceph/keyring',
    onlyif  => "/usr/bin/ceph --admin-daemon /var/run/ceph/ceph-mon.${contrail_storage_mon_hostname}.asok \
mon_status|egrep -v '\"state\": \"(leader|peon)\"'",
  }
	}
}
