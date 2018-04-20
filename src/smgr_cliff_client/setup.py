#!/usr/bin/env python

PROJECT = 'servermanagercli'

def get_version():
    version = None
    with open('version.txt') as f:
        version = f.read()
        version = version.strip()
    if version:
        return version
    else:
        return "1.0"

CONTRAIL_VERSION = get_version()

VERSION = CONTRAIL_VERSION.replace('-','.')

import setuptools
import ConfigParser

install_reqs = []

for line in open('requirements.txt', 'r'):
    if not str(line.strip()).startswith("#"):
        install_reqs.append(line.strip())

reqs = install_reqs
config = ConfigParser.ConfigParser()
config.read('setup.cfg')

config_dict = dict(config._sections)
for k in config_dict:
    config_dict[k] = dict(config._defaults, **config_dict[k])
    config_dict[k].pop('__name__', None)

console_script_list = [str(x) for x in (config_dict['entry_points']['console_scripts']).splitlines() if x and x[0] != "#"]
entry_points_dict = dict()
entry_points_dict['console_scripts'] = console_script_list

entry_points = [key for key in (config_dict['entry_points']) if key != "console_scripts"]
for entry_point in entry_points:
    command_list = [str(x) for x in (config_dict['entry_points'][str(entry_point)]).splitlines() if x and x[0] != "#"]
    entry_points_dict[str(entry_point)] = command_list


setuptools.setup(
    name=PROJECT,
    version=VERSION,
    setup_requires=['configparser'],
    description='Server Manager Command Line Interface',
    package_data={'': ['*.ini', '*.txt', '*.sh']},
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=reqs,
    platforms=['Any'],
    entry_points=entry_points_dict,
    scripts=['setup_server_manager_client.sh'],
    data_files=[
        ('/tmp', ['smgrcliapp/sm-client-config.ini']),
        ('/tmp', ['servermanagerclient'])
    ],
    zip_safe=False)
