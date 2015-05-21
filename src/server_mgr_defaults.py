

#validation DS
server_fields = {
    "match_keys": "['id', 'mac_address', 'cluster_id', 'ip_address', 'tag', 'where']",
    "obj_name": "server",
    "primary_keys": "['id', 'mac_address']",
    "id": "",
    "host_name": "",
    "mac_address": "",
    "ip_address": "",
    "parameters": """{
                    'interface_name': '',
                    'partition': ''
                    }""",
    "roles": [],
    "cluster_id": "",
    "subnet_mask": "",
    "gateway": "",
    "network": {},
    "contrail": {},
    "top_of_rack" : {},
    "password": "",
    "domain": "",
    "email": "",
    "ipmi_username": "",
    "ipmi_type": "",
    "ipmi_password": "",
    "control_data_network": "",
    "bond_interface": "",
    "ipmi_address": "",
    "tag": None,
    "base_image_id": "",
    "package_image_id": ""
}

cluster_fields = {
    "match_keys": "['id', 'where']",
    "obj_name": "cluster",
    "id": "",
    "email": "",
    "primary_keys": "['id']",
    "base_image_id": "",
    "package_image_id": "",
    "parameters": """{
                'router_asn': '64512',
                'database_dir': '/home/cassandra',
                'database_token': '0',
                'openstack_mgmt_ip': '',
                'use_certificates': 'False',
                'multi_tenancy': 'True',
                'encapsulation_priority': 'MPLSoUDP,MPLSoGRE,VXLAN',
                'keystone_username': 'admin',
                'keystone_password': 'c0ntrail123',
                'keystone_tenant': 'admin',
                'analytics_data_ttl': '168',
                'haproxy': 'disable',
                'subnet_mask': '255.255.255.0',
                'gateway': '10.204.221.46',
                'password': 'c0ntrail123',
                'external_bgp': '',
                'domain': 'contrail.juniper.net'
                }"""
}

image_fields = {
    "match_keys": "['id', 'where']",
    "obj_name": "image",
    "primary_keys": "['id']",
    "id": "",
    "category": "",
    "type": "",
    "version": "",
    "path": "",
    "parameters": """{
                "kickstart": "",
                "kickseed":""
                }"""
}

fru_fields = {
    "id": "",
    "fru_description": "",
    "board_serial_number": "",
    "chassis_type": "",
    "chassis_serial_number": "",
    "board_mfg_date": "",
    "board_manufacturer": "",
    "board_product_name": "",
    "board_part_number": "",
    "product_manfacturer": "",
    "product_name": "",
    "product_part_number": ""
}

email_events = ["reimage_started", "reimage_completed", "provision_completed"]
server_blocked_fields = ["ssh_private_key"]

