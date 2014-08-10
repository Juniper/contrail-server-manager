#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4

import os
import json

_DEF_SMGR_PORT = 9001
_DEF_SMGR_CFG_FILE = os.path.dirname(__file__) + "/sm-client-config.ini"

def print_rest_response(resp):
    if resp:
        try:
            resp_str = json.loads(resp)
            resp = json.dumps(resp_str, sort_keys=True, indent=4)
        except ValueError:
            pass
    print resp

#end print_rest_resp
