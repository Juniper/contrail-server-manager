#Upgrade script to upgrade the server-manager RPM(Centos)
#Usage: ./smgr_upgrade_script.sh <RPM>
#!/bin/sh
set -x -v
mkdir -p /contrail-smgr-save
cp /etc/cobbler/dhcp.template /contrail-smgr-save
cp /etc/cobbler/named.template /contrail-smgr-save
cp /etc/cobbler/settings /contrail-smgr-save
cp /etc/cobbler/zone.template /contrail-smgr-save
cp -r /etc/cobbler/zone_templates /contrail-smgr-save
service contrail-server-manager stop
yum -y remove contrail-server-manager
yum -y localinstall $1
cp /contrail-smgr-save/dhcp.template /etc/cobbler/dhcp.template
cp /contrail-smgr-save/named.template /etc/cobbler/named.template
cp /contrail-smgr-save/settings /etc/cobbler/settings
cp /contrail-smgr-save/zone.template /etc/cobbler/zone.template
cp -r /contrail-smgr-save/zone_templates /etc/cobbler/
service contrail-server-manager start

