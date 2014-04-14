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

_DEF_SMGR_PORT = 9001
_DEF_SMGR_CFG_FILE = "/etc/contrail_smgr/smgr_client_config.ini"


def parse_arguments(args_str=None):
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''upload image to server manager DB'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''upload image to server manager DB''',
            prog="server-manager uplaod_image"
        )
    # end else
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--ip_port", "-i",
                        help=("ip addr & port of server manager "
                              "<ip-addr>[:<port>] format, default port "
                              " 9001"))
    group1.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              _DEF_SMGR_CFG_FILE)))
    parser.add_argument("image_id",
                        help="Name of the new image")
    parser.add_argument("image_version",
                        help="version number of the image")
    parser.add_argument(
        "image_type",
        help="type of the image (fedora/centos/ubuntu/contrail-ubuntu-repo)")
    parser.add_argument("file_name",
                        help="complete path for the file")
    args = parser.parse_args(args_str)
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
    args = parse_arguments(args_str)
    if args.ip_port:
        smgr_ip, smgr_port = args.ip_port.split(":")
        if not smgr_port:
            smgr_port = _DEF_SMGR_PORT
    else:
        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        # end args.config_file
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not smgr_ip:
                sys.exit(("listen_ip_addr missing in config file"
                          "%s" %config_file))
            smgr_port = smgr_config.get("listen_port", _DEF_SMGR_PORT)
        except:
            sys.exit("Error reading config file %s" %config_file)
        # end except
    # end else args.ip_port
    image_id = args.image_id
    image_version = args.image_version
    image_type = args.image_type
    payload = {
        'image_id' : image_id,
        'image_version' : image_version,
        'image_type' : image_type
    }
    file_name = args.file_name
    
    resp = send_REST_request(smgr_ip, smgr_port,
                      payload, file_name)
    print resp
# End of upload_image

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    upload_image(sys.argv[1:])
# End if __name__
