#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_prov_ci.py
   Author : Bharat Putta
   Description : This file contains code that will add cluster, server, baseOS and repo and then provisions the target server and checks provision status.
   Usage : python smgr_prov_ci.py <target_node_IP>
"""

import re
import os
import sys
import ConfigParser
import commands
import pxssh
import glob
import datetime
import subprocess
import json
import argparse
import paramiko
import base64
import shutil
import string
from urlparse import urlparse, parse_qs
from time import gmtime, strftime, localtime
import pdb
import ast
import uuid
import traceback
import platform
import tempfile
import pexpect
import time
from time import sleep

PROVISION_TIME = 1000


def send_cmd(handle,cmd,prompt,wait_time):

   handle.expect ('.*',timeout=2)
   print handle.before
   handle.sendline(cmd)
   handle.PROMPT=prompt
   i = handle.expect ([prompt,pexpect.EOF,pexpect.TIMEOUT], timeout=wait_time)
   if i != 0 :
     print "ERROR: cmd : %s timed-out"%cmd
     output = handle.before
   else:
     output = handle.before + handle.match.group()
   print output
   return output
#END of def send_cmd(handle,cmd,prompt,wait_time):

class Provision_and_Validate(object):


    def __init__(self):
       print "Assumes contrail-packages are present in /tmp/smgr path"
       targetnode_ip = sys.argv[1]
       self.createclusterjson(targetnode_ip)
       self.createserverjson(targetnode_ip)
       self.addbaseOS()
       self.addpkgjson()
       self.InstallPuppetonTarget(targetnode_ip)
       self.verify_server_status("provision_completed")
    #End of def __init__(self):

    def createserverjson(self, targetnode_ip):
       ''' Creates server.json and adds it to server-manager '''
       params = []
       cmd = "mkdir -p /tmp/smgr"
       commands.getoutput(cmd) 
       json_object = open('/tmp/smgr/server.json', 'w+')
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
         ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
         pass
       cmd = "ifconfig"
       output = send_cmd(handle,cmd,prompt,120)
       print output
       interface = re.search("(eth\d+).*\n.*(%s)"%ip,output, re.I).group(1)
       print interface
       parameters_value = { 'interface_name': interface}
       mac_addr= re.search("([0-9A-F]{2}[:]){5}([0-9A-F]{2}).*\\r\\n.*(%s)"%ip,output, re.I).group()
       mac_addr = mac_addr.split()
       mac = mac_addr[0]
       print mac
       cmd = "hostname"
       host_object = send_cmd(handle,cmd,prompt,120)
       host_raw = host_object.split('\n')
       host_raw1 = host_raw[1]
       host_data = host_raw1.split('\r')
       hostname = host_data[0]
       print hostname
       octet = ip.split('.')
       domain = 'englab.juniper.net'
       subnet = '255.255.255.0'
       password = 'c0ntrail123'
       my_dict = { 'id': hostname, 'hostname': hostname, 'mac_address': mac, 'roles' : '["config", "control", "collector", "compute", "database", "openstack", "webui"]','ip_address': ip, 'gateway': '10.204.'+ octet[2]+ '.254', 'subnet_mask': subnet, 'domain': domain, 'cluster_id' : 'clustervm', 'password': password, 'parameters' : parameters_value }
       params.append(my_dict)
       print params
       server_params = { 'server' : params }
       json_output = json.dumps(server_params)
       json_object.write(json_output)
       json_object.close()
       cmd = "server-manager add server -f /tmp/smgr/server.json"
       server_detail = commands.getoutput(cmd)  
       print server_detail
    #End of def createserverjson(self, targetnode_ip):

    def createclusterjson(self, targetnode_ip):
      ''' Crestes cluster json and adds it to server-manager ''' 
      cluster_raw = []
      ip = targetnode_ip
      octet = ip.split('.')
      domain = 'englab.juniper.net'
      subnetmask = '255.255.255.0'
      password = 'c0ntrail123'
      print password
      cluster_object = open('/tmp/smgr/cluster.json', 'w+')
      parameters_value = { 'router_asn': '64512', "database_dir": '/home/cassandra', 'database_token': '', 'use_certificates': 'False', 'multi_tenancy': 'True', 'encapsulation_priority': 'MPLSoUDP,MPLSoGRE,VXLAN', 'keystone_user': 'admin', 'keystone_passwd': 'contrail123', 'keystone_tenant': 'admin', 'openstack_passwd': 'contrail123', 'analytics_data_ttl': '168', "haproxy": "disable", 'subnet_mask': subnetmask, 'gateway': '10.204.'+ octet[2]+ '.254', 'password': password, 'external_bgp': '[]', 'domain': domain } 
      print parameters_value     
      cluster_dict = { "id" : "clustervm", "email": "pbharat@juniper.net", "parameters" : parameters_value }
      print cluster_dict
      cluster_raw.append(cluster_dict)
      print cluster_raw
      cluster_params = { 'cluster' : cluster_raw } 
      cluster_jsonoutput = json.dumps(cluster_params)
      cluster_object.write(cluster_jsonoutput)
      cluster_object.close()
      cmd = "server-manager add cluster -f /tmp/smgr/cluster.json"
      cluster_detail = commands.getoutput(cmd)
      print cluster_detail
   #End of def createclusterjson(self, targetnode_ip):


    def addpkgjson(self):
      ''' adds contrail-repo to server-manager '''
      pkg_params = []
      pkg_object = open('/tmp/smgr/pkg.json', 'w+')
      cmd = " ls -lrt /tmp/smgr/"
      list_output = commands.getoutput(cmd)
      print list_output
      pkg = re.search( 'contrail-install-packages_.*_all.deb',list_output, re.I).group()
      print pkg
      pkg_raw =  {"id": "buildci123", "type": "contrail-ubuntu-package", "version": "ci", "path": "/tmp/smgr/"+ pkg }
      print pkg_raw
      pkg_params.append(pkg_raw)
      print pkg_params
      pkg_dict = { 'image' : pkg_params }
      print pkg_dict 
      pkg_jsonoutput = json.dumps(pkg_dict)      
      pkg_object.write(pkg_jsonoutput)
      pkg_object.close()
      cmd = "server-manager add image -f /tmp/smgr/pkg.json"
      pkg_detail = commands.getoutput(cmd)
      print pkg_detail
      remove_pkg = "rm -rf /tmp/smgr/%s"%pkg
      cmd = remove_pkg
      print commands.getoutput(cmd)
   #End of def addpkgjson(self):

    def addbaseOS(self):
      ''' adds base OS image to server-manager '''
      cmd = "apt-get install sshpass" 
      print commands.getoutput(cmd)
      cmd = "which sshpass"
      ssh_pass = commands.getoutput(cmd)
      cmd = "%s -p root@nodeb11 scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@10.204.216.4:/cs-shared/images/ubuntu-12.04.3-server-amd64.iso /tmp/smgr/"%ssh_pass
      print commands.getoutput(cmd)
      img_params = []
      img_object = open('/tmp/smgr/image.json', 'w+')
      cmd = " ls -lrt /tmp/smgr/"
      list_output = commands.getoutput(cmd)
      print list_output
      img = '/tmp/smgr/ubuntu-12.04.3-server-amd64.iso'
      print img
      img_raw =  {"id": "ubuntuiso", "type": "ubuntu", "version": "12.04.3", "path": img }
      print img_raw
      img_params.append(img_raw)
      print img_params
      img_dict = { 'image' : img_params }
      print img_dict
      img_jsonoutput = json.dumps(img_dict)
      img_object.write(img_jsonoutput)
      img_object.close()
      cmd = "server-manager add image -f /tmp/smgr/image.json"
      img_detail = commands.getoutput(cmd)
      print img_detail
   #End of def addbaseOS(self):

    def InstallPuppetonTarget(self, targetnode_ip):
      ''' Installs puppet agent on target node and provisions it with contrail-repo and verifies provision will be done or not and also verifies contrail-status on target ''' 
      result = True
      handle = pxssh.pxssh()
      ip = targetnode_ip
      login = "root"
      passwd = 'c0ntrail123'
      prompt = "#"
      try:
        ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
      except:
        pass
      cmd = "apt-get install sshpass"
      output = send_cmd(handle,cmd,prompt,120)
      cmd = "which sshpass"
      ssh_pass =  send_cmd(handle,cmd,prompt,120)
      sshpass_raw = ssh_pass.split('\n')
      sshpass_raw1 = sshpass_raw[1]
      sshpass_out = sshpass_raw1.split('\r')
      sshpass_path = sshpass_out[0]
      print sshpass_path
      cmd = "%s -p root@nodeb11 scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@10.204.216.4:/cs-shared/images/puppet*.deb /tmp/smgr/"%sshpass_path
      print send_cmd(handle,cmd,prompt,120)
      cmd = "apt-get install -y gdebi-core"
      print "Installing gdebi on target node"
      print send_cmd(handle,cmd,prompt,120)
      cmd = "gdebi -n /tmp/smgr/puppet-common_2.7.11-1ubuntu2.7_all.deb"
      print "Installing Puppet-common"
      print send_cmd(handle,cmd,prompt,120)
      cmd = "gdebi -n /tmp/smgr/puppet_2.7.11-1ubuntu2.7_all.deb"
      print "Installing Puppet Agent"
      print send_cmd(handle,cmd,prompt,120)
      string = "10.204.217.216" + "\t"+ "puppet" + "\n"
      f_obj = "file_object = open( '/etc/hosts', 'a')"
      cmd = "ifconfig"
      output = commands.getoutput(cmd)
      import pdb; pdb.set_trace()
      puppet_master_ip = re.search('(\eth\d+).*\\n.*(\inet addr\:)((\d+\.){3}\d+)',output, re.I).group(3)
      cmd = "echo '%s    puppet' >> /etc/hosts"%puppet_master_ip
      print send_cmd(handle,cmd,prompt,120)
      cmd = "cat /etc/hosts"
      print send_cmd(handle,cmd,prompt,120)
      cmd = "hostname"
      host_object = send_cmd(handle,cmd,prompt,120)
      host_raw = host_object.split('\n')
      host_raw1 = host_raw[1]
      host_data = host_raw1.split('\r')
      hostname = host_data[0]
      print hostname
      cmd = "server-manager provision -F --server_id %s buildci123"%hostname
      cluster_detail = commands.getoutput(cmd)
      print cluster_detail
      sleep(PROVISION_TIME)
      if not self.verify_server_status():
            result = result and False
      if not self.verify_contrail_status():
            result = result and False
    #def InstallPuppetonTarget(self, targetnode_ip):
  

    def verify_server_status(self):
       ''' provision status will be verified '''        
       result = True
       cmd = "server-manager status server --cluster_id clustervm"
       output = commands.getoutput(cmd)
       print output
       pattern = "provision_completed"
       if pattern not in output:
           print 'Provision failed'
           result = result and False
           assert result
    #end verify_server_status

   
    def verify_contrail_status(self):
        ''' Verify contrail-status on Target '''
        result = True
        targetnode_ip = sys.argv[1]
        if not self.verify_database(targetnode_ip):
           result = result and False
        if not self.verify_config(targetnode_ip):
           result = result and False
        if not self.verify_control(targetnode_ip):
           result = result and False
        if not self.verify_collector(targetnode_ip):
           result = result and False
        if not self.verify_webui(targetnode_ip):
           result = result and False
        if not self.verify_compute(targetnode_ip):
           result = result and False
        if not self.verify_openstack(targetnode_ip):
           result = result and False
        assert result
        return result
    #end verify_contrail_status 


    def verify_database(self, targetnode_ip):
      result = True
      handle = pxssh.pxssh()
      ip = targetnode_ip
      login = "root"
      passwd = 'c0ntrail123'
      prompt = "#"
      try:
         ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
      except:
         pass
      cmd = "contrail-status"
      output = send_cmd(handle,cmd,prompt,120)
      pattern = ["supervisord-contrail-database:active",
                 "contrail-database             active",
                 "contrail-database-nodemgr     active"]
      for line in pattern:
        if line not in output:
           print 'verify %s has Failed' %line
           result = result and False
      print "result of verify_database %s"%result
      assert result
      return result
    # END of def verify_database(self, targetnode_ip):
 
    def verify_openstack(self, targetnode_ip):
      result = True
      handle = pxssh.pxssh()
      ip = targetnode_ip
      login = "root"
      passwd = 'c0ntrail123'
      prompt = "#"
      try:
         ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
      except:
         pass
      cmd = "openstack-status"
      output = send_cmd(handle,cmd,prompt,120)
      pattern = ["openstack-nova-api:           active",
                 "openstack-nova-compute:       active",
                 "openstack-nova-network:       inactive (disabled on boot)",
                 "openstack-nova-scheduler:     active",
                 "openstack-nova-volume:        inactive (disabled on boot)",
                 "openstack-nova-conductor:     active",
                 "openstack-glance-api:         active",
                 "openstack-glance-registry:    active",
                 "openstack-keystone:           active",
                 "openstack-cinder-api:         active",
                 "openstack-cinder-scheduler:   active",
                 "openstack-cinder-volume:      inactive (disabled on boot)",
                 "mysql:                        inactive (disabled on boot)",
                 "libvirt-bin:                  active",
                 "rabbitmq-server:              active",
                 "memcached:                    inactive (disabled on boot)"]
      for line in pattern:
         if line not in output:
           print 'verify %s has Failed' %line
           result = result and False
      assert result
      return result
   #end verify_openstack(self, targetnode_ip):
 
    
    def verify_compute(self, targetnode_ip):
       result = True
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
          ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
          pass
       cmd = "contrail-status"
       output = send_cmd(handle,cmd,prompt,120) 
       pattern = ["supervisor-vrouter:           active",
                  "contrail-vrouter-agent        active",
                  "contrail-vrouter-nodemgr      active"]
       for line in pattern:
          if line not in output:
            print 'verify %s has Failed' %line
            result = result and False
       
       print "result of verify_compute %s"%result
       assert result
       return result
    #end verify_compute(self, targetnode_ip):

    def verify_webui(self, targetnode_ip):
       result = True
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
          ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
          pass
       cmd = "contrail-status"
       output = send_cmd(handle,cmd,prompt,120)       
       pattern = ["supervisor-webui:             active",
                  "contrail-webui                active",
                  "contrail-webui-middleware     active",
                  "redis-webui                   active"]
       for line in pattern:
          if line not in output:
             print 'verify %s has Failed' %line
             result = result and False
       print "result of verify_webui %s"%result
       assert result
       return result 
    #end verify_webui(self, targetnode_ip):

    def verify_collector(self, targetnode_ip):
       result = True
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
          ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
          pass
       cmd = "contrail-status"
       output = send_cmd(handle,cmd,prompt,120)
       pattern = ["supervisor-analytics:         active",
                  "contrail-analytics-api        active",
                  "contrail-analytics-nodemgr    active",
                  "contrail-collector            active",
                  "contrail-query-engine         active"]
       for line in pattern:
          if line not in output:
            print 'verify %s has Failed' %line
            result = result and False
       print "result of verify_collector %s"%result
       assert result
       return result
    #end verify_collector(self):

    def verify_config(self, targetnode_ip):
       result = True
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
          ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
          pass
       cmd = "contrail-status"
       output = send_cmd(handle,cmd,prompt,120)
       pattern = ["supervisor-config:            active",
                  "contrail-api:0                active",
                  "contrail-config-nodemgr       active",
                  "contrail-discovery:0          active",
                  "contrail-schema               active",
                  "contrail-svc-monitor          active",
                  "ifmap                         active"]

       for line in pattern:
         if line not in output:
           print 'verify %s has Failed' %line
           result = result and False
       print "result of verify_config %s"%result
       assert result
       return result
    #end verify_config(self, targetnode_ip):

    def verify_control(self, targetnode_ip):
       result = True
       handle = pxssh.pxssh()
       ip = targetnode_ip
       login = "root"
       passwd = 'c0ntrail123'
       prompt = "#"
       try:
          ret = handle.login (ip,login,passwd,original_prompt=prompt, login_timeout=1000,auto_prompt_reset=False)
       except:
          pass
       cmd = "contrail-status"
       output = send_cmd(handle,cmd,prompt,120)
       pattern = ["supervisor-control:           active",
                  "contrail-control              active",
                  "contrail-control-nodemgr      active",
                  "contrail-dns                  active",
                  "contrail-named                active"]
       for line in pattern:
          if line not in output:
            print 'verify %s has Failed' %line
            result = result and False
       print "result of verify_control %s"%result
       assert result
       return result
      #end verify_control(self, targetnode_ip):



Provision_and_Validate()


