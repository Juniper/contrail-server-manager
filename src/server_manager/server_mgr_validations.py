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
        required_params = {'agent_id': 'positive_number',
                           'ip':'ip_address',
                           'tunnel_ip': 'ip_address',
                           'agent_name':'string',
                           'name':'string',
                           'tsn_name':'string',
                           'type': {'fixed': ['ovs']},
                           'ovs_protocol': {'fixed': ['tcp', 'pssl']},
                           'ovs_port':'port',
                           'agent_ovs_ka':'positive_number',
                           'agent_http_server_port':'port',
                           'vendor_name':'string'}
        ## chcek if ID, port_numer, IP-address, hostnames are valid
        ## chcek if all IDs are unique
        ## check if all switch_names are unique
        id_set = set()
        ip_address_set = set()
        hostname_set = set()
        for  switch in switch_list:
            #data += '  %s%s:\n' %(switch['switch_name'],switch['id'])
            if 'agent_id' in switch:
                if not switch['agent_id'] or switch['agent_id'] == "":
                    return (1, "param 'agent_id' is empty for a switch config")
            else:
                return (1, "param 'agent_id' not found for a switch")

            for param in required_params:
                if param in switch:
                    if not switch[param] or switch[param] == "":
                        msg = "param '%s' is empty for %s"  %(param, switch['agent_id'])
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
                                    msg = "param %s for switch %s has invalid value" %(param, switch['agent_id'])
                                    status = 1
                        else:
                            self._smgr_log.log(self._smgr_log.DEBUG, "invalid type for => %s" %(required_params[param]))
                            msg = "param %s has invalid type for validation" %(required_params[param])
                            return (1, msg)

                        if status != 0:
                            msg = "switch config %s has invalid value '%s' for %s" %(switch['agent_id'], switch[param], param)
                            return ("1", msg)
                else:
                    msg = "param '%s' not found for switch with 'agent_id' as %s" \
                          %(param, switch['agent_id'])
                    return (1, msg)

            ## add the value to set()
            if switch['agent_id'] in id_set:
                msg = "switch id %s is duplicate" %(switch['agent_id'])
                return (1, msg)
            else:
                id_set.add(switch['agent_id'])

            if switch['ip'] in ip_address_set:
                msg = "switch %s has duplicate ip_address" %(switch['agent_id'])
                return (1, msg)
            else:
                ip_address_set.add(switch['ip'])

            if switch['name'] in hostname_set:
                msg = "switch id %s has duplicate hostname" %(switch['agent_id'])
                return (1, msg)
            else:
                hostname_set.add(switch['name'])

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

    #The following logic the interface type of servers
    #Will return single if all the servers are single
    #Will return multi if all the interfaces are multi
    #Will return None if you have a combination
    def get_server_interface_type(self,servers_dict):
        all_single = False
        all_multi = False
        for server in servers_dict:
            management_intf = eval(server['parameters']).get('interface_name',None)
            ctrl_data_intf = eval(server['contrail']).get('control_data_interface',None)
            if ctrl_data_intf and management_intf != ctrl_data_intf:
                all_multi = True
            elif management_intf:
                all_single = True
            else:
                return None
        #If you have a mix of single and multi interface servers then return None
        if all_multi and all_single:
             return None
        if all_multi:
             return "MULTI_INTERFACE"
        return "SINGLE_INTERFACE"

    #This function returns the list of servers with a specific roles assigned to it
    def get_servers_roles_list(self, servers):
        openstack_only_list =[]
        config_only_list= []
        openstack_config_list= []
        for server in servers:
            roles_list = server['roles']
            #Check if the server has both config and openstack role assigned to it
            if 'config' in roles_list and 'openstack' in roles_list:
                openstack_config_list.append(server)
            #Check if the server has config role assigned to it
            elif 'config' in roles_list:
                config_only_list.append(server)
            #Check if the server has openstack role assigned to it
            elif 'openstack' in roles_list:
                openstack_only_list.append(server)
        return (openstack_config_list, config_only_list, openstack_only_list) 
   
    #Function to get the vips defined for a cluster
    def get_vips_in_cluster(self,cluster):
        cluster_params = eval(cluster['parameters'])
        cluster_provision_params = cluster_params.get("provision", {})
        if cluster_provision_params:
            openstack_params = cluster_provision_params.get("openstack", {})
            ha_params = openstack_params.get("ha", {})
            internal_vip = ha_params.get('internal_vip', None)
            external_vip = ha_params.get('external_vip', None)
            contrail_params = cluster_provision_params.get("contrail", {})
            contrail_ha_params = contrail_params.get("ha", {})
            contrail_internal_vip = contrail_ha_params.get('contrail_internal_vip', None)
            contrail_external_vip = contrail_ha_params.get('contrail_external_vip', None)
        else:
            internal_vip = cluster_params.get('internal_vip', None)
            external_vip = cluster_params.get('external_vip', None)
            contrail_internal_vip = cluster_params.get('contrail_internal_vip', None)
            contrail_external_vip = cluster_params.get('contrail_external_vip', None)
        return (internal_vip, external_vip, contrail_internal_vip, contrail_external_vip)

    # Function to validate ext lb params
    def validate_external_lb_params(self, cluster):
        cl_params = cluster['parameters']['provision']['contrail']
        lb_params = cl_params.get('loadbalancer', None)
        if not lb_params:
            return "cluster does not contain loadbalancer in "\
                    "provision:contrail stanza"
        lb_method = lb_params.get('loadbalancer_method', None)
        if not lb_method:
            return "cluster does not contain loadbalancer method in "\
                   "provision:contrail:loadbalancer stanza"
        return None
        
    #Function to validate vip configuration for a multi interface server
    def validate_multi_interface_vip(self,cluster, servers):
        #Get the list of servers with specific roles
        openstack_config_list, config_only_list, openstack_only_list = self.get_servers_roles_list(servers)
        #Get the values of all vips in a cluster
        internal_vip,external_vip,contrail_internal_vip,contrail_external_vip = self.get_vips_in_cluster(cluster)
        #If no vips are configured then it means no HA is configured. Just skip the validation
        if internal_vip is None and external_vip is None and contrail_internal_vip is None and contrail_external_vip is None:
            return
        #Validation for nodes configured for both contrail and openstack HA
        if len(openstack_config_list) > 1:
            #Both internal and external vip's have be configured
            if not internal_vip or not external_vip:
               raise Exception("Both internal and external vips need to be configured")
            #If internal and external vips are specified they should not be equal
            if internal_vip and external_vip and internal_vip == external_vip:
                raise Exception("internal and external vips cannot be the same")
            #If contrail internal vip and external vips are specified they should be equal to the internal and external vips
            if contrail_internal_vip and contrail_external_vip and contrail_internal_vip != internal_vip and contrail_external_vip != external_vip:
                raise Exception("If contrail internal and external vips are configured they need to be same as the internal and external vips")
            return
        #Validation for nodes configured only for contrail HA
        if len(config_only_list) > 1:
            #Both contrail internal and external vips have to be configured
            if not contrail_internal_vip or not contrail_external_vip:
                raise Exception("contrail_internal_vip and contrail_external_vip have to be configured")
            #Contrail internal and external vip cannot be the same
            if contrail_internal_vip and contrail_external_vip and contrail_internal_vip == contrail_external_vip:
                raise Exception("contrail_internal_vip and contrail_external_vip cannot be same")
            return 
        #Validation for nodes configured only for Openstack HA
        if len(openstack_only_list) > 1:
            #Both the internal and external vips have to be configured
            if not internal_vip or not external_vip:
                raise Exception("Both internal and external vips have to be configured")
            #internal and external vips cannot be the same
            if internal_vip and external_vip and internal_vip == external_vip:
                raise Exception("internal and external vips cannot be the same")
            return

    #Function to validate vip configuration for a multi interface server
    def validate_single_interface_vip(self, cluster, servers):
        #Get the list of servers with specific roles
        openstack_config_list, config_only_list, openstack_only_list = self.get_servers_roles_list(servers)
        #Get the values of all vips in a cluster
        internal_vip,external_vip,contrail_internal_vip,contrail_external_vip = self.get_vips_in_cluster(cluster)
        #If no vips are configured then it means no HA is configured. Just skip the validation
        if internal_vip is None and external_vip is None and contrail_internal_vip is None and contrail_external_vip is None:
            return
        #Validation for nodes configured for both contrail and openstack HA
        if len(openstack_config_list) > 1:
            #internal vip has to be configured
            if not internal_vip:
                raise Exception("internal vip has to be configured. external vip or contrail external vip cannot be configured")
            #external and internal vip if configured, has to be the same
            if external_vip and external_vip != internal_vip:
                raise Exception("internal vip and external vip have to be the same")
            #contrail external vip and internal vip if configured, has to be the same
            if contrail_external_vip and contrail_external_vip != internal_vip:
                raise Exception("internal vip and contrail external vip have to be the same")
            #contrail internal vip and internal vip if configured, has to be the same
            if contrail_internal_vip and contrail_internal_vip != internal_vip:
                raise Exception("internal vip and contrail internal vip have to be the same")
            return
        #Validation for nodes configured only for contrail HA
        if len(config_only_list) > 1:
            #contrail internal vip has to be configured
            if not contrail_internal_vip:
                raise Exception("Contrail internal vip has to be configured")
            #If contrail external vip is configured it has to be the same the contrail internal vip
            if contrail_external_vip and contrail_external_vip != contrail_internal_vip:
                raise Exception("contrail internal vip and contrail external vip have to be the same")
            return
        #Validation for nodes configured only for Openstack HA
        if len(openstack_only_list) > 1:
            #external vip has to be configured
            if not external_vip:
                raise Exception("External vip has to be configured have to be the same if there is only one interface")
            #If external vip is configured it has to be the same as internal vip
            if internal_vip and external_vip != internal_vip:
                raise Exception("Internal vip and External vip have to be the same if there is only one interface")
            return
    
    #Function to do the configuration validation of vips 
    def validate_vips(self, cluster_id, serverDb):
        try:
            #Get the cluster given the cluster id
            cluster_list =  serverDb.get_cluster({"id": cluster_id}, detail=True) 
            #Since we are getting the cluster given an id only one cluster will be there in the list
            cluster = cluster_list[0]
            match_dict = {"cluster_id": cluster['id']}
            #Get the list of servers belonging to that cluster
            servers = serverDb.get_server(match_dict, detail=True)
            #Find out what type of interface do the servers have
            interface_type = self.get_server_interface_type(servers)
            if interface_type == 'MULTI_INTERFACE':
                self.validate_multi_interface_vip(cluster, servers)              
            elif interface_type == 'SINGLE_INTERFACE':
                self.validate_single_interface_vip(cluster, servers)
            return
        except Exception as e:
            raise e

    def __init__(self):
        self._smgr_log = ServerMgrlogger()
        self._smgr_log.log(self._smgr_log.DEBUG, "ServerMgrValidations Init")

if __name__ == "__main__":
    pass
