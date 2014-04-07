#!/bin/bash
set -x
ostype=$1;shift
uuid=$1;shift
master=$1;shift
is_master=$1;shift
#TODO Ppvide support for centos

this_host=$(hostname)


rabbitmqctl cluster_status | grep $master
master_added=$?
rabbitmqctl cluster_status | grep $this_host
slave_added=$?

existing_uuid=$(cat /var/lib/rabbitmq/.erlang.cookie)

if [ $is_master == "yes" ] && [ $existing_uuid == $uuid ]; then
    exit 0
fi


if [ $is_master == "no" ] && [ $master_added == 0 ] && [ $slave_added == 0 ]; then
    exit 0
fi


eval "sudo ufw disable"

eval "service rabbitmq-server stop"
eval "epmd -kill"
echo ${uuid} > /var/lib/rabbitmq/.erlang.cookie


eval "service rabbitmq-server start"

eval "rabbitmqctl stop_app"

eval "rabbitmqctl force_reset"

if [ $is_master == "yes" ]; then
    eval "rabbitmqctl start_app"
else
    eval "rabbitmqctl cluster rabbit@$this_host rabbit@$master"
    if [ $? != 0  ];then
        exit 1
    fi
    eval "rabbitmqctl start_app"
fi
rabbitmqctl cluster_status | grep $master
master_added=$?
rabbitmqctl cluster_status | grep $this_host
slave_added=$?

if [ $master_added != 0 ] || [ $master_added != 0 ]; then
    exit 1
fi
eval "rabbitmqctl cluster_status"

