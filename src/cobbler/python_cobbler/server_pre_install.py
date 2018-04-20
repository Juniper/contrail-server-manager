"""
"""

import distutils.sysconfig
import sys
import os
from utils import _
import traceback
import cexceptions
import os
import sys
import time
import pycurl
from StringIO import StringIO
import json
import socket
import urllib
import ConfigParser

plib = distutils.sysconfig.get_python_lib()
mod_path="%s/cobbler" % plib
sys.path.insert(0, mod_path)

#[root@a3s17 modules]# more /var/log/cobbler/install.log
#system  a3s10   10.84.16.3      start    1401606565.15

_DEF_SMGR_CONFIG_FILE = '/opt/contrail/server_manager/sm-config.ini'
_DEF_SMGR_STATUS_PORT = 9002

def register():
    # trigger type
    return "/var/lib/cobbler/triggers/install/pre/*"


def send_REST_request(ip, port, object, payload):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" %(
            ip, port, object)
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.POST, 1)
        conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
        conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None


def run(api, args, logger):
    objtype = args[0] # "system" or "profile"
    name    = args[1] # name of system or profile
    server_ip      = args[2] # ip or "?"
    # get server manager ip
    try:
        config = ConfigParser.SafeConfigParser()
        config.read(_DEF_SMGR_CONFIG_FILE)
        ip = dict(config.items("SERVER-MANAGER"))['listen_ip_addr']
    except:
        ip = socket.gethostbyname(socket.gethostname())
    object = 'server_status'
    url_str = object + "?" + "server_id=" + name + "&state=reimage_started"
    payload = 'reimage start'
    send_REST_request(ip, str(_DEF_SMGR_STATUS_PORT), url_str, payload)
    fd = open("/var/log/cobbler/contrail_install.log","a+")
    fd.write("\n%s\t%s\t%s\tstart\t%s\n" % (objtype,name,ip,time.asctime(time.localtime(time.time()))))
    fd.write("url:%s, payload:%s\n" % (url_str, payload))
    fd.close()
    return 0
