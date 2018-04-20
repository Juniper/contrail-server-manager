#!/bin/bash

set -e

DOCKER_IP=`ifconfig docker0 | grep "inet addr" | awk '{print $2}' | cut -d ':' -f 2`
HOST_IP_LIST=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e "s/:$DOCKER_IP//g" -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`

if [[ ! $HOST_IP ]]; then
  HOST_IP=`echo $HOST_IP_LIST | cut -d' ' -f1`
fi

HOST_MAC=`ifconfig -a | grep $HOST_IP -b2 | grep ether | awk '{print $3}'`
HOST_FQDN=`hostname -f`
HOST_NAME=`hostname`

SUBNET_ADDRESS=`ip route | grep $HOST_IP | awk '{print $1}' | cut -d '/' -f 1`
SUBNET_MASK=`ifconfig -a | grep $HOST_IP -b4 | grep netmask | awk '{print $5}' | cut -d ':' -f 2`

SUBNET_GATEWAY=`ip route | grep $HOST_IP -b3 | grep default | awk '{print $3}'`

DOMAIN=`hostname -d`
rel=`cat /etc/os-release | grep VERSION_ID= | awk '{print $1}' | cut -d'"' -f2`

# Configure Cobbler
sed -i "s/__\$IPADDRESS__/$HOST_IP/g" /etc/cobbler/settings
sed -i "s/bind_master:.*/bind_master: $HOST_IP/g" /etc/cobbler/settings
sed -i "s/next_server:.*/next_server: $HOST_IP/g" /etc/cobbler/settings
sed -i "s/server:.*/server: $HOST_IP/g" /etc/cobbler/settings
sed -i "s/module = authn_.*/module = authn_testing/g" /etc/cobbler/modules.conf

for f in /etc/cobbler/power/*.template; do
if ! grep -q '#for \$fact' $f; then
cat << EOT >> $f
#for \$fact, \$value in  \$ks_meta.items()
  #if \$fact=='ipmi_interface' and \$value == 'lanplus'
    lanplus=1
  #elif \$fact=='ipmi_interface' and \$value=='lan'
    lan
  #else
    #pass
  #end if
#end for
EOT
else
sed -i 's/lanplus$/lanplus=1/g' $f
fi
done

# Set SM Config
sed -i "s/__\$IPADDRESS__/$HOST_IP/g" /opt/contrail/server_manager/sm-config.ini
sed -i "s/127.0.0.1/$HOST_IP/g" /opt/contrail/server_manager/sm-config.ini
sed -i "s/__\$IPADDRESS__/$HOST_IP/g" /opt/contrail/server_manager/smgr_dhcp_event.py
sed -i "s/cobbler_username         = cobbler/cobbler_username         = testing/g" /opt/contrail/server_manager/sm-config.ini
sed -i "s/cobbler_password         = cobbler/cobbler_password         = testing/g" /opt/contrail/server_manager/sm-config.ini

# DHCP Auto-add the server manager to DHCP HOSTS
sed -i "s/__\$IPADDRESS__/$HOST_IP/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$MACADDRESS__/$HOST_MAC/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$HOSTFQDN__/$HOST_FQDN/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$HOSTNAME__/$HOST_NAME/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$SUBNETADDRESS__/$SUBNET_ADDRESS/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$SUBNETGATEWAY__/$SUBNET_GATEWAY/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$SUBNETMASK__/$SUBNET_MASK/g" /opt/contrail/server_manager/generate_dhcp_template.py
sed -i "s/__\$DOMAIN__/$DOMAIN/g" /opt/contrail/server_manager/generate_dhcp_template.py

sed -i "s/__\$IPADDRESS__/$HOST_IP/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$MACADDRESS__/$HOST_MAC/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$HOSTFQDN__/$HOST_FQDN/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$HOSTNAME__/$HOST_NAME/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$SUBNETADDRESS__/$SUBNET_ADDRESS/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$SUBNETGATEWAY__/$SUBNET_GATEWAY/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$SUBNETMASK__/$SUBNET_MASK/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u
sed -i "s/__\$DOMAIN__/$DOMAIN/g" /etc/contrail_smgr/cobbler/bootup_dhcp.template.u

# Configure client

sed -i "s/listen_ip_addr = .*/listen_ip_addr = $HOST_IP/g" /etc/contrail/sm-client-config.ini
sed -i "s/export SMGR_IP=.*/export SMGR_IP=$HOST_IP/g" /etc/contrail/servermanagerclient
source /etc/contrail/servermanagerclient
ln -s /opt/contrail/bin/server-manager-client /usr/bin/server-manager

cp /etc/cobbler/dhcp.template /etc/cobbler/dhcp.template.save
cp /etc/contrail_smgr/cobbler/bootup_dhcp.template.u /etc/cobbler/dhcp.template

exec "$@"
