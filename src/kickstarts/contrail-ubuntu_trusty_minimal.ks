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

cat >>/etc/apt/sources.list.servermanager <<EOF

#deb cdrom:[Ubuntu 14.04 _Trusty Tahr_ - Release i386]/ Trusty main restricted
# See http://help.ubuntu.com/community/UpgradeNotes for how to upgrade to
# newer versions of the distribution.

deb http://us.archive.ubuntu.com/ubuntu/ trusty main restricted
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty main restricted

## Major bug fix updates produced after the final release of the
## distribution.
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates main restricted
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates main restricted

## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu
## team. Also, please note that software in universe WILL NOT receive any
## review or updates from the Ubuntu security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty universe
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty universe
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates universe
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates universe

## N.B. software from this repository is ENTIRELY UNSUPPORTED by the Ubuntu 
## team, and may not be under a free licence. Please satisfy yourself as to 
## your rights to use the software. Also, please note that software in 
## multiverse WILL NOT receive any review or updates from the Ubuntu
## security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty multiverse
deb http://us.archive.ubuntu.com/ubuntu/ trusty-updates multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-updates multiverse

## Uncomment the following two lines to add software from the 'backports'
## repository.
## N.B. software from this repository may not have been tested as
## extensively as that contained in the main release, although it includes
## newer versions of some applications which may provide useful features.
## Also, please note that software in backports WILL NOT receive any review
## or updates from the Ubuntu security team.
deb http://us.archive.ubuntu.com/ubuntu/ trusty-backports main restricted universe multiverse
deb-src http://us.archive.ubuntu.com/ubuntu/ trusty-backports main restricted universe multiverse

## Uncomment the following two lines to add software from Canonical's
## 'partner' repository. This software is not part of Ubuntu, but is
## offered by Canonical and the respective vendors as a service to Ubuntu
## users.
deb http://archive.canonical.com/ubuntu trusty partner
deb-src http://archive.canonical.com/ubuntu trusty partner

deb http://security.ubuntu.com/ubuntu trusty-security main restricted
deb-src http://security.ubuntu.com/ubuntu trusty-security main restricted
deb http://security.ubuntu.com/ubuntu trusty-security universe
deb-src http://security.ubuntu.com/ubuntu trusty-security universe
deb http://security.ubuntu.com/ubuntu trusty-security multiverse
deb-src http://security.ubuntu.com/ubuntu trusty-security multiverse

EOF

#Set up the ntp client 
apt-get -y install ntp
ntpdate -s $server
mv /etc/ntp.conf /etc/ntp.conf.orig
touch /var/lib/ntp/drift
cat << __EOT__ > /etc/ntp.conf
driftfile /var/lib/ntp/drift
server $server
restrict 127.0.0.1
restrict -6 ::1
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
__EOT__
service ntp restart
#--------------------------------------------------------------------------

blacklist mei module for ocp
echo "blacklist mei" >> /etc/modprobe.d/blacklist.conf
wget http://$server/cblr/svc/op/trig/mode/post/system/$system_name
%end
