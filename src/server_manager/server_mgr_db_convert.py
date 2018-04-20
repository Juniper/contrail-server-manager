#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_db_convert.py
   Author : Abhay Joshi
   Description : This file contains code that provides REST api interface to
                 configure, get and manage configurations for servers which
                 are part of the contrail cluster of nodes, interacting
                 together to provide a scalable virtual network system.
"""
import os
import sys
import re
import datetime
import json
import argparse
from gevent import monkey
monkey.patch_all(thread=not 'unittest' in sys.modules)
import subprocess
import ConfigParser
import paramiko
import base64
import shutil
import string
import tarfile
from urlparse import urlparse, parse_qs
from time import gmtime, strftime, localtime
import pdb
import server_mgr_db
import ast
import uuid
import traceback
import platform
import copy
import distutils.core
from server_mgr_db import ServerMgrDb as db
import pycurl
import json
import xmltodict
from StringIO import StringIO
import requests
import tempfile
from gevent import monkey

monkey.patch_all()

_DEF_SMGR_DB_LOCATION = '/etc/contrail_smgr/smgr_data.db'
_DEF_TRANS_DICT_LOCATION = '/opt/contrail/server_manager/client/parameter-translation-dict.json'
_DEF_UPGRADE_TRANS_DICT_LOCATION = '/opt/contrail/server_manager/client/upgrade-parameter-translation-dict.json'
class DatabaseConvert():
    def __init__(self, args_str=None):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "-t", "--translation_dict_location",
            help=(
                "The location of the Parameter Translation Dictionary,"
                " default /opt/contrail/server_manager/client/parameter-translation-dict.json"))
        parser.add_argument(
            "-ut", "--upgrade_translation_dict_location",
            help=(
                "The location of the Upgrade Parameter Translation Dictionary,"
                " default /opt/contrail/server_manager/client/upgrade-parameter-translation-dict.json"))
        parser.add_argument(
            "-d", "--db_location",
            help=(
                "The location of the Server Manager Database to convert,"
                " default /etc/contrail_smgr/smgr_data.db"))
        serverMgrCfg = { 'db_location': _DEF_SMGR_DB_LOCATION, 'translation_dict_location': _DEF_TRANS_DICT_LOCATION,
            'upgrade_translation_dict_location': _DEF_UPGRADE_TRANS_DICT_LOCATION }
        parser.set_defaults(**serverMgrCfg)
        self._args = None
        self._args = parser.parse_args(args_str)
        try:
            self._serverDb = db(self._args.db_location)
        except Exception as e:
            print "Cannot find DB at: " + str(self._args.db_location)
            print "Error: " + str(e)
            exit()
        self.translation_dict = {}
        self.upgrade_translation_dict = {}
        try:
            with open(str(self._args.translation_dict_location)) as json_file:
                self.translation_dict = json.load(json_file)
            self.old_to_new_dict = self._trans_dict_convert(self.translation_dict)
        except Exception as e:
            print "Cannot find translation dictionary at: " + str(self._args.translation_dict_location)
            print "Error: " + str(e)
            exit()
        try:
            with open(str(self._args.upgrade_translation_dict_location)) as json_file:
                self.upgrade_translation_dict = json.load(json_file)
            self.upgrade_dict = self._upgrade_trans_dict_convert(self.upgrade_translation_dict)
        except Exception as e:
            print "Cannot find translation dictionary at: " + str(self._args.translation_dict_location)
            print "Error: " + str(e)
            exit()

    def _trans_dict_convert(self, trans_dict):
        old_to_new_dict = {}
        for key in trans_dict:
            old_to_new_dict[str(trans_dict[key]["oldname"])] = str(trans_dict[key]["newname"])
        return old_to_new_dict

    def _upgrade_trans_dict_convert(self, trans_dict):
        upgrade_dict = {}
        for key in trans_dict:
            upgrade_dict[str(trans_dict[key]["oldname"])] = str(trans_dict[key]["newname"])
        return upgrade_dict

    def _find_key_in_dict(self, dict_to_search, search_key):
        if search_key in dict_to_search.keys():
            return dict_to_search
        else:
            for key in dict_to_search.keys():
                if isinstance(dict_to_search[key], dict):
                    dict_found = self._find_key_in_dict(dict_to_search[key], search_key)
                    if dict_found:
                        return dict_found
            return None

    def _set_key_in_dict(self, dict_to_set, key_to_set, value):
        key_to_set_list = key_to_set.split('.')
        last_level = key_to_set_list[-1]
        key_set = 0
        iter_list = iter(key_to_set_list)
        key_to_set = next(iter_list)
        while not key_set:
            if key_to_set in dict_to_set.keys():
                if key_to_set == str(last_level):
                    dict_to_set[key_to_set] = value
                    key_set = 1
                else:
                    dict_to_set = dict_to_set[key_to_set]
                    key_to_set = next(iter_list)
            else:
                if key_to_set == str(last_level):
                    dict_to_set[key_to_set] = value
                    key_set = 1
                else:
                    dict_to_set[key_to_set] = {}
                    dict_to_set = dict_to_set[key_to_set]
                    key_to_set = next(iter_list)


    def old_to_new_convert(self, cluster_id, cluster_params):
        if not cluster_id or not cluster_params:
            raise ValueError('Invalid cluster_id and or cluster_params')
        discard_key_list = []
        new_cluster_params = {}
        if "provision" not in cluster_params:
            for old_key in cluster_params:
                if old_key in self.old_to_new_dict:
                    new_key = self.old_to_new_dict[str(old_key)]
                    split_dest_v_name = new_key.split('.')
                    tmp_dict = new_cluster_params
                    for level in split_dest_v_name[:-1]:
                        if level not in tmp_dict.keys():
                            tmp_dict[str(level)] = {}
                        tmp_dict = tmp_dict[str(level)]
                    tmp_dict[split_dest_v_name[-1]] = cluster_params[old_key]
                    discard_key_list.append(old_key)
            cluster_params['provision'] = new_cluster_params
            for key in discard_key_list:
                cluster_params[key] = None
            modified_cluster = {'id': cluster_id, 'parameters': None}
            modified_cluster = {'id': cluster_id, 'parameters': cluster_params}
            #print "Cluster: " + str(cluster_id) + "  Params: " + str(json.dumps(cluster_params,sort_keys=True,indent=4)) + "\n"
            try:
                self._serverDb.modify_cluster(modified_cluster)
            except Exception as e:
                print "Exception: " + str(e)

    def new_params_upgrade(self, cluster_id, cluster_params):
        if not cluster_id or not cluster_params:
            raise ValueError('Invalid cluster_id and or cluster_params')
        discard_key_list = []
        new_cluster_params = {}
        if "provision" in cluster_params:
            for old_key_name, new_key_name in self.upgrade_dict.iteritems():
                old_key_name = str((old_key_name.split('.'))[-1])
                dict_to_set = self._find_key_in_dict(cluster_params["provision"], old_key_name)
                if dict_to_set:
                    val_to_set = dict_to_set[old_key_name]
                    dict_to_set[old_key_name] = None
                    self._set_key_in_dict(cluster_params["provision"], new_key_name, val_to_set)
            modified_cluster = {'id': cluster_id, 'parameters': None}
            modified_cluster = {'id': cluster_id, 'parameters': cluster_params}
            #print "Cluster: " + str(cluster_id) + "  Params: " + str(json.dumps(cluster_params,sort_keys=True,indent=4)) + "\n"
            try:
                self._serverDb.modify_cluster(modified_cluster)
            except Exception as e:
                print "Exception: " + str(e)

    def convert(self):
        clusters = self._serverDb.get_cluster({},detail=True)
        for cluster in clusters:
            new_cluster_params = {}
            discard_key_list = []
            cluster_params = eval(cluster['parameters'])
            cluster_id = str(cluster['id'])
            if "provision" not in cluster_params:
                self.old_to_new_convert(cluster_id, cluster_params)
            else:
                self.new_params_upgrade(cluster_id, cluster_params)

def main(args_str=None):
    db_convert = DatabaseConvert(args_str)
    db_convert.convert()

# End of main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')
    main()
# End if __name__
