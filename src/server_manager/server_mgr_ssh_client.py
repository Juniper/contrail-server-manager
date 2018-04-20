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
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_utils import *

DEF_SERVER_DB_LOCATION = "/etc/contrail_smgr/smgr_data.db"


class ServerMgrSSHClient(object):

    _serverDb = None
    _key_folder = None
    _ssh_client = None

    def __init__(self, serverdb=None, log_file=None):
        if serverdb:
            self._serverDb = serverdb
        else:
            self._serverDb = db(DEF_SERVER_DB_LOCATION)

        self._smgr_log = ServerMgrlogger()

    def connect(self, ip, server_id, option="key"):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            match_dict = dict()
            match_dict["id"] = server_id
            smutil = ServerMgrUtil()
            server = self._serverDb.get_server(match_dict, detail=True)
            password = smutil.get_password(server[0],self._serverDb)
            if len(server) == 1:
                server = server[0]
                if "ssh_private_key" in server and option == "key" and server["ssh_private_key"]:
                    key = str(server["ssh_private_key"])
                    private_key = StringIO(key)
                    pkey = paramiko.RSAKey.from_private_key(private_key)
                    ssh.connect(ip, username='root', pkey=pkey, timeout=30)
                elif option == "password" and password is not None:
                    root_pwd = password
                    ssh.connect(ip, username='root', password=root_pwd, timeout=30)
            self._ssh_client = ssh

        except Exception as e:
            msg = "CONNECT FAILED: Host => %s, option => %s, ERROR => %s" % (ip, option, str(e))
            self._smgr_log.log(self._smgr_log.INFO, msg)
            ssh.close()
            raise e

        msg = "CONNECT SUCCESS: Host => %s, option => %s" % (ip, option)
        self._smgr_log.log(self._smgr_log.INFO, msg)
        return ssh

    def copy(self, source, dest):
        try:
            sftp = self._ssh_client.open_sftp()
            sftp_attr = sftp.put(source, dest)
            bytes_sent = sftp_attr.st_size
            sftp.close()
        except Exception as e:
            if sftp:
                sftp.close()
            raise e
        return bytes_sent

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
        if self._ssh_client:
            self._ssh_client.close()

