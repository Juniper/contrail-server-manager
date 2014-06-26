class contrail-storage {

define contrail-storage (
	$contrail_storage_fsid,
	$contrail_storage_mon_secret,
	$contrail_storage_auth_type = 'cephx',
	$contrail_storage_mon_hosts,
	$contrail_mon_addr = $ipaddress,
	$contrail_mon_port  = 6789,
	$contrail_storage_hostname = $hostname,
	$contrail_storage_journal_size_mb = 200
    ) {
        package { 'contrail-storage-packages' : ensure => present,}
        package { 'contrail-storage' : ensure => present,}
        package { 'ruby-json' : ensure => present,}

	notify { "BLKID FACT ${contrail_storage_hostname}: ${contrail_mon_addr}": }

  	$ceph_all_osd = "${::ceph_all_osds}"
	notify { "ALL OSDs OF $hostname: ${ceph_all_osd}": }

    	file { "/etc/ceph/ceph.conf" : 
        	ensure  => present,
	        content => template("contrail-storage/ceph.conf.erb"),
    	}
	contrail_storage_monitor{'config_monitor':
		contrail_storage_mon_secret => $contrail_storage_mon_secret,
		contrail_storage_mon_hostname => $contrail_storage_hostname,
		require => File['/etc/ceph/ceph.conf']
	}
	#contrail_storage_osd{'':
		#journal => $contrail_storage_mon_secret,
		#journal_size => $contrail_storage_hostname,
		#require => File['/etc/ceph/ceph.conf']
	#}
    }

define contrail_storage_osd_setup(
	$journal = "",
	$journal_size,
	) {


  	$devname = regsubst($name, '.*/', '')

  exec { "mktable_gpt_${devname}":
    command => "/sbin/parted -a optimal --script ${name} mktable gpt",
    unless  => "/sbin/parted --script ${name} print|/bin/grep -sq 'Partition Table: gpt'",
    logoutput => "true"
    #require => Package['parted']
  }

  exec { "mkpart_${devname}":
    command => "/sbin/parted -a optimal -s ${name} mkpart ceph 0% 100%",
    unless  => "/sbin/parted --script ${name} print | /bin/egrep '^ 1.*ceph$'",
    require => Exec["mktable_gpt_${devname}"]
    #require => [Package['parted'], Exec["mktable_gpt_${devname}"]]
  }
  exec { "mkfs_${devname}":
    command => "/sbin/mkfs.xfs -f -d agcount=${::processorcount} -l \
size=1024m -n size=64k ${name}1",
    unless  => "/usr/sbin/xfs_admin -l ${name}1",
    require => Exec["mkpart_${devname}"],
    #require => [Package['xfsprogs'], Exec["mkpart_${devname}"]],
  }

  $blkid_uuid_fact = "blkid_uuid_${devname}1"
  notify { "BLKID FACT ${devname}: ${blkid_uuid_fact}": }
  $blkid = inline_template('<%= scope.lookupvar(blkid_uuid_fact) or "undefined" %>')
  notify { "BLKID ${devname}: ${blkid}": }

  if $blkid != 'undefined' {
    exec { "ceph_osd_create_${devname}":
      command => "/usr/bin/ceph osd create ${blkid}",
      unless  => "/usr/bin/ceph osd dump | /bin/grep -sq ${blkid}",
    }

    $osd_id_fact = "ceph_osd_id_${devname}1"
    notify { "OSD ID FACT ${devname}: ${osd_id_fact}": }
    $osd_id = inline_template('<%= scope.lookupvar(osd_id_fact) or "undefined" %>')
    notify { "OSD ID ${devname}: ${osd_id}":}

    if $osd_id != 'undefined' {

      #ceph::conf::osd { $osd_id:
        #device       => $name,
        #cluster_addr => $::ceph::osd::cluster_address,
        #public_addr  => $::ceph::osd::public_address,
        #journal      => $journal,
        #journalsize  => $journalsize,
      #}

      $osd_data = "/var/lib/ceph/osd/ceph-$osd_id"

      file { $osd_data:
        ensure => directory,
      }

      mount { $osd_data:
        ensure  => mounted,
        device  => "${name}1",
        atboot  => true,
        fstype  => 'xfs',
        options => 'rw,noatime,inode64',
        pass    => 2,
        require => [
          Exec["mkfs_${devname}"],
          File[$osd_data]
        ],
      }

      exec { "ceph-osd-mkfs-${osd_id}":
        command => "/usr/bin/ceph-osd -c /etc/ceph/ceph.conf \
		-i ${osd_id} \
		--mkfs \
		--mkkey \
		--mkjournal \
		--osd-uuid ${blkid}
",
        creates => "${osd_data}/keyring",
        unless  => "/usr/bin/ceph auth list | /bin/egrep '^osd.${osd_id}$'",
        require => [
          Mount[$osd_data],
          #Concat['/etc/ceph/ceph.conf'],
          ],
      }

      exec { "ceph-osd-register-${osd_id}":
        command => "\
/usr/bin/ceph auth add osd.${osd_id} osd 'allow *' mon 'allow rwx' \
-i ${osd_data}/keyring",
        unless  => "/usr/bin/ceph auth list | egrep '^osd.${osd_id}$'",
        require => Exec["ceph-osd-mkfs-${osd_id}"],
      }

      service { "ceph-osd.${osd_id}":
        ensure    => running,
        provider  => 'init',
        start     => "service ceph start osd.${osd_id}",
        stop      => "service ceph stop osd.${osd_id}",
        status    => "service ceph status osd.${osd_id}",
        #subscribe => Concat['/etc/ceph/ceph.conf'],
      }

    }

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
    creates => "/var/lib/ceph/mon/ceph-${contrail_storage_mon_hostname}/keyring",
    require => Exec['ceph-mon-keyring']
  }


  service { "ceph-mon.${contrail_storage_mon_hostname}":
    ensure   => running,
    provider => 'init',
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
