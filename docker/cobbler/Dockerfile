FROM centos:7
 
MAINTAINER Nitish Krishna nitishk@juniper.net

COPY docker/cobbler/entrypoint.sh /

# Copy our custom cobbler configs
COPY src/cobbler/etc_cobbler/* /etc/cobbler/
COPY src/cobbler/var_lib_cobbler/* /var/lib/cobbler/
COPY src/cobbler/python_cobbler/* /usr/lib/python2.7/dist-packages/cobbler/modules/

# Configure systemd
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

# Mount common volumes
VOLUME [ "/sys/fs/cgroup", "/etc/xinetd.d/", "/usr/lib/python2.7/dist-packages/cobbler/modules/", "/var/lib/cobbler/loaders/", "/var/www/cobbler/", "/etc/cobbler/" ]

# Install dependent packages
RUN yum -y install epel-release
RUN yum -y install cobbler cobbler-web dhcp bind syslinux pykickstart initscripts net-tools

# Enable required packages
RUN systemctl enable cobblerd
RUN systemctl enable httpd
RUN systemctl enable dhcpd

# enable tftp
RUN sed -i -e 's/\(^.*disable.*=\) yes/\1 no/' /etc/xinetd.d/tftp
RUN touch /etc/xinetd.d/rsync

# Expose the ports for Cobbler/Httpd/DHCPD APIs
EXPOSE 69
EXPOSE 80
EXPOSE 443
EXPOSE 25151

#ENTRYPOINT ["bash", "entrypoint.sh"]
CMD ["/sbin/init"]
