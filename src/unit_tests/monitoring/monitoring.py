import sys, os, time, pdb
import unittest
from decimal import *
from flexmock import flexmock, Mock
sys.path.append(os.path.abspath(os.pardir))
from server_mgr_ipmi_monitoring import ServerMgrIPMIMonitoring
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_ssh_client import ServerMgrSSHClient
import verify_result

package_installed = True

#This is the class for mocking Server Manager logging	 
class mock_logger(object):
    def __init__(self, *args, **kwargs):
        return

#Mock class for ServerManager SSH client connection
class mock_ServerMgrSSHClient(object):
    filename = None
    def __init__(self, *args, **kwargs):
        return
    def exec_command(self, cmd):
        if cmd == 'which iostat' and package_installed == False:
            return None
        elif cmd == 'which iostat' and package_installed == True:
            return "package_installed"
        elif cmd == 'iostat -m':
            file_name = './monitoring/test-data/' + self.filename
        f = open(file_name, 'r')
        result= f.read()
        return result

#Class for testing the entire monitoring functionality	
class TestMonitoring(unittest.TestCase):
    filename = None
    noresponse = False
    delayed_response = False
    ipmonitor = None
    raiseException = False
    
    #Mock function for the call_subprocess	
    def mock_subprocess(self,cmd):
        file_name = './monitoring/test-data/' + self.filename
        f = open(file_name, 'r')
        result= f.read()
        #This is for simulating the case for which there is no response
        if self.noresponse:
            return None
        if self.delayed_response:
            time.sleep(2)
        if self.raiseException:
            time.sleep("3")
        return result

    #Mock function for send_ipmi_stats	
    def mock_send_ipmi_stats(self,*args, **kwargs):
        if args[3] == 'ipmi_data':
            if self.filename == 'sensor/quanta_sensor_expected_output.txt':
                verify_result.checkQuantaData(self,args[1])
            elif self.filename == 'sensor/supermicro_sensor_expected_output.txt':
                verify_result.checkSuperMicroData(self,args[1])
        elif args[3] == 'ipmi_chassis_data':
            if self.filename == 'chassis/chassis_expected_output.txt':
                verify_result.checkChassisData(self,args[1])
        elif args[3] == 'disk_list_tot':
            verify_result.checkDiskTotInfoData(self, args[1], package_installed)
        elif args[3] == 'disk_list':
            verify_result.checkDiskInfoData(self, args[1], package_installed)
   
    #setup function which sets up environemnt required for unit testing 
    def setUp(self):
        #Mock the ServerMgrlogger class. We will have our own log file
        flexmock(ServerMgrlogger, __new__=mock_logger)
        flexmock(ServerMgrSSHClient, __new__=mock_ServerMgrSSHClient)
        ServerMgrIPMIMonitoring.log_file='fake-logger.conf'
        self.ipmonitor = ServerMgrIPMIMonitoring(ServerMgrIPMIMonitoring, 10, 10)
        self.ipmonitor.base_obj.call_subprocess = self.mock_subprocess
        self.ipmonitor.send_ipmi_stats = self.mock_send_ipmi_stats

    def tearDown(self):
        global package_installed
        self.ipmonitor = None
        self.filename = None
        self.noresponse = False
        self.delayed_response = False
        self.raiseException = False
        package_installed = True

    def testSensorData(self):
        supported_sensors = ['FAN|.*_FAN', '^PWR', '.*Temp', '.*_Power']
        #Simulate correct Qunata sensor info output
        self.filename = 'sensor/quanta_sensor_expected_output.txt'
        self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

        #Simulate correct SuperMicro sensor info output
        self.filename = 'sensor/supermicro_sensor_expected_output.txt'
        self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

        #Simulate IPMI2.0 output
        self.filename = 'sensor/noipmi_output.txt'
        self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

        #Simulate wrong output
        self.filename = 'sensor/sensor_wrongoutput.txt'
        #Make sure the exception is raised. If the exception is not raised the test case will fail
        with self.assertRaises(Exception):
            self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

        #Simulate no response from device
        self.noresponse = True
        self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

        #Simulate delayed response from the device
        self.noresponse = False
        self.delayed_response = True
        self.filename = 'sensor/quanta_sensor_expected_output.txt'
        self.ipmonitor.fetch_and_process_monitoring("dummy", "dummy", "dummy", "dummy", "dummy",supported_sensors)

    def testChassisData(self):
        self.filename = 'chassis/chassis_expected_output.txt'
        self.ipmonitor.fetch_and_process_chassis("dummy", "dummy", "dummy", "dummy", "dummy")
        with self.assertRaises(Exception):
            self.raiseException = True
            self.ipmonitor.fetch_and_process_chassis("dummy", "dummy", "dummy", "dummy", "dummy")

    def testDiskInfo(self):
        global package_installed
        sshclient = ServerMgrSSHClient(None)
        sshclient.filename = 'disk_info/disk_info_expected_output.txt'
        self.ipmonitor.fetch_and_process_disk_info("dummy", "dummy", sshclient)
        #Test the case where the diff between the previous and current iteration is sent
        sshclient.filename = 'disk_info/disk_info_diff_expected_output.txt'
        self.ipmonitor.fetch_and_process_disk_info("dummy", "dummy", sshclient)
        #Test the situation where the sysstat package is not installed on the target node
        package_installed = False
        self.ipmonitor.fetch_and_process_disk_info("dummy", "dummy", sshclient)
        sshclient.filename = 'disk_info/disk_info_wrong_output.txt'
        #Make sure the exception is raised. If the exception is not raised the test case will fail
        package_installed = True
        with self.assertRaises(Exception):
            self.ipmonitor.fetch_and_process_disk_info("dummy","dummy",sshclient)

#Create a TestSuite for the testing the entire Monitoring functionality
def monitoring_suite():
    suite = unittest.TestSuite()
    suite.addTest(TestMonitoring('testSensorData'))
    suite.addTest(TestMonitoring('testChassisData'))
    suite.addTest(TestMonitoring('testDiskInfo'))
    return suite

#Run the Monitoring testsuite when this scrip is run
if __name__ == '__main__':
    mySuite = monitoring_suite()
    runner = unittest.TextTestRunner()
    runner.run(mySuite)
