#!/usr/bin/python

import sys
import pdb
import logging
import logging.config
import logging.handlers
import inspect
import os

_DEF_SM_BASELOG_PATH = '/var/log/contrail-server-manager/'
_DEF_SM_PROVLOG_PATH = _DEF_SM_BASELOG_PATH + 'provision/'
_DEF_SM_REIMGLOG_PATH = _DEF_SM_BASELOG_PATH + 'reimage/'

def common_log(log_obj, level, msg):
    try:
        if level == "debug":
            log_obj.debug(msg)
        elif level == "info":
            log_obj.info(msg)
        elif level == "warn":
            log_obj.warn(msg)
        elif level == "error":
            log_obj.error(msg)
        elif level == "critical":
            log_obj.critical(msg)
    except formatException as e:
      print "format exception"
    except Exception as e:
      print "Error logging msg"
    
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

# python singleton with parameters
# for the same parameter you get the same object
class Singleton(type):
    '''Reference code: https://gist.github.com/noamkush/856ccc86734f6301689a'''
    _instances = {}
    _init = {}

    def __init__(cls, name, bases, dct):
        cls._init[cls] = dct.get('__init__', None)

    def __call__(cls, *args, **kwargs):
        init = cls._init[cls]
        if init is not None:
            key = (cls, frozenset(
                    inspect.getcallargs(init, None, *args, **kwargs).items()))
        else:
            key = cls

        if key not in cls._instances:
            cls._instances[key] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[key]

class SMProvisionLogger(object):
    __metaclass__ = Singleton
    _smgr_prov_log = None

    def __init__(self, name):
        self._smgr_prov_log = logging.getLogger(name)
        self._smgr_prov_log.setLevel(logging.DEBUG)
        if not os.path.exists(_DEF_SM_PROVLOG_PATH):
            os.makedirs(_DEF_SM_PROVLOG_PATH)
        handler = logging.handlers.RotatingFileHandler(os.path.join(_DEF_SM_PROVLOG_PATH, name + '_provision.log'),maxBytes=100*1000*1024, backupCount=10)
        self._smgr_prov_log.addHandler(handler)

    def log(self,level,msg):
        common_log(self._smgr_prov_log,level,msg)


# THIS CLASS IS NOT WORKING AS EXPECTED NOW
# WILL REVISIT THIS ONE
class SMReimageLogger(object):
    __metaclass__ = Singleton
    _smgr_reimg_log = None
    
    def __init__(self, name):
        self._smgr_reimg_log = logging.getLogger(name)
        self._smgr_reimg_log.setLevel(logging.INFO)
        if not os.path.exists(_DEF_SM_REIMGLOG_PATH):
            os.makedirs(_DEF_SM_REIMGLOG_PATH)
        handler = logging.handlers.RotatingFileHandler(os.path.join(_DEF_SM_REIMGLOG_PATH, 'reimage.log'),maxBytes=100*1000*1024, backupCount=10)
        self._smgr_reimg_log.addHandler(handler)
    
    def log(self,level,msg):
        common_log(self._smgr_reimg_log,level,msg)

if __name__ == "__main__":
    smgr_log = ServerMgrlogger()
    smgr_log.log(smgr_log.DEBUG, "test log ")
    smgr_log.log("info", "INFO log %s" % "Thilak")
    prov_log =  SMProvisionLogger('server1')
    prov_log.log("debug", "test log ")
    reimg_log =  SMReimageLogger()
    reimg_log.log("debug", "test2 log ")
    prov_log =  SMProvisionLogger('server1')
    prov_log.log("debug", "test3 log ")
    prov_log =  SMProvisionLogger('server3')
    prov_log.log("debug", "test4 log ")
    reimg_log =  SMReimageLogger()
    reimg_log.log("debug", "test6 log ")
