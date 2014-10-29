#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_upgrade.py
   Author : Bharat Putta
   Description : This file contains code that will upgrade server-manager server and client on same physical server by taking rpm to be upgraded as command line parameter and logs into /var/log/smgr_install.log.
   Usage : python smgr_upgrade.py <server-mananger server IP Address> <server-manager server package> <server-manager client package>
   example: python smgr_upgrade.py 10.204.217.206 contrail-server-manager-1.20-44.el6.noarch.rpm contrail-server-manager-client-1.20-44.el6.noarch.rpm
   Installation Log : /var/log/smgr_install.log
"""

import re
import os
import sys
import ConfigParser
import commands
import time
import logging

installation_status = True
log_object = open('/var/log/smgr_install.log', 'w+')

class smgrupgrade(object):

    def __init__(self): 
        smgr_ip = sys.argv[1]
        smgr_server_pkg = sys.argv[2]
        smgr_client_pkg = sys.argv[3]
        installation_status = True
        self.smgr_server_upgrade(smgr_server_pkg)
        self.smgr_client_upgrade(smgr_client_pkg)
        self.check_installation(smgr_server_pkg, smgr_client_pkg)
        log_object.close()
    #END of def __init__(self):

    def smgr_server_upgrade(self, smgr_server_pkg):
        ''' Install/upgrades Server-manager Server '''
        info = "***************************** Installing Server-manager server *************************************"
        log_object.write(info)
        log_object.write("\n")
        save_dir = "/tmp/contrail-smgr-save"
        cmd = "mkdir -p /tmp/contrail-smgr-save"
        output = commands.getoutput(cmd)
        log_object.write(output)
        cmd = "cp -r /etc/cobbler/dhcp.template /etc/cobbler/named.template /etc/cobbler/settings /etc/cobbler/zone.template /etc/cobbler/zone_templates /tmp/contrail-smgr-save"
        output =commands.getoutput(cmd)
        log_object.write(output)
        cmd = "service contrail-server-manager stop"
        output = commands.getoutput(cmd)
        log_object.write(output)
        log_object.write("\n")
        if smgr_server_pkg.endswith('.rpm'):
            info = "Checking server-manager is installed ot not, if installed will remove existing one and upgrades the current one else installs from scratch"
            log_object.write(info)
            cmd = "yum -y remove contrail-server-manager"
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n")
            if re.search('No Match for argument: contrail-server-manager', output , re.I):
                print "Server-manager is not installed, installing from the scratch, its not hung installing necesary softwares background"
                output = "Server-manager is not installed, installing from the scratch"  
                log_object.write(output) 
                cmd = 'rpm -qa | grep epel-release'
                epel_output = commands.getoutput(cmd)
                log_object.write(epel_output)
                if 'epel-release-6-8.noarch' != epel_output:
                    cmd = 'wget http://buaya.klas.or.id/epel/6/i386/epel-release-6-8.noarch.rpm'
                    output = commands.getoutput(cmd) 
                    log_object.write(output)
                    cmd = 'rpm -ivh epel-release-6-8.noarch.rpm'
                    output = commands.getoutput(cmd)
                    log_object.write(output) 
            print "Upgrading the server-manager, please wait for some time......"
            cmd = "yum -y install %s"%smgr_server_pkg
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n")
            if re.search('error',output,re.I):
                installation_status = False
            print "Upgrading server-manager done"
            info = "Upgrading server-manager done"
            log_object.write(info)
            log_object.write("\n")
        elif smgr_server_pkg.endswith('.deb'):
            print "Checking server-manager is installed or not, if installed will remove existing one and upgrades the current one else installs from scratch"
            print " Its not hung installing necessary softwares in background, please wait for some time"
            info = "Checking server-manager is installed or not, if installed will remove existing one and upgrades the current one else installs from scratch \n"
            log_object.write(info)
            cmd = "dpkg -P contrail-server-manager"
            output = commands.getoutput(cmd) 
            log_object.write(output)
            log_object.write("\n") 
            if re.search('no installed package matching contrail-server-manager', output , re.I):
                info = "Server-manager is not installed on this server, so installing from the scratch with all dependencies \n"
                log_object.write(info)
                info = "Installing required software, not hung,, please wait for some time \n"
                log_object.write(info)
                cmd = "apt-get -y update"
                output = commands.getoutput(cmd)
                log_object.write(output)
                log_object.write("\n")
                cmd = "dpkg -l | grep gdebi"
                gdebi_output = commands.getoutput(cmd)
                log_object.write(gdebi_output)
                if not re.search('gdebi', gdebi_output,re.I):
                    cmd = "apt-get install -y gdebi-core"
                    info = "Installing gdebi \n"
                    log_object.write(info)
                    output = commands.getoutput(cmd)
                    log_object.write(output)
                    log_object.write("\n")
                cmd = "dpkg -l | grep puppet"
                puppet_output = commands.getoutput(cmd)
                log_object.write(puppet_output)
                if not re.search('puppet-common', puppet_output,re.I):
                    if not re.search('2.7.25-1', puppet_output,re.I):  
                        cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppet-common_2.7.25-1puppetlabs1_all.deb"
                        output = commands.getoutput(cmd)
                        log_object.write(output)
                        cmd = "gdebi -n puppet-common_2.7.25-1puppetlabs1_all.deb"
                        info = "******************** Installing Puppet-common ************************ \n"
                        log_object.write(info)
                        output = commands.getoutput(cmd)
                        log_object.write(output)
                        log_object.write("\n")
                if not re.search('puppetmaster', puppet_output,re.I):
                    if not re.search('2.7.25-1', puppet_output,re.I):
                        cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppetmaster-common_2.7.25-1puppetlabs1_all.deb"
                        output = commands.getoutput(cmd)
                        log_object.write(output) 
                        cmd = "gdebi -n puppetmaster-common_2.7.25-1puppetlabs1_all.deb"
                        info = "********************Installing puppetmaster-common ******************* \n" 
                        log_object.write(info)
                        output = commands.getoutput(cmd)
                        log_object.write(output)
                        log_object.write("\n")
                if not re.search('puppetmaster', puppet_output,re.I):
                    if not re.search('2.7.25-1', puppet_output,re.I):
                        cmd = "wget http://apt.puppetlabs.com/pool/stable/main/p/puppet/puppetmaster_2.7.25-1puppetlabs1_all.deb"
                        output = commands.getoutput(cmd)
                        log_object.write(output)
                        cmd = "gdebi -n puppetmaster_2.7.25-1puppetlabs1_all.deb"
                        info = "******************Installing puppetmaster ****************** \n"
                        log_object.write(info)
                        output = commands.getoutput(cmd) 
                        log_object.write(output)
             
            cmd = "gdebi -n %s"%smgr_server_pkg
            info = "Installing server-manager, please wait for some time...... \n"
            log_object.write(info)
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n")
            if re.search('error|failed',output,re.I):
                 installation_status = False
            info = "Upgrading Ubuntu server-manager done"
            log_object.write(info)
        cmd = "cp /contrail-smgr-save/dhcp.template /etc/cobbler/dhcp.template"
        output = commands.getoutput(cmd)
        log_object.write(output) 
        cmd = "cp /contrail-smgr-save/named.template /etc/cobbler/named.template"
        output = commands.getoutput(cmd)
        log_object.write(output)
        cmd = "cp /contrail-smgr-save/settings /etc/cobbler/settings"
        output = commands.getoutput(cmd)
        log_object.write(output)
        cmd = "cp /contrail-smgr-save/zone.template /etc/cobbler/zone.template"
        output = commands.getoutput(cmd)
        log_object.write(output)
        cmd = "cp -r /contrail-smgr-save/zone_templates /etc/cobbler/"
        output = commands.getoutput(cmd)
        log_object.write(output)
        cmd = "service contrail-server-manager restart"
        output =  commands.getoutput(cmd) 
        log_object.write(output)
        info = "***************************** Installation of Server-manager server ENDS ***********************************"
        log_object.write(info) 
    #End of def smgr_server_upgrade(self, smgr_server_pkg):   


    def smgr_client_upgrade(self, smgr_client_pkg):
        ''' Install/Upgrades Server-manager Client '''
        smgr_ip = sys.argv[1]
        info = "********************* Installing Server-manager CLient ******************************"
        log_object.write(info)  
        log_object.write("\n") 
        if smgr_client_pkg.endswith('.rpm'):
            cmd = "yum -y remove contrail-server-manager-client"
            output = commands.getoutput(cmd)
            log_object.write(output) 
            log_object.write("\n")
            cmd = "yum -y install %s"%smgr_client_pkg
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n")
            if re.search('error|failed',output,re.I):
       	        installation_status = False

        elif smgr_client_pkg.endswith('.deb'):
            cmd = "dpkg -r contrail-server-manager-client"
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n")
            cmd = "gdebi -n %s"%smgr_client_pkg
            output = commands.getoutput(cmd)
            log_object.write(output)
            log_object.write("\n") 
            if re.search('error',output,re.I):
                installation_status = False

        config= ConfigParser.RawConfigParser()
        config.read(r'/opt/contrail/server_manager/client/sm-client-config.ini')
        config.set('SERVER-MANAGER','listen_ip_addr',smgr_ip)
        with open(r'/opt/contrail/server_manager/client/sm-client-config.ini', 'wb') as configfile:
      		config.write(configfile)
        info = "****************** Installation of Server-manager CLient Ends *************************"
        log_object.write(info)
    #END of def smgr_client_upgrade(self, smgr_client_pkg):


    def check_installation(self, smgr_server_pkg, smgr_client_pkg):
        ''' Check Server and client Installation status ''' 
        smgr_ip = sys.argv[1]
        info = "********************* Checking installation status *****************************"
        log_object.write(info)
        log_object.write("\n")
        if smgr_server_pkg.endswith('.rpm'):
    	     output = commands.getoutput("rpm -qa | grep contrail")
             log_object.write(output)

   	     d,f1 = os.path.split(smgr_server_pkg)
   	     smgr_server_pkg_str = f1.strip(".rpm")
             log_object.write(smgr_server_pkg_str)

   	     d,f2 = os.path.split(smgr_client_pkg)
   	     smgr_client_pkg_str = f2.strip(".rpm")
             log_object.write(smgr_client_pkg_str)

   	     if re.search(smgr_server_pkg_str,output):
       	         info = "%s installed successfully"%f1
                 log_object.write(info)
   	     else:
      	         info = "% installation failed"%f1
                 self.installation_status = False
                 log_object.write(info)

             if re.search(smgr_client_pkg_str,output):
                 info = "%s installed successfully"%f2
                 log_object.write(info)
             else:
                 info = "% installation failed"%f2
                 log_object.write(info)
                 self.installation_status = False

             if installation_status :
                 print "PASS : server-manager server and client installated successfully"
                 info = "PASS : server-manager server and client installated successfully \n"
                 log_object.write(info)
             else:
                 print "FAIL : server-manager server and client installation failed"
                 info = "FAIL : server-manager server and client installation failed \n"
                 log_object.write(info)
                 sys.exit(1)
        

        elif smgr_server_pkg.endswith('.deb'):
            output = commands.getoutput("dpkg -l | grep contrail")
            log_object.write(output)

            d,f1 = os.path.split(smgr_server_pkg)
            smgr_server_pkg_str = re.search('\d\.\d+\-\d+', f1, re.I).group()
            log_object.write(smgr_server_pkg_str) 

            d,f2 = os.path.split(smgr_client_pkg)
            smgr_client_pkg_str = re.search('\d\.\d+\-\d+', f2, re.I).group()
            log_object.write(smgr_client_pkg_str)
    
            if re.search(smgr_server_pkg_str,output):
                 info = "%s installed successfully"%f1
                 log_object.write(info)
            else:
                 info = "% installation failed"%f1
                 self.installation_status = False
                 log_object.write(info)

            if re.search(smgr_client_pkg_str,output):
                 info = "%s installed successfully"%f2
                 log_object.write(info)
            else:
                 info = "% installation failed"%f2
                 log_object.write(info)
                 self.installation_status = False

            if installation_status :
                 print "PASS : server-manager server and client installated successfully"
                 info = "PASS : server-manager server and client installated successfully \n"
                 log_object.write(info)
            else:
                 print "FAIL : server-manager server and client installation failed"
                 info = "FAIL : server-manager server and client installation failed \n"
                 log_object.write(info)
                 sys.exit(1)
      
        time.sleep(30) 
        cmd = "netstat -anp | grep 9001"
        output = commands.getoutput(cmd)
        log_object.write(output)
        output = output.split('\n')
        matched_line = output[0] 
        if re.search('%s:9001.*listen.*python'%smgr_ip,matched_line,re.I) :
            print "server-manager is running sucessfully"
            info = "server-manager is running sucessfully \n"
            log_object.write(info)
        else:
            print "server-manager is not started after installation"
            info = "server-manager is not started after installation \n"
            log_object.write(info)
            sys.exit(1)  
        cmd = "server-manager show image"
        output = commands.getoutput(cmd)
        log_object.write(output)
        log_object.write("\n")
        cmd = "echo $?"
        output = commands.getoutput(cmd) 
        log_object.write(output)
        info = "********************* Checking installation status *****************************"
        log_object.write(info)
    #END of check_installation(self, smgr_server_pkg, smgr_client_pkg):   


smgrupgrade()

