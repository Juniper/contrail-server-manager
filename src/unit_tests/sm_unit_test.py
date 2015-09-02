import sys, os, time, pdb
import unittest
sys.path.append(os.path.abspath(os.pardir))
sys.path.append(os.path.abspath('../..'))
from test_sm_rest_api.test_sm_rest_api import *
from monitoring.monitoring import *

#Create a TestSuite for the running the unit-test for the entire ServerManger
def sm_unit_test_suite():
    suite = unittest.TestSuite()
    #Adding the Monitoring uni-test suite
    suite.addTest(monitoring_suite())
    suite.addTest(sm_server_rest_api_suite())
    suite.addTest(sm_cluster_rest_api_suite())
    return suite

#Run the entire SM unit testsuite when this scrip is run
if __name__ == '__main__':
    mySuite = sm_unit_test_suite()
    runner = unittest.TextTestRunner()
    runner.run(mySuite)
