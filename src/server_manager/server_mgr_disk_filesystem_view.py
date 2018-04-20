#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_disk_filesystem_view.py
   Author : Sivakumar Gurumurthy
   Description : Separate Module to get the Information of all the different filesystems and disks under them in a
   monitored server.
"""

import datetime
import subprocess
import time
import cStringIO
import re
import os
import signal
import math
import logging
import logging.config
import logging.handlers
from contrail_sm_monitoring.monitoring.ttypes import *
import inspect


class file_system_disk_view:
    file_system_list = []
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self):
        self.file_system_list = []
        logging.config.fileConfig('/opt/contrail/server_manager/logger.conf')
        # create logger
        self._monitoring_log = logging.getLogger('MONITORING')

    def log(self, level, msg):
        frame, filename, line_number, function_name, lines, index = inspect.stack()[1]
        log_dict = dict()
        log_dict['log_frame'] = frame
        log_dict['log_filename'] = os.path.basename(filename)
        log_dict['log_line_number'] = line_number
        log_dict['log_function_name'] = function_name
        log_dict['log_line'] = lines
        log_dict['log_index'] = index
        try:
            if level == self.DEBUG:
                self._monitoring_log.debug(msg, extra=log_dict)
            elif level == self.INFO:
                self._monitoring_log.info(msg, extra=log_dict)
            elif level == self.WARN:
                self._monitoring_log.warn(msg, extra=log_dict)
            elif level == self.ERROR:
                self._monitoring_log.error(msg, extra=log_dict)
            elif level == self.CRITICAL:
                self._monitoring_log.critical(msg, extra=log_dict)
        except Exception as e:
            print "Error logging msg in Mon" + e.message

    # This function just gets the disk_name name given the disk_name name in the file system output
    def get_disk_name(self, partition_name):
        try:
            disk_name = None
            #Get the lvm volumne group name
            #Get the lvm partition name after the last '/'
            pos = partition_name.rfind('/')
            if pos != -1:
                disk_name = disk_partition = partition_name[pos + 1:].strip()
                #Ignore the name after the last '-'
                pos = disk_partition.rfind('-')
                if pos != -1:
                    #Get the name before the last '-'
                    disk_name = disk_name_name = disk_partition[:pos]
                    #Check if there is double continous hypen in the name
                    pos = disk_name_name.find('--')
                    #If so remove one hypen
                    if pos != -1:
                        disk_name = disk_name_name[:pos] + disk_name_name[pos + 1:]
        except Exception as e:
            self.log("error", "Error in get_disk_name function: " + str(e.message))
        return disk_name

    #This function returns the list of physical disknames associated with the given lvm
    #More then one disk can be part of the same lvm
    #Same disk can be part of multiple lvm as well
    def get_lvm_physical_disk_names(self, lvm_vg_name, sshclient):
        try:
            lvm_physical_disk_names = []
            result = sshclient.exec_command('pvs')
            fileoutput = cStringIO.StringIO(result)
            for line in fileoutput:
                col_list = line.split()
                if col_list[1].strip() == lvm_vg_name:
                    lvm_physical_disk_names.append(self.get_disk_name(col_list[0].strip())[:-1])
        except Exception as e:
            self.log("error", "Error in get_lvm_physical_disk_names function: " + str(e.message))
        return lvm_physical_disk_names

    #Get the actual physical disk size in Kilobytes
    def get_physical_disk_size(self, disk_name, sshclient):
        try:
            #Get the actual physical disk size from lsblk command
            cmd = 'lsblk -b -d -o NAME,SIZE'
            result = sshclient.exec_command(cmd)
            if result:
                fileoutput = cStringIO.StringIO(result)
                for line in fileoutput:
                    cols = line.split()
                    #Check if the disk names match
                    if cols[0].strip() == disk_name:
                        #Convert the size which is in bytes to kilobytes
                        size = long(cols[1].strip()) / 1024
                        return size
        except Exception as e:
            self.log("error", "Error inget_lvm_physical_disk_namecal_disk_size function: " + str(e.message))
        return 0

    #The following function aggregates the size, used, availble for the same physical disk
    #The use percentage is calculated
    def aggregate_disk_data(self, physical_disk_view, file_system):
        physical_disk_view.disk_used += long(file_system.used)
        physical_disk_view.disk_available += long(file_system.available)

    #This function checks if the physical disk name already exists in the lists
    def get_existing_disk(self, physical_disks, disk_name):
        for file_system in self.file_system_list:
            physical_disks = file_system.physical_disks
            for disks in physical_disks:
                if disks.name == disk_name:
                    return disks
        return None

    #This function checks if the disk name is already there in the dictionary
    #if so just aggregates data, otherwise it creates a new physical disk view
    #instance and adds data to it
    def add_disk_view(self, file_system, disk_name, sshclient, lvm_disk_size=0):
        try:
            #It's a new physical disk name. Create a physical_disk_view instance
            disk_view = physical_disk_view()
            #Get the actual physical disk size
            disk_view.disk_size_kb = self.get_physical_disk_size(disk_name, sshclient)
            disk_view.disk_name = disk_name
            #If lvm disk size if not zero then multiple physical disks are part of this lvm
            #Calculate the used and available propotional to the size of the disk
            if lvm_disk_size != 0:
                disk_view.disk_used_kb = long(
                    math.ceil(float(disk_view.disk_size_kb * long(file_system.used_kb)) / float(lvm_disk_size)))
                disk_view.disk_available_kb = long(
                    math.ceil(float(disk_view.disk_size_kb * long(file_system.available_kb)) / float(lvm_disk_size)))
            else:
                disk_view.disk_used_kb = long(file_system.used_kb)
                disk_view.disk_available_kb = long(file_system.available_kb)
            #Append the disk_view to physical_disks list in the file_system view
            file_system.physical_disks.append(disk_view)
        except Exception as e:
            self.log("error", "Error add_disk_view function: " + str(e.message))
        return 0

    #Get the list of all physical disk associated with the given lvm
    #This function gets the disk view of the system
    def get_disk_view(self, file_system, sshclient):
        try:
            #Check if this is partition of the physical disks
            if file_system.type == 'partition':
                #Get the actual physical disk name by removing the last char which is typically a number
                disk_name = self.get_disk_name(file_system.fs_name)[:-1]
                self.add_disk_view(file_system, disk_name, sshclient)
            #else it is an lvm
            else:
                #Get the physical disk names associated with this lvm
                lvm_physical_disk_name_list = self.get_lvm_physical_disk_names(self.get_disk_name(file_system.fs_name),
                                                                               sshclient)
                #Get the lvm size from the 'df' output
                lvm_size = long(file_system.size_kb)
                #Get the number of disks in lvm
                num_disks_in_lvm = len(lvm_physical_disk_name_list)
                for disk_name in lvm_physical_disk_name_list:
                    #if there is more than one physical disks in an lvm then worry about
                    #passing the lvm_size, else don't pass anything
                    #If more than 1 disks in lvm then only we need to divided the used and available data
                    #propotionate to the size of the disk
                    #import pdb; pdb.set_trace()
                    if num_disks_in_lvm > 1:
                        self.add_disk_view(file_system, disk_name, sshclient, lvm_size)
                    else:
                        self.add_disk_view(file_system, disk_name, sshclient)
            #Calculate teh used_percentage
            for value in file_system.physical_disks:
                value.disk_used_percentage = int(math.ceil(float(value.disk_used_kb * 100) / float(value.disk_size_kb)))
        except Exception as e:
            self.log("error", "Error get_disk_view function: " + str(e.message))

    #This function determines the type of disk and assings accordingly
    def find_and_assign_disk_type(self, file_system, partition, sshclient):
        try:
            partition_name = ""
            pos = partition.rfind('/')
            if pos != -1:
                partition_name = partition[pos + 1:].strip()
            cmd = 'lsblk | grep ' + partition_name + '| grep lvm'
            #result = call_subprocess(cmd)
            result = sshclient.exec_command(cmd)
            if result:
                file_system.type = 'lvm'
            else:
                file_system.type = 'partition'
        except Exception as e:
            self.log("error", "Error find_and_assign_disk_type function: " + str(e.message))

    #This function gives the file system view as the output of the 'df' command
    def get_file_system_view(self, sshclient):
        try:
            count = 1
            #Keep track of the col index. The column values may be wrapped in multiple lines
            #Make sure all the 6 columns are read even if it spans multiple lines
            #Get the column values
            col_index = 0
            #If this condition is true it means that we have 'lvm' in this server
            #Handle the 2 possible cases here:
            #1.Multiple physical disks can be in one lvm
            #2.One or more disks can be in multiple lvms
            #cmd_df_output = call_subprocess('df')
            cmd_df_output = sshclient.exec_command('df')
            fileoutput = cStringIO.StringIO(cmd_df_output)
            for line in fileoutput:
                #Skip the first line of the output which just has column names
                if count == 1:
                    count = count + 1
                    continue
                cols = line.split()
                #Get the disk partition name
                partition = cols[0].strip()
                #print "line: ",count,line
                #If the column value starts with '/' it means that it is a disk partition
                #The basic assumption here is that only either the 'Filesystem' or 'Mounted on'
                #output can be long enough for the lines to wrap
                if partition.startswith('/') and col_index == 0:
                    file_system = file_system_view()
                    file_system.physical_disks = []
                    #Find the disk type and assign the type
                    self.find_and_assign_disk_type(file_system, partition, sshclient)
                    file_system.fs_name = partition
                    try:
                        #Get the values of other columns
                        file_system.size_kb = long(cols[1].strip())
                        file_system.used_kb = long(cols[2].strip())
                        file_system.available_kb = long(cols[3].strip())
                        file_system.used_percentage = int(cols[4].strip()[:-1])
                        #Now either the 'filesystem' name or 'Mounted on' path can be long
                        #and the output can wrap
                        #Set the col_index value to 4 so that we know we have processed 4
                        #columns so far
                        col_index = 4
                        file_system.mountpoint = cols[5].strip()
                        #All columns are successfully parsed. Rest the col_index to zero
                        col_index = 0
                        self.get_disk_view(file_system, sshclient)
                        self.file_system_list.append(file_system)
                    except IndexError:
                        #The particular column value is not there. It's a wrapped ouput
                        continue
                #If this condition is true then it means that the 'Mounted on' path is wrapped into the next line
                #and the rest of the columns have been processed
                if partition.startswith('/') and col_index == 4:
                    file_system.mountpoint = cols[0].strip()
                    self.get_disk_view(file_system, sshclient)
                    self.file_system_list.append(file_system)
                #if the column value starts with a number it means the disk partition name
                #is too long and the rest of the column values have moved to the next line
                elif partition.isdigit():
                    try:
                        file_system.size_kb = long(cols[0].strip())
                        file_system.used_kb = long(cols[1].strip())
                        file_system.available_kb = long(cols[2].strip())
                        file_system.used_percentage = int(cols[3].strip()[:-1])
                        col_index = 4
                        file_system.mountpoint = cols[4].strip()
                        col_index = 0
                        self.get_disk_view(file_system, sshclient)
                        self.file_system_list.append(file_system)
                    except IndexError:
                        continue
                count = count + 1
        except Exception as e:
            self.log("error", "Error get_file_system_view function: " + str(e.message))
        return self.file_system_list


