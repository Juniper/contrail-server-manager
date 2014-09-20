import os
import syslog
import time
import signal
import sys
import re
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

    def return_impi_call(self, ipmi_list=None):
        if ipmi_list is None:
            cmd = 'ipmitool -H 10.87.129.207 -U admin -P admin sdr list all'
            result = self.call_subprocess(cmd)
            return {"result": result}
        else:
            results_dict = {}
            for address in ipmi_list:
                cmd = 'ipmitool -H ' + str(address) + ' -U admin -P admin sdr list all'
                print cmd
                result = self.call_subprocess(cmd)
                print result
                results_dict[str(address)] = result
            return results_dict

    def call_subprocess(self, cmd):
        times = datetime.datetime.now()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        return p.stdout.read()

    def filter_impi_results(self, results_dict, key, match_patterns):
        return_data = dict()
        if len(results_dict.keys()) == 1 and "result" in results_dict:
            return_data = dict()
            fileoutput = cStringIO.StringIO(results_dict["result"])
            return_data[key] = dict()
            for line in fileoutput:
                reading = line.split("|")
                sensor = reading[0].strip()
                for pattern in match_patterns:
                    if re.match(pattern, sensor):
                        return_data[key][reading[0].strip()] = list()
                        return_data[key][reading[0].strip()].append(reading[1].strip())
                        return_data[key][reading[0].strip()].append(reading[2].strip())
        elif len(results_dict.keys()) >= 1 and "result" not in results_dict:
            for server in results_dict:
                return_data[server] = dict()
                fileoutput = cStringIO.StringIO(results_dict[server])
                return_data[server][key] = dict()
                for line in fileoutput:
                    reading = line.split("|")
                    sensor = reading[0].strip()
                    for pattern in match_patterns:
                        if re.match(pattern, sensor):
                            return_data[server][key][reading[0].strip()] = list()
                            return_data[server][key][reading[0].strip()].append(reading[1].strip())
                            return_data[server][key][reading[0].strip()].append(reading[2].strip())
        else:
            return_data = None
        return return_data

    def get_env_details(self, ipmi_list=None):
        print ipmi_list
        match_patterns = ['^SYS_FAN', '^PWR', 'CPU[0-9] Temp', '.*_Temp']
        key = "ENV"
        results_dict = dict(self.return_impi_call(ipmi_list))
        return_data = self.filter_impi_results(results_dict, key, match_patterns)
        return return_data


    def get_fan_details(self, ipmi_list=None):
        match_patterns = ['^SYS_FAN']
        key = "FAN"
        results_dict = dict(self.return_impi_call(ipmi_list))
        return_data = self.filter_impi_results(results_dict, key, match_patterns)
        return return_data

    def get_temp_details(self, ipmi_list=None):
        match_patterns = ['CPU[0-9] Temp', '.*_Temp']
        key = "TEMP"
        results_dict = dict(self.return_impi_call(ipmi_list))
        return_data = self.filter_impi_results(results_dict, key, match_patterns)
        return return_data

    def get_pwr_consumption(self, ipmi_list=None):
        match_patterns = ['^PWR']
        key = "PWR"
        results_dict = dict(self.return_impi_call(ipmi_list))
        return_data = self.filter_impi_results(results_dict, key, match_patterns)
        return return_data

