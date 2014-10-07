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
import ConfigParser
import smgr_client_def


def parse_arguments(args_str=None):
    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''upload image to server manager DB'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''upload image to server manager DB''',
            prog="server-manager upload_image"
        )
    # end else
    parser.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    parser.add_argument("image_id",
                        help="Name of the new image")
    parser.add_argument("image_version",
                        help="version number of the image")
    parser.add_argument(
        "image_type",
        help=("type of the image (fedora/centos/ubuntu/"
              "contrail-ubuntu-package/contrail-centos-package/contrail-storage-ubuntu-package)"))
    parser.add_argument("file_name",
                        help="complete path for the file")
    parser.add_argument("--kickstart", "-ks",
                        help="kickstart filename for base image")
    parser.add_argument("--kickseed", "-kseed",
                        help="kickseed filename for base image, applies"
                        " only to ubuntu based base images and ignored for other image types")
    args = parser.parse_args(args_str)
    return args


def send_REST_request(ip, port, payload, file_name,
                      kickstart='', kickseed=''):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/image/upload" %(
            ip, port)
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.POST, 1)
        payload["file"] = (pycurl.FORM_FILE, file_name)
        if kickstart:
            payload["kickstart"] = (pycurl.FORM_FILE, kickstart)
        if kickseed:
            payload["kickseed"] = (pycurl.FORM_FILE, kickseed)
        conn.setopt(pycurl.HTTPPOST, payload.items())
        conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None

def upload_image(args_str=None):
    args = parse_arguments(args_str)
    if args.config_file:
        config_file = args.config_file
    else:
        config_file = smgr_client_def._DEF_SMGR_CFG_FILE
    # end args.config_file
    try:
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        smgr_config = dict(config.items("SERVER-MANAGER"))
        smgr_ip = smgr_config.get("listen_ip_addr", None)
        if not smgr_ip:
            sys.exit(("listen_ip_addr missing in config file"
                      "%s" %config_file))
        smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
    except:
        sys.exit("Error reading config file %s" %config_file)
    # end except
    image_id = args.image_id
    image_version = args.image_version
    image_type = args.image_type
    kickstart = kickseed = ''
    if args.kickstart:
        kickstart = args.kickstart
    # end args.kickstart
    if args.kickseed:
        kickseed = args.kickseed
    # end args.kickseed

    payload = {
        'id' : image_id,
        'version' : image_version,
        'type' : image_type
    }
    file_name = args.file_name
    
    resp = send_REST_request(smgr_ip, smgr_port,
                      payload, file_name, 
                      kickstart, kickseed)
    print resp
# End of upload_image

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    upload_image(sys.argv[1:])
# End if __name__
