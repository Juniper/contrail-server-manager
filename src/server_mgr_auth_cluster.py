#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_auth_cluster.py
   Author : Nitish Krishna
   Description : This file contains code that copies the SSH public key of the Server Manager node into the
                 servers that come under the control of Server Manager. This is done to allow Server Manager keyless
                 access when it uses its private key
"""

import sys
from gevent import monkey
import paramiko
monkey.patch_all(thread=not 'unittest' in sys.modules)
from server_mgr_db import ServerMgrDb as Db
from gevent import monkey
monkey.patch_all()
import gevent


_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_DB_FILE = _DEF_SMGR_BASE_DIR + 'smgr_data.db'
_DEF_KEY_PATH = '/root/.ssh/server_mgr_rsa.pub'


class AuthCluster():

    def __init__(self):
        self._serverDb = None
        self._keyFile = None

    def connect_to_db(self, db_path):
        self._serverDb = Db(db_path)

    def set_key_to_copy(self, key_file):
        self._keyFile = key_file

    def gevent_runner_func(self, ip, username, password):
        try:
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username="root", password=password)
            sftp = client.open_sftp()
            sftp.put(self._keyFile, "/root/.ssh/authorized_keys")
            sftp.close()
            client.close()
        except Exception as e:
            # Set up log to log the errors
            pass

    def copy_key_to_cluster(self):

        servers = self._serverDb.get_server({None: None}, detail=True)
        gevent_threads = []
        for server in servers:
            ip_address = server['ip_address']
            root_pwd = server['password']
            thread = gevent.spawn(self.gevent_runner_func, ip_address, "root", root_pwd)
            gevent_threads.append(thread)


def main(args=None):
    auth_obj = AuthCluster()
    db_path = None
    key_file = None
    if args:
        db_path = args[0]
        key_file = args[0]
    elif sys.argv[1] == "--dbpath" and sys.argv[2]:
        db_path = sys.argv[2]
    elif sys.argv[3] == "--keyfile" and sys.argv[4]:
        key_file = sys.argv[4]
    else:
        db_path = _DEF_SMGR_DB_FILE
        key_file = _DEF_KEY_PATH
    auth_obj.connect_to_db(db_path)
    auth_obj.set_key_to_copy(key_file)
    auth_obj.copy_key_to_cluster()

if __name__ == "__main__":
    main()
# End if __name__