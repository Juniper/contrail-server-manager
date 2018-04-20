#platform=x86, AMD64, or Intel EM64T
# System authorization information
auth  --useshadow  --enablemd5
# System bootloader configuration
bootloader --location=mbr
# Partition clearing information
clearpart --all --initlabel --drives=sda
# Use text mode install
text
# Firewall configuration
firewall --enabled
# Run the Setup Agent on first boot
firstboot --disable
# System keyboard
keyboard us
# System language
lang en_US
# Use network installation
url --url=$tree
# If any cobbler repo definitions were referenced in the kickstart profile, include them here.
$yum_repo_stanza
# Network information
## $SNIPPET('network_config')
# Reboot after installation
reboot

# Root password
rootpw --iscrypted $passwd
# SELinux configuration
selinux --disabled
# Do not configure the X Window System
skipx
# System timezone
timezone  America/Los_Angeles
# Install OS instead of upgrade
install
# Clear the Master Boot Record
zerombr
# Allow anaconda to partition the system as needed
part /boot --fstype ext4 --size=1024
part swap --recommended
part pv.01      --size=1000     --grow  --ondisk=sda
volgroup $system_name-vg00 pv.01
# /     => 10%
# /var  => 70%
# /home => 5%
# /tmp  => 10%
logvol /     --vgname=$system_name-vg00 --fstype=ext4 --percent=10 --name=lv_root
logvol /tmp  --vgname=$system_name-vg00 --fstype=ext4 --percent=10 --name=lv_tmp
logvol /home --vgname=$system_name-vg00 --fstype=ext4 --percent=5  --name=lv_home
logvol /var  --vgname=$system_name-vg00 --fstype=ext4 --percent=70 --name=lv_var


%pre
$SNIPPET('log_ks_pre')
$SNIPPET('kickstart_start')
## $SNIPPET('pre_install_network_config')
# Enable installation monitoring
## $SNIPPET('pre_anamon')
%end

#if $getVar('kernel_repo_url','') != ''
    repo --name=updates --baseurl="$kernel_repo_url"
#end if

%packages --nobase
@core
openssh-clients
puppet
#if $getVar('kernel_version','') != ''
$kernel_version
#end if

$SNIPPET('func_install_if_enabled')
%end

%post
$SNIPPET('log_ks_post')
yum -y install wget ntp ntpdate python-netaddr.noarch

## Copy the interfce and static under root
wget -O /root/interface_setup.py http://$server/kickstarts/interface_setup.py
wget -O /root/staticroute_setup.py http://$server/kickstarts/staticroute_setup.py
## Wierd CentOS behavior. You need to explicityly concatenate the system_name to the '.sh' string
#set $sname = str($system_name)+ '.sh'
## Get a copy of the script in the target system
wget -O /root/$sname http://$server/contrail/config_file/$sname
chmod +x /root/$sname
## Add the following lines for script to be part of initd in CentOS
sed -i '1 a # chkconfig: 2345 80 20' /root/$sname
sed -i '2 a # description: Interface and static route configuration entries' /root/$sname
## Comment out the following line from /etc/sudoers to overcome a Centos bug https://bugzilla.redhat.com/show_bug.cgi?id=1020147
sed -i 's/Defaults    requiretty/#Defaults requiretty/g' /etc/sudoers
## Copy the script to the init.d 
cp /root/$sname /etc/init.d
cd /etc/init.d
## Add and enable the script as part of the init.d 
/sbin/chkconfig --add $sname
/sbin/chkconfig $sname on
rm /root/$sname

## Configure NTP to access cobbler/puppet master as NTP server
/usr/sbin/ntpdate $http_server
/sbin/hwclock --systohc
/bin/mv /etc/ntp.conf /etc/ntp.conf.orig
/bin/touch /var/lib/ntp/drift
cat << __EOT__ > /etc/ntp.conf
driftfile /var/lib/ntp/drift
server $http_server  iburst
restrict 127.0.0.1
restrict -6 ::1
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
__EOT__
/sbin/chkconfig ntpd on
/sbin/chkconfig
/sbin/service ntpd start

# Start yum configuration 
$yum_config_stanza
# End yum configuration
$SNIPPET('post_install_kernel_options')
## $SNIPPET('post_install_network_config')
$SNIPPET('func_register_if_enabled')
##$SNIPPET('puppet_register_if_enabled')
## Configure puppet agent and start it
echo "$server puppet" >> /etc/hosts
echo "$ip_address $system_name.$system_domain $system_name" >> /etc/hosts

# add hostname file for persistence across reboot
rm -rf /etc/hostname
echo "$system_name" >> /etc/hostname

## Tmp fix, copy the init.d script for puppet agent. This should be included in puppet package install.
wget -O /etc/init.d/puppet "http://$server:$http_port/cobbler/aux/puppet"
chmod 755 /etc/init.d/puppet
echo "[agent]" >> /etc/puppet/puppet.conf
echo "    pluginsync = true" >> /etc/puppet/puppet.conf
echo "    ignorecache = true" >> /etc/puppet/puppet.conf
echo "    usecacheonfailure = false" >> /etc/puppet/puppet.conf
echo "    listen = true" >> /etc/puppet/puppet.conf
echo "    ordering = manifest" >> /etc/puppet/puppet.conf
echo "    stringify_facts = false" >> /etc/puppet/puppet.conf
echo "[main]" >> /etc/puppet/puppet.conf
echo "runinterval=60" >> /etc/puppet/puppet.conf
cat >/tmp/puppet-auth.conf <<EOF
# Allow puppet kick access
path    /run
method  save
auth    any
# allow   $server.$system_domain
allow   *
EOF
cat /etc/puppet/auth.conf >> /tmp/puppet-auth.conf
cp -f /tmp/puppet-auth.conf /etc/puppet/auth.conf
# Tempprary patch to work around puppet issue of custom facts not working. The custom
# fact scripts get installed with incorrect permissions (no execute permission). This
# results in custom facts not working. Putting a hot patch to work around this problem.
# could be removed once puppet issue is resolved. Abhay
sed -i "s/initialize(name, path, source, ignore = nil, environment = nil, source_permissions = :ignore)/initialize(name, path, source, ignore = nil, environment = nil, source_permissions = :use)/g" /usr/share/ruby/vendor_ruby/puppet/configurer/downloader.rb
# disable selinux and iptables
sed -i 's/SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
service iptables stop
/sbin/chkconfig iptables off

$SNIPPET('download_config_files')
$SNIPPET('koan_environment')
$SNIPPET('redhat_register')
$SNIPPET('cobbler_register')
# Enable post-install boot notification
## $SNIPPET('post_anamon')
# Start final steps
$SNIPPET('kickstart_done')
# End final steps
%end
