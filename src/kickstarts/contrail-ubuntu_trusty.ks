# Kickstart template for the NewNode (ubuntu)
%pre
wget http://$server/cblr/svc/op/trig/mode/pre/system/$system_name

%post
set -x -v
#--------------------------------------------------------------------------
# Uodate entries in /etc/hosts file for self and puppet ip address
sed -i '/127\.0\..\.1/d' /etc/hosts
echo "127.0.0.1 localhost.$system_domain localhost" >> /etc/hosts
echo "127.0.0.1 $system_name.$system_domain $system_name" >> /etc/hosts
echo "$ip_address $system_name.$system_domain $system_name" >> /etc/hosts
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
# Enable ssh for root
sed -i '/PermitRootLogin/c\PermitRootLogin yes' /etc/ssh/sshd_config
service ssh restart

#--------------------------------------------------------------------------
# Install puppet

# Update sources.list so that ubuntu repo is available to download all
# dependencies needed by puppet such as ruby, puppet-common etc.
# add repos needed for puppet and its dependencies

#Install puppet 2.7 against 3.x which is got from trusty repo.
#Need to revisit this logic to use preferences.

mv /etc/apt/sources.list /etc/apt/sources.list.orig

echo "deb http://$server/thirdparty_packages/ ./" > /etc/apt/sources.list

apt-get update
apt-get -y install puppet

cp /etc/apt/sources.list.orig /etc/apt/sources.list

cat >>/etc/apt/sources.list <<EOF
# add repos needed for puppet and its dependencies
deb http://$server/thirdparty_packages/ ./

#deb cdrom:[Ubuntu 14.04 _Trusty Tahr_ - Release i386]/ Trusty main restricted
# See http://help.ubuntu.com/community/UpgradeNotes for how to upgrade to
# newer versions of the distribution.

deb http://us.archive.ubuntu.com/ubuntu/ trusty main restricted
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty main restricted

## Major bug fix updates produced after the final release of the
## distribution.
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates main restricted
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates main restricted

## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu
## team. Also, please note that software in universe WILL NOT receive any
## review or updates from the Ubuntu security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty universe
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty universe
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates universe
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates universe

## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu 
## team, and may not be under a free licence. Please satisfy yourself as to 
## your rights to use the software. Also, please note that software in 
## multiverse WILL NOT receive any review or updates from the Ubuntu
## security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty multiverse
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates multiverse

## Uncomment the following two lines to add software from the 'backports'
## repository.
## N.B. software from this repository may not have been tested as
## extensively as that contained in the main release, although it includes
## newer versions of some applications which may provide useful features.
## Also, please note that software in backports WILL NOT receive any review
## or updates from the Ubuntu security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty-backports main restricted universe multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-backports main restricted universe multiverse

## Uncomment the following two lines to add software from Canonical's
## 'partner' repository. This software is not part of Ubuntu, but is
## offered by Canonical and the respective vendors as a service to Ubuntu
## users.
deb http://archive.canonical.com/ubuntu trusty partner
deb-src http://archive.canonical.com/ubuntu trusty partner

deb http://security.ubuntu.com/ubuntu trusty-security main restricted
deb-src http://security.ubuntu.com/ubuntu trusty-security main restricted
deb http://security.ubuntu.com/ubuntu trusty-security universe
deb-src http://security.ubuntu.com/ubuntu trusty-security universe
deb http://security.ubuntu.com/ubuntu trusty-security multiverse
deb-src http://security.ubuntu.com/ubuntu trusty-security multiverse

## Medibuntu - Ubuntu 14.04 "Trusty Tahr"
## Please report any bug on https://bugs.launchpad.net/medibuntu/
deb http://packages.medibuntu.org/ trusty free non-free
deb-src http://packages.medibuntu.org/ trusty free non-free

# Google software repository
deb http://dl.google.com/linux/deb/ stable non-free

EOF

# Get puppet repo
apt-get update
apt-get -y install biosdevname

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
