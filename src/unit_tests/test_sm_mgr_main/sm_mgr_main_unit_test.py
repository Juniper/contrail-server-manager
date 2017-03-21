import unittest
import sys, os
import verfiy_server_cfg as verifyServerConfig
sys.path.append("/opt/contrail/server_manager")
from server_mgr_issu import *
from flexmock import flexmock, Mock
from server_mgr_certs import ServerMgrCerts

dict = {
    'id': 'host05',
    'network': "{'routes': [{'interface': 'eth1', 'netmask': '255.255.255.0', 'network': '3.3.4.0', 'gateway': '3.3.3.254'}], 'management_interface': 'em1', 'interfaces': [{'dhcp': 'true', 'mtu': '1400', 'vlan': '1', 'mac_address': 'c4:54:44:44:d7:4a', 'ip_address': '172.16.70.30/24', 'name': 'em1', 'default_gateway': '172.16.70.254'}, {'mac_address': '90:e2:ba:50:aa:88', 'name': 'eth1', 'default_gateway': '3.3.3.254'},{'bond_options': {'miimon': '100', 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4'}, 'ip_address': '192.168.100.1/24', 'type': 'bond', 'name': 'bond0', 'member_interfaces': ['eht1', 'em1']}],'provisioning': 'kickstart'}",
  }

class mock_ServerMgrCerts(object):

  def __init__(self, *args,**kwargs):
      return

  def create_sm_ca_cert(self):
      return "",""

class smgr_main(unittest.TestCase):
  vncServerMgr = None

  def setUp(self):
      args_str = ["-c",
                  "/opt/contrail/server_manager/sm-config.ini"
                 ]
      flexmock(ServerMgrCerts,__new__=mock_ServerMgrCerts)
      self.vncServerMgr =  VncServerManager(args_str)

  def bld_server_cfg(self):
      self.vncServerMgr.build_server_cfg(dict)
      #Verify the results
      f = open('/var/www/html/contrail/config_file/host05.sh')
      output = f.read()
      verifyServerConfig.verify_server_cfg(self,output)

def smgr_main_suite():
    suite = unittest.TestSuite()
    suite.addTest(smgr_main('bld_server_cfg'))
    return suite

if __name__ == '__main__':
    mySuite = smgr_main_suite()
    runner = unittest.TextTestRunner()
    runner.run(mySuite)
