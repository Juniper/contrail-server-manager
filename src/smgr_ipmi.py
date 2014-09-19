import os
import syslog
import time
import signal
import sys
import abc
import datetime
import subprocess
import cStringIO
from threading import Thread
from smgr_env_base import DeviceEnvBase

# Signal handler function. Exit on CTRL-C
def exit_gracefully(signal, frame):
    #Perform any cleanup actions in the logging system
    print "Exit"
    sys.exit(0)


class Ipmi_EnvInfo(Thread, DeviceEnvBase):
    def __init__(self, val, frequency):
        ''' Constructor '''
        Thread.__init__(self)
        self.val = val
        self.freq = frequency

    def get_pwr_consumption(self):
        return 1200

    def call_subprocess(self, cmd):
        times = datetime.datetime.now()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        return p.stdout.read()

    def get_fan_details(self):
	supported_sensors = ['FAN', '^PWR', 'CPU[0-9] Temp', '.*_Temp']
                target_nodes = ['10.87.129.207', '10.87.129.208']
                while True:
                        for ip in target_nodes:
                                cmd = 'ipmitool -H %s -U admin -P admin sdr list all'% ip
                                print cmd
                                result = self.call_subprocess(cmd)
                                if result is not None:
                                        fileoutput = cStringIO.StringIO(result)
                                        for line in fileoutput:
                                                reading = line.split("|")
                                                sensor = reading[0].strip()
                                                for i in supported_sensors:
                                                        if re.search(i, sensor) is not None:
                                                                print "'%s' '%s' %s" % (reading[0].strip(), reading[1].strip(), reading[2].strip())
                        time.sleep(self.freq)
