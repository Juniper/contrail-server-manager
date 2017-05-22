#!/usr/bin/python

import re
import subprocess
from server_mgr_defaults import *
# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_utils.py
   Author : Abhay Joshi
   Description : generic utility functions for server manager code.
"""
__version__ = '1.0'

from copy import deepcopy

class ServerMgrUtil():
    def convert_unicode():
        def convert_unicode(input):
            if isinstance(input, dict):
                return {convert_unicode(key): convert_unicode(value) for key, value in input.iteritems()}
            elif isinstance(input, list):
                return [convert_unicode(element) for element in input]
            elif isinstance(input, unicode):
                return input.encode('utf-8')
            else:
                return input
        # end convert_unicode(input)
        return convert_unicode
    convert_unicode = staticmethod(convert_unicode())

    # local function to return the output of executing a shell command
    def command_output(self, cmd):
        try:
            result = subprocess.check_output(cmd, shell = True).strip()
        except subprocess.CalledProcessError as e:
            result = None
        return result

    # this function returns the package type given the image
    def get_tgz_package_type(self,img_path):
       base_cmd = "tar -tzf " +img_path +" " + "--wildcards "
       cmd = base_cmd + "'contrail-puppet*'"
       if self.command_output(cmd) is not None:
         return "contrail-install-tgz"
       cmd = base_cmd + "'contrail-networking-docker*'"
       if self.command_output(cmd) is not None:
         return "contrail-cloud-docker-tgz"
       cmd = base_cmd + "'contrail-networking-dependents*'"
       if self.command_output(cmd) is not None:
         return "contrail-networking-docker-tgz"
       return None

    def get_package_version(self,package, image_type):
        if (image_type == "contrail-ubuntu-package" or image_type == "contrail-storage-ubuntu-package"):
            version = subprocess.check_output(['dpkg-deb', '-f',str(package),'Version'])
        elif (image_type == "contrail-centos-package"):
            cmd = "rpm -qp --qf \"%{V}\" " + str(package)
            ver = subprocess.check_output(cmd, shell = True).strip()
            cmd = "rpm -qp --qf \"%{R}\" " + str(package)
            release = subprocess.check_output(cmd, shell = True).strip()
            version = ver + "-"+ release.split('.')[0]
        return version

    def calculate_kernel_upgrade(self,server_config,contrail_package_params):
        dbutils = DbUtils()
        server_contrail_4 = dbutils.get_contrail_4(server_config)
        if not isinstance(server_config["parameters"],dict):
            server_config["parameters"] = eval(server_config["parameters"])
        if "provision" not in server_config["parameters"]:
            server_config["parameters"]["provision"] = {}
        if "contrail" not in server_config["parameters"].get("provision",{}):
            server_config["parameters"]["provision"]["contrail"] = {}

        if "kernel_upgrade" in server_contrail_4 and server_contrail_4["kernel_upgrade"]:
            server_config["parameters"]["provision"]["contrail"]["kernel_upgrade"] = server_contrail_4["kernel_upgrade"]
            if "kernel_version" in server_contrail_4 and server_contrail_4["kernel_version"]:
                server_config["parameters"]["provision"]["contrail"]["kernel_version"] = server_contrail_4["kernel_version"]
            else:
                if "14.0" in contrail_package_params["contrail"]["package_sku"]:
                    server_config["parameters"]["provision"]["contrail_4"]["kernel_version"] = default_kernel_xenial
                    server_config["parameters"]["provision"]["contrail"]["kernel_version"] = default_kernel_xenial
                else:
                    server_config["parameters"]["provision"]["contrail_4"]["kernel_version"] = default_kernel_trusty
                    server_config["parameters"]["provision"]["contrail"]["kernel_version"] = default_kernel_trusty
        return server_config

class DbUtils():
    def get_contrail_4(self,parent):
        params     = parent.get("parameters", {})
        if isinstance(params, unicode):
            pparams = eval(params)
            prov    = pparams.get("provision", {})
        else:
            prov       = params.get("provision", {})
        return prov.get("contrail_4", {})


class DictUtils():
    def merge_dict():
        def merge_dict(a, b):
            if isinstance(b, dict) and isinstance(a, dict):
                a_b_intersection = a.viewkeys() & b.viewkeys()
                a_b_all  = a.viewkeys() | b.viewkeys()
                return {k: merge_dict(a[k], b[k]) if k in a_b_intersection else 
                        deepcopy(a[k] if k in a else b[k]) for k in a_b_all}
            return deepcopy(b)
        return merge_dict
    merge_dict = staticmethod(merge_dict())

    def remove_none_from_dict():
        def remove_none_from_dict(a):
            if isinstance(a, dict):
                a_keys = a.viewkeys()
                return {k: remove_none_from_dict(a[k]) for k in a_keys if a[k] is not None}
            if a == '""':
                a = ''
            return a
        return remove_none_from_dict
    remove_none_from_dict = staticmethod(remove_none_from_dict())

if __name__ == '__main__':
    # test code
    print ServerMgrUtil.convert_unicode(u'this is converted unicode string')
    sm = ServerMgrUtil()
    print sm.get_package_version('/root/contrail-install-packages-3.0-2712~juno.el7.centos.noarch.rpm')
