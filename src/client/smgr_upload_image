#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_upload_image.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   upload an image to server manager database. When image is
   uploaded corresponding entries for distro and profile for the
   image are also created in cobbler.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import json

_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 9001


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]

    # Process the arguments
    parser = argparse.ArgumentParser(
        description='''Create a Server Manager object''',
    )
    parser.add_argument("--smgr_ip", "-i",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port", "-p",
                        help="server manager listening port number")
    parser.add_argument("image_id",
                        help="Name of the new image")
    parser.add_argument("image_version",
                        help="version number of the image")
    parser.add_argument(
        "image_type",
        help="type of the image (fedora/centos/ubuntu/contrail-ubuntu-repo)")
    parser.add_argument("file_name",
                        help="complete path for the file")
    args = parser.parse_args()
    return args


def send_REST_request(ip, port, payload, file_name):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/image/upload" %(
            ip, port)
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.POST, 1)
        #conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
        conn.setopt(pycurl.HTTPPOST, payload)
        #conn.setopt(pycurl.HTTPPOST, [("file_name", (pycurl.FORM_FILE, file_name))])
        conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None

def upload_image(args_str=None):
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }
    args = parse_arguments(args_str)
    if args.smgr_ip:
        serverMgrCfg['smgr_ip_addr'] = args.smgr_ip
    if args.smgr_port:
        serverMgrCfg['smgr_port'] = args.smgr_port
    image_id = args.image_id
    image_version = args.image_version
    image_type = args.image_type
    payload = {
        'image_id' : image_id,
        'image_version' : image_version,
        'image_type' : image_type
    }
    file_name = args.file_name
    
    resp = send_REST_request(serverMgrCfg['smgr_ip_addr'],
                      serverMgrCfg['smgr_port'],
                      payload, file_name)
    print resp
# End of upload_image

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    upload_image(sys.argv[1:])
# End if __name__
