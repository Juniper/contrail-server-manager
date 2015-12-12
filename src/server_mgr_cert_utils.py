#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_mgr_cert_utils.py
   Author : Prasad Miriyala
   Description : Cert utility
"""
import os
import logging
import subprocess
import sys

__version__ = '1.0'

log = logging.getLogger('smgrcerts')
log.setLevel(logging.DEBUG)

class CertsLogger(object):
    @staticmethod
    def initialize_logger(log_file='smgrcerts.log', log_level=40, stdout=True):
        log = logging.getLogger('smgrcerts')
        file_h = logging.FileHandler(log_file)
        file_h.setLevel(logging.DEBUG)
        long_format = '[%(asctime)-15s: %(filename)s:%(lineno)s:%(funcName)s: %(levelname)s] %(message)s'
        file_formatter = logging.Formatter(long_format)
        file_h.setFormatter(file_formatter)
        log.addHandler(file_h)
        if not stdout:
            return
        stream_h = logging.StreamHandler(sys.stdout)
        stream_h.setLevel(log_level)
        short_format = '[%(asctime)-15s: %(funcName)s] %(message)s'
        stream_formatter = logging.Formatter(short_format)
        stream_h.setFormatter(stream_formatter)
        log.addHandler(stream_h)

class Cmd(object):
    @staticmethod
    def local_exec(cmd, error_on_fail=False):
        exit_status = 1
        log.info('[localhost]: %s' % cmd)
        proc = subprocess.Popen(cmd, shell=True, close_fds=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            exit_status = 0
            log.error(stdout)
            log.error(stderr)
            if error_on_fail:
                raise RuntimeError('Command (%s) Failed' % cmd)
        return exit_status, stdout, stderr

class Cert(object):
    @staticmethod
    def generate_private_key(location, method='rsa', numbits=2048, force=False):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        exit_status, stdout, stderr = \
        Cmd.local_exec('openssl genrsa -out %s' % (location), error_on_fail=True)
        return exit_status

    @staticmethod
    def generate_csr(location, private_key, subj='/', force=False):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        exit_status, stdout, stderr = \
            Cmd.local_exec('openssl req -new -key %s -out %s -subj %s' % (private_key, location, subj), 
                           error_on_fail=True)
        return exit_status
    
    
    @staticmethod
    def generate_cert(location, key, root_pem='', csr='',
                      force=False, self_signed=False, subj='/',
                      days=3640, method='rsa', numbits=4096):
        exit_status = 1
        if not force:
            if os.path.isfile(location):
                return exit_status
        if self_signed:
            cmd = 'openssl req -x509 -new -nodes -key %s -days %s -out %s -subj %s' % \
            (key, days, location, subj)
        else:
            cmd = 'openssl x509 -req -in %s -CA %s -CAkey %s -CAcreateserial -out %s -days %s' % \
            (csr, root_pem, key, location, days)
        exit_stats, stdout, stderr = Cmd.local_exec(cmd, error_on_fail=True)
        return exit_status


if __name__ == '__main__':
    log.info('Executing: %s' % " ".join(sys.argv))
    # update log level and log file
    log_level = [logging.ERROR, logging.WARN, \
                     logging.INFO, logging.DEBUG]
    CertsLogger.initialize_logger(log_file='smgrcerts.log',
                            log_level=log_level[3], stdout=True)
    # test code
    Cert.generate_private_key('test.key')
    Cert.generate_cert('test.pem', 'test.key', self_signed=True)
    Cert.generate_private_key('server.key')
    Cert.generate_csr('server.csr', 'server.key', subj='test')
    Cert.generate_cert('server.pem', 'test.key', 'test.pem', 'server.csr')





