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
import logging
from cliff.command import Command


class UploadImage(Command):
    log = logging.getLogger(__name__)
    command_dictionary = {}
    smgr_ip = None
    smgr_port = None

    def get_command_options(self):
        return self.command_dictionary

    def get_description(self):
        return "Delete a Server Manager object"

    def get_parser(self, prog_name):
        parser = super(UploadImage, self).get_parser(prog_name)
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
        self.command_dictionary["upload-image"] = ['image_id', 'image_version', 'image_type', 'file_name', 'kickstart',
                                                   'kickseed']
        for key in self.command_dictionary:
            new_dict = dict()
            new_dict[key] = [str("--" + s) for s in self.command_dictionary[key] if len(s) > 1]
            new_dict[key] += [str("-" + s) for s in self.command_dictionary[key] if len(s) == 1]
            new_dict[key] += ['-h', '--help']
            self.command_dictionary[key] = new_dict[key]

        return parser

    def take_action(self, parsed_args):
        try:
            self.smgr_ip = self.smgr_port = None
            smgr_dict = self.app.get_smgr_config()

            if smgr_dict["smgr_ip"]:
                self.smgr_ip = smgr_dict["smgr_ip"]
            else:
                self.app.report_missing_config("smgr_ip")
            if smgr_dict["smgr_port"]:
                self.smgr_port = smgr_dict["smgr_port"]
            else:
                self.app.report_missing_config("smgr_port")
        except Exception as e:
            sys.exit("Exception: %s : Error getting smgr config" % e.message)

        image_id = getattr(parsed_args, "image_id", None)
        image_version = getattr(parsed_args, "image_version", None)
        image_type = getattr(parsed_args, "image_type", None)
        kickstart = kickseed = ''
        if getattr(parsed_args, "kickstart", None):
            kickstart = getattr(parsed_args, "kickstart", None)
        # end args.kickstart
        if getattr(parsed_args, "kickseed", None):
            kickseed = getattr(parsed_args, "kickseed", None)
        # end args.kickseed
        file_name = getattr(parsed_args, "file_name", None)
        payload = dict()
        payload['id'] = image_id
        payload['version'] = image_version
        payload['type'] = image_type
        payload["file"] = (pycurl.FORM_FILE, file_name)
        if kickstart:
            payload["kickstart"] = (pycurl.FORM_FILE, kickstart)
        if kickseed:
            payload["kickseed"] = (pycurl.FORM_FILE, kickseed)

        if image_id:
            resp = self.app.send_REST_request(self.smgr_ip, self.smgr_port, obj="image/upload",
                                              payload=payload,
                                              method="PUT")
            smgr_client_def.print_rest_response(resp)
            self.app.stdout.write("\n" + str(smgr_client_def.print_rest_response(resp)) + "\n")
