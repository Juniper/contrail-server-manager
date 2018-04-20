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
RUN mkdir -p /opt/contrail/server_manager /etc/contrail_smgr/

# Mount common volumes
VOLUME [ "/sys/fs/cgroup", "/etc/xinetd.d/", "/usr/lib/python2.7/dist-packages/cobbler/modules/", "/var/lib/cobbler/loaders/", "/var/www/cobbler/", "/etc/cobbler/" ]

COPY src/server_manager/ /opt/contrail/server_manager/
RUN ls -la /opt/contrail/server_manager/*

RUN yum install -y epel-release \
        python \
        sqlite \
        python-pip \
        python-gevent \
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
        dpkg \
        dpkg-devel \
        syslinux \
        gcc-c++ \
        libcurl-devel \
        openssl-devel \
        zlib-devel \
        ipmitool \
        createrepo \
        mod_wsgi \
        tftp-server \
        python-urlgrabber \
        python2-django \
        python-simplejson \
        python-requests \
        reprepro \
        python-netaddr \
        python-yaml \
        libnss3* \
        python-paramiko \
        python-xmltodict \
        python-pycurl \
        python2-crypto \
        python-paste \
        ansible \
        centos-release-openstack-ocata \
        python2-oslo-config \
        python-urllib3 \
        python-ipaddress \
        python-websocket-client \
        ceph-common \
        && pip install --upgrade pip

EXPOSE 9001
WORKDIR /etc/contrail_smgr/
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/sbin/init"]
#CMD ["python", "/opt/contrail/server_manager/server_mgr_main.py", "-c", "/opt/contrail/server_manager/sm-config.ini"]
