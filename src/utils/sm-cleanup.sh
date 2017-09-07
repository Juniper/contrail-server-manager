#!/bin/sh
# This script removes all files and packages related to server manager

# If you do not have docker running or do not wish to stop docker, you can skip the docker lines

docker rmi -f `docker images -a | grep -v registry | grep -v REPOSITORY | awk '{print $3}'`
docker stop registry
docker rm registry
docker images -a | awk '{print $3}' | xargs docker rmi -f

service contrail-server-manager stop
service supervisor-webui-sm stop
sleep 4

dpkg -l | grep contrail | awk -F ' ' '{print $2}' | xargs dpkg -P
dpkg -l | grep puppet | awk -F ' ' '{print $2}' | xargs dpkg -P
dpkg -l | grep cobbler | awk -F ' ' '{print $2}' | xargs dpkg -P
dpkg -l | grep passenger | awk -F ' ' '{print $2}' | xargs dpkg -P
dpkg -l | grep docker | awk -F ' ' '{print $2}' | xargs dpkg -P
dpkg -l | grep ansible | awk -F ' ' '{print $2}' | xargs dpkg -P

rm -rf /etc/contrail_smgr/contrail-centos-repo /etc/contrail_smgr/contrail-redhat-repo /var/www/html/thirdparty_packages /opt/contrail/ /var/log/contrail /etc/cobbler/pxe /srv/www/cobbler/ /var/lib/cobbler/ /usr/src/contrail/contrail-web-core/webroot/img /etc/puppet/ /var/lib/puppet /usr/share/puppet /etc/contrail_smgr /etc/contrail /var/www/html/contrail/ /etc/ansible
rm -rf /var/lib/cobbler /var/lib/puppet /etc/puppet /etc/cobbler /etc/contrail* /opt/contrail/contrail_server_manager
rm -rf /var/lib/docker /etc/docker /run/docker
rm -rf /usr/local/bin/ansible*
rm -rf /etc/apt/sources.list.d/*.list
