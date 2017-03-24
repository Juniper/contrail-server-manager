import os
import sys
import pycurl
import ConfigParser
import subprocess
import json
from StringIO import StringIO

SM_STATUS_PORT = "9002"
STATUS_VALID = "parameters_valid"
STATUS_IN_PROGRESS = "provision_in_progress"
STATUS_SUCCESS = "provision_completed"
STATUS_FAILED  = "provision_failed"


# Role strings
CONTROLLER_CONTAINER  = "contrail-controller"
ANALYTICS_CONTAINER   = "contrail-analytics"
ANALYTICSDB_CONTAINER = "contrail-analyticsdb"
AGENT_CONTAINER       = "contrail-agent"
LB_CONTAINER          = "contrail-lb"
BARE_METAL_COMPUTE    = "contrail-compute"

# Add new roles and corresponding container_name here
_container_names = { CONTROLLER_CONTAINER  : 'controller',
                     ANALYTICS_CONTAINER   : 'analytics',
                     ANALYTICSDB_CONTAINER : 'analyticsdb',
                     LB_CONTAINER          : 'lb',
                     AGENT_CONTAINER       : 'agent',
                     BARE_METAL_COMPUTE    : 'agent' }
_valid_roles = _container_names.keys()

_inventory_group = { CONTROLLER_CONTAINER  : "contrail-controllers",
                     ANALYTICS_CONTAINER   : "contrail-analytics",
                     ANALYTICSDB_CONTAINER : "contrail-analyticsdb",
                     LB_CONTAINER          : "contrail-lb",
                     AGENT_CONTAINER       : "contrail-compute",
                     BARE_METAL_COMPUTE    : "contrail-compute" }

_container_img_keys = { CONTROLLER_CONTAINER  : "controller_image",
                        ANALYTICS_CONTAINER   : "analytics_image",
                        ANALYTICSDB_CONTAINER : "analyticsdb_image",
                        LB_CONTAINER          : "lb_image",
                        AGENT_CONTAINER       : "agent_image" }

def send_REST_request(ip, port, endpoint, payload,
                      method='POST', urlencode=False):
    try:
        response = StringIO()
        headers = ["Content-Type:application/json"]
        url = "http://%s:%s/%s" %(ip, port, endpoint)
        conn = pycurl.Curl()
        if method == "PUT":
            conn.setopt(pycurl.CUSTOMREQUEST, method)
            if urlencode == False:
                first = True
                for k,v in payload.iteritems():
                    if first:
                        url = url + '?'
                        first = False
                    else:
                        url = url + '&'
                    url = url + ("%s=%s" % (k,v))
            else:
                url = url + '?' + payload
        print "Sending post request to %s" % url
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        conn.setopt(pycurl.POST, 1)
        if urlencode == False:
            conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None

def create_inv_file(fname, dictionary):
    with open(fname, 'w') as invfile:
        for key, value in dictionary.items():
            if isinstance(value, str):
                invfile.write(key)
                invfile.write('\n')
                invfile.write(value)
                invfile.write('\n')
                invfile.write('\n')
            if isinstance(value, list):
                invfile.write(key)
                invfile.write('\n')
                for item in value:
                    invfile.write(item)
                    invfile.write('\n')
                invfile.write('\n')
            if isinstance(value, dict):
                invfile.write(key)
                invfile.write('\n')
                for k, v in value.items():
                    if isinstance(v, str) or isinstance(v, bool):
                        invfile.write(k+"=")
                        invfile.write(str(v))
                        invfile.write('\n')
                        invfile.write('\n')
                    if isinstance(v, list) or isinstance(v, dict):
                        invfile.write(k+"=")
                        invfile.write(str(v))
                        invfile.write('\n')
                        invfile.write('\n')


'''
SM Lite + Ansible Provision related functions
'''

def ansible_verify_provision_complete(smlite_server, smlite_non_mgmt_ip):
    try:
        cmd = ("lsmod | grep vrouter")
        output = subprocess.check_output(cmd, shell=True)
        if "vrouter" not in output:
            return False
        cmd = ("ifconfig vhost0 | grep %s" %(smlite_non_mgmt_ip))
        output = subprocess.check_output(cmd, shell=True)
        if str(smlite_non_mgmt_ip) not in output:
            return False
        return True
    except subprocess.CalledProcessError as e:
        raise e
    except Exception as e:
        raise e

'''
Recursively process the dictionary and create the INI format file
'''
def create_sections(config, dictionary, section=None):
    for key, value in dictionary.items():
        if isinstance(value, dict):
            create_sections(config, dictionary=value,
                                   section=key)
        else:
            try:
                config.set(section, key, value)
            except ConfigParser.NoSectionError:
                try:
                    config.add_section(section)
                    config.set(section, key, value)
                except ConfigParser.DuplicateSectionError:
                    print "Ignore DuplicateSectionError"

            except TypeError:
                try:
                    config.add_section(section)
                except ConfigParser.DuplicateSectionError:
                    print "ignore Duplicate Sections"


def create_conf_file(ini_file, dictionary={}):
    if not ini_file:
        return
    config = ConfigParser.SafeConfigParser()
    create_sections(config, dictionary)
    with open(ini_file, 'w') as configfile:
        config.write(configfile)

def update_inv_file(ini_file, section, dictionary={}):
    if not ini_file:
        return
    config = ConfigParser.SafeConfigParser()
    create_sections(config, dictionary)
    with open(ini_file, 'a') as configfile:
        config.write(configfile)




