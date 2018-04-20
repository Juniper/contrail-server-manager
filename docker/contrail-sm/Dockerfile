FROM centos:7

MAINTAINER Nitish Krishna nitishk@juniper.net

COPY docker/contrail-sm/entrypoint.sh /

# Setup systemd

RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

# Create required folders
RUN mkdir -p /opt/contrail/server_manager /etc/contrail_smgr/ /var/log/contrail-server-manager/

# Copy SM Code
COPY src/server_manager/ /opt/contrail/server_manager/
COPY src/contrail_smgr/cobbler/*template* /etc/contrail_smgr/cobbler/
COPY src/contrail_smgr/cobbler/*conf* /etc/contrail_smgr/cobbler/

# RUN ls -la /opt/contrail/server_manager/*

RUN yum install -y epel-release \
        centos-release-openstack-ocata

RUN yum install -y  initscripts\
        net-tools \ 
        python2-pip \
        python2-gevent \
        dhcp \
        httpd \
        httpd-devel \
        mod_ssl\
        fence-agents \
        python-devel \
        ntp \
        autoconf \
        gcc \
        bind \
        tftp \
        wget \
        sendmail \
        syslinux \
        gcc-c++ \
        libcurl-devel \
        openssl-devel \
        zlib-devel \
        ipmitool \
        createrepo \
        mod_wsgi \
        tftp-server \
        python2-django \
        python-simplejson \
        python2-requests \
        reprepro \
        python-netaddr \
        python-yaml \
        python-paramiko \
        python2-xmltodict \
        python2-crypto \
        python-paste \
        ansible \
        python2-oslo-config \
        python2-urllib3 \
        python-ipaddress \
        python-websocket-client \
        ceph-common \
        && pip install --upgrade pip

# Mount common volumes
VOLUME ["/sys/fs/cgroup"]

EXPOSE 9001
WORKDIR /opt/contrail/server_manager/
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/init"]
#CMD ["python", "/opt/contrail/server_manager/server_mgr_main.py", "-c", "/opt/contrail/server_manager/sm-config.ini"]
