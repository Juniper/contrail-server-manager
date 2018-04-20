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

# Copy our custom cobbler configs
RUN mkdir -p /opt/contrail/server_manager /etc/contrail_smgr/ /var/log/contrail-server-manager/

# Mount common volumes
VOLUME [ "/usr/bin", "/sys/fs/cgroup", "/etc/xinetd.d/", "/usr/lib/python2.7/dist-packages/cobbler/modules/", "/var/lib/cobbler/loaders/", "/var/www/cobbler/", "/etc/cobbler/" ]

COPY src/server_manager/ /opt/contrail/server_manager/
RUN ls -la /opt/contrail/server_manager/*

RUN yum install -y epel-release \
        centos-release-openstack-ocata

RUN yum install -y  \
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

EXPOSE 9001
WORKDIR /etc/contrail_smgr/
#ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/init"]
#CMD ["python", "/opt/contrail/server_manager/server_mgr_main.py", "-c", "/opt/contrail/server_manager/sm-config.ini"]
