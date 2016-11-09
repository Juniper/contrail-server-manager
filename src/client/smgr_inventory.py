#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_inventory.py
   Author : Nitish Krishna
   Description : TBD
"""

import os
import syslog
import time
import signal
from StringIO import StringIO
import sys
import re
import abc
import datetime
import subprocess
import cStringIO
import pycurl
import json
import xmltodict
import pdb

# Class ServerMgrInventory describes the API layer exposed to ServerManager to allow it to query
# the device inventory information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Node that hosts the relevant DB and Cache.
class ServerMgrInventory():

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the ServerManager node
    def send_REST_request(self, server_ip, port):
        try:
            response = StringIO()
            url = "http://%s:%s/%s" % (server_ip, port, 'InventoryInfo')
            headers = ["Content-Type:application/json"]
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, str(url))
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(conn.WRITEFUNCTION, response.write)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.perform()
            data_dict = response.getvalue()
            data_dict = dict(json.loads(data_dict))
            data_list = list(data_dict["__ServerInventoryInfoUve_list"]["ServerInventoryInfoUve"])
            return data_list
        except Exception as e:
            print "Inventory Error is: " + str(e)
            return None

    # end def send_REST_request

    # Filters the data returned from REST API call for requested information


    def show_inv_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'InventoryInfo'
        if args.server_id:
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif args.cluster_id:
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif args.tag:
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif args.where:
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        rest_api_params['select'] = None
        return rest_api_params
    # end def show_inv_details
