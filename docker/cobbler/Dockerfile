FROM centos:7
 
MAINTAINER Nitish Krishna nitishk@juniper.net

COPY docker/cobbler/entrypoint.sh /

# Copy our custom cobbler configs
COPY src/cobbler/etc_cobbler/* /etc/cobbler/
COPY src/cobbler/var_lib_cobbler/* /var/lib/cobbler/
COPY src/cobbler/python_cobbler/* /usr/lib/python2.7/dist-packages/cobbler/modules/
COPY src/cobbler/etc_bind/named.conf.options /etc/named/

# Configure systemd
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

# Install dependent packages
RUN yum -y install epel-release
RUN yum -y install cobbler cobbler-web dhcp bind syslinux pykickstart initscripts net-tools

# Enable required packages
RUN systemctl enable cobblerd
RUN systemctl enable httpd
RUN systemctl enable dhcpd

# Mount common volumes
VOLUME [ "/sys/fs/cgroup", "/etc/cobbler/" ]

# Expose the ports for Cobbler/Httpd/DHCPD APIs
EXPOSE 69
EXPOSE 80
EXPOSE 443
EXPOSE 25151

ENTRYPOINT ["bash", "entrypoint.sh"]
CMD ["/sbin/init"]
