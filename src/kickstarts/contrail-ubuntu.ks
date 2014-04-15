# Kickstart template for the NewNode (ubuntu)
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
# Create directory to copy the package file
mkdir -p /tmp
cd /tmp
wget http://$server/contrail/images/$contrail_repo_name
#--------------------------------------------------------------------------
# Install the package file
dpkg -i $contrail_repo_name
#--------------------------------------------------------------------------
# Execute shell script to create repo
cd /opt/contrail/contrail_packages
./setup.sh
#--------------------------------------------------------------------------
# Install puppet
apt-get -f -y install
apt-get -y install puppet
#--------------------------------------------------------------------------
#Set up the ntp client 
apt-get -y install ntp
/sbin/ntpdate $server
/bin/mv /etc/ntp.conf /etc/ntp.conf.orig
/bin/touch /var/lib/ntp/drift
cat << __EOT__ > /etc/ntp.conf
driftfile /var/lib/ntp/drift
server $server
server 172.17.28.5
server 66.129.255.62
server 172.28.16.17
restrict 127.0.0.1
restrict -6 ::1
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
__EOT__
service ntp restart

#--------------------------------------------------------------------------
#

#--------------------------------------------------------------------------
# Enable puppet conf setting to allow custom facts
echo "[agent]" >> /etc/puppet/puppet.conf
echo "    pluginsync = true" >> /etc/puppet/puppet.conf
echo "    ignorecache = true" >> /etc/puppet/puppet.conf
echo "    usecacheonfailure = false" >> /etc/puppet/puppet.conf
echo "[main]" >> /etc/puppet/puppet.conf
echo "runinterval=60" >> /etc/puppet/puppet.conf

#--------------------------------------------------------------------------
# Enable to start puppet agent on boot & Run Puppet agent
sed -i 's/START=.*$/START=yes/' /etc/default/puppet
puppet agent --waitforcert 60 --test
%end
