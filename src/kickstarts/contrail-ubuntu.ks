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
# Install puppet

# Update sources.list so that ubuntu repo is available to download all
# dependencies needed by puppet such as ruby, puppet-common etc.
cat >>/etc/apt/sources.list <<EOF
# add repos needed for puppet and its dependencies
deb http://us.archive.ubuntu.com/ubuntu/ precise main restricted
deb http://us.archive.ubuntu.com/ubuntu/ precise universe
EOF
# Get puppet repo
wget https://apt.puppetlabs.com/puppetlabs-release-precise.deb
dpkg -i ./puppetlabs-release-precise.deb
apt-get update
apt-get -f -y install
apt-get -y install puppet
#--------------------------------------------------------------------------
# Enable puppet conf setting to allow custom facts, allow listen from puppet
# kick and also configure auth.conf file.
echo "[agent]" >> /etc/puppet/puppet.conf
echo "    pluginsync = true" >> /etc/puppet/puppet.conf
echo "    ignorecache = true" >> /etc/puppet/puppet.conf
echo "    usecacheonfailure = false" >> /etc/puppet/puppet.conf
echo "    listen = true" >> /etc/puppet/puppet.conf
cat >/tmp/puppet-auth.conf <<EOF
# Allow puppet kick access
path    /run
method  save
auth    any
allow   $server.$system_domain
EOF
cat /etc/puppet/auth.conf >> /tmp/puppet-auth.conf
cp -f /tmp/puppet-auth.conf /etc/puppet/auth.conf
#--------------------------------------------------------------------------
# Enable to start puppet agent on boot & Run Puppet agent
sed -i 's/START=.*$/START=yes/' /etc/default/puppet
puppet agent --waitforcert 60 --test
if [ "$contrail_repo_name" != "" ];
then
    #--------------------------------------------------------------------------
    # Create directory to copy the package file
    mkdir -p /tmp
    cd /tmp
    wget http://$server/contrail/images/$contrail_repo_name.deb
    #--------------------------------------------------------------------------
    # Install the package file
    dpkg -i $contrail_repo_name.deb
    #--------------------------------------------------------------------------
    # Execute shell script to create repo
    cd /opt/contrail/contrail_packages
    ./setup.sh
fi
%end
