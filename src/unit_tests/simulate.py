import sys, os, time, pdb
import unittest
from decimal import *
from flexmock import flexmock, Mock
sys.path.append(os.path.abspath(os.pardir))
from server_mgr_ipmi_monitoring import ServerMgrIPMIMonitoring
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
    
class mock_logger(object):
    def __init__(self, *args, **kwargs):
	return

class TestMonitoring(unittest.TestCase):
	filename = None
	noresponse = False
	delayed_response = False
        ipmonitor = None
	raiseException = False
	
	def mock_subprocess(self,cmd):
		f = open(self.filename, 'r')
		result= f.read()
		#This is for simulating the case for which there is no response
		if self.noresponse:
			return None
		if self.delayed_response:
			time.sleep(2)
		if self.raiseException:
			time.sleep("3")
		return result

	def checkQuantaData(self,output):
		self.assertEqual(output[0].sensor, 'MB1_Temp')
		self.assertEqual(output[0].sensor_type, 'temperature')
		self.assertEqual(output[0].reading, 28)
		self.assertEqual(output[0].unit, 'C')
		self.assertEqual(output[0].status, 'ok')
		self.assertEqual(output[1].sensor, 'PDB_FAN1A')
		self.assertEqual(output[1].sensor_type, 'fan')
		self.assertEqual(output[1].reading, 4700)
		self.assertEqual(output[1].unit, 'RPM')
		self.assertEqual(output[1].status, 'ok')
		self.assertEqual(output[2].sensor, 'PSU_Input_Power')
		self.assertEqual(output[2].sensor_type, 'power')
		self.assertEqual(output[2].reading, 0)
		self.assertEqual(output[2].unit, 'Watts')
		self.assertEqual(output[2].status, 'ok')
	
	def checkSuperMicroData(self,output):
		self.assertEqual(output[0].sensor, 'System Temp')
		self.assertEqual(output[0].sensor_type, 'temperature')
		self.assertEqual(output[0].reading, 28)
		self.assertEqual(output[0].unit, 'C')
		self.assertEqual(output[0].status, 'ok')
		self.assertEqual(output[1].sensor, 'CPU Temp')
		self.assertEqual(output[1].sensor_type, 'temperature')
		self.assertEqual(output[1].reading, 0)
		self.assertEqual(output[1].unit, 'unspecified')
		self.assertEqual(output[1].status, 'ok')
		self.assertEqual(output[2].sensor, 'FAN 1')
		self.assertEqual(output[2].sensor_type, 'fan')
		self.assertEqual(output[2].reading, 3825)
		self.assertEqual(output[2].unit, 'RPM')
		self.assertEqual(output[2].status, 'ok')

	def checkChassisData(self, output):
	    self.assertEqual(output.system_power, 'on')
	    self.assertFalse(output.power_overload)
	    self.assertEqual(output.power_interlock, 'inactive')
	    self.assertFalse(output.main_power_fault)
	    self.assertFalse(output.power_control_fault)
	    self.assertEqual(output.power_restore_policy, 'always-off')
	    self.assertEqual(output.last_power_event, 'command')
	    self.assertEqual(output.chassis_intrusion, 'inactive')
	    self.assertEqual(output.front_panel_lockout, 'inactive')
	    self.assertFalse(output.drive_fault)
	    self.assertFalse(output.cooling_fan_fault)
	
	def mock_send_ipmi_stats(self,*args, **kwargs):
		if args[3] == 'ipmi_data':
			if self.filename == './test-data/quanta_sensor.txt':
				self.checkQuantaData(args[1])
			elif self.filename == './test-data/supermicro_sensor.txt':
				self.checkSuperMicroData(args[1])
		elif args[3] == 'ipmi_chassis_data':
		    if self.filename == './test-data/chassis/chassis_output.txt':
		        self.checkChassisData(args[1])
			#print sensor.sensor,sensor.sensor_type,sensor.reading,sensor.unit,sensor.status
	def setUp(self):
		#Mock the ServerMgrlogger class. We will have our own log file
		flexmock(ServerMgrlogger, __new__=mock_logger)
		ServerMgrIPMIMonitoring.log_file='fake-logger.conf'
		self.ipmonitor = ServerMgrIPMIMonitoring(ServerMgrIPMIMonitoring, 10, 10)
		self.ipmonitor.base_obj.call_subprocess = self.mock_subprocess
		self.ipmonitor.send_ipmi_stats = self.mock_send_ipmi_stats
	
	def tearDown(self):
		self.ipmonitor = None
		self.filename = None
        	self.noresponse = False
        	self.delayed_response = False
        	self.raiseException = False

	def testSensorData(self):
		supported_sensors = ['FAN|.*_FAN', '^PWR', '.*Temp', '.*_Power']
		#Simulate correct Qunata sensor info output
		self.filename = './test-data/sensor/quanta_sensor.txt'
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate correct SuperMicro sensor info output
		self.filename = './test-data/sensor/supermicro_sensor.txt'
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate IPMI2.0 output
		self.filename = './test-data/sensor/noipmi_output.txt'
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate wrong output
		self.filename = './test-data/sensor/sensor_wrongoutput.txt'
		#Make sure the exception is raised. If the exception is not raised the test case will fail
		with self.assertRaises(Exception):
		   self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate no response from device
		self.noresponse = True
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate delayed response from the device
		self.noresponse = False
		self.delayed_response = True
		self.filename = './test-data/sensor/quanta_sensor.txt'
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)
	def testChassisData(self):
	    self.filename = './test-data/chassis/chassis_output.txt'
            self.ipmonitor.fetch_and_process_chassis("dummy", "dummy", "dummy", "dummy", "dummy")
	    with self.assertRaises(Exception):
		self.raiseException = True
            	self.ipmonitor.fetch_and_process_chassis("dummy", "dummy", "dummy", "dummy", "dummy")

def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestMonitoring('testSensorData'))
    suite.addTest(TestMonitoring('testChassisData'))
    return suite

if __name__ == '__main__':
	mySuite = suite()
	runner = unittest.TextTestRunner()
	runner.run(mySuite)
