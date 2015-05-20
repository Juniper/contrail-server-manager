#!/bin/sh
# This script removes all files and packages related to server manager
# and then if optional parameter 1 is specified (debian package for new server
# manager), installs the new version. The script can be used to install a new
# version of server manager on a machine that has some server manager already loaded.
# Please note that this is not upgrade, i.e. none of the old files including old database
# is preserved. This provies a clean install of server manager software.
# usage : <clean-sm-install.sh [new-sm-installer.deb]
set +x
service contrail-server-manager stop
apt-get purge -y contrail-server-manager-installer
apt-get purge -y contrail-server-manager-client
apt-get purge -y contrail-server-manager-monitoring
apt-get purge -y contrail-server-manager
apt-get purge -y contrail-web-server-manager
mkdir -p /tmp/saved-files
cp /etc/cobbler/dhcp.template /tmp/saved-files/dhcp.template
cp /etc/bind/named.conf.options /tmp/saved-files/named.conf.options
# Remove All systems from cobbler
for systemname in `cobbler system report | grep "^Name                           :" | awk '{print $3}'`
do
    echo "removing cobbler system $systemname"
    cobbler system remove --name=$systemname
done
# Remove All distros and profiles from cobbler
for distroname in `cobbler distro report | grep "^Name                           :" | awk '{print $3}'`
do
    echo "removing cobbler distro and profile $distroname"
    cobbler distro remove --name=$distroname --recursive
done
# Remove All repos from cobbler
for reponame in `cobbler repo report | grep "^Name                           :" | awk '{print $3}'`
do
    echo "removing cobbler repo $reponame"
    cobbler repo remove --name=$reponame
done
# Remove all puppet environments
for envname in `ls /var/www/html/contrail/repo`
do
    echo "removing puppet environment $envname"
    rm -rf /etc/puppet/environments/$envname
    rm -rf /etc/puppet/environments/contrail_$envname
done
rm -rf /opt/contrail/contrail_server_manager
rm -rf /opt/contrail/server_manager
rm -rf /etc/contrail_smgr
rm -rf /var/www/html/contrail
# Now install the new SM.
if [ $# -eq 1 ]; then
    echo "Installing Server Manager from $1"
    dpkg -i $1
    cd /opt/contrail/contrail_server_manager
    ./setup.sh --all
    cp /tmp/saved-files/dhcp.template /etc/cobbler/dhcp.template
    cp /tmp/saved-files/named.conf.options /etc/bind/named.conf.options
    service contrail-server-manager restart
fi
