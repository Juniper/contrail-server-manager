#!/usr/bin/python

"""
   Name : create_smgr_db.py
   Author : rishiv@juniper.net
   Description : This program is a simple cli interface to
   create server manager database with objects.
   Objects can be vns, cluster, server, or image.
   Takes  -t testbed.py or/and --vns_id <vns_id> as command line input
"""


import pdb
import subprocess
import json
import string
import textwrap
import tempfile
import os
import re
import fabric
import ConfigParser
import argparse
import sys
from datetime import datetime as dt
from os.path import expanduser
from smgr_add import get_default_object as get_default_object
import smgr_client_def
import imp

def svrmgr_add_all():
    verify_user_input()
    create_json()
    add_vns()
    add_image()
    add_pkg()
    add_server()


def create_json():
    modify_server_json()
    modify_vns_json()


def modify_server_json():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None
    if not params.has_key('server_file'):
        return None
    server_file = params['server_file']

    timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    subprocess.call( 'cp %s %s.org.%s' %(server_file, server_file, timestamp), shell = True )

    in_file = open( server_file, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    update_roles_from_testbed_py(server_dict)

    out_file = open(server_file, 'w')
    out_data = json.dumps(server_dict, indent=4)
    out_file.write(out_data)
    out_file.close()

    return server_dict


def update_roles_from_testbed_py(server_dict):
    testbed = get_testbed()
    if not testbed.env.has_key('roledefs'):
        return server_dict
    for  node in server_dict['server']:
      roles = []
      for key in testbed.env.roledefs:
        if key == 'all' or key == 'build' :
          continue
        for  host_string in testbed.env.roledefs[key]:
          ip = getIp(host_string)
          if node['ip'] == ip:
            if key == 'cfgm':
                roles.append("config")
            else:
                roles.append(key)
      if not len(roles):
        node['roles'] = [ "compute" ]            
      else:
        node['roles'] =  roles 
      
    for  node in server_dict['server']:
       node['vns_id'] =  get_pref_vns_id()

    return server_dict
# end update_roles_from_testbed_py


def getIp(string) :
   regEx = re.compile( '\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}' )
   result = regEx.search(string)

   if result:
     return result.group()
   else:
     return  None

# end getIp()

def get_image_id() :
    params=read_ini_file(sys.argv[1:])
    image_file = params['image_file']

    image_file = open( image_file, 'r' )
    image_data = image_file.read()
    image_json = json.loads(image_data)
    image_id = image_json['image'][0]['image_id']
    image_file.close()
    return image_id

# end get_image_id()


def get_pkg_id() :
    params=read_ini_file(sys.argv[1:])
    pkg_file = params['pkg_file']

    pkg_file = open( pkg_file, 'r' )
    pkg_data = pkg_file.read()
    pkg_json = json.loads(pkg_data)
    pkg_id = pkg_json['image'][0]['image_id']
    pkg_file.close()
    return pkg_id

# end get_pkg_id()


def get_vns_id() :
    params=read_ini_file(sys.argv[1:])
    vns_file = params['vns_file']

    vns_file = open( vns_file, 'r' )
    vns_data = vns_file.read()
    vns_json = json.loads(vns_data)
    vns_id = vns_json['vns'][0]['vns_id']
    vns_file.close()
    return vns_id

# end get_vns_id()


def add_vns():
    vns_file = None
    params=read_ini_file(sys.argv[1:])
    if params:
        try:
            vns_file = params['vns_file']
        except KeyError:
            pass

    vns_id = get_pref_vns_id()
    if not vns_file:
        vns_dict = get_vns_with_vns_id_from_db()
        if not len(vns_dict['vns']):
            vns_dict = new_vns()
        else:
            vns_dict = {
                          "vns" : [
                              {
                                  "vns_id" : "",
                                  "vns_params" : {
    
                                      }
                              }
                          ]
                       }

        vns_dict['vns'][0]['vns_id'] = vns_id
        modify_vns_from_testbed_py(vns_dict)
        temp_dir= expanduser("~")
        vns_file = '%s/vns.json' %temp_dir
        subprocess.call('touch %s' %vns_file, shell = True)
        out_file = open(vns_file, 'w')
        out_data = json.dumps(vns_dict, indent=4)
        out_file.write(out_data)
        out_file.close()
    else :
        timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        subprocess.call( 'cp %s %s.org.%s' %(vns_file, vns_file, timestamp), shell=True )
        subprocess.call("sed -i 's/\"vns_id\".*,/\"vns_id\":\"%s\",/'  %s" %(vns_id,vns_file), shell=True )
        subprocess.call("sed -i 's/\"vns_id\".*/\"vns_id\":\"%s\"/'  %s" %(vns_id,vns_file), shell=True )

    subprocess.call('server-manager add  vns -f %s' %(vns_file), shell=True )

# end add_vns()

def add_server():
    add_server_using_json()
    update_server_in_db_with_testbed_py()

def add_image():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None
    if not params.has_key('image_file'):
        return None
    image_file = params['image_file']

    subprocess.call('server-manager add  image -f %s' %(image_file), shell=True )
    subprocess.call('server-manager show all ', shell=True)

def add_pkg():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None
    if not params.has_key('pkg_file'):
        return None
    pkg_file = params['pkg_file']

    subprocess.call('server-manager add  image -f %s' %(pkg_file), shell=True )
    subprocess.call('server-manager show image ', shell=True)


def add_server_using_json():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None

    if not params.has_key('server_file'):
        return None
    server_file = params['server_file']

    subprocess.call('server-manager add  server -f %s' %(server_file), shell=True )
    subprocess.call('server-manager show server ', shell=True)



def modify_vns_json():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None
    if not params.has_key('vns_file'):
        return None
    vns_file = params['vns_file']

    timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    subprocess.call( 'cp %s %s.org.%s' %(vns_file, vns_file, timestamp), shell=True )

    in_file = open( vns_file, 'r' )
    in_data = in_file.read()
    vns_dict = json.loads(in_data)

    modify_vns_from_testbed_py(vns_dict)

    out_file = open(vns_file, 'w')
    out_data = json.dumps(vns_dict, indent=4)
    out_file.write(out_data)
    out_file.close()


def modify_vns_from_testbed_py(vns_dict):
    testbed = get_testbed()
    if testbed.env.has_key('mail_to'):
        vns_dict['vns'][0]['email'] = testbed.env.mail_to
    if testbed.env.has_key('encap_priority'):
        vns_dict['vns'][0]['vns_params']['encap_priority'] = testbed.env.encap_priority
    if 'multi_tenancy' in dir(testbed):
        vns_dict['vns'][0]['vns_params']['multi_tenancy'] = testbed.multi_tenancy
    if 'os_username' in dir(testbed):
        vns_dict['vns'][0]['vns_params']['ks_user'] = testbed.os_username
    if 'os_password' in dir(testbed):
        vns_dict['vns'][0]['vns_params']['ks_passwd'] = testbed.os_password
    if 'os_tenant_name' in dir(testbed):
        vns_dict['vns'][0]['vns_params']['ks_tenant'] = testbed.os_tenant_name
    if 'router_asn' in dir(testbed):
        vns_dict['vns'][0]['vns_params']['router_asn'] = testbed.router_asn
        


def new_vns():
    params=read_ini_file(sys.argv[1:])
    vns_id = get_user_vns_id()
    if not vns_id:
        vns_id = params['vns_id']
    vns_dict = {
                  "vns" : [
                      {
                          "vns_id" : vns_id,
                          "vns_params" : {
                              "router_asn": "64512",
                              "database_dir": "/home/cassandra",
                              "db_initial_token": "",
                              "openstack_mgmt_ip": "",
                              "use_certs": "False",
                              "multi_tenancy": "False",
                              "encap_priority": "'MPLSoUDP','MPLSoGRE','VXLAN'",
                              "service_token": "contrail123",
                              "ks_user": "admin",
                              "ks_passwd": "contrail123",
                              "ks_tenant": "admin",
                              "openstack_passwd": "contrail123",
                              "analytics_data_ttl": "168",
                              "mask": "255.255.255.0",
                              "gway": "1.1.1.254",
                              "passwd": "c0ntrail123",
                              "domain": "contrail.juniper.net",
                              "haproxy": "disable"
                              }
                          }
                      ]
                  }
    config = ConfigParser.SafeConfigParser()
    config.read([smgr_client_def._DEF_SMGR_CFG_FILE])
    default_config_object = get_default_object("vns", config)
    vns_params_dict = dict(vns_dict["vns"][0]["vns_params"].items() + default_config_object["vns_params"].items())
    tmp_vns_dict = dict(vns_dict["vns"][0].items() + default_config_object.items())
    tmp_vns_dict["vns_params"] = vns_params_dict
    vns_dict["vns"][0] = tmp_vns_dict
    return vns_dict

# End new_vns()


def parse_arguments(args_str=None):
    parser = argparse.ArgumentParser(
            description='''Server Manager Tool to generate json from testbed.py'''
    )
    #group1 = parser.add_mutually_exclusive_group()

    parser.add_argument("--config_file", "-c",
                        help="Server manager client config file ")
    parser.add_argument("--vns_id", "-v",
                        help="user specified preferred vns_id ")
    parser.add_argument("--testbed_py", "-t",
                        help="your testbed.py file")

    args = parser.parse_args(args_str)
    return args

# End parse_arguments

def read_ini_file(args_str=None):
    args = parse_arguments(args_str)
    if args.config_file:
        config_file = args.config_file
    try:
        config = ConfigParser.SafeConfigParser()
        config.read([config_file])
        smgr_config = dict(config.items("SERVER-MANAGER"))
        return smgr_config

    except:
        # ini file not mandatory input
        return None

    return smgr_config

# End read_ini_file

def get_testbed_py(args_str=None):
    args = parse_arguments(args_str)
    testbed_py = None
    if args.testbed_py:
        testbed_py = args.testbed_py

    return testbed_py

# End read_ini_file


def get_user_vns_id(args_str=None):
    args = parse_arguments(args_str)
    vns_id = None
    if args.vns_id:
        vns_id = args.vns_id
    return vns_id


def get_server_with_vns_id_from_db():
    vns_id = get_pref_vns_id()

    temp_dir= expanduser("~")
    file_name = '%s/server_with_vns_id_from_db.json' %(temp_dir)
    subprocess.call('server-manager show --detail server --vns_id %s \
                 | tr -d "\n" \
                 | sed "s/[^{]*//" \
                 > %s' %(vns_id, file_name), shell=True )


    in_file = open( file_name, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    return server_dict

def get_vns_with_vns_id_from_db():
    vns_id = get_user_vns_id()
    if not vns_id:
        params=read_ini_file(sys.argv[1:])
        vns_id = params['vns_id']

    vns_dict = {"vns": []}
 
    temp_dir= expanduser("~")

    file_name = '%s/vns.json' %(temp_dir)

    subprocess.call('server-manager show --detail vns --vns_id %s \
                 | tr -d "\n" \
                 | sed "s/[^{]*//" \
                 > %s' %(vns_id, file_name), shell=True )

    in_file = open( file_name, 'r' )
    in_data = in_file.read()

    vns_dict = json.loads(in_data)

    return vns_dict


def get_server_with_ip_from_db(ip=None):
    params=read_ini_file(sys.argv[1:])
  
    server_dict={}
    if not ip:
        print "Please provide an ip as input arg"
        return ip

    temp_dir= expanduser("~")

    file_name = '%s/server.json' %(temp_dir)

    subprocess.call('server-manager show --detail server --ip %s \
                 | tr -d "\n" \
                 | sed "s/[^{]*//" \
                 > %s' %(ip, file_name), shell=True )


    in_file = open( file_name, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    return server_dict

def get_host_roles_from_testbed_py():
    testbed = get_testbed()
    node = {}
    if not testbed.env.has_key('roledefs'):
        return node
    for key in testbed.env.roledefs:
        if key == 'all' or key == 'build':
            continue
        for  host_string in testbed.env.roledefs[key]:
            ip = getIp(host_string)
            if not node.has_key(ip):
                node[ip] = []
            if key == 'cfgm':
                node[ip].append('config')
            else:
                node[ip].append(key)
    return node
# end get_host_roles_from_testbed_py


def update_server_in_db_with_testbed_py():
    vns_id = get_pref_vns_id()  
    node = get_host_roles_from_testbed_py()
    if not node:
        return
    u_server_dict = {}
    u_server_dict['server'] = []
    for key in node:
        server_dict = {}
        server_dict = get_server_with_ip_from_db(key)
        if not server_dict or not server_dict['server']:
            print ("ERROR: Server with ip %s not present in Server Manager" % key)
            continue
        server_id = server_dict['server'][0]['server_id']
        u_server = {}
        u_server['server_id'] = server_id
        u_server['vns_id'] = vns_id
        u_server['roles'] = node[key]
        u_server_dict['server'].append(u_server)
    
    temp_dir= expanduser("~")
    server_file = '%s/server.json' %temp_dir
    subprocess.call('touch %s' %server_file, shell=True)
    out_file = open(server_file, 'w')
    out_data = json.dumps(u_server_dict, indent=4)
    out_file.write(out_data)
    out_file.close()

    subprocess.call('server-manager add  server -f %s' %(server_file), shell=True )
    for u_server in u_server_dict['server']:
        subprocess.call('server-manager show --detail server --server_id %s' \
                  % u_server['server_id'], shell=True )
#End  update_server_in_db_with_vns_id


def get_pref_vns_id():
    vns_id = get_user_vns_id()
    if not vns_id:
        params=read_ini_file(sys.argv[1:])
        vns_id = params['vns_id']
    return vns_id

def verify_user_input():
    params=read_ini_file(sys.argv[1:])
    vns_id = get_user_vns_id()

    if not params and not vns_id:
        sys.exit(" User should either provide --vns_id or config.ini ")

def get_testbed():
    filepath = get_testbed_py(sys.argv[1:])
    if not filepath:
        sys.exit("tesbed.py missing in commandline args  ")
    mod_name,file_ext = os.path.splitext(os.path.split(filepath)[-1])

    if file_ext.lower() == '.py':
        py_mod = imp.load_source(mod_name, filepath)

    return py_mod


if __name__ == "__main__" :
    import cgitb
    cgitb.enable(format='text')
    svrmgr_add_all()
    



