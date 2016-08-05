# view contents of rpm file: rpm -qlp <filename>.rpm

%define         _contrailopt /opt/contrail

%if 0%{?_buildTag:1}
%define         _relstr      %{_buildTag}
%else
%define         _relstr      %(date -u +%y%m%d%H%M)
%endif
%{echo: "Building release %{_relstr}\n"}
%if 0%{?_fileList:1}
%define         _flist      %{_fileList}
%else
%define         _flist      None
%endif
%if 0%{?_srcVer:1}
%define         _verstr      %{_srcVer}
%else
%define         _verstr      1
%endif
%if 0%{?_skuTag:1}
%define         _sku     %{_skuTag}
%else
%define         _sku      None
%endif


Name:		    contrail-puppet
Version:	    %{_verstr}
Release:	    %{_relstr}%{?dist}
Summary:	    Contrail Puppet Code%{?_gitVer}
BuildArch:          noarch

Group:              Applications/System
License:            Commercial
URL:                http://www.juniper.net/
Vendor:             Juniper Networks Inc



%description
Contrail Puppet code for Server Manager

%install

# Setup directories
rm -rf %{buildroot}
install -d -m 755 %{buildroot}%{_contrailopt}
install -d -m 755 %{buildroot}%{_contrailopt}/puppet

# Install puppet manifests
tar -cvzf %{_builddir}/../build/contrail-puppet-manifest.tgz -C %{_builddir}/../tools/puppet .
install -p -m 755 %{_builddir}/../build/contrail-puppet-manifest.tgz %{buildroot}%{_contrailopt}/puppet/contrail-puppet-manifest.tgz


%files
%defattr(-, root, root)
%{_contrailopt}/puppet/contrail-puppet-manifest.tgz

%changelog
* Thu Aug 4 2016 - npchandran@juniper.net contrail-puppet
- Adding contrail-puppet rpm package for Opencontrail
