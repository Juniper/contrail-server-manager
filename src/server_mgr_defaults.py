

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
                    'interface_name': ''
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
    "ipmi_address": "",
    "ipmi_interface": "",
    "tag": None,
    "base_image_id": "",
    "ssh_public_key": "",
    "ssh_private_key" : "",
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

dhcp_host_fields = {
    "match_keys": "['host_fqdn']",
    "primary_keys": "['host_fqdn']",
    "obj_name": "dhcp_host",
    "host_fqdn": "",
    "mac_address": "",
    "ip_address": "",
    "host_name": "",
    "parameters": """{
                }"""
}

dhcp_subnet_fields = {
    "match_keys": "['subnet_address']",
    "primary_keys": "['subnet_address']",
    "obj_name": "dhcp_subnet",
    "subnet_address": "",
    "subnet_mask": "",
    "subnet_gateway": "",
    "subnet_domain": "",
    "search_domains_list": [],
    "dns_server_list": [],
    "parameters": """{
                }""",
    "default_lease_time": 21600,
    "max_lease_time": 43200
}

default_kernel_trusty = "3.13.0-106"
default_kernel_xenial = "4.4.0-38"

email_events = ["reimage_started", "reimage_completed", "provision_completed"]
server_blocked_fields = ["ssh_private_key"]
default_global_ansible_config = {
    "ssl_certs_src_dir": "/etc/contrail_smgr/puppet/ssl",
    "tor_ca_cert_file": "/etc/contrail_smgr/puppet/ssl/ca-cert.pem",
    "tor_ssl_certs_src_dir": "/etc/contrail_smgr/puppet/ssl/tor",
    "docker_install_method": "package",
    "docker_package_name": "docker-engine",
    "contrail_compute_mode": "bare_metal",
    "docker_registry_insecure": True,
    "docker_network_bridge": False,
    "enable_lbaas": True
}
