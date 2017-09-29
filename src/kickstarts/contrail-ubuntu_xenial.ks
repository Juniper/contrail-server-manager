# Kickstart template for the NewNode (ubuntu)
%pre
wget http://$server/cblr/svc/op/trig/mode/pre/system/$system_name

%post
set -x -v
#--------------------------------------------------------------------------
# Uodate entries in /etc/hosts file for self and puppet ip address
sed -i '/127\.0\..\.1/d' /etc/hosts
echo "127.0.0.1 localhost.$system_domain localhost" >> /etc/hosts
echo "$ip_address $system_name.$system_domain $system_name" >> /etc/hosts
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
#Add Banner for Contrail Cloud
cat > /etc/ssh/banner.base64.txt << BANNER
CiBfX19fXyAgICAgICAgICAgICBfICAgICAgICAgICAgIF8gXyAgIF9fX19fIF8gICAgICAgICAg
ICAgICAgIF8gCi8gIF9fIFwgICAgICAgICAgIHwgfCAgICAgICAgICAgKF8pIHwgLyAgX18gXCB8
ICAgICAgICAgICAgICAgfCB8CnwgLyAgXC8gX19fICBfIF9fIHwgfF8gXyBfXyBfXyBfIF98IHwg
fCAvICBcLyB8IF9fXyAgXyAgIF8gIF9ffCB8CnwgfCAgICAvIF8gXHwgJ18gXHwgX198ICdfXy8g
X2AgfCB8IHwgfCB8ICAgfCB8LyBfIFx8IHwgfCB8LyBfYCB8CnwgXF9fL1wgKF8pIHwgfCB8IHwg
fF98IHwgfCAoX3wgfCB8IHwgfCBcX18vXCB8IChfKSB8IHxffCB8IChffCB8CiBcX19fXy9cX19f
L3xffCB8X3xcX198X3wgIFxfXyxffF98X3wgIFxfX19fL198XF9fXy8gXF9fLF98XF9fLF98CiAg
ICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg
ICAgICAgCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAg
ICAgICAgICAgICAgICAgCg==
BANNER
base64 -d /etc/ssh/banner.base64.txt > /etc/ssh/banner.txt
sed -i '/Banner/c\Banner \/etc\/ssh\/banner.txt' /etc/ssh/sshd_config
# Enable ssh for root
sed -i '/PermitRootLogin/c\PermitRootLogin yes' /etc/ssh/sshd_config
service ssh restart

#--------------------------------------------------------------------------
mv /etc/apt/sources.list /etc/apt/sources.list.save
touch /etc/apt/sources.list

cat >>/etc/apt/sources.list <<EOF
# add repos needed for puppet and its dependencies
deb http://$server/thirdparty_packages/ ./
deb http://$server/thirdparty_packages_ubuntu_1604/ ./

EOF

apt-get update
apt-get install -y python

# Build script file to be executed in case of bond bring-up. This will be called
# from rc.local.
cat >/etc/setup_bond.sh <<EOF
#!/bin/sh

sleep 5

vrouter_provisioned=0
if [ -f /etc/contrail/supervisord_vrouter_files/contrail-vrouter-dpdk.ini ];
then
    vrouter_provisioned=1
fi
if [ -f /lib/systemd/system/contrail-vrouter-dpdk.service ];
then
    vrouter_provisioned=1
fi

for iface in \$(ifquery --list); do
    ifquery \$iface | grep "bond-master"
    if [ \$? -eq 0 ]; then
        ifdown \$iface
    fi
    if [ $vrouter_provisioned -eq 0 ];
    then
        ifquery \$iface | grep "vlan-raw-device"
        if [ \$? -eq 0 ]; then
            ifdown \$iface
        fi
    fi
done

sleep 2

for iface in \$(ifquery --list); do
    ifquery \$iface | grep "bond-master"
    if [ \$? -eq 0 ]; then
        ifup \$iface
    fi
    if [ $vrouter_provisioned -eq 0 ];
    then
        ifquery \$iface | grep "vlan-raw-device"
        if [ \$? -eq 0 ]; then
            ifup \$iface
        fi
    fi
done
EOF
chmod 755 /etc/setup_bond.sh

wget http://$server/cblr/svc/op/trig/mode/post/system/$system_name
%end
