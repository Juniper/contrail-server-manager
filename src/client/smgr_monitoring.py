#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_monitoring.py
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
import pdb


# Class ServerMgrIPMIQuerying describes the API layer exposed to ServerManager to allow it to query
# the device environment information of the servers stored in its DB. The information is gathered through
# REST API calls to the Server Mgr Analytics Node that hosts the relevant DB.
class ServerMgrIPMIQuerying():
    _query_engine_port = 8107

    def __init__(self):
        ''' Constructor '''

    # Packages and sends a REST API call to the Server Manager node
    def send_REST_request(self, server_ip, port):
        try:
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = "http://%s:%s/%s" % (server_ip, port, 'MonitorInfo')
            args_str = ''
            conn = pycurl.Curl()
            conn.setopt(pycurl.URL, url)
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(pycurl.HTTPGET, 1)
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.perform()
            data_dict = response.getvalue()
            data_dict = dict(json.loads(data_dict))
            data_list = list(data_dict["__ServerMonitoringInfoTrace_list"]["ServerMonitoringInfoTrace"])
            return data_list
        except Exception as e:
            print "Error is: " + str(e)
            return None
    # end def send_REST_request

    def show_mon_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'MonitorInfo'
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
    # end def show_mon_details


