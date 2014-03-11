#
# Spec  file for server manager...
#

%define         _contrailetc /etc/contrail
%define         _initd/etc /etc/init.d
%define         _contrailutils /opt/contrail/utils
%define		_etc /etc
%define		_server_mgr /server_manager
%define		_server_mgr_src	    %(pwd)/
%define		_third_party	    %(pwd)/../../third_party/
%define		_mydate %(date)
%define		_initdetc   /etc/init.d/
%define		_etc	    /etc/
%define		_cobbleretc /etc/cobbler/
%define		_puppetetc /etc/puppet/
%define             _venv_root    /opt/contrail/smgr-venv
%define             _venvtr       --prefix=%{_venv_root}
%define		_contrailopt /opt/contrail/
%define		_sbinusr    /usr/sbin/

Name: server_mgr
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
Requires: contrail-smgr-venv
Requires: ntp

%description
A Server manager description

%prep
#%setup -q

%post
HOST_IP=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`
echo $HOST_IP

cp -r /etc/contrail/cobbler /etc/
cp -r /etc/contrail/puppet /etc/
cp -r /etc/contrail/kickstarts /var/www/html/

cp /usr/bin/server_manager/dhcp.template /etc/cobbler/
cp -r /usr/bin/server_manager/kickstarts /var/www/html/
mkdir -p /var/www/html/contrail

cp -u /etc/puppet/puppet_init_rd /var/www/cobbler/aux/puppet
easy_install argparse
easy_install paramiko
easy_install pycrypto

mkdir -p /etc/contrail/images/
service httpd start
service xinetd restart
service sqlite start
service cobblerd start

service puppetmaster start
service puppet start

sed -i "s/10.84.51.11/$HOST_IP/" /etc/cobbler/settings
/sbin/chkconfig --add smgrd
sed -i "s/authn_denyall/authn_testing/g" /etc/cobbler/modules.conf
sed -i "s/127.0.0.1/$HOST_IP/g" /opt/contrail/server_manager/server_config.ini


chkconfig httpd on
chkconfig puppetmaster on
chkconfig smgrd on
chkconfig puppet on


service smgrd restart
%build


%install
rm -rf %{buildroot}
mkdir -p  %{buildroot}


install -d -m 755 %{buildroot}%usr
install -d -m 755 %{buildroot}%{_sbinusr}

install -d -m 755 %{buildroot}%{_contrailopt}
install -d -m 755 %{buildroot}%{_contrailetc}
install -d -m 755 %{buildroot}%{_initdetc}
install -d -m 755 %{buildroot}%{_contrailopt}%{_server_mgr}
#install -d -m 755 %{buildroot}%{_cobbleretc}
#install -d -m 755 %{buildroot}%{_puppetetc}

#cp *.py %{buildroot}%{_bindir}%{_server_mgr}
pwd
#install -p -m 755 server_mgr_main.py %{buildroot}%{_bindir}%{_server_mgr}
cp %{_server_mgr_src}server_mgr_main.py %{buildroot}%{_contrailopt}%{_server_mgr}
cp %{_server_mgr_src}server_mgr_db.py %{buildroot}%{_contrailopt}%{_server_mgr}
cp %{_server_mgr_src}server_mgr_cobbler.py %{buildroot}%{_contrailopt}%{_server_mgr}
cp %{_server_mgr_src}server_mgr_puppet.py %{buildroot}%{_contrailopt}%{_server_mgr}
cp %{_server_mgr_src}smgr_dhcp_event.py %{buildroot}%{_contrailopt}%{_server_mgr}
cp %{_server_mgr_src}server_config.ini %{buildroot}%{_contrailopt}%{_server_mgr}

cp -r %{_server_mgr_src}client %{buildroot}%{_contrailopt}%{_server_mgr}


cp %{_third_party}/bottle-0.11.6/bottle.py %{buildroot}%{_contrailopt}%{_server_mgr}


cp %{_server_mgr_src}smgrd %{buildroot}%{_initdetc}
cp -r %{_server_mgr_src}/puppet %{buildroot}%{_contrailetc}
cp -r %{_server_mgr_src}repos/puppet-repo %{buildroot}%{_contrailetc}
cp -r %{_server_mgr_src}cobbler %{buildroot}%{_contrailetc}
cp -r %{_server_mgr_src}kickstarts %{buildroot}%{_contrailetc}

cp %{_server_mgr_src}smgrd.start %{buildroot}%{_sbinusr}smgrd

#install -p -m 755 %{_server_mgr_src}cobbler/dhcp.template %{buildroot}%{_bindir}%{_server_mgr}
#install -p -m 755 %{_server_mgr_src}cobbler/settings %{buildroot}%{_bindir}%{_server_mgr}


%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
#%config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%{_contrailopt}/*
/usr/sbin/*
/etc/init.d/smgrd
/etc/contrail/*
#/etc/cobbler/dhcp.template
#/etc/cobbler/dhcp.template
#/etc/puppet/*


%changelog
* Thu Nov 29 2013  Thilak Raj S <tsurendra@juniper.net> 1.0-1
- First Build

