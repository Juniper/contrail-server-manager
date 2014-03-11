#!/bin/bash
if [ -f "/etc/contrail/interface_renamed" ]
then
    cat /etc/contrail/interface_renamed
else
    echo "0"
fi
