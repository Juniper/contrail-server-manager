#!/bin/bash

set -e

# Copy our custom xinetd TFTP config
cp /etc/cobbler/tftpd.template /etc/xinetd.d/tftp

# enable tftp
touch /etc/xinetd.d/rsync

# configure HOST_IP on cobbler config files

# Execute Dockerfile CMD
exec "$@"
