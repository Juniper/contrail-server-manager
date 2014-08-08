

#validation DS
server_fields = {
    "match_keys": "['server_id', 'mac', 'cluster_id', 'rack_id', 'pod_id', 'vns_id', 'ip']",
    "obj_name": "server",
    "primary_keys": "['server_id', 'mac']",
    "server_id": "",
    "mac": "",
    "ip": "",
    "server_params": """{
                    'compute_non_mgmt_ip': '',
                    'compute_non_mgmt_gway': ''
                    }""",
    "roles": ["config","openstack","control","compute","collector","webui","database"],
    "cluster_id": "",
    "vns_id": "",
    "mask": "",
    "gway": "",
    "passwd": "",
    "domain": "",
    "email": "",
    "power_user": "",
    "power_type": "",
    "power_pass": "",
    "control": "",
    "bond": "",
    "power_address": "",
    "tag": ""
}

vns_fields = {
    "match_keys": "['vns_id']",
    "obj_name": "vns",
    "vns_id": "",
    "email": "",
    "primary_keys": "['vns_id']",
    "vns_params": """{
                'router_asn': '64512',
                'database_dir': '/home/cassandra',
                'db_initial_token': '',
                'openstack_mgmt_ip': '',
                'use_certs': 'False',
                'multi_tenancy': 'False',
                'encap_priority': 'MPLSoUDP,MPLSoGRE,VXLAN',
                'service_token': 'contrail123',
                'ks_user': 'admin',
                'ks_passwd': 'contrail123',
                'ks_tenant': 'admin',
                'openstack_passwd': 'contrail123',
                'analytics_data_ttl': '168',
                'compute_non_mgmt_ip': '',
                'compute_non_mgmt_gway': '',
                'haproxy': 'disable',
                'mask': '255.255.255.0',
                'gway': '10.204.221.46',
                'passwd': 'c0ntrail123',
                'ext_bgp': '',
                'domain': 'contrail.juniper.net'
                }"""
}

cluster_fields = {
    "match_keys": "['cluster_id']",
    "obj_name": "cluster",
    "primary_keys": "['cluster_id']",
    "cluster_id": ""
}

image_fields = {
    "match_keys": "['image_id']",
    "obj_name": "image",
    "primary_keys": "['image_id']",
    "image_id": "",
    "image_type": "",
    "image_version": "",
    "image_path": ""
}

