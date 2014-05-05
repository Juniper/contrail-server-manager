#!/usr/bin/env python

from setuptools import setup

setup(name = "server-manager-client",
      version = "1.0",
      author = "Prasad Miriyala",
      author_email = "pmiriyala@juniper.net",
      description = ("Server Manager Client and contrail lab utilities"),
      packages=['server_manager', 'server_manager.client', 'server_manager.contrail'],
      package_data={'server-manager': ['client/*.ini', 'client/*.json', 'contrail/*.xml']},
      scripts=['server_manager/client/server-manager', 'server_manager/contrail/reimage']
)
