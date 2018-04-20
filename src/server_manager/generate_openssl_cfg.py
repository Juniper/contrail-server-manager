#!/usr/bin/python
#
# Copyright (c) 2016 Juniper Networks, Inc. All rights reserved.
#
import string
import sys
import platform
import os
import pdb
import ast
import uuid
import subprocess
from netaddr import *
from server_mgr_err import *
from server_mgr_utils import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

_DEF_OPENSSL_CFG_FILE = '/etc/pki/tls/openssl.cnf'

openssl_template = string.Template("""
[ new_oids ]
[ ca ]
default_ca              = CA_default
[ CA_default ]
dir             = ./demoCA              # Where everything is kept
certs           = $dir/certs            # Where the issued certs are kept
crl_dir         = $dir/crl              # Where the issued crl are kept
database        = $dir/index.txt        # database index file.
new_certs_dir   = $dir/newcerts         # default place for new certs.
certificate     = $dir/cacert.pem       # The CA certificate
serial          = $dir/serial           # The current serial number
crlnumber       = $dir/crlnumber        # the current crl number
crl             = $dir/crl.pem          # The current CRL
private_key     = $dir/private/cakey.pem# The private key
RANDFILE        = $dir/private/.rand    # private random number file
x509_extensions = usr_cert              # The extentions to add to the cert
default_days    = 365                   # how long to certify for
default_crl_days= 30                    # how long before next CRL
default_md      = default                  # which md to use.
preserve        = no                    # keep passed DN ordering
policy          = policy_match
[ policy_match ]
countryName                     = match
stateOrProvinceName             = match
organizationName                = match
organizationalUnitName          = optional
commonName                      = supplied
emailAddress                    = optional
[ policy_anything ]
countryName                     = optional
stateOrProvinceName             = optional
localityName                    = optional
organizationName                = optional
organizationalUnitName          = optional
commonName                      = supplied
emailAddress                    = optional
[ req ]
default_bits                    = 1024
default_keyfile                 = privkey.pem
distinguished_name              = req_distinguished_name
attributes                      = req_attributes
x509_extensions = v3_ca # The extentions to add to the self signed cert
req_extensions = v3_req
[ req_distinguished_name ]
countryName                             = Country Name (2 letter code)
countryName_min                         = 2
countryName_max                         = 2
stateOrProvinceName                     = State or Province Name (full name)
localityName                            = Locality Name (eg, city)
0.organizationName                      = Organization Name (eg, company)
commonName                              = Common Name (eg, YOUR name)
#Default certificate generation filelds
organizationalUnitName_default          = Juniper Contrail
0.organizationName_default              = OpenContrail
stateOrProvinceName_default             = California
localityName_default                    = Sunnyvale
countryName_default                     = US
commonName_default                      = $__COMMON_NAME__
commonName_max                          = 64
emailAddress                            = Email Address
emailAddress_max                        = 40
[ v3_req ]
basicConstraints = CA:true
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
[alt_names]
$__DNS_DOMAIN_STANZA__
$__SAN_IPS_STANZA__
[ req_attributes ]
challengePassword                       = A challenge password
challengePassword_min                   = 4
challengePassword_max                   = 20
unstructuredName                        = An optional company name
[ usr_cert ]
basicConstraints=CA:FALSE
nsComment                       = "OpenSSL Generated Certificate"
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer:always
[ v3_ca]
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer:always
basicConstraints = CA:true
[ crl_ext ]
authorityKeyIdentifier=keyid:always,issuer:always
""")

class OpensslConfigGenerator:

    def __init__(self, server_config, cluster_config):
        ''' Constructor '''
        self._server_config = server_config
        self._cluster_config = cluster_config
        self._openssl_cfg_location = _DEF_OPENSSL_CFG_FILE

    def get_vips_in_cluster(self,cluster):
        cluster_params = eval(cluster['parameters'])
        cluster_provision_params = cluster_params.get("provision", {})
        internal_vip = ""
        external_vip = ""
        if cluster_provision_params:
            openstack_params = cluster_provision_params.get("openstack", {})
            ha_params = openstack_params.get("ha", {})
            internal_vip = ha_params.get('internal_vip', None)
            external_vip = ha_params.get('external_vip', None)
        return (internal_vip, external_vip)

    def calculate_san_ip_stanza(self):
        san_ips_stanza = ""
        san_ips_list = []
        list_of_interfaces = eval(str(self._server_config["network"]))["interfaces"]
        for intf_config in list_of_interfaces:
            if isinstance(intf_config,dict) and "ip_address" in intf_config and\
              intf_config["ip_address"] and len(intf_config["ip_address"]):
                san_ips_list.append(intf_config["ip_address"].split('/')[0])

        cluster_id = str(self._server_config['cluster_id'])
        roles = eval(str(self._server_config['roles']))
        if cluster_id != "" and 'openstack' in roles:
            # get vip ip-addresses from cluster
            int_vip, ext_vip = self.get_vips_in_cluster(self._cluster_config)
            print int_vip, ext_vip
            if int_vip:
                san_ips_list.append(str(int_vip))
            if ext_vip:
                san_ips_list.append(str(ext_vip))

        for idx,val in enumerate(san_ips_list):
            san_ip_line = "IP."+str(idx+1) + " = " + str(val)
            san_ips_stanza += san_ip_line + "\n"

        return san_ips_stanza

    def calculate_dns_stanza(self, hostname, domain):
        dns_stanza = ""
        dns_stanza+="DNS.1 = " + str(hostname) + "\n"
        dns_stanza+="DNS.2 = " + str(hostname) + "." + str(domain) + "\n"
        return dns_stanza

    def generate_openssl_config(self):
        try:
            openssl_cfg_content = openssl_template.safe_substitute({
                '__COMMON_NAME__' : str(self._server_config["host_name"]),
                '__DNS_DOMAIN_STANZA__': self.calculate_dns_stanza(
                    str(self._server_config["host_name"]), str(self._server_config["domain"])),
                '__SAN_IPS_STANZA__' : self.calculate_san_ip_stanza()
            })

            self._openssl_cfg_location = "/etc/contrail_smgr/" + \
                    str(self._server_config["host_name"]) + "_openssl.cnf"
            openssl_cfg_file = open(self._openssl_cfg_location, 'w+')
            openssl_cfg_file.write(openssl_cfg_content)
            openssl_cfg_file.close()

        except Exception as e:
            raise e

    def get_openssl_cfg_location(self):
        return self._openssl_cfg_location
