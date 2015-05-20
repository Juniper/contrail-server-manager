#!/usr/bin/python

import pdb
import re 
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_exception import ServerMgrException as ServerMgrException


class ServerMgrValidations:
    def validate_tor_config(self, input_data):
        #self._smgr_log.log(self._smgr_log.DEBUG, "validate input_data=> %s" %(input_data))
        if 'top_of_rack' not in input_data:
            return (1, "top_of_rack configuration not found")
        tor_config = input_data['top_of_rack']
        switch_list = tor_config.get('switches', "")
        if not switch_list:
            return (1, "switches config not found")
        num_switch = len(switch_list)
        self._smgr_log.log(self._smgr_log.DEBUG, "validate input_data switch_len => %s" %(num_switch))
        if num_switch > 128:
            self._smgr_log.log(self._smgr_log.DEBUG, "validate input_data switch_len => %s" %(num_switch))
            return (1, "More than 128 switches are not supported")

        ## check for all mandatory params
        required_params = {'id': 'positive_number',
                           'ip_address':'ip_address',
                           'tunnel_ip_address': 'ip_address', 
                           'switch_name':'hostname',
                           'type': {'fixed': ['ovs']},
                           'ovs_protocol': {'fixed': ['tcp']},
                           'ovs_port':'port',
                           'http_server_port':'port',
                           'vendor_name':'string'}
        ## chcek if ID, port_numer, IP-address, hostnames are valid
        ## chcek if all IDs are unique
        ## check if all switch_names are unique
        id_set = set()
        ip_address_set = set()
        hostname_set = set()
        for  switch in switch_list:
            #data += '  %s%s:\n' %(switch['switch_name'],switch['id'])
            if 'id' in switch:
                if not switch['id'] or switch['id'] == "":
                    return (1, "param 'id' is empty for a switch config")
            else:
                return (1, "param 'id' not found for a switch")

            for param in required_params:
                if param in switch:
                    if not switch[param] or switch[param] == "":
                        msg = "param '%s' is empty for %s"  %(param, switch['id'])
                        return (1, msg)
                    else:
                        ## we should validate the param now
                        self._smgr_log.log(self._smgr_log.DEBUG, "validate switch-config => %s" %(required_params[param]))
                        if required_params[param] == 'positive_number':
                            status,msg = self.is_valid_number(switch[param])
                        elif required_params[param] == 'ip_address':
                            status,msg = self.is_valid_ip_address(switch[param])
                        elif required_params[param] == 'hostname':
                            status,msg = self.is_valid_hostname(switch[param])
                        elif required_params[param] == 'port':
                            status,msg = self.is_valid_port(switch[param])
                        elif required_params[param] == 'string':
                            self._smgr_log.log(self._smgr_log.DEBUG, "validate string => %s" %(switch[param]))
                        elif type(required_params[param]) == dict:
                            subtype=required_params[param]
                            if 'fixed' in subtype:
                                if switch[param] not in subtype['fixed']:
                                    msg = "param %s for switch %s has invalid value" %(param, switch['id'])
                                    status = 1
                        else:
                            self._smgr_log.log(self._smgr_log.DEBUG, "invalid type for => %s" %(required_params[param]))
                            msg = "param %s has invalid type for validation" %(required_params[param])
                            return (1, msg)

                        if status != 0:
                            msg = "switch config %s has invalid value '%s' for %s" %(switch['id'], switch[param], param)
                            return ("1", msg)
                else:
                    msg = "param '%s' not found for switch with 'id' as %s" \
                          %(param, switch['id'])
                    return (1, msg)

            ## add the value to set()
            if switch['id'] in id_set:
                msg = "switch id %s is duplicate" %(switch['id'])
                return (1, msg)
            else:
                id_set.add(switch['id'])

            if switch['ip_address'] in ip_address_set:
                msg = "switch %s has duplicate ip_address" %(switch['id'])
                return (1, msg)
            else:
                ip_address_set.add(switch['ip_address'])

            if switch['switch_name'] in hostname_set:
                msg = "switch id %s has duplicate hostname" %(switch['id'])
                return (1, msg)
            else:
                hostname_set.add(switch['switch_name'])

        return (0, "")
   
        
    def is_valid_hostname (self, hostname):
        if len(hostname) > 255:
            return (1, "hostname length is more than 255")

        if hostname[-1] == ".":
            hostname = hostname[:-1] # strip exactly one dot from the right, if present

        allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
        regex_status = all(allowed.match(x) for x in hostname.split("."))
        status = 1
        if regex_status:
            status = 0
        self._smgr_log.log(self._smgr_log.DEBUG, "validate hostname=> %s , %s" %(hostname, status))
        return (status, "")

    def is_valid_ip_address(self, ip_address):
        self._smgr_log.log(self._smgr_log.DEBUG, "validate ip_address => %s" %(ip_address))
        msg = ""
        pattern = r"\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        if re.match(pattern,ip_address):
            status = 0
        else:
            status = 1
            msg = "Invalid IP Address"

        return (status, msg)
    
    def is_valid_port(self, port_number):
        self._smgr_log.log(self._smgr_log.DEBUG, "validate port => %s" %(port_number))
        status,msg = self.is_valid_number(port_number)
        if status == 0:
            ## check for range of port number
            if int(port_number) > 65535 or int(port_number) < 1:
                msg = "port %s has invalid range" %(port_number)
                status =  1
                
        return (status, msg)
    
    def is_valid_protocol(self, protocol):
        self._smgr_log.log(self._smgr_log.DEBUG, "validate protocol => %s" %(protocol))
        return (0, "")

    def is_valid_number(self, number):
        self._smgr_log.log(self._smgr_log.DEBUG, "validate valid number => %s" %(number))
        if number.isdigit():
            return (0, "")
        else:
           return (1, "invalid number")

    def __init__(self):
        self._smgr_log = ServerMgrlogger()
        self._smgr_log.log(self._smgr_log.DEBUG, "ServerMgrValidations Init")

if __name__ == "__main__":
    pass
