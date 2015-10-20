#!/usr/bin/python

import sys
import pdb
import logging
import logging.config
import logging.handlers
import inspect
import os

class ServerMgrlogger(object):
    class _ServerMgrlogger:
        DEBUG = "debug"
        INFO = "info"
        WARN = "warn"
        ERROR = "error"
        CRITICAL = "critical"
        log_file = '/opt/contrail/server_manager/logger.conf'

        _smgr_log = None   
        def __init__(self):
            logging.config.fileConfig(self.log_file)
            #create logger
            self._smgr_log = logging.getLogger('SMGR')


        def log(self, level, msg):
            frame,filename,line_number,function_name,lines,index = inspect.stack()[1]
            log_dict = {}
            log_dict['log_frame'] = frame
            log_dict['log_filename'] = os.path.basename(filename)
            log_dict['log_line_number'] = line_number
            log_dict['log_function_name'] = function_name
            log_dict['log_line'] = lines
            log_dict['log_index'] = index
            try:
                if level == self.DEBUG:
                    self._smgr_log.debug(msg, extra = log_dict)
                elif level == self.INFO:
                    self._smgr_log.info(msg, extra = log_dict)
                elif level == self.WARN:
                    self._smgr_log.warn(msg, extra = log_dict)
                elif level == self.ERROR:
                    self._smgr_log.error(msg, extra = log_dict)
                elif level == self.CRITICAL:
                    self._smgr_log.critical(msg, extra = log_dict)
            except formatException as e:
                print "format exception"
            except Exception as e:
                print "Error logging msg"

        def set_level(self, log, level):
            print "set log level"

    _instance = None

    def __setattr__(self, name):
        return setattr(self._instance, name)

    def __getattr__(self, name):
        return getattr(self._instance, name)

    def __init__(self):
        if not ServerMgrlogger._instance:
            ServerMgrlogger._instance = ServerMgrlogger._ServerMgrlogger()

    def __new__(cls): # __new__ always a classmethod
        if not ServerMgrlogger._instance:
            ServerMgrlogger._instance = ServerMgrlogger._ServerMgrlogger()
        return ServerMgrlogger._instance



class ServerMgrTransactionlogger:
    GET_SMGR_CFG_ALL = "GET_SMGR_ALL"
    GET_SMGR_CFG_CLUSTER = "GET_SMGR_CLUSTER"
    GET_SMGR_CFG_SERVER = "GET_SMGR_SERVER"
    GET_SMGR_CFG_IMAGE = "GET_SMGR_IMAGE"
    GET_SMGR_CFG_STATUS = "GET_SMGR_STATUS"   
    GET_SMGR_CFG_CHASSIS_ID = "GET_SMGR_CHASSIS_ID"   
    GET_SMGR_CFG_TAG = "GET_SMGR_TAG"
    GET_SMGR_CFG_TABLE_COLUMNS = "GET_SMGR_TABLE_COLUMNS"

    PUT_SMGR_CFG_ALL = "PUT_SMGR_ALL"
    PUT_SMGR_CFG_CLUSTER = "PUT_SMGR_CLUSTER"
    PUT_SMGR_CFG_SERVER = "PUT_SMGR_SERVER"
    PUT_SMGR_CFG_IMAGE = "PUT_SMGR_IMAGE"
    PUT_SMGR_CFG_STATUS = "PUT_SMGR_STATUS"  
    PUT_SMGR_CFG_TAG = "PUT_SMGR_TAG"  

    DELETE_SMGR_CFG_ALL = "DELETE_SMGR_ALL"
    DELETE_SMGR_CFG_CLUSTER = "DELETE_SMGR_CLUSTER"
    DELETE_SMGR_CFG_SERVER = "DELETE_SMGR_SERVER"
    DELETE_SMGR_CFG_IMAGE = "DELETE_SMGR_IMAGE"
    DELETE_SMGR_CFG_STATUS = "DELETE_SMGR_STATUS"  

    MODIFY_SMGR_CFG_ALL = "MODIFY_SMGR_ALL"
    MODIFY_SMGR_CFG_CLUSTER = "MODIFY_SMGR_CLUSTER"
    MODIFY_SMGR_CFG_SERVER = "MODIFY_SMGR_SERVER"
    MODIFY_SMGR_CFG_IMAGE = "MODIFY_SMGR_IMAGE"
    MODIFY_SMGR_CFG_STATUS = "MODIFY_SMGR_STATUS"  

    SMGR_PROVISION = "SMGR_PROVISION"
    SMGR_REIMAGE = "SMGR_REIMAGE"
    SMGR_REBOOT = "SMGR_REBOOT"
    log_file = '/opt/contrail/server_manager/logger.conf'

    _smgr_trans_log = None
    def __init__(self):
        #Create transaction logger
        logging.config.fileConfig(self.log_file)

        self._smgr_trans_log = logging.getLogger('TRANSACTION')

    def log(self, data, transaction_type, success=True):
        msg = None
        if data.query_string == '':
            query_string = "ALL"
        else:
            query_string = data.query_string
        if success:
            success_str = "Success"
        else:
            success_str = "Failed"
        
        #Get the frame detail and so on
        msg = "ACTION %s: %s %s From %s %s" % \
            (transaction_type, data.url, query_string, data.remote_route, success_str)

        self._smgr_trans_log.error(msg)

    

if __name__ == "__main__":
    smgr_log = ServerMgrlogger()
    smgr_log.log(DEBUG, "test log ")
    smgr_log.log(INFO, "INFO log %s" % "Thilak")
