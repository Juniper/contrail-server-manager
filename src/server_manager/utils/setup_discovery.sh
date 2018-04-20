#!/bin/bash
# 1. Create ProgressBar function
# 1.1 Input is currentState($1) and totalState($2)
#set -x
function ProgressBar {
# Process data
    let _progress=(${1}*100/${2}*100)/100
    let _done=(${_progress}*4)/10
    let _left=40-$_done
    _string=${3}
# Build progressbar string lengths
    _fill=$(printf "%${_done}s")
    _empty=$(printf "%${_left}s")

# 1.2 Build progressbar strings and print the ProgressBar line
# 1.2.1 Output example:
# 1.2.1.1 Progress : [########################################] 100%
printf "\r${_string} : [${_fill// /#}${_empty// /-}] ${_progress}%%"

}

# Variables
_start=1

# This accounts as the "totalState" variable for the ProgressBar function
_end=100

ProgressBar 2 ${_end}  "Gather Info........."
DISCOVERY_URL=http://10.84.5.100/contrail/disovery-image6.iso
DISCOVERY_IMG_PATH=/tmp/hw-discover
DISCOVERY_IMG_NAME=disovery-image6.iso

SM_IP_ADDRESS=`grep -s listen_ip_addr /opt/contrail/server_manager/sm-config.ini  | awk -F '=' '{printf $2}' | tr -d ' ' `
if [ "x${SM_IP_ADDRESS}" = "x" ];
then
  printf "\n Not able to find SM_IP from sm-config.ini\n"
  exit 1
fi

sudo mkdir -p /tmp/hw-discover
sudo wget -q ${DISCOVERY_URL} -O ${DISCOVERY_IMG_PATH}/${DISCOVERY_IMG_NAME}
if [ ! -f ${DISCOVERY_IMG_PATH}/${DISCOVERY_IMG_NAME} ];
then
  printf "\n Not able to find discovery image at ${DISCOVERY_IMG_PATH}/${DISCOVERY_IMG_NAME} \n"
  exit 1
fi
#printf "\n Found $SM_IP_ADDRESS"
#printf "\n Found ${DISCOVERY_IMG_PATH}/${DISCOVERY_IMG_NAME} \n"


ProgressBar 5 ${_end}  "Setting up Dirs....."
sudo mkdir -p /var/www/html/contrail/images/hw_discover
sudo mkdir -p /root/lshw-data/
sudo mkdir -p /var/www/html/contrail/lstopo/

echo "deb file:/opt/contrail/contrail_server_manager/packages ./" > /etc/apt/sources.list.d/smgr_sources.list
apt-get update > /dev/null 2>&1 

echo ""
ProgressBar 10 ${_end} "Package Installation"
sudo apt-get -qy install nfs-common nfs-kernel-server hwloc > /dev/null

echo ""
ProgressBar 40 ${_end} "Setting up NFS......"
if ! grep -q '/var/www/html/contrail/images/hw_discover' /etc/exports; then
  ProgressBar 42 ${_end} "Setting up NFS......"
  sudo echo '/var/www/html/contrail/images/hw_discover *(async,no_root_squash,no_subtree_check,ro)' >> /etc/exports
fi
ProgressBar 45 ${_end} "Exports Configured.."
sudo service nfs-kernel-server restart > /dev/null
if ! grep -q 'rpcbind mountd nfsd statd lockd rquotad :ALL' /etc/hosts.allow; then
  sudo echo 'rpcbind mountd nfsd statd lockd rquotad :ALL' >> /etc/hosts.allow
fi
sudo service rpcbind restart > /dev/null
sudo exportfs -r > /dev/null
sudo exportfs -v > /dev/null

echo ""
ProgressBar 50 ${_end} "Setup Image........."
set +e
sudo umount /mnt > /dev/null 2>&1
set -e
sudo mount -o loop ${DISCOVERY_IMG_PATH}/${DISCOVERY_IMG_NAME} /mnt  > /dev/null 2>&1
sudo rm -fr /var/www/html/contrail/images/hw_discover
sudo cp -a /mnt/. /var/www/html/contrail/images/hw_discover
sudo umount /mnt


ProgressBar 70 ${_end} "Setup Cobbler......."
set +e
sudo cobbler system remove --name=default  > /dev/null 2>&1
sudo cobbler profile remove --name hw_discover > /dev/null 2>&1
sudo cobbler distro remove --name hw_discover > /dev/null 2>&1
set -e
ProgressBar 80 ${_end} "Setup Cobbler......."
sudo cobbler distro add --name hw_discover --initrd=/var/www/html/contrail/images/hw_discover/casper/initrd.img --kernel=/var/www/html/contrail/images/hw_discover/casper/vmlinuz
ProgressBar 85 ${_end} "Setup Cobbler......."
sudo cobbler profile add --name=hw_discover --distro=hw_discover --kopts="boot=casper netboot=nfs nfsroot=${SM_IP_ADDRESS}:/var/www/html/contrail/images/hw_discover root=/dev/nfs server-manager=${SM_IP_ADDRESS}"
ProgressBar 90 ${_end} "Setup Cobbler......."
sudo cobbler system add --name=default --profile=hw_discover
ProgressBar 95 ${_end} "Setup Cobbler......."

ProgressBar 99 ${_end} "Setup Completed....."

printf '\nFinished!\n'

