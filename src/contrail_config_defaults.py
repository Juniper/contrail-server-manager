# Config from Puppet Templates
USE_CONFIG_TEMPLATES = False

role_config_list_map = {
    "controller": "controller_config_list"
}

common_config = {
    "host_control_ip": "",
    "internal_vip": "",
    "keystone_ip": "",
    "openstack_ip": "",
    "disc_server_ip": "",
    "uuid": "",
    "external_vip": "",
    "contrail_internal_vip": "",
    "contrail_external_vip": "",
    "internal_virtual_router_id": 102,
    "external_virtual_router_id": 101,
    "contrail_internal_virtual_router_id": 103,
    "contrail_external_virtual_router_id": 104,
    "analytics_data_ttl": 48,
    "analytics_config_audit_ttl": 2160,
    "analytics_statistics_ttl": 168,
    "analytics_flow_ttl": 2,
    "snmp_scan_frequency": 600,
    "snmp_fast_scan_frequency": 60,
    "topology_scan_frequency": 60,
    "analytics_syslog_port": -1,
    "database_dir": "/var/lib/cassandra",
    "analytics_data_dir": "",
    "ssd_data_dir": "",
    "database_minimum_diskGB": 256,
    "enable_lbass": "",
    "redis_password": "",
    "keystone_admin_password": "contrail123",
    "keystone_admin_user": "admin",
    "keystone_admin_tenant": "admin",
    "keystone_service_tenant": "services",
    "keystone_region_name": "RegionOne",
    "keystone_insecure_flag": "false",
    "keystone_auth_protocol": "http",
    "multi_tenancy": "true",
    "zookeeper_ip_list": "",
    "haproxy": "",
    "hc_interval": "",
    "nfs_server": "",
    "nfs_glance_path": "",
    "database_token": "",
    "encapsulation_priority": 'VXLAN,MPLSoUDP,MPLSoGRE',
    "router_asn": "",
    "external_bgp": "",
    "use_certificates": "false",
    "contrail_logoutput": "false",
    "enable_ceilometer": "false",
    "config_ip_list": "",
    "collector_ip_list": "",
    "zookeeper_ip_port": 2181,
    "openstack_mgmt_ip_list": "",
    "openstack_ip_list": "",
    "amqp_server_ip": "",
    "openstack_manage_amqp": "false",
    "zk_ip_port": 2181,
    "database_ip_port": '9160',
    "database_ip_list": "",
    "keystone_auth_port": 35357,
    "memcached_servers": "",
    "ifmap_server_port": "",
}

calculated_config = {
    "keystone_auth_host": "",
    "zk_ip_list_to_use": "",
    "openstack_mgmt_ip_list_to_use": "",
    "keystone_ip_to_use": "",
    "vip_to_use": "",
    "config_ip_to_use": "",
    "collector_ip_to_use": "",
    "contrail_rabbit_port": "",
    "openstack_ip_to_use": "",
    "discovery_ip_to_use": "",
    "amqp_server_to_use": "",
    "rest_api_port": "",
    "cassandra_ip_list": "",
    "kafka_broker_list": "",
    "zk_ip_port_list_to_use": "",
    "memcache_servers" : ""
}
controller_config_list = ['contrail_keystone_auth_conf', 'contrail_analytics_api_conf', 'contrail_collector_conf',
                          'contrail_query_engine_conf', 'contrail_snmp_collector_conf', 'contrail_snmp_collector_ini',
                          'contrail_analytics_nodemgr_conf', 'contrail_alarm_gen_conf', 'contrail_topology_conf']

contrail_api_conf = {
    "DEFAULT": {
        "ifmap_server_ip": {
            "common_config": "host_control_ip"
        },
        "ifmap_server_port": {
            "common_config": "ifmap_server_port"
        },
        "ifmap_username": "",
        "ifmap_password": "",
        "cassandra_server_list": {
            "calculated_config": "cassandra_ip_list"
        },
        "listen_ip_addr": "0.0.0.0",
        "listen_port": 8082,
        "auth": "keystone",
        "multi_tenancy": {
            "common_config": "multi_tenancy"
        },
        "log_file": "/var/log/contrail/api.log",
        "log_local": 1,
        "log_level": "SYS_NOTICE",
        "disc_server_ip": {
            "calculated_config": "config_ip_to_use"
        },
        "disc_server_port": 5998,
        "zk_server_ip": {
            "calculated_config": "zk_ip_port_list_to_use"
        },
        "rabbit_server": {
            "calculated_config": "config_ip_to_use"
        },
        "rabbit_port": {
            "calculated_config": "contrail_rabbit_port"
        },
    },
    "SECURITY": {
        "use_certs": {
            "common_config": "use_certs"
        },
        "keyfile": "/etc/contrail/ssl/private_keys/apiserver_key.pem",
        "certfile": "/etc/contrail/ssl/certs/apiserver.pem",
        "ca_certs": "/etc/contrail/ssl/certs/ca.pem"
    }
}

contrail_keystone_auth_conf = {
    "KEYSTONE": {
        "auth_host": {
            "calculated_config": "keystone_ip_to_use"
        },
        "auth_protocol": {
            "common_config": "keystone_auth_protocol"
        },
        "auth_port": {
            "common_config": "keystone_auth_port"
        },
        "admin_user": {
            "common_config": "keystone_username"
        },
        "admin_password": {
            "common_config": "keystone_password"
        },
        "admin_tenant_name": {
            "common_config": "keystone_tenant"
        },
        "insecure": {
            "common_config": "keystone_insecure_flag"
        },
        "memcached_servers": {
            "calculated_config": "memcached_servers"
        }
    }
}

contrail_analytics_api_conf = {
    "DEFAULTS": {
        "host_ip": {
            "common_config": "host_control_ip"
        },
        "cassandra_server_list": {
            "calculated_config": "cassandra_ip_list"
        },
        "collectors": {
            "calculated_config": "collector_ip_port_list"
        },
        "http_server_port": 8090,
        "rest_api_port": {
            "calculated_config": "rest_api_port"
        },
        "rest_api_ip": "0.0.0.0",
        #"log_file": "/var/log/contrail/contrail-analytics-api.log",
        #"log_local": 1,
        #"log_level": "SYS_NOTICE",
        "log_category": "*",
        "analytics_data_ttl": {
            "common_config": "analytics_data_ttl"
        },
        "analytics_config_audit_ttl": {
            "common_config": "analytics_config_audit_ttl"
        },
        "analytics_statistics_ttl": {
            "common_config": "analytics_statistics_ttl"
        },
        "analytics_flow_ttl": {
            "common_config": "analytics_flow_ttl"
        },
    },
    "DISCOVERY": {
        "disc_server_ip": {
            "calculated_config": "config_ip_to_use"
        },
        "disc_server_port": 5998
    },
    "REDIS": {
        "redis_server_port": 6379,
        "redis_query_port": 6379,
        "redis_password": {
            "common_config": "redis_password"
        }
    }
}

contrail_collector_conf = {
    "DEFAULT": {
        "analytics_data_ttl": {
            "common_config": "analytics_data_ttl"
        },
        "analytics_config_audit_ttl": {
            "common_config": "analytics_config_audit_ttl"
        },
        "analytics_statistics_ttl": {
            "common_config": "analytics_statistics_ttl"
        },
        "analytics_flow_ttl": {
            "common_config": "analytics_flow_ttl"
        },
        "cassandra_server_list": {
            "calculated_config": "cassandra_ip_list"
        },
        "kafka_broker_list": {
            "calculated_config": "kafka_broker_list"
        },
        "http_server_port": 8089,
        "log_file": "/var/log/contrail/contrail-collector.log",
        "log_local": 1,
        "log_level": "SYS_NOTICE",
        #"log_category": "*",
        "log_files_count": 10,
        #"log_file_size": 1048576,
        "syslog_port": {
            "common_config": "analytics_syslog_port"
        },
        #"sflow_port": 6343,
    },
    "COLLECTOR": {
        "port": 8086,
        #"server": "0.0.0.0",
        #"protobuf_port": 3333,

    },
    "DISCOVERY": {
        #"port": 5998,
        "server": {
            "calculated_config": "config_ip_to_use"
        }
    },
    "REDIS": {
        "port": 6379,
        "redis_password": {
            "common_config": "redis_password"
        },
        "server": "127.0.0.1"
    }
}

contrail_query_engine_conf = {
    "DEFAULT": {
        "hostip": {
            "common_config": "host_control_ip"
        },
        "analytics_data_ttl": {
            "common_config": "analytics_data_ttl"
        },
        "cassandra_server_list": {
            "calculated_config": "cassandra_ip_list"
        },
        "collectors": "127.0.0.1:8086",
        "log_file": "/var/log/contrail/contrail-query-engine.log",
        "log_local": 1,
        "log_level": "SYS_NOTICE",
        #"log_category": "*",
        "log_files_count": 10,
        #"log_file_size": 1048576,
        #"log_disable": 0,
        #"test_mode": 0
    },
    "DISCOVERY": {
        #"port": 5998,
        #"server": {
            #"calculated_config": "discovery_ip_to_use"
        #},
    },
    "REDIS": {
        "port": 6379,
        "server": "127.0.0.1",
        "password": {
            "common_config": "redis_password"
        }
    }
}

contrail_snmp_collector_conf = {
    "DEFAULTS": {
        "log_file": "/var/log/contrail/contrail-snmp-collector.log",
        "log_local": 1,
        "log_level": "SYS_NOTICE",
        #"log_category": "*",
        "scan_frequency": {
            "common_config": "snmp_scan_frequency"
        },
        "fast_scan_frequency": {
            "common_config": "snmp_fast_scan_frequency"
        },
        "http_server_port": 5920,
        "zookeeper": {
            "calculated_config": "zk_ip_port_list_to_use"
        }
    },
    "DISCOVERY": {
        "disc_server_ip": {
            "calculated_config": "discovery_ip_to_use"
        },
        "disc_server_port": 5998
    }
}

contrail_snmp_collector_ini = {
    "program:contrail-snmp-collector": {
        "command": "/usr/bin/contrail-snmp-collector --conf_file /etc/contrail/contrail-snmp-collector.conf --conf_file /etc/contrail/contrail-keystone-auth.conf",
        "priority": 340,
        "autostart": "true",
        "killasgroup": "true",
        "stopsignal": "KILL",
        "stdout_capture_maxbytes": "1MB",
        "redirect_stderr": "true",
        "stdout_logfile": "/var/log/contrail/contrail-snmp-collector-stdout.log",
        "stderr_logfile": "/var/log/contrail/contrail-snmp-collector-stderr.log",
        "startsecs": 5,
        "exitcodes": 0,
        "user": "contrail"
    }
}

contrail_analytics_nodemgr_conf = {
    "DISCOVERY": {
        "server": {
            "calculated_config": "config_ip_to_use"
        },
        "port": 5998
    },
    #"COLLECTOR": {
        #"server_list": {
            #"calculated_config": "collector_ip_port_list"
        #}
    #}
}

contrail_alarm_gen_conf = {
    "DEFAULTS": {
        "http_server_port": 5995,
        #"log_file": "/var/log/contrail/contrail-alarm-gen.log",
        #"log_local": 1,
        #"log_level": "SYS_NOTICE",
        #"log_category": "*",
        "kafka_broker_list": {
            "calculated_config": "kafka_broker_list"
        },
        "zk_list": {
            "calculated_config": "zk_ip_port_list_to_use"
        }
    },
    "DISCOVERY": {
        "disc_server_ip": {
            "calculated_config": "config_ip_to_use"
        },
        "disc_server_port": 5998
    }
}

contrail_topology_conf = {
    "DEFAULTS": {
        #"log_file": "/var/log/contrail/contrail-topology.log",
        #"log_local": 1,
        #"log_level": "SYS_NOTICE",
        #"log_category": "*",
        "scan_frequency": "60",
        #"http_server_port": 5921,
        "zookeeper": {
            "calculated_config": "zk_ip_port_list_to_use"
        }
    }
}
"""
redis_conf = {
    "daemonize": "yes",
    "pidfile": "/var/run/redis/redis-server.pid",
    "port": 6379,
    "timeout": 0,
    "tcp-keepalive": 0,
    "loglevel": "notice",
    "logfile": "/var/log/redis/redis-server.log",
    "databases": 16,
    "stop-writes-on-bgsave-error": "yes",
    "rdbcompression": "yes",
    "rdbchecksum": "yes",
    "dir": "/var/lib/redis",
    "slave-serve-stale-data": "yes",
    "repl-disable-tcp-nodelay": "no",
    "requirepass": {
        "common_config": "redis_password"
    },
    "appendonly": "no",
    "appendfilename": "appendonly.aof",
    "appendfsync": "everysec",
    "no-appendfsync-on-rewrite": "no",
    "auto-aof-rewrite-percentage": 100,
    "auto-aof-rewrite-min-size": "64mb",
    "lua-time-limit": 5000,
    "slowlog-max-len": 128,
    "slowlog-log-slower-than": 10000,
    "notify-keyspace-events": "",
    "hash-max-ziplist-entries": 512,
    "hash-max-ziplist-value": 64,
    "list-max-ziplist-entries": 512,
    "list-max-ziplist-value": 64,
    "set-max-ziplist-entries": 512,
    "zset-max-ziplist-entries": 128,
    "zset-max-ziplist-value": 64,
    "activerehashing": "yes"
    "client-output-buffer-limit": {
        "normal": "0 0 0",
        "slave": "256mb 64mb 60",
        "pubsub": "32mb 8mb 60"
    }

}

"""
