

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

email_events = ["reimage_started", "reimage_completed", "provision_completed"]
server_blocked_fields = ["ssh_private_key"]

