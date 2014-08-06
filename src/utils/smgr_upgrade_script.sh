#Upgrade script to upgrade the server-manager RPM(Centos)
#Usage: ./smgr_upgrade_script.sh <RPM>
#!/bin/sh
set -x -v
mkdir -p /contrail-smgr-save
cp /etc/cobbler/dhcp.template /contrail-smgr-save
cp /etc/cobbler/named.template /contrail-smgr-save
cp /etc/cobbler/settings /contrail-smgr-save
service contrail_smgrd stop
yum -y remove contrail_smgr.noarch
yum -y localinstall $1
cp /contrail-smgr-save/dhcp.template /etc/cobbler/dhcp.template
cp /contrail-smgr-save/named.template /etc/cobbler/named.template
cp /contrail-smgr-save/settings /etc/cobbler/settings
service contrail_smgrd start

