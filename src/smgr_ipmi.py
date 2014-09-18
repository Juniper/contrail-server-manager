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
        cmd = 'ipmitool -H 10.87.129.207 -U admin -P admin sdr list all'
        result = self.call_subprocess(cmd)
        if result is not None:
            fileoutput = cStringIO.StringIO(result)
            return_data = dict()
            return_data['FAN'] = dict()
            for line in fileoutput:
                reading = line.split("|")
                sensor = reading[0].strip()
                if "FAN" in sensor:
                    return_data['FAN'][reading[0].strip()] = list()
                    return_data['FAN'][reading[0].strip()].append(reading[1].strip())
                    return_data['FAN'][reading[0].strip()].append(reading[2].strip())
        else:
            return_data = 0
        return return_data