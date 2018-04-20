#!/bin/bash

set -e

# enable tftp
touch /etc/xinetd.d/rsync

#systemctl restart xinetd
#systemctl restart tftp

# Execute Dockerfile CMD
exec "$@"
