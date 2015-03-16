import os
import time
import signal
import sys
import datetime
import syslog
import subprocess
import re
import socket
import pdb
import re
import ast
from StringIO import StringIO
import paramiko
from os import chmod
from server_mgr_db import ServerMgrDb as db

DEF_SERVER_DB_LOCATION = "/etc/contrail_smgr/smgr_data.db"


class ServerMgrSSHClient():

    _serverDb = None
    _key_folder = None
    _ssh_client = None

    def __init__(self, serverdb=None, log_file=None):
        if serverdb:
            self._serverDb = serverdb
        else:
            self._serverDb = db(DEF_SERVER_DB_LOCATION)

    def connect(self, ip, option="key"):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            match_dict = dict()
            match_dict["ip_address"] = ip
            server = self._serverDb.get_server(match_dict, detail=True)
            if len(server) == 1:
                server = server[0]
                if "ssh_private_key" in server and option == "key":
                    key = str(server["ssh_private_key"])
                    private_key = StringIO(key)
                    pkey = paramiko.RSAKey.from_private_key(private_key)
                    ssh.connect(ip, username='root', pkey=pkey, timeout=3)
                elif "password" in server and option == "password":
                    root_pwd = server["password"]
                    ssh.connect(ip, username='root', password=root_pwd, timeout=3)
            self._ssh_client = ssh
        except Exception as e:
            raise e
        return ssh

    def copy(self, source, dest):
        try:
            sftp = self._ssh_client.open_sftp()
            sftp.put(source, dest)
            sftp.close()
        except Exception as e:
            raise e
        return 1

    def exec_command(self, cmd):
        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(cmd)
            if stdout.channel.recv_exit_status() is 1 or stdout.channel.recv_exit_status() is 127:
                return None
            filestr = stdout.read()
            if not filestr:
                return None
            else:
                return filestr
        except Exception as e:
            raise e

    def close(self):
        self._ssh_client.close()