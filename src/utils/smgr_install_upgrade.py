#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_upgrade.py
   Author : Bharat Putta
   Description : This file contains code that will upgrade server-manager server and client on same physical server by taking rpm to be upgraded as command line parameter.
   Usage : python smgr_upgrade.py <server-mananger server IP Address> <server-manager server package> <server-manager client package>
   example: python smgr_upgrade.py 10.204.217.206 contrail-server-manager-1.20-44.el6.noarch.rpm contrail-server-manager-client-1.20-44.el6.noarch.rpm
"""

import re
import os
import sys
import ConfigParser
import commands
import time

installation_status = True

class smgrupgrade(object):

    def __init__(self): 
       smgr_ip = sys.argv[1]
       smgr_server_pkg = sys.argv[2]
       smgr_client_pkg = sys.argv[3]
       installation_status = True 
       self.smgr_server_upgrade(smgr_server_pkg)
       self.smgr_client_upgrade(smgr_client_pkg)
       self.check_installation(smgr_server_pkg, smgr_client_pkg)


    def smgr_server_upgrade(self, smgr_server_pkg):
       save_dir = "/tmp/contrail-smgr-save"
       cmd = "mkdir -p /tmp/contrail-smgr-save"
       commands.getoutput(cmd)
       cmd = "cp -r /etc/cobbler/dhcp.template /etc/cobbler/named.template /etc/cobbler/settings /etc/cobbler/zone.template /etc/cobbler/zone_templates /tmp/contrail-smgr-save"
       commands.getoutput(cmd)
       cmd = "service contrail-server-manager stop"
       commands.getoutput(cmd)
       if smgr_server_pkg.endswith('.rpm'):
           print "Removing existing server-manager"
           cmd = "yum -y remove contrail-server-manager"
           output = commands.getoutput(cmd)
           if re.search('No Match for argument: contrail-server-manager', output , re.I):
              print "Server-manager is not installed, installing from the scratch"
              cmd = 'rpm -qa | grep epel-release'
              epel_output = commands.getoutput(cmd)
              if 'epel-release-6-8.noarch' != epel_output:
                 cmd = 'wget http://buaya.klas.or.id/epel/6/i386/epel-release-6-8.noarch.rpm'
                 commands.getoutput(cmd) 
                 cmd = 'rpm -ivh epel-release-6-8.noarch.rpm'
                 commands.getoutput(cmd)
           print "Upgrading the server-manager, please wait for some time......"
           cmd = "yum -y install %s"%smgr_server_pkg
           output = commands.getoutput(cmd)
           print output
           if re.search('error',output,re.I):
               installation_status = False
           print "Upgrading server-manager done"
       elif smgr_server_pkg.endswith('.deb'):
           print "Upgrading Ubuntu Server-manager"
           print "Removing existing one"
           cmd = "dpkg -P contrail-server-manager"
           output = commands.getoutput(cmd) 
           print output
           if re.search('no installed package matching contrail-server-manager', output , re.I):
              print "Server-manager is not installed on this server, so installing from the scratch with all dependencies"
              print "Installing required software, not hung,, please wait for some time"
              cmd = "apt-get -y update"
              print commands.getoutput(cmd)
              cmd = "dpkg -l | grep gdebi"
              gdebi_output = commands.getoutput(cmd)
              if not re.search('gdebi', gdebi_output,re.I):
                 cmd = "apt-get install -y gdebi-core"
                 print "Installing gdebi"
                 output = commands.getoutput(cmd)
              cmd = "dpkg -l | grep puppet"
              puppet_output = commands.getoutput(cmd)
              if not re.search('puppet-common', puppet_output,re.I):
                 if not re.search('2.7.25-1', puppet_output,re.I):  
                    cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppet-common_2.7.25-1puppetlabs1_all.deb"
                    print commands.getoutput(cmd)
                    cmd = "gdebi -n puppet-common_2.7.25-1puppetlabs1_all.deb"
                    print "Installing Puppet-common"
                    print commands.getoutput(cmd)
              if not re.search('puppetmaster', puppet_output,re.I):
                 if not re.search('2.7.25-1', puppet_output,re.I):
                    cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppetmaster-common_2.7.25-1puppetlabs1_all.deb"
                    print commands.getoutput(cmd)
                    cmd = "gdebi -n puppetmaster-common_2.7.25-1puppetlabs1_all.deb"
                    print "Installing puppetmaster-common" 
                    print commands.getoutput(cmd)
              if not re.search('puppetmaster', puppet_output,re.I):
                 if not re.search('2.7.25-1', puppet_output,re.I):
                    cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppetmaster_2.7.25-1puppetlabs1_all.deb"
                    print commands.getoutput(cmd)
                    cmd = "gdebi -n puppetmaster_2.7.25-1puppetlabs1_all.deb"
                    print "Installing puppetmaster"
                    print commands.getoutput(cmd) 
             
           cmd = "gdebi -n %s"%smgr_server_pkg
           print "Installing server-manager, please wait for some time......"
           output = commands.getoutput(cmd)
           print output
           if re.search('error|failed',output,re.I):
               installation_status = False
           print "Upgrading Ubuntu server-manager done"
       cmd = "cp /contrail-smgr-save/dhcp.template /etc/cobbler/dhcp.template"
       commands.getoutput(cmd)
       cmd = "cp /contrail-smgr-save/named.template /etc/cobbler/named.template"
       commands.getoutput(cmd)
       cmd = "cp /contrail-smgr-save/settings /etc/cobbler/settings"
       commands.getoutput(cmd)
       cmd = "cp /contrail-smgr-save/zone.template /etc/cobbler/zone.template"
       commands.getoutput(cmd)
       cmd = "cp -r /contrail-smgr-save/zone_templates /etc/cobbler/"
       commands.getoutput(cmd)
       cmd = "service contrail-server-manager restart"
       print commands.getoutput(cmd) 


    def smgr_client_upgrade(self, smgr_client_pkg):
       smgr_ip = sys.argv[1]
       if smgr_client_pkg.endswith('.rpm'):
         cmd = "yum -y remove contrail-server-manager-client"
         print commands.getoutput(cmd)
         cmd = "yum -y install %s"%smgr_client_pkg
         output = commands.getoutput(cmd)
         print output
         if re.search('error|failed',output,re.I):
       	    installation_status = False

       elif smgr_client_pkg.endswith('.deb'):
          cmd = "dpkg -r contrail-server-manager-client"
          print commands.getoutput(cmd)
          cmd = "gdebi -n %s"%smgr_client_pkg
          output = commands.getoutput(cmd)
          print output
          if re.search('error',output,re.I):
            installation_status = False

       config= ConfigParser.RawConfigParser()
       config.read(r'/opt/contrail/server_manager/client/sm-client-config.ini')
       config.set('SERVER-MANAGER','listen_ip_addr',smgr_ip)
       with open(r'/opt/contrail/server_manager/client/sm-client-config.ini', 'wb') as configfile:
      		config.write(configfile)

    def check_installation(self, smgr_server_pkg, smgr_client_pkg):
       
       smgr_ip = sys.argv[1]
       if smgr_server_pkg.endswith('.rpm'):
           print "Checking installation status" 
    	   output = commands.getoutput("rpm -qa | grep contrail")

   	   d,f1 = os.path.split(smgr_server_pkg)
   	   smgr_server_pkg_str = f1.strip(".rpm")

   	   d,f2 = os.path.split(smgr_client_pkg)
   	   smgr_client_pkg_str = f2.strip(".rpm")

   	   print output
           print smgr_server_pkg_str,smgr_client_pkg_str

   	   if re.search(smgr_server_pkg_str,output):
       	       print "%s installed successfully"%f1
   	   else:
      	       print "% installation failed"%f1
               self.installation_status = False

           if re.search(smgr_client_pkg_str,output):
              print "%s installed successfully"%f2
           else:
              print "% installation failed"%f2
              self.installation_status = False

           if installation_status :
              print "PASS : server-manager server and client installated successfully"
           else:
              print "FAIL : server-manager server and client installation failed"
        

       elif smgr_server_pkg.endswith('.deb'):
           print "Checking installation status"
           output = commands.getoutput("dpkg -l | grep contrail")

           d,f1 = os.path.split(smgr_server_pkg)
           smgr_server_pkg_str = re.search('\d\.\d+\-\d+', f1, re.I).group()

           d,f2 = os.path.split(smgr_client_pkg)
           smgr_client_pkg_str = re.search('\d\.\d+\-\d+', f2, re.I).group()
           print output,
           print smgr_server_pkg,smgr_client_pkg

           if re.search(smgr_server_pkg_str,output):
               print "%s installed successfully"%f1
           else:
               print "% installation failed"%f1
               self.installation_status = False

           if re.search(smgr_client_pkg_str,output):
              print "%s installed successfully"%f2
           else:
              print "% installation failed"%f2
              self.installation_status = False
           
           if installation_status :
              print "PASS : server-manager server and client installated successfully"
           else:
              print "FAIL : server-manager server and client installation failed"  
      
       time.sleep(30) 
       cmd = "netstat -anp | grep 9001"
       output = commands.getoutput(cmd)
       print output
       output = output.split('\n')
       matched_line = output[0] 
       if re.search('%s:9001.*listen.*python'%smgr_ip,matched_line,re.I) :
          print "server-manager is running"
       else:
          print "server-manager is not started after installation"
       cmd = "server-manager show image"
       print commands.getoutput(cmd)


smgrupgrade()

