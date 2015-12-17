#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_certs.py
   Author : Prasad Miriyala
   Description : server manager certs
"""
from server_mgr_cert_utils import *

__version__ = '1.0'

_DEF_CERT_LOCATION = '/etc/contrail_smgr/puppet/ssl/'
_DEF_CERT_LOG = '/var/log/contrail-server-manager/smgrcerts.log'

class ServerMgrCerts():
    def __init__(self, cert_location=_DEF_CERT_LOCATION, log_file=_DEF_CERT_LOG,
                 log_level = logging.DEBUG,
                 db=None):
        Cmd.local_exec('mkdir -p %s' % (cert_location), error_on_fail=True)
        self._smgr_cert_location = cert_location
        self._smgr_ca_private_key = None
        self._smgr_ca_cert = None
        CertsLogger.initialize_logger(log_file=log_file,
                            log_level=log_level)

    def create_sm_ca_cert(self, force=False):
        sm_ca_private_key = self._smgr_cert_location + 'ca-cert-privkey.pem'
        sm_ca_cert = self._smgr_cert_location + 'ca-cert.pem'
        if not force and os.path.isfile(sm_ca_private_key) and os.path.isfile(sm_ca_cert):
            self._smgr_ca_private_key = sm_ca_private_key
            self._smgr_ca_cert = sm_ca_cert
            return sm_ca_private_key, sm_ca_cert
        Cert.generate_private_key(sm_ca_private_key, force=force)
        self._smgr_ca_private_key = sm_ca_private_key
        exit_code, fqdn, _ = Cmd.local_exec('hostname -f')
        subject = '/CN=' + fqdn 
        Cert.generate_cert(sm_ca_cert, sm_ca_private_key, self_signed=True, subj=subject, force=force)
        self._smgr_ca_cert = sm_ca_cert
        return sm_ca_private_key, sm_ca_cert

    def create_server_cert(self, server, force=False):
        server_private_key = self._smgr_cert_location + server['id'] + '-privkey.pem'
        server_csr = self._smgr_cert_location + server['id'] + '.csr'
        server_pem = self._smgr_cert_location + server['id'] + '.pem'
        if not force and os.path.isfile(server_private_key) and os.path.isfile(server_pem):
            return server_private_key, server_csr, server_pem
        subject = '/CN=' + server['id']
        Cert.generate_private_key(server_private_key, force=force)
        Cert.generate_csr(server_csr, server_private_key, subj=subject, force=force)
        Cert.generate_cert(server_pem, self._smgr_ca_private_key, root_pem=self._smgr_ca_cert,
                           csr=server_csr, force=force)
        return server_private_key, server_csr, server_pem

    def delete_server_cert(self, server):
        server_private_key = self._smgr_cert_location + server['id'] + '-privkey.pem'
        server_csr = self._smgr_cert_location + server['id'] + '.csr'
        server_pem = self._smgr_cert_location + server['id'] + '.pem'
        if os.path.isfile(server_private_key):
            os.remove(server_private_key)
        if os.path.isfile(server_csr):
            os.remove(server_csr)
        if os.path.isfile(server_pem):
            os.remove(server_pem)


if __name__ == '__main__':
    # test cases
    sm_certs = ServerMgrCerts(os.path.expanduser('./'), 
                              os.path.expanduser('./smgrcerts.log'))
    sm_private_key, sm_cert = sm_certs.create_sm_ca_cert()
    server = {'id':'server1'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server)
    server = {'id':'server2'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server, force=True)
    sm_private_key, sm_cert = sm_certs.create_sm_ca_cert(force=True)
    server = {'id':'server1'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server, force=True)
    server = {'id':'server2'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server, force=True)
    server = {'id':'server1'}
    sm_certs.delete_server_cert(server)
    server = {'id':'server2'}
    sm_certs.delete_server_cert(server)
    server = {'id':'server1'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server)
    server = {'id':'server2'}
    server_private_key, _, server_cert = sm_certs.create_server_cert(server)



