#
# Spec  file for server manager...
#

%define         _contrailetc /etc/contrail_smgr
%define         _initd/etc /etc/init.d
%define         _contrailutils /opt/contrail/utils
%define		_etc /etc
%define		_contrail_smgr /server_manager
%define         _vmware /vmware/
%define		_contrail_smgr_src	    %(pwd)/
%define		_third_party	    %(pwd)/../../third_party/
%define		_mydate %(date)
%define		_initdetc   /etc/init.d/
%define		_etc	    /etc/
%define		_cobbleretc /etc/cobbler/
%define		_puppetetc /etc/puppet/
%define		_contrailopt /opt/contrail/
%define		_sbinusr    /usr/sbin/
%define         _pyver        %( %{__python} -c "import sys; print '%s.%s' % sys.version_info[0:2]" )
%define         _pysitepkg    /usr/lib/python%{_pyver}/site-packages


Name: contrail-server-manager
Version: 1.0
Release: 1
Summary: A server manager

Group: Applications/System
License: Commercial
URL: http://www.juniper.net/
Vendor: Juniper Networks Inc

BuildArch: noarch
SOURCE0 : %{name}-%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

#BuildRequires:
Requires: python >= 2.6.6
Requires: httpd
Requires: sqlite
Requires: cobbler
Requires: cobbler-web
Requires:fence-agents
Requires: puppet
Requires: puppet-server
Requires: python-devel
Requires: python-pip
Requires: dhcp
Requires: ntp
Requires: autoconf
Requires: gcc
Requires: bind
Requires: tftp
Requires: ntp
Requires: wget
Requires: sendmail
Requires: dpkg
Requires: dpkg-devel

%description
A Server manager description

%prep
#%setup -q

%post
HOST_IP=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`
echo $HOST_IP

cp -r %{_contrailetc}/cobbler /etc/
# Copy cobbler distro signatures file that contains esxi5.5 signature.
mv /etc/cobbler/distro_signatures.json /etc/cobbler/distro_signatures.json-save
mv /var/lib/cobbler/distro_signatures.json /var/lib/cobbler/distro_signatures.json-save
cp %{_contrailetc}/cobbler/distro_signatures.json-esxi55 /etc/cobbler/distro_signatures.json
cp %{_contrailetc}/cobbler/distro_signatures.json-esxi55 /var/lib/cobbler/distro_signatures.json

# Copy cobbler boot.cfg template file for esxi5.5
cp -f %{_contrailetc}/cobbler/bootcfg_esxi55.template /etc/cobbler/pxe

# Copy cobbler pxesystem template file for esxi
mv /etc/cobbler/pxe/pxesystem_esxi.template /etc/cobbler/pxe/pxesystem_esxi.template-save
cp %{_contrailetc}/cobbler/pxesystem_esxi.template /etc/cobbler/pxe

cp -r %{_contrailetc}/puppet /etc/
cp -r %{_contrailetc}/kickstarts /var/www/html/
cp %{_contrailetc}/sendmail.cf /etc/mail/

cp /usr/bin/server_manager/dhcp.template /etc/cobbler/
cp -r /usr/bin/server_manager/kickstarts /var/www/html/
mkdir -p /var/www/html/contrail

cp -u /etc/puppet/puppet_init_rd /var/www/cobbler/aux/puppet
easy_install argparse
easy_install paramiko
easy_install pycrypto
easy_install ordereddict

mkdir -p %{_contrailetc}/images/
service httpd start
service xinetd restart
service sqlite start
service cobblerd start

service puppetmaster start
service puppet start

service postfix stop
service sendmail restart

sed -i "s/10.84.51.11/$HOST_IP/" /etc/cobbler/settings
/sbin/chkconfig --add contrail-server-manager
sed -i "s/module = authn_.*/module = authn_configfile/g" /etc/cobbler/modules.conf
sed -i "s/127.0.0.1/$HOST_IP/g" /opt/contrail/server_manager/sm-config.ini


chkconfig httpd on
chkconfig puppetmaster on
chkconfig contrail-server-manager on
chkconfig puppet on


#service contrail-server-manager restart
%build

%install
rm -rf %{buildroot}
mkdir -p  %{buildroot}


install -d -m 755 %{buildroot}%usr
install -d -m 755 %{buildroot}%{_sbinusr}

install -d -m 755 %{buildroot}%{_contrailopt}
install -d -m 755 %{buildroot}%{_contrailetc}
install -d -m 755 %{buildroot}%{_initdetc}
install -d -m 755 %{buildroot}%{_contrailopt}%{_contrail_smgr}
#install -d -m 755 %{buildroot}%{_cobbleretc}
#install -d -m 755 %{buildroot}%{_puppetetc}

#cp *.py %{buildroot}%{_bindir}%{_contrail_smgr}
pwd
#install -p -m 755 server_mgr_main.py %{buildroot}%{_bindir}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_main.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_db.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_cobbler.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_puppet.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_exception.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_logger.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}server_mgr_status.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}smgr_dhcp_event.py %{buildroot}%{_contrailopt}%{_contrail_smgr}

cp %{_contrail_smgr_src}server_mgr_defaults.py %{buildroot}%{_contrailopt}%{_contrail_smgr}

cp %{_contrail_smgr_src}utils/send_mail.py %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}sm-config.ini %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}tags.ini %{buildroot}%{_contrailetc}
cp %{_contrail_smgr_src}logger.conf %{buildroot}%{_contrailopt}%{_contrail_smgr}
cp %{_contrail_smgr_src}%{_vmware}esxi_contrailvm.py %{buildroot}%{_contrailopt}%{_contrail_smgr}


cp %{_contrail_smgr_src}third_party/bottle.py %{buildroot}%{_contrailopt}%{_contrail_smgr}


cp %{_contrail_smgr_src}contrail-server-manager %{buildroot}%{_initdetc}
cp -r %{_contrail_smgr_src}/puppet %{buildroot}%{_contrailetc}
cp -r %{_contrail_smgr_src}repos/contrail-centos-repo %{buildroot}%{_contrailetc}
cp -r %{_contrail_smgr_src}cobbler %{buildroot}%{_contrailetc}
cp -r %{_contrail_smgr_src}kickstarts %{buildroot}%{_contrailetc}
cp %{_contrail_smgr_src}contrail-server-manager.start %{buildroot}%{_sbinusr}contrail-server-manager
cp %{_contrail_smgr_src}utils/sendmail.cf %{buildroot}%{_contrailetc}

#install -p -m 755 %{_contrail_smgr_src}cobbler/dhcp.template %{buildroot}%{_bindir}%{_contrail_smgr}
#install -p -m 755 %{_contrail_smgr_src}cobbler/settings %{buildroot}%{_bindir}%{_contrail_smgr}

install -d -m 755 %{buildroot}%{_pysitepkg}/cobbler/modules
cp %{_contrail_smgr_src}third_party/server_post_install.py %{buildroot}%{_pysitepkg}/cobbler/modules/
cp %{_contrail_smgr_src}third_party/server_pre_install.py %{buildroot}%{_pysitepkg}/cobbler/modules/

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
#%config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%{_contrailopt}/*
/usr/sbin/*
/etc/init.d/contrail-server-manager
%{_contrailetc}/*
#/etc/cobbler/dhcp.template
#/etc/cobbler/dhcp.template
#/etc/puppet/*
%{_pysitepkg}/cobbler/modules/*
%changelog
* Thu Nov 29 2013  Thilak Raj S <tsurendra@juniper.net> 1.0-1
- First Build

