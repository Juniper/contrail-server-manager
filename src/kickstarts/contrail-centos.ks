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
autopart


%pre
$SNIPPET('log_ks_pre')
$SNIPPET('kickstart_start')
## $SNIPPET('pre_install_network_config')
# Enable installation monitoring
## $SNIPPET('pre_anamon')
%end

%packages --nobase
@core
wget
openssh-clients
ntpdate
ntp
puppet

#if $getVar("contrail_repo_name","") != ""
contrail-install-packages
#end if

$SNIPPET('func_install_if_enabled')
## $SNIPPET('puppet_install_if_enabled')
%end

%post
$SNIPPET('log_ks_post')

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

#if $str($getVar('puppet_auto_setup','')) == "1"
## Tmp fix, copy the init.d script for puppet agent. This should be included in puppet package install.
wget -O /etc/init.d/puppet "http://$server:$http_port/cobbler/aux/puppet"
chmod 755 /etc/init.d/puppet
echo "[agent]" >> /etc/puppet/puppet.conf
echo "    pluginsync = true" >> /etc/puppet/puppet.conf
echo "    ignorecache = true" >> /etc/puppet/puppet.conf
echo "    usecacheonfailure = false" >> /etc/puppet/puppet.conf
echo "    listen = true" >> /etc/puppet/puppet.conf
echo "[main]" >> /etc/puppet/puppet.conf
echo "runinterval=180" >> /etc/puppet/puppet.conf
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
# disable selinux and iptables
sed -i 's/SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config
service iptables stop
/sbin/chkconfig iptables off
#if $getVar("contrail_repo_name","") != ""
cd /opt/contrail/contrail_packages
./setup.sh
echo "exec-contrail-setup-sh" >> exec-contrail-setup-sh.out
#end if
## generate puppet certificates and trigger a signing request, but
## don't wait for signing to complete
/usr/sbin/puppetd --test --waitforcert 0
## turn puppet service on for reboot
/sbin/chkconfig puppet on
#end if

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
