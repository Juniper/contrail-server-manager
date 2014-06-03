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


plib = distutils.sysconfig.get_python_lib()
mod_path="%s/cobbler" % plib
sys.path.insert(0, mod_path)

#[root@a3s17 modules]# more /var/log/cobbler/install.log
#system  a3s10   10.84.16.3      stop    1401606565.15

_DEF_SMGR_PORT=9001

def register():
    # trigger type
    return "/var/lib/cobbler/triggers/install/post/*"


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
    ip = socket.gethostbyname(socket.gethostname())
    object = 'status'
    url_str = object + "?" + "server_id=" + name
    payload = 'reimage'
    send_REST_request(ip, '9001', url_str, payload)
    fd = open("/var/log/cobbler/install.log","a+")
    fd.write("%s\t%s\t%s\tstop\t%s\n" % (objtype,name,ip,time.time()))
    fd.write("url:%s, payload:%s\n" % (url_str, payload))
    fd.close()
    return 0
