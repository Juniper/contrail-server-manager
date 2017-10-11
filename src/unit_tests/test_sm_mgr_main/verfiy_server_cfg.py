import unittest

def verify_interface(self, output):
  list = output.split()
  self.assertEqual(list[0].strip(), 'python')
  self.assertEqual(list[1].strip(), '/root/interface_setup.py')
  self.assertEqual(list[2].strip(), '--device')
  self.assertEqual(list[3].strip(), 'c4:54:44:44:d7:4a')
  self.assertEqual(list[4].strip(), '--ip')
  self.assertEqual(list[5].strip(), '172.16.70.30/24')
  self.assertEqual(list[6].strip(), '--gw')
  self.assertEqual(list[7].strip(), '172.16.70.254')

def verify_bond_interface(self, output):
  list = output.split()
  self.assertEqual(list[0].strip(), 'python')
  self.assertEqual(list[1].strip(), '/root/interface_setup.py')
  self.assertEqual(list[2].strip(), '--device')
  self.assertEqual(list[3].strip(), 'bond0')
  self.assertEqual(list[4].strip(), '--members')
  self.assertEqual(list[5].strip(), '--bond-opts')
#  self.assertEqual(list[6].strip(), '"{"miimon":')
  self.assertEqual(list[7].strip(), '"100",')
  self.assertEqual(list[8].strip(), '"mode":')
  self.assertEqual(list[9].strip(), '"802.3ad",')
  self.assertEqual(list[10].strip(), '"xmit_hash_policy":')
  #self.assertEqual(list[11].strip(), '"layer3+4"}"')
  self.assertEqual(list[12].strip(), '--ip')
  self.assertEqual(list[13].strip(), '192.168.100.1/24')
  
def verify_static_route(self, output):
  list = output.split()
  self.assertEqual(list[0].strip(), 'python')
  self.assertEqual(list[1].strip(), '/root/staticroute_setup.py')
  self.assertEqual(list[2].strip(), '--device')
  self.assertEqual(list[3].strip(), 'eth1')
  self.assertEqual(list[4].strip(), '--network')
  self.assertEqual(list[5].strip(), '3.3.4.0')
  self.assertEqual(list[6].strip(), '--netmask')
  self.assertEqual(list[7].strip(), '255.255.255.0')
  self.assertEqual(list[8].strip(), '--gw')
  self.assertEqual(list[9].strip(), '3.3.3.254')

def verify_dhcp_config(self, output):
  list = output.split()
  self.assertEqual(list[0].strip(), 'python')
  self.assertEqual(list[1].strip(), '/root/interface_setup.py')
  self.assertEqual(list[2].strip(), '--device')
  self.assertEqual(list[3].strip(), 'c4:54:44:44:d7:4a')
  self.assertEqual(list[4].strip(), '--mtu')
  self.assertEqual(list[5].strip(), '1400')
  self.assertEqual(list[6].strip(), '--vlan')
  self.assertEqual(list[7].strip(), '1')
  self.assertEqual(list[8].strip(), '--dhcp')

def verify_rm_line(self, output):
  list = output.split()
  self.assertEqual(list[0].strip(), 'rm')
  self.assertEqual(list[1].strip(), '/etc/init.d/host05.sh')
 
def verify_server_cfg(self,output):
 list = output.split('\n')
 verify_interface(self, list[1].strip())
 verify_bond_interface(self, list[2].strip())
 verify_rm_line(self, list[4].strip())

def verify_parameter_translation(self, translated_params,key_list):
  translated_key_list = translated_params['provision']['contrail']
  self.assertEqual(set(key_list), set(translated_key_list))
