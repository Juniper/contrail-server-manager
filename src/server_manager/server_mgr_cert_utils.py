#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_cert_utils.py
   Author : Prasad Miriyala
   Description : Cert utility
"""
import os
import subprocess
import sys
import logging
import logging.config
import logging.handlers
import inspect

__version__ = '1.0'

class Cert(object):

    _certs_log = None
    log_conf_file = '/opt/contrail/server_manager/logger.conf'
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

    def __init__(self):
        self._certs_log = self.initialize_logger()
        msg = ("Initializing Certs logger")
        self.log("info", msg)

    def initialize_logger(self):
        logging.config.fileConfig(self.log_conf_file)
        #create logger
        log = logging.getLogger('CERT')
        return log

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
                self._certs_log.debug(msg, extra=log_dict)
            elif level == self.INFO:
                self._certs_log.info(msg, extra=log_dict)
            elif level == self.WARN:
                self._certs_log.warn(msg, extra=log_dict)
            elif level == self.ERROR:
                self._certs_log.error(msg, extra=log_dict)
            elif level == self.CRITICAL:
                self._certs_log.critical(msg, extra=log_dict)
        except Exception as e:
            print "Error logging msg in Certs" + e.message

    def local_exec(self, cmd, error_on_fail=False):
        exit_status = 1
        self.log("info", '[localhost]: %s' % cmd)
        proc = subprocess.Popen(cmd, shell=True, close_fds=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            exit_status = 0
            self.log("error", stdout)
            self.log("error",stderr)
            if error_on_fail:
                raise RuntimeError('Command (%s) Failed' % cmd)
        return exit_status, stdout, stderr

    def generate_private_key(self, location, method='rsa', numbits=2048, force=False):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        exit_status, stdout, stderr = \
        self.local_exec('openssl genrsa -out %s' % (location), error_on_fail=True)
        return exit_status

    def generate_csr(self, location, private_key, subj='/', force=False):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        exit_status, stdout, stderr = \
            self.local_exec('openssl req -new -key %s -out %s -subj %s' % (private_key, location, subj), 
                           error_on_fail=True)
        return exit_status
    
    def generate_cert(self, location, key, openssl_cfg_file, root_pem='', csr='',
                      force=False, self_signed=False, subj='/',
                      days=3640, method='rsa', numbits=4096):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        if self_signed:
            cmd = 'openssl req -x509 -new -nodes -key %s -days %s -out %s -subj %s -config %s' % \
            (key, days, location, subj, openssl_cfg_file)
        else:
            cmd = 'openssl x509 -req -in %s -CA %s -CAkey %s -CAcreateserial -out %s -days %s -extensions v3_req -extfile %s' % \
            (csr, root_pem, key, location, days, openssl_cfg_file)
        exit_stats, stdout, stderr = self.local_exec(cmd, error_on_fail=True)
        return exit_status

if __name__ == '__main__':
    # update log level and log file
    log_level = [logging.ERROR, logging.WARN, \
                     logging.INFO, logging.DEBUG]
    cert_obj = Cert()
    cert_obj.log("info",'Executing: %s' % " ".join(sys.argv))
    # test code
    cert_obj.generate_private_key('test.key')
    cert_obj.generate_cert('test.pem', 'test.key', '/usr/lib/ssl/openssl.cnf', self_signed=True)
    cert_obj.generate_private_key('server.key')
    cert_obj.generate_csr('server.csr', 'server.key', subj='test')
    cert_obj.generate_cert('server.pem', 'test.key', '/usr/lib/ssl/openssl.cnf', 'test.pem', 'server.csr')
