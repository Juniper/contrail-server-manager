FROM centos:7

MAINTAINER Nitish Krishna nitishk@juniper.net

COPY docker/xinetd/entrypoint.sh /

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
RUN yum -y install xinetd initscripts

# Mount common/shared volumes
VOLUME [ "/sys/fs/cgroup", "/etc/xinetd.d/"]

# Enable required packages
RUN systemctl enable xinetd

#ENTRYPOINT ["bash", "entrypoint.sh"]
CMD ["xinetd", "-dontfork"]
