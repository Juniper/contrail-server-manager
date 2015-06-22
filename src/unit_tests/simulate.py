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
	
	def mock_subprocess(self,cmd):
		print self.filename
		f = open(self.filename, 'r')
		result= f.read()
		#This is for simulating the case for which there is no response
		if self.noresponse:
			return None
		if self.delayed_response:
			time.sleep(2)
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

	def mock_send_ipmi_stats(self,*args, **kwargs):
		if args[3] == 'ipmi_data':
			if self.filename == './test-data/quanta_sensor.txt':
				self.checkQuantaData(args[1])
			elif self.filename == './test-data/supermicro_sensor.txt':
				self.checkSuperMicroData(args[1])
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

	def testSensorData(self):
		supported_sensors = ['FAN|.*_FAN', '^PWR', '.*Temp', '.*_Power']
		#Simulate correct Qunata sensor info output
		self.filename = './test-data/quanta_sensor.txt'
		#self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate correct SuperMicro sensor info output
		self.filename = './test-data/supermicro_sensor.txt'
		#self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate IPMI2.0 output
		self.filename = './test-data/noipmi_output.txt'
		#self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate wrong output
		self.filename = './test-data/wrongoutput.txt'
		self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate no response from device
		self.noresponse = True
		#self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

		#Simulate delayed response from the device
		self.noresponse = False
		self.delayed_response = True
		self.filename = './test-data/quanta_sensor.txt'
		#self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)


if __name__ == '__main__':
    unittest.main()
