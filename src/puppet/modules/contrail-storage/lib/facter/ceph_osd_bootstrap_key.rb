# Fact: ceph_osd_bootstrap_key
#
# Purpose:
#
# Resolution:
#
# Caveats:
#

require 'facter'
require 'timeout'

timeout = 4
cmd_timeout = 4

# ceph_osd_bootstrap_key
# Fact that gets the ceph key "client.bootstrap-osd"

Facter.add(:ceph_admin_key, :timeout => timeout) do
  if system("timeout #{cmd_timeout} ceph -s > /dev/null 2>&1")
    setcode { Facter::Util::Resolution.exec("timeout #{cmd_timeout} ceph auth get-key client.admin") }
  end
end

## blkid_uuid_#{device} / ceph_osd_id_#{device}
## Facts that export partitions uuids & ceph osd id of device

# Load the osds/uuids from ceph

ceph_osds = Hash.new
ceph_num_osds = 0
begin
  Timeout::timeout(timeout) {
    if system("timeout #{cmd_timeout} ceph -s > /dev/null 2>&1")
      ceph_osd_dump = Facter::Util::Resolution.exec("timeout #{cmd_timeout} ceph osd dump")
      ceph_osd_dump and ceph_osd_dump.each_line do |line|
        if line =~ /^osd\.(\d+).* ([a-f0-9\-]+)$/
          ceph_osds[$2] = $1
	  ceph_num_osds += 1
        end
      end

    end
  }
rescue Timeout::Error
  Facter.warnonce('ceph command timeout in ceph_osd_bootstrap_key fact')
end

# Load the disks uuids

ceph_all_osds = ""
blkid = Facter::Util::Resolution.exec("blkid")
blkid and blkid.each_line do |line|
  if line =~ /^\/dev\/(.+):.*UUID="([a-fA-F0-9\-]+)"/
    device = $1
    uuid = $2

    Facter.add("blkid_uuid_#{device}") { setcode { uuid } }
    Facter.add("ceph_osd_id_#{device}") { setcode { ceph_osds[uuid] } }
	if ceph_osds[uuid]
		ceph_all_osds += "#{device}:#{ceph_osds[uuid]}|"
	end
  end
end

Facter.add("ceph_all_osds") do 
	setcode { ceph_all_osds } 
end

Facter.add("ceph_pg_num") do 
	setcode do 
		#num_osds = Facter::Util::Resolution.exec("ceph -s| grep osdmap | awk ' {printf $3}'")  
		pg_num = 2**((ceph_num_osds*100)/2).to_s(2).size
		pg_num
	end
end
