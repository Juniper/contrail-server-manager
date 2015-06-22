import sys, os, time, pdb
import unittest
sys.path.append(os.path.abspath(os.pardir))
sys.path.append(os.path.abspath('../..'))
from monitoring.monitoring import *


#Create a TestSuite for the testing the entire Monitoring functionality
def sm_unit_test_suite():
    suite = unittest.TestSuite()
    suite.addTest(monitoring_suite())
    return suite

#Run the Monitoring testsuite when this scrip is run
if __name__ == '__main__':
        mySuite = sm_unit_test_suite()
        runner = unittest.TextTestRunner()
        runner.run(mySuite)
