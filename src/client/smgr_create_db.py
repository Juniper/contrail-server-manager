#!/usr/bin/python

"""
   Name : create_smgr_db.py
   Author : rishiv@juniper.net
   Description : This program is a simple cli interface to
   create server manager database with objects.
   Objects can be cluster, server or image.
   Mandatory Parameter : testbed.py
   Optional Parameter : cluster_id
   Optional Parameter : server Manager specific config file
"""


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
    add_cluster()
    add_image()
    add_pkg()
    add_server()


def create_json():
    modify_server_json()
    modify_cluster_json()


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
    update_bond_from_testbed_py(server_dict)
    update_multi_if_from_testbed_py(server_dict)

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
          if node['ip_address'] == ip:
            if key == 'cfgm':
                roles.append("config")
            else:
                roles.append(key)
      if not len(roles):
        node['roles'] = [ "compute" ]            
      else:
        node['roles'] =  roles 
      
    for  node in server_dict['server']:
       node['cluster_id'] =  get_pref_cluster_id()

    return server_dict
# end update_roles_from_testbed_py

def update_bond_from_testbed_py(server_dict):
    testbed = get_testbed()
    if 'control_data' in dir(testbed):
      for  node in server_dict['server']:
        for  key in testbed.bond:
          ip = getIp(key)
          if node['ip_address'] == ip:
              node['parameters']['setup_interface'] = "Yes"
              #node['parameters']['compute_non_mgmt_ip'] = ""
              #node['parameters']['compute_non_mgmt_gw'] = ""

              name = testbed.bond[key]['name']
              mode = testbed.bond[key]['mode']
              member = testbed.bond[key]['member']
              option = {}
              option['miimon'] = '100'
              option['mode'] = mode
              option['xmit_hash_policy'] = 'layer3+4'

              node['bond']={}
              node['bond'][name]={}
              node['bond'][name]['bond_options'] = "%s"%option
              node['bond'][name]['member'] = "%s"%member
    return server_dict
#End update_bond_from_testbed_py(server_dict):


def update_multi_if_from_testbed_py(server_dict):
    testbed = get_testbed()
    if 'control_data' in dir(testbed):
      for  node in server_dict['server']:
        for  key in testbed.control_data:
          ip = getIp(key)
          if node['ip_address'] == ip:
              node['parameters']['setup_interface'] = "Yes"
              #node['parameters']['compute_non_mgmt_ip'] = ""
              #node['parameters']['compute_non_mgmt_gway'] = ""

              ip = testbed.control_data[key]['ip']
              gw = testbed.control_data[key]['gw']
              device = testbed.control_data[key]['device']

              node['control']={}
              node['control'][device] = {}
              node['control'][device]['ip'] = ip
              node['control'][device]['gw'] = gw
    return server_dict
#End update_multi_if_from_testbed_py(server_dict):



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


def get_cluster_id() :
    params=read_ini_file(sys.argv[1:])
    cluster_file = params['cluster_file']

    cluster_file = open( cluster_file, 'r' )
    cluster_data = cluster_file.read()
    cluster_json = json.loads(cluster_data)
    cluster_id = cluster_json['cluster'][0]['id']
    cluster_file.close()
    return cluster_id

# end get_cluster_id()


def add_cluster():
    cluster_file = None
    params=read_ini_file(sys.argv[1:])
    if params:
        try:
            cluster_file = params['cluster_file']
        except KeyError:
            pass

    cluster_id = get_pref_cluster_id()
    if not cluster_file:
        cluster_dict = {}
        cluster_dict = get_cluster_with_cluster_id_from_db()
        if not len(cluster_dict['cluster']):
            cluster_dict = new_cluster()
        else:
            cluster_dict = {
                          "cluster" : [
                              {
                                  "id" : "",
                                  "parameters" : {
    
                                      }
                              }
                          ]
                       }

        cluster_dict['cluster'][0]['id'] = cluster_id
        modify_cluster_from_testbed_py(cluster_dict)
        temp_dir= expanduser("~")
        cluster_file = '%s/cluster.json' %temp_dir
        subprocess.call('touch %s' %cluster_file, shell = True)
        out_file = open(cluster_file, 'w')
        out_data = json.dumps(cluster_dict, indent=4)
        out_file.write(out_data)
        out_file.close()
    else :
        timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
        subprocess.call( 'cp %s %s.org.%s' %(cluster_file, cluster_file, timestamp), shell=True )
        subprocess.call("sed -i 's/\"id\":.*,/\"id\":\"%s\",/'  %s" %(cluster_id,cluster_file), shell=True )

    subprocess.call('server-manager add  cluster -f %s' %(cluster_file), shell=True )

# end add_cluster()

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



def modify_cluster_json():
    params=read_ini_file(sys.argv[1:])
    if not params:
        return None
    if not params.has_key('cluster_file'):
        return None
    cluster_file = params['cluster_file']

    timestamp = dt.now().strftime("%Y_%m_%d_%H_%M_%S")
    subprocess.call( 'cp %s %s.org.%s' %(cluster_file, cluster_file, timestamp), shell=True )

    in_file = open( cluster_file, 'r' )
    in_data = in_file.read()
    cluster_dict = json.loads(in_data)

    modify_cluster_from_testbed_py(cluster_dict)

    out_file = open(cluster_file, 'w')
    out_data = json.dumps(cluster_dict, indent=4)
    out_file.write(out_data)
    out_file.close()


def modify_cluster_from_testbed_py(cluster_dict):
    testbed = get_testbed()
    if testbed.env.has_key('mail_to'):
        cluster_dict['cluster'][0]['email'] = testbed.env.mail_to
    if testbed.env.has_key('encap_priority'):
        cluster_dict['cluster'][0]['parameters']['encapsulation_priority'] = testbed.env.encap_priority
    #if 'multi_tenancy' in dir(testbed):
    #    cluster_dict['cluster'][0]['parameters']['multi_tenancy'] = testbed.multi_tenancy
    if 'multi_tenancy' in dir(testbed):
        if testbed.multi_tenancy == True :
            cluster_dict['cluster'][0]['parameters']['multi_tenancy'] = "True"
        elif testbed.multi_tenancy == False :
            cluster_dict['cluster'][0]['parameters']['multi_tenancy'] = "False"
        else:
            cluster_dict['cluster'][0]['parameters']['multi_tenancy'] = "False"

    if 'os_username' in dir(testbed):
        cluster_dict['cluster'][0]['parameters']['keystone_username'] = testbed.os_username
    if 'os_password' in dir(testbed):
        cluster_dict['cluster'][0]['parameters']['keystone_password'] = testbed.os_password
    if 'os_tenant_name' in dir(testbed):
        cluster_dict['cluster'][0]['parameters']['keystone_tenant'] = testbed.os_tenant_name
    if 'router_asn' in dir(testbed):
        cluster_dict['cluster'][0]['parameters']['router_asn'] = testbed.router_asn
        


def new_cluster():
    params=read_ini_file(sys.argv[1:])
    cluster_id = get_user_cluster_id()
    if not cluster_id:
        cluster_id = params['cluster_id']
    cluster_dict={
                  "cluster" : [
                      {
                          "id" : cluster_id,
                          "parameters" : {
                              "router_asn": "64512",
                              "database_dir": "/home/cassandra",
                              "database_token": "",
                              "openstack_mgmt_ip": "",
                              "use_certificates": "False",
                              "multi_tenancy": "False",
                              "encapsulation_priority": "'MPLSoUDP','MPLSoGRE','VXLAN'",
                              "keystone_user": "admin",
                              "keystone_password": "contrail123",
                              "keystone_tenant": "admin",
                              "openstack_password": "contrail123",
                              "analytics_data_ttl": "168",
                              "subnet_mask": "255.255.255.0",
                              "gateway": "1.1.1.254",
                              "password": "c0ntrail123",
                              "domain": "contrail.juniper.net",
                              "haproxy": "disable"
                              }
                          }
                      ]
                  }
    config = ConfigParser.SafeConfigParser()
    config.read([smgr_client_def._DEF_SMGR_CFG_FILE])
    default_config_object = get_default_object("cluster", config)
    cluster_params_dict = dict(cluster_dict["cluster"][0]["parameters"].items() + default_config_object["parameters"].items())
    tmp_cluster_dict = dict(cluster_dict["cluster"][0].items() + default_config_object.items())
    tmp_cluster_dict["parameters"] = cluster_params_dict
    cluster_dict["cluster"][0] = tmp_cluster_dict
    return cluster_dict

# End new_cluster()


def parse_arguments(args_str=None):
    parser = argparse.ArgumentParser(
            description='''Server Manager Tool to generate json from testbed.py .
                           Value specified in --cluster_id will override value in 
                           server.json and vns.json .
                        ''',
            usage= '''server-manager [-f <config_file>] [-c <cluster_id>]  -t testbed.py '''

    )
    #group1 = parser.add_mutually_exclusive_group()

    parser.add_argument("--config_file", "-f",
                        help="Server manager client config file ")
    parser.add_argument("--cluster_id", "-c",
                        help="user specified preferred cluster_id ")
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


def get_user_cluster_id(args_str=None):
    args = parse_arguments(args_str)
    cluster_id = None
    if args.cluster_id:
        cluster_id = args.cluster_id
    return cluster_id


def get_server_with_cluster_id_from_db():
    cluster_id = get_pref_cluster_id()

    temp_dir= expanduser("~")
    file_name = '%s/server_with_cluster_id_from_db.json' %(temp_dir)
    subprocess.call('server-manager show  server --cluster_id %s --detail \
                 | tr -d "\n" \
                 | sed "s/[^{]*//" \
                 > %s' %(cluster_id, file_name), shell=True )


    in_file = open( file_name, 'r' )
    in_data = in_file.read()
    server_dict = json.loads(in_data)

    return server_dict

def get_cluster_with_cluster_id_from_db():
    cluster_id = get_user_cluster_id()
    if not cluster_id:
        params=read_ini_file(sys.argv[1:])
        cluster_id = params['cluster_id']

    cluster_dict = {"cluster": []}
 
    temp_dir= expanduser("~")

    file_name = '%s/cluster.json' %(temp_dir)

    subprocess.call('server-manager show  cluster --cluster_id %s --detail \
                 | tr -d "\n" \
                 | sed "s/[^{]*//" \
                 > %s' %(cluster_id, file_name), shell=True )

    in_file = open( file_name, 'r' )
    in_data = in_file.read()

    cluster_dict = json.loads(in_data)

    return cluster_dict


def get_server_with_ip_from_db(ip=None):
    params=read_ini_file(sys.argv[1:])
  
    server_dict={}
    if not ip:
        print "Please provide an ip as input arg"
        return ip

    temp_dir= expanduser("~")

    file_name = '%s/server.json' %(temp_dir)

    subprocess.call('server-manager show  server --ip %s --detail \
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

def get_storage_node_config_from_testbed_py():
    testbed = get_testbed()
    storage_config = {}
    allowed_disk_types = ['disks']
    if not testbed.env.has_key('storage_node_config'):
        return storage_config
    for key in testbed.env.storage_node_config:
        node_config_dict = dict(testbed.env.storage_node_config[key])
        ip = getIp(key)
        if not storage_config.has_key(ip):
            storage_config[ip] = {}
        for disk_type in node_config_dict:
            if disk_type not in allowed_disk_types:
                print ("ERROR: An invalid disk type has been specified in the testbed.py storage node config")
            else:
                storage_config[ip][disk_type] = node_config_dict[disk_type]
    return storage_config
# end get_storage_node_config_from_testbed_py


def update_server_in_db_with_testbed_py():
    cluster_id = get_pref_cluster_id()  
    node = get_host_roles_from_testbed_py()
    storage_config = get_storage_node_config_from_testbed_py()
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
        server_id = server_dict['server'][0]['id']
        u_server = {}
        u_server['id'] = server_id
        u_server['cluster_id'] = cluster_id
        u_server['roles'] = node[key]
        u_server['server_params'] = {}
        if key in storage_config:
            for disk_type in storage_config[key]:
                u_server['server_params'][disk_type] = storage_config[key][disk_type]
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
        subprocess.call('server-manager show  server --server_id %s --detail' \
                  % u_server['id'], shell=True )
#End  update_server_in_db_with_cluster_id


def get_pref_cluster_id():
    cluster_id = get_user_cluster_id()
    if not cluster_id:
        params=read_ini_file(sys.argv[1:])
        cluster_id = params['cluster_id']
    return cluster_id

def verify_user_input():
    params=read_ini_file(sys.argv[1:])
    cluster_id = get_user_cluster_id()

    if not params and not cluster_id:
        sys.exit(" User should either provide --cluster_id or config.ini ")

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
    



