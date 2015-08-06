#
# Copyright (c) 2013 Juniper Networks, Inc. All rights reserved.
#

from setuptools import setup
import setuptools

setup(
    name='contrail-server-manager',
    version='0.1dev',
    packages=setuptools.find_packages(exclude=["*.pyc"]),
    zip_safe=False,
    long_description="Server Manager package",
)
