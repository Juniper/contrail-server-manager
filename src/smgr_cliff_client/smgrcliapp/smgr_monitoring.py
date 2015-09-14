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

    def show_mon_details(self, args):
        rest_api_params = {}
        rest_api_params['object'] = 'MonitorInfo'
        rest_api_params['select'] = getattr(args, 'select', None)
        if getattr(args, "server_id", None):
            rest_api_params['match_key'] = 'id'
            rest_api_params['match_value'] = args.server_id
        elif getattr(args, "cluster_id", None):
            rest_api_params['match_key'] = 'cluster_id'
            rest_api_params['match_value'] = args.cluster_id
        elif getattr(args, "tag", None):
            rest_api_params['match_key'] = 'tag'
            rest_api_params['match_value'] = args.tag
        elif getattr(args, "where", None):
            rest_api_params['match_key'] = 'where'
            rest_api_params['match_value'] = args.where
        else:
            rest_api_params['match_key'] = None
            rest_api_params['match_value'] = None
        return rest_api_params
    # end def show_mon_details


