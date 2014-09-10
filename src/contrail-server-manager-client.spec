#
# Spec  file for server manager...
#

%define         _contrailetc /etc/contrail_smgr
%define         _initd/etc /etc/init.d
%define         _contrailutils /opt/contrail/utils
%define		_etc /etc
%define		_contrail_smgr /server_manager
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


Name: contrail_smgr_client
Version: 1.0
Release: 1
Summary: A Client for Server Manager

Group: Applications/System
License: Commercial
URL: http://www.juniper.net/
Vendor: Juniper Networks Inc

BuildArch: noarch
SOURCE0 : %{name}-%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

#BuildRequires:
Requires: python >= 2.6.6

%description
A Client for Server manager

%prep
#%setup -q

%post
HOST_IP=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`
echo $HOST_IP

easy_install argparse
easy_install pycurl

if [ -e /usr/bin/server-manager ]; then
   unlink /usr/bin/server-manager
fi
ln -s /opt/contrail/server_manager/client/server-manager /usr/bin/server-manager
%build
cd %{_contrail_smgr_src}client/

%install
rm -rf %{buildroot}
mkdir -p  %{buildroot}


install -d -m 755 %{buildroot}%usr

install -d -m 755 %{buildroot}%{_contrailopt}
install -d -m 755 %{buildroot}%{_contrailopt}%{_contrail_smgr}
install -d -m 755 %{buildroot}%{_contrailopt}%{_contrail_smgr}/client


pwd
cp %{_contrail_smgr_src}client/*.py %{buildroot}%{_contrailopt}%{_contrail_smgr}/client
cp %{_contrail_smgr_src}client/*.json %{buildroot}%{_contrailopt}%{_contrail_smgr}/client
cp %{_contrail_smgr_src}utils/create_smgr_db.py %{buildroot}%{_contrailopt}%{_contrail_smgr}/client
cp %{_contrail_smgr_src}client/server-manager %{buildroot}%{_contrailopt}%{_contrail_smgr}/client


cp -r %{_contrail_smgr_src}client/sm-client-config.ini %{buildroot}%{_contrailopt}%{_contrail_smgr}/client

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
#%config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%{_contrailopt}/*
%changelog
* Thu Nov 29 2013  Thilak Raj S <tsurendra@juniper.net> 1.0-1
- First Build

