# Kickstart template for the NewNode (ubuntu)
%pre
wget http://$server/cblr/svc/op/trig/mode/pre/system/$system_name

%post
set -x -v
#--------------------------------------------------------------------------
# Uodate entries in /etc/hosts file for self and puppet ip address
sed -i '/127\.0\..\.1/d' /etc/hosts
echo "127.0.0.1 localhost.$system_domain localhost" >> /etc/hosts
echo "$ip_address $system_name" >> /etc/hosts
echo "$server puppet" >> /etc/hosts
#--------------------------------------------------------------------------
# Set apt-get config option to allow un-authenticated packages to be installed
# This is needed for puppet package resource to succeed. In the long run, we
# need to have contrail deb packaged correctly signed before creating repo.
cat >/etc/apt/apt.conf <<EOF
/* Configuration file to specify default option for apt-get command.
   This is temporary workaround to have our un-authenticated packages
   install successfully. Long term, we need to have the packages signed
   when those are built.
*/

APT
{
  // Options for apt-get
  Get
  {
     AllowUnauthenticated "true";
  };
}
EOF

#--------------------------------------------------------------------------
# Install puppet

# Update sources.list so that ubuntu repo is available to download all
# dependencies needed by puppet such as ruby, puppet-common etc.
# add repos needed for puppet and its dependencies

cat >>/etc/apt/sources.list <<EOF
# add repos needed for puppet and its dependencies
deb http://$server/thirdparty_packages/ ./

# deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ dists/precise/main/binary-i386/
# deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ dists/precise/restricted/binary-i386/
# deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ precise main restricted
 
#deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ dists/precise/main/binary-i386/
#deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ dists/precise/restricted/binary-i386/
#deb cdrom:[Ubuntu-Server 12.04 LTS _Precise Pangolin_ - Release amd64 (20120424.1)]/ precise main restricted
 
# See http://help.ubuntu.com/community/UpgradeNotes for how to upgrade to
# newer versions of the distribution.
deb http://archive.ubuntu.com/ubuntu/ precise main restricted
deb-src http://archive.ubuntu.com/ubuntu/ precise main restricted
 
## Major bug fix updates produced after the final release of the
## distribution.
deb http://archive.ubuntu.com/ubuntu/ precise-updates main restricted
deb-src http://archive.ubuntu.com/ubuntu/ precise-updates main restricted
 
## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu
## team. Also, please note that software in universe WILL NOT receive any
## review or updates from the Ubuntu security team.
deb http://archive.ubuntu.com/ubuntu/ precise universe
deb-src http://archive.ubuntu.com/ubuntu/ precise universe
deb http://archive.ubuntu.com/ubuntu/ precise-updates universe
deb-src http://archive.ubuntu.com/ubuntu/ precise-updates universe
 
## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu
## team, and may not be under a free licence. Please satisfy yourself as to
## your rights to use the software. Also, please note that software in
## multiverse WILL NOT receive any review or updates from the Ubuntu
## security team.
deb http://archive.ubuntu.com/ubuntu/ precise multiverse
deb-src http://archive.ubuntu.com/ubuntu/ precise multiverse
deb http://archive.ubuntu.com/ubuntu/ precise-updates multiverse
deb-src http://archive.ubuntu.com/ubuntu/ precise-updates multiverse
 
## N.B. software from this repository may not have been tested as
## extensively as that contained in the main release, although it includes
## newer versions of some applications which may provide useful features.
## Also, please note that software in backports WILL NOT receive any review
## or updates from the Ubuntu security team.
deb http://archive.ubuntu.com/ubuntu/ precise-backports main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu/ precise-backports main restricted universe multiverse
 
deb http://security.ubuntu.com/ubuntu precise-security main restricted
deb-src http://security.ubuntu.com/ubuntu precise-security main restricted
deb http://security.ubuntu.com/ubuntu precise-security universe
deb-src http://security.ubuntu.com/ubuntu precise-security universe
deb http://security.ubuntu.com/ubuntu precise-security multiverse
deb-src http://security.ubuntu.com/ubuntu precise-security multiverse
 
## Uncomment the following two lines to add software from Canonical's
## 'partner' repository.
## This software is not part of Ubuntu, but is offered by Canonical and the
## respective vendors as a service to Ubuntu users.
# deb http://archive.canonical.com/ubuntu precise partner
# deb-src http://archive.canonical.com/ubuntu precise partner
 
## Uncomment the following two lines to add software from Ubuntu's
## 'extras' repository.
## This software is not part of Ubuntu, but is offered by third-party
## developers who want to ship their latest software.
# deb http://extras.ubuntu.com/ubuntu precise main
# deb-src http://extras.ubuntu.com/ubuntu precise main

EOF

# Get puppet repo
apt-get update
apt-get -y install puppet
apt-get -y install python-netaddr
apt-get -y install ifenslave

wget http://$server/kickstarts/interface_setup.py
wget http://$server/contrail/config_file/$system_name.sh
chmod +x $system_name.sh
./$system_name.sh

#--------------------------------------------------------------------------
#Set up the ntp client 
apt-get -y install ntp
ntpdate $server
mv /etc/ntp.conf /etc/ntp.conf.orig
touch /var/lib/ntp/drift
cat << __EOT__ > /etc/ntp.conf
driftfile /var/lib/ntp/drift
server $server
restrict 127.0.0.1
restrict -6 ::1
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
__EOT__
service ntp restart
#--------------------------------------------------------------------------

#--------------------------------------------------------------------------
# Enable puppet conf setting to allow custom facts, allow listen from puppet
# kick and also configure auth.conf file.
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
allow   *
EOF
cat /etc/puppet/auth.conf >> /tmp/puppet-auth.conf
cp -f /tmp/puppet-auth.conf /etc/puppet/auth.conf
#--------------------------------------------------------------------------
# Enable to start puppet agent on boot & Run Puppet agent
sed -i 's/START=.*$/START=yes/' /etc/default/puppet
puppet agent --waitforcert 60 --test
if [ "$contrail_repo_name" != "" ];
then
    cd /etc/apt
    datetime_string=`date +%Y_%m_%d__%H_%M_%S`
    cp sources.list sources.list.$datetime_string
    echo "deb http://$server/contrail/repo/$contrail_repo_name ./" > new_repo

    #modify /etc/apt/soruces.list/ to add new repo on the top
    grep "deb http://$server/contrail/repo/$contrail_repo_name ./" sources.list

    if [ $? != 0 ]; then
         cat new_repo sources.list > new_sources.list
         mv new_sources.list sources.list
    fi
    apt-get update
    # Kept for now to create local /opt/contrail on target, should be removed
    # later - Abhay
    apt-get -y install contrail-install-packages
    #--------------------------------------------------------------------------
    # below was to create local repo on target, commented out as we create a
    # repo on cobbler. Kept the commented below for reference.
    # Create directory to copy the package file
    # mkdir -p /tmp
    # cd /tmp
    # wget http://$server/contrail/images/$contrail_repo_name.deb
    #--------------------------------------------------------------------------
    # Install the package file
    # dpkg -i $contrail_repo_name.deb
    #--------------------------------------------------------------------------
    # Execute shell script to create repo
    cd /opt/contrail/contrail_packages
    ./setup.sh
    echo "exec-contrail-setup-sh" >> exec-contrail-setup-sh.out
fi
#blacklist mei module for ocp
echo "blacklist mei" >> /etc/modprobe.d/blacklist.conf
wget http://$server/cblr/svc/op/trig/mode/post/system/$system_name
%end
