#!/usr/bin/env python
import shutil
from setuptools import setup
from setuptools.command.install import install as _install
import os
import shutil
import glob

class install(_install):
    def run(self):
        _install.run(self)
        try:
            import server_manager.client
            import server_manager.contrail
            client_dir = os.path.dirname(server_manager.client.__file__)
            json_files = client_dir+'/*.json'
            json_list = glob.glob(json_files)
            dst_location = '/etc/contrail_smgr'
            if not os.path.exists(dst_location):
                os.makedirs(dst_location)
            print ("Coping to %s") % (dst_location)
            for jfile in json_list:
                shutil.copy(jfile, dst_location)
                print jfile
            ini_files = client_dir+'/*.ini'
            ini_list = glob.glob(ini_files)
            for ifile in ini_list:
                shutil.copy(ifile, dst_location)
                print ifile
            contrail_dir = os.path.dirname(server_manager.contrail.__file__)
            xml_files = contrail_dir+'/*.xml'
            xml_list = glob.glob(xml_files)
            for xmlfile in xml_list:
                shutil.copy(xmlfile, dst_location)
                print xmlfile
        except:
            print "Post installation failed"


setup(name = "server-manager-client",
      cmdclass={'install': install},
      version = "1.0",
      author = "Prasad Miriyala",
      author_email = "pmiriyala@juniper.net",
      description = ("Server Manager Client and contrail lab utilities"),
      include_package_data=True,
      packages=['server_manager', 'server_manager.client', 'server_manager.contrail'],
      package_data={'': ['*.ini', 'server_manager/client/*.json', '*.xml']},
      scripts=['server_manager/client/server-manager'],
      #install_requires=['pycurl',],
)
