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
if [ "$contrail_repo_name" != "" ];
then
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
    # Enable puppet conf setting to allow custom facts
    echo "[agent]" >> /etc/puppet/puppet.conf
    echo "    pluginsync = true" >> /etc/puppet/puppet.conf
    echo "    ignorecache = true" >> /etc/puppet/puppet.conf
    echo "    usecacheonfailure = false" >> /etc/puppet/puppet.conf
    #--------------------------------------------------------------------------
    # Enable to start puppet agent on boot & Run Puppet agent
    sed -i 's/START=.*$/START=yes/' /etc/default/puppet
    puppet agent --waitforcert 60 --test
fi
%end
