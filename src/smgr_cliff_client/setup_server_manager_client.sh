#!/bin/bash
set -e

DOCKER_IP=`ifconfig docker0 | grep "inet addr" | awk '{print $2}' | cut -d ':' -f 2`
HOST_IP_LIST=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e "s/$DOCKER_IP//g" -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`
HOST_IP=`echo $HOST_IP_LIST | cut -d' ' -f1`
if [ -f /opt/contrail/contrail_server_manager/IP.txt ];
then
   HOST_IP=$(cat /opt/contrail/contrail_server_manager/IP.txt)
fi
echo $HOST_IP
mkdir -p /etc/contrail/
cp /tmp/servermanagerclient /etc/contrail/servermanagerclient
cp /tmp/sm-client-config.ini /etc/contrail/sm-client-config.ini
sed -i "s/listen_ip_addr = .*/listen_ip_addr = $HOST_IP/g" /etc/contrail/sm-client-config.ini
sed -i "s/export SMGR_IP=.*/export SMGR_IP=$HOST_IP/g" /etc/contrail/servermanagerclient
source /etc/contrail/servermanagerclient
ln -sbf /opt/contrail/bin/* /usr/bin/
