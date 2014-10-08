#!/usr/bin/python

import sys
import pdb
import logging
import logging.config
import logging.handlers

class ServerMgrlogger:
    class _ServerMgrlogger:
        DEBUG = "debug"
        INFO = "info"
        WARN = "warn"
        ERROR = "error"
        CRITICAL = "critical"

        _smgr_log = None   
        def __init__(self):
            print "Logger init" 
            logging.config.fileConfig('logger.conf')

            #create logger
            self._smgr_log = logging.getLogger('SMGR')


        def log(self, level, msg):
            print "Log command"
            if level == self.DEBUG:
                self._smgr_log.debug(msg)
            elif level == self.INFO:
                self._smgr_log.info(msg)
            elif level == self.WARN:
                self._smgr_log.warn(msg)
            elif level == self.ERROR:
                self._smgr_log.error(msg)
            elif level == self.CRITICAL:
                self._smgr_log.critical(msg)

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
        if not ServerMgrlogger._intance:
            ServerMgrlogger._instance = ServerMgrlogger._ServerMgrlogger()
        return ServerMgrlogger._instance



class ServerMgrTransactionlogger:
    GET_SMGR_CFG_ALL = "GET_SMGR_ALL"
    GET_SMGR_CFG_CLUSTER = "GET_SMGR_CLUSTER"
    GET_SMGR_CFG_SERVER = "GET_SMGR_SERVER"
    GET_SMGR_CFG_IMAGE = "GET_SMGR_IMAGE"
    GET_SMGR_CFG_STATUS = "GET_SMGR_STATUS"   
    GET_SMGR_CFG_TAG = "GET_SMGR_TAG"   

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

    _smgr_trans_log = None
    def __init__(self):
        print "Transaction Logger init"

        #Create transactio logger
        logging.config.fileConfig('logger.conf')

        self._smgr_trans_log = logging.getLogger('TRANSACTION')

    def log(self, data, transaction_type, success=True):
        msg = None
        if transaction_type == self.GET_SMGR_CFG_ALL:
            msg = "ACTION %s: %s %s" % \
                     (self.GET_SMGR_CFG_ALL, data.query_string, success)
        elif transaction_type == self.GET_SMGR_CFG_CLUSTER:
            msg = "ACTION %s: %s %s" % \
                       (self.GET_SMGR_CFG_CLUSTER, data.query_string, success)
        elif transaction_type == self.GET_SMGR_CFG_SERVER:
             msg = "ACTION %s: %s %s" % \
                        (self.GET_SMGR_CFG_SERVER, data.query_string, success)
        elif transaction_type == self.GET_SMGR_CFG_IMAGE:
             msg = "ACTION %s: %s %s" % \
                        (self.GET_SMGR_CFG_IMAGE, data.query_string, success)
        elif transaction_type == self.GET_SMGR_CFG_TAG:
             msg = "ACTION %s: %s %s" % \
                        (self.GET_SMGR_CFG_TAG, data.query_string, success)
        elif transaction_type == self.PUT_SMGR_CFG_ALL:
            msg = "ACTION %s: %s %s" % \
                     (transaction_type, data.query_string, success)
        elif transaction_type == self.PUT_SMGR_CFG_CLUSTER:
            msg = "ACTION %s: %s %s" % \
                       (transaction_type, data.query_string, success)
        elif transaction_type == self.PUT_SMGR_CFG_SERVER:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.PUT_SMGR_CFG_IMAGE:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.PUT_SMGR_CFG_TAG:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.DELETE_SMGR_CFG_ALL:
            msg = "ACTION %s: %s %s" % \
                     (transaction_type, data.query_string, success)
        elif transaction_type == self.DELETE_SMGR_CFG_CLUSTER:
            msg = "ACTION %s: %s %s" % \
                       (transaction_type, data.query_string, success)
        elif transaction_type == self.DELETE_SMGR_CFG_SERVER:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.DELETE_SMGR_CFG_IMAGE:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.MODIFY_SMGR_CFG_ALL:
            msg = "ACTION %s: %s %s" % \
                     (transaction_type, data.query_string, success)
        elif transaction_type == self.MODIFY_SMGR_CFG_CLUSTER:
            msg = "ACTION %s: %s %s" % \
                       (transaction_type, data.query_string, success)
        elif transaction_type == self.MODIFY_SMGR_CFG_SERVER:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.MODIFY_SMGR_CFG_IMAGE:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.SMGR_REIMAGE:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.SMGR_REBOOT:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)
        elif transaction_type == self.SMGR_PROVISION:
             msg = "ACTION %s: %s %s" % \
                        (transaction_type, data.query_string, success)

        self._smgr_trans_log.error(msg)

    

if __name__ == "__main__":
    smgr_log = ServerMgrlogger()
    smgr_log.log(DEBUG, "test log ")
    smgr_log.log(INFO, "INFO log %s" % "Thilak")
