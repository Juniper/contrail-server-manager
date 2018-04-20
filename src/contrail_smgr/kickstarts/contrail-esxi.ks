#
# Sample scripted installation file
# for ESXi 5+
#

vmaccepteula
reboot --noeject
rootpw --iscrypted $passwd

# Set the network to DHCP on the first network adapter
network --bootproto=dhcp --device=$esx_nicname

install --firstdisk --overwritevmfs
clearpart --firstdisk --overwritevmfs

%pre --interpreter=busybox

%firstboot --interpreter=busybox
# enable VHV (Virtual Hardware Virtualization to run nested 64bit Guests + Hyper-V VM)
grep -i "vhv.enable" /etc/vmware/config || echo "vhv.enable = \"TRUE\"" >> /etc/vmware/config
# enable & start remote ESXi Shell  (SSH)
vim-cmd hostsvc/enable_ssh
vim-cmd hostsvc/start_ssh
# enable & start ESXi Shell (TSM)
vim-cmd hostsvc/enable_esx_shell
vim-cmd hostsvc/start_esx_shell
# supress ESXi Shell shell warning
esxcli system settings advanced set -o /UserVars/SuppressShellWarning -i 1
# ESXi Shell interactive idle time logout
esxcli system settings advanced set -o /UserVars/ESXiShellInteractiveTimeOut -i 3600
# assign license
vim-cmd vimsvc/license --set $server_license

%post --interpreter=busybox
$SNIPPET('kickstart_done')
