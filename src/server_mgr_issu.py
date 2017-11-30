import paramiko
from server_mgr_main import VncServerManager
from server_mgr_utils import *

class SmgrIssuClass(VncServerManager):
    def __init__(self, vnc_smgr_obj, entity):
        self.smgr_obj = vnc_smgr_obj
        self._serverDb = vnc_smgr_obj._serverDb
        self._smgr_log = vnc_smgr_obj._smgr_log
        self._reimage_queue = vnc_smgr_obj._reimage_queue
        self._smgr_puppet = vnc_smgr_obj._smgr_puppet
        self._smgr_validations = vnc_smgr_obj._smgr_validations
        self._smgr_trans_log = vnc_smgr_obj._smgr_trans_log
        self.old_cluster = entity['old_cluster']
        self.new_cluster = entity['new_cluster']
        self.opcode = entity['opcode']
        self.new_image = entity.get('new_image', None)
        self.old_image = entity.get('old_image', None)
        self.compute_tag = entity.get('compute_tag', "")
        self.compute_server_id = entity.get('server_id', "")
        self.is_docker_image = None
        self.setup_params()
        if self.check_issu_cluster_status(self.new_cluster):
            self.is_docker_image = self.check_image()
            self.set_configured_params()
        self.issu_script = "/opt/contrail/bin/issu/contrail-issu"
        self.issu_conf_file = "/opt/contrail/bin/issu/inventory/inventory.conf"

    def check_image(self):
        cmd = "docker ps -a |grep controller -q"
        status = self._execute_cmd(self.ssh_old_config, cmd)
        if status:
            return False
        return True

    def setup_params(self):
        smutil = ServerMgrUtil()
        old_cluster_det = self._serverDb.get_cluster(
                               {"id" : self.old_cluster},
                               detail=True)[0]
        new_cluster_det = self._serverDb.get_cluster(
                               {"id" : self.new_cluster},
                               detail=True)[0]
        self.old_cluster_params = eval(old_cluster_det['parameters'])
        self.new_cluster_params = eval(new_cluster_det['parameters'])
        self.old_servers = self._serverDb.get_server(
                                           {"cluster_id" : 
                                            self.old_cluster}, detail=True)
        self.new_servers = self._serverDb.get_server(
                                           {"cluster_id" : 
                                            self.new_cluster}, detail=True)
        if len(self.old_servers) == 0 or \
           len(self.new_servers) == 0 :
            self.log_and_raise_exception(
                        "ISSU: Number of server in one of clusters is 0!!")
        self.old_config_list = self.role_get_servers(self.old_servers, 
                                                              'config')
        if not self.old_config_list:
            self.old_config_list = self.role_get_servers(self.old_servers, 
                                                    'contrail-controller')
        self.new_config_list = self.role_get_servers(self.new_servers, 
                                                 'contrail-controller')
        self.old_control_list = self.role_get_servers(self.old_servers, 
                                                             'control')
        if not self.old_control_list:
            self.old_control_list = self.role_get_servers(self.old_servers, 
                                                     'contrail-controller')
        self.new_control_list = self.role_get_servers(self.new_servers, 
                                                 'contrail-controller')
        self.old_config_ip = self.old_config_list[0]['ip_address']
        self.old_config_username = self.old_config_list[0].get('username',
                                                                   'root')
        self.old_config_password = self.old_config_list[0]['password']
        self.old_api_server = self.get_control_ip(self.old_config_list[0])
        self.new_api_server = self.get_control_ip(self.new_config_list[0])
        self.old_api_admin_pwd = self.old_cluster_params['provision']\
                               ['openstack']['keystone']['admin_password']
        self.new_api_admin_pwd = self.new_cluster_params['provision']\
                               ['openstack']['keystone']['admin_password']
        self.old_cn_info = self.old_cluster_params['provision']\
                                           ['contrail'].get('control', {})
        self.new_cn_info = self.new_cluster_params['provision']\
                                           ['contrail'].get('control', {})
        self.old_router_asn = self.old_cn_info.get('router_asn', '64512')
        self.new_router_asn = self.new_cn_info.get('router_asn', '64512')
        self.new_config_ip = self.new_config_list[0]['ip_address']
        self.new_config_username = self.new_config_list[0].get('username', 'root')
        self.new_config_password = self.new_config_list[0]['password']
        self.ssh_old_config = paramiko.SSHClient()
        self.ssh_old_config.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_old_config.connect(self.old_config_ip,
                               username = self.old_config_username,
                               password = self.old_config_password)
        self.old_config_ip_list = []
        for server in self.old_config_list:
            server_password = smutil.get_password(server,self._serverDb)
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server_password)
            self.old_config_ip_list.append(tup)
        self.old_control_ip_list = []
        for server in self.old_control_list:
            server_password = smutil.get_password(server,self._serverDb)
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server_password)
            self.old_control_ip_list.append(tup)
        self.old_webui_ip_list = []
        self.old_webui_list = self.role_get_servers(self.old_servers,
                                                               'webui')
        for server in self.old_webui_list:
            server_password = smutil.get_password(server,self._serverDb)
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server_password)
            self.old_webui_ip_list.append(tup)
        self.old_collector_ip_list = []
        self.old_collector_list = self.role_get_servers(self.old_servers,
                                                            'collector')
        for server in self.old_collector_list:
            server_password = smutil.get_password(server,self._serverDb)
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server_password)
            self.old_collector_ip_list.append(tup)
        self.old_database_list = self.role_get_servers(self.old_servers,
                                                             'database')

        self.cluster_synced = self.set_cluster_issu_params()
        self.issu_task_master = (self.new_config_ip,
                                 self.new_config_username,
                                 self.new_config_password)
        if self.cluster_synced == "true":
            cluster_params = eval(new_cluster_det['parameters'])
            issu_params = cluster_params.get("issu", {})
            self.issu_task_master = issu_params['issu_task_master']
        self.openstack_ip_list = []
        self.openstack_list = self.role_get_servers(self.old_servers,
                                                            'openstack')
        self.ssh_new_config = paramiko.SSHClient()
        self.ssh_new_config.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_new_config.connect(self.issu_task_master[0],
                               username = self.issu_task_master[1],
                               password = self.issu_task_master[2])
        for server in self.openstack_list:
            server_password = smutil.get_password(server,self._serverDb)
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server_password)
            self.openstack_ip_list.append(tup)
        self.is_docker_image = self.get_image()
        # end setup_params

    def set_configured_params(self):
        self.old_cass_server = self.get_set_config_parameters(self.ssh_old_config,
                                            "/etc/contrail/contrail-api.conf",
                                                      "cassandra_server_list",
                                            docker_flag = self.is_docker_image)
        self.old_zk_server = self.get_set_config_parameters(self.ssh_old_config,
                                          "/etc/contrail/contrail-api.conf",
                                                             "zk_server_ip",
                                            docker_flag = self.is_docker_image)
        self.old_rabbit_server = self.get_set_config_parameters(self.ssh_old_config,
                                              "/etc/contrail/contrail-api.conf",
                                                                "rabbit_server",
                                            docker_flag = self.is_docker_image)

    def do_issu(self):
        if not self.issu_check_clusters():
            # cluster needs provisioning
            msg = "ISSU: New cluster %s needs provisioning" %(
                                             self.new_cluster)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
            provision_status = self.smgr_obj.provision_server(issu_flag = True)
            # subsequent steps for issu are done after provision complete
            return provision_status
        provision_item = (self.opcode, self.old_cluster,
                                       self.new_cluster, self.new_image)
        self._reimage_queue.put_nowait(provision_item)
        msg = "New cluster %s is already provisoned, Queued ISSU job" %(
                                                       self.new_cluster)
        self._smgr_log.log(self._smgr_log.DEBUG, msg)
        req_status = {}
        req_status['return_code'] = "0"
        req_status['return_message'] = msg
        return req_status
    # end do_issu

    def do_finalize_issu(self):
        if not self.issu_check_clusters():
            # cluster needs provisioning
            msg = "ISSU-FIANLIZE: Clusters not provisioned"
            self.log_and_raise_exception(msg)
        # make sure old cluster doent have any computes left
        if self.role_get_servers(self.old_servers, 'compute'):
            self.log_and_raise("Old cluster %s still has compute nodes" %(
                                                         self.old_cluster))
        provision_item = (self.opcode, self.old_cluster,
                                          self.new_cluster, self.new_image)
        self._reimage_queue.put_nowait(provision_item)
        msg = "Queued ISSU-Finalize job for cluster %s" %(
                                                       self.new_cluster)
        self._smgr_log.log(self._smgr_log.DEBUG, msg)
        req_status = {}
        req_status['return_code'] = "0"
        req_status['return_message'] = msg
        return req_status
        
    # end do_finalize_issu

    def do_rollback_compute(self):
        '''recieve rest call from provision_server and queue rollback
           job to the backend'''
        if self.compute_server_id:
            compute = self._serverDb.get_server({"id" :
                                       self.compute_server_id}, detail=True)[0]
            if "contrail-compute" not in compute['roles']:
                self.log_and_raise_exception("ISSU-ROLLBACK: Server %s not compute" %(
                                                    self.compute_server_id))
        if self.compute_tag:
            if self.compute_tag == "all_computes":
                servers = self._serverDb.get_server({"cluster_id" :
                                       self.new_cluster}, detail=True)
                computes = self.role_get_servers(servers, "contrail-compute")
            else:
                computes = self.smgr_obj.get_servers_for_tag(self.compute_tag)
            for each in computes:
                if "contrail-compute" not in each['roles']:
                    self.log_and_raise_exception("ISSU-ROLLBACK: Server %s not compute" %(
                                                                    each['id']))
        provision_item = (self.opcode, self.old_cluster,
                                          self.new_cluster, self.old_image,
                                  self.compute_tag, self.compute_server_id)
        self._reimage_queue.put_nowait(provision_item)
        msg = "Queued ISSU-rollback for compute server_id %s, tag %s" %(
                                  self.compute_server_id, self.compute_tag)
        self._smgr_log.log(self._smgr_log.DEBUG, msg)
        req_status = {}
        req_status['return_code'] = "0"
        req_status['return_message'] = msg
        return req_status

    def set_cluster_issu_params(self):
        # set issu flag on the involved clusters
        cluster_det = self._serverDb.get_cluster(
                           {'id': self.new_cluster}, detail = True)[0]
        cluster_params = eval(cluster_det['parameters'])
        issu_params = cluster_params.get("issu", {})
        cluster_synced = issu_params.get('issu_clusters_synced', "false")
        cluster_data = {"id":self.new_cluster,
                        "parameters": {
                            "issu": {
                                "issu_partner": self.old_cluster,
                                "issu_clusters_synced": cluster_synced,
                                "issu_image": self.new_image,
                                "issu_compute_tag": self.compute_tag,
                                "issu_task_master": (self.new_config_ip,
                                                     self.new_config_username,
                                                     self.new_config_password),
                                "issu_finalized": "false"
                                }
                           }
                       }
        self._serverDb.modify_cluster(cluster_data)
        return cluster_synced

    def issu_check_clusters(self):
        # check cluster config are similar

        # check if clusters are ready for issu
        if self.cluster_synced == "true":
            return True
        if not self.check_issu_cluster_status(self.old_cluster):
            self.log_and_raise_exception("ISSU: old cluster doesnt seem to be " \
                                         "provisioned, please check cluster status")
        return self.check_issu_cluster_status(self.new_cluster)
    # end issu_check_clusters

    def migrate_all_computes(self, old_cluster, new_cluster, image,
                                               compute_list = None):
        if not compute_list:
            servers = self._serverDb.get_server({"cluster_id" :
                                       old_cluster}, detail=True)
        else:
            servers = compute_list
        computes = []
        for server in servers:
            if ("compute" in eval(server["roles"])) or \
               ("contrail-compute" in eval(server["roles"])):
                computes.append(server)
                # change the cluster_id for the compute
                roles = eval(server["roles"])
                # if target cluster is pre-4.0 handle compute role
                cluster_det = self._serverDb.get_cluster(
                                   {"id" : new_cluster},
                                   detail=True)[0]
                cluster_params = eval(cluster_det['parameters'])
                cluster_provision_params = cluster_params.get("provision", {})
                if cluster_provision_params.get("contrail_4", {}):
                    new_roles = [ "contrail-compute" if each == "compute" \
                                              else each for each in roles ]
                else:
                    new_roles = [ "compute" if each == "contrail-compute" \
                                              else each for each in roles ]
                server_data = {"id": server["id"],
                               "cluster_id": new_cluster,
                               "roles": new_roles}
                server['cluster_id'] = new_cluster
                server['roles'] = unicode(new_roles)
                self._serverDb.modify_server(server_data)
        if len(computes) == 0:
            msg = "ISSU: No compute nodes found in cluster %s" % \
                            (old_cluster)
            self.log_and_raise_exception(msg)
        compute_data = {}
        compute_data['server_packages'] = []
        compute_data['servers'] = []
        for compute in computes:
            req_json = {'id': compute['id'],
                        'package_image_id': image}
            ret_data = self.smgr_obj.validate_smgr_provision(
                                "PROVISION", req_json, issu_flag=True)
            if ret_data['status'] == 0:
                compute_data['status'] = 0
                compute_data['cluster_id'] = ret_data['cluster_id']
                compute_data['package_image_id'] = ret_data['package_image_id']
                if (eval(self.smgr_obj.get_package_parameters(image) \
                                            ).get("containers",None)):
                    compute_data["server_packages"].append( \
                                     self.smgr_obj.get_container_packages( \
                                                        [compute], image)[0])
                    compute_data["contrail_image_id"] = image
                    compute_data["category"] = "container"
                else:
                    compute_data['server_packages'].append( \
                          self.smgr_obj.get_server_packages( \
                                           [compute], image)[0])
                compute_data['servers'].append(
                                        ret_data['servers'][0])
            else:
                msg = "ISSU: Error validating request for server %s" % \
                                                            compute['id']
                self.log_and_raise_exception(msg)
        provision_server_list, role_sequence, provision_status = \
                                     self.smgr_obj.prepare_provision(compute_data)
        provision_item = ('provision', provision_server_list, new_cluster,
                                                                 role_sequence,
                                                                          None)
        self._reimage_queue.put_nowait(provision_item)
        self._smgr_log.log(self._smgr_log.DEBUG, 
                          "ISSU: computes provision queued. " \
                          "Number of servers provisioned is %d:" % \
                          len(provision_server_list))
        # end migrate_all_computes

    def migrate_computes(self):
        if not self.compute_tag:
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "ISSU: No computes were specified for migrate")
            return
        if self.compute_tag == "all_computes":
            self.migrate_all_computes(self.old_cluster, self.new_cluster,
                                                            self.new_image)
            return
        compute_prov = []
        # update cluster for the computes
        if "__server__id__" in self.compute_tag:
            srv_id = self.compute_tag.split('__server__id__')[-1]
            computes = self._serverDb.get_server({"id" :
                                                 srv_id}, detail=True)
        else:
            computes = self.smgr_obj.get_servers_for_tag(self.compute_tag)
        if len(computes) == 0:
            msg = "ISSU: No compute nodes found for tag %s" % \
                                             (self.compute_tag)
            self.log_and_raise_exception(msg)
        for each in computes:
            if (each['cluster_id'] == self.new_cluster):
                msg = "ISSU: compute node already part of new cluster %s, " \
                      "will re-provision" %(each['cluster_id'])
                self._smgr_log.log(self._smgr_log.DEBUG, msg)
            elif (each['cluster_id'] != self.old_cluster):
                msg = "ISSU: compute %s is not part of old cluster %s, " \
                      "cant migrate" %(each['id'], self.old_cluster)
                self.log_and_raise_exception(msg)
            compute_prov.append(each)
        if compute_prov:
            self.migrate_all_computes(self.old_cluster, self.new_cluster,
                                            self.new_image, compute_prov)
    # migrate_computes

    def check_issu_cluster_status(self, cluster):
        servers = self._serverDb.get_server({"cluster_id" : cluster}, detail=True)
        for server in servers:
            if 'provision_completed' not in server['status']:
                return False
        return True
    # end check_issu_cluster_status

    def get_set_config_parameters(self, conn_handle, filename,
                              param, section = "DEFAULTS",
                              action = "get", value = None,
                              docker_flag = False):
        if action == "get":
            cmd = "openstack-config --get %s %s %s" %(
                                      filename, section, param)
        else:
            cmd = "openstack-config --set %s %s %s %s" %(
                               filename, section, param, value)
        if docker_flag:
            cmd = "docker exec controller %s" %cmd
        stdin, stdout, stderr = conn_handle.exec_command(cmd)
        err = stderr.read()
        op = stdout.read()
        if err:
            self.log_and_raise_exception(err)
        else:
            return op.strip()
    # end get_set_config_parameters

    def _do_issu_sync(self):
        '''Function creates BGP peering between two clusters, runs issu
           pre_sync script to runs issu_sync_task'''

        if self.cluster_synced == "true":
            self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: Clusters are already synced for Cluster %s" \
                                                    %self.new_cluster)
            return

        # On underlay controller host, apt-get install contrail-docker-tools
        cmd = "DEBIAN_FRONTEND=noninteractive apt-get install -y contrail-docker-tools"
        self._execute_cmd(self.ssh_new_config, cmd)

        # populate inventory.conf @ /opt/contrail/bin/issu/inventory/inventory.conf
        # This file needs old_api_ip, new_api_ip, passwords, username, 
        # old_control, old_config, old_analytics, old_webui lists
        cmd = "crudini --set %s GLOBAL oldapiip %s" %(self.issu_conf_file,
                                                      self.old_api_server)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL oldapiuser %s" %(self.issu_conf_file,
                                                   self.old_config_username)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL oldapipwd %s" %(self.issu_conf_file,
                                                  self.old_config_password)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL apiip %s" %(self.issu_conf_file,
                                                    self.new_config_ip)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL api_node_user_name %s" %(
                          self.issu_conf_file, self.new_config_username)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL api_node_password %s" %(
                         self.issu_conf_file, self.new_config_password)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL user %s" %(self.issu_conf_file,
                                             self.new_config_username)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s GLOBAL password %s" %(self.issu_conf_file,
                                                 self.new_config_password)
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s V1_CONTROLLER control_list \"%s\"" %(
                  self.issu_conf_file, str([str(each[0]) for each in \
                                           self.old_control_ip_list]))
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s V1_CONTROLLER config_list \"%s\"" %(
                  self.issu_conf_file, str([str(each[0]) for each in \
                                            self.old_config_ip_list]))
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s V1_CONTROLLER analytics_list \"%s\"" %(
                  self.issu_conf_file, str([str(each[0]) for each in \
                                       self.old_collector_ip_list]))
        self._execute_cmd(self.ssh_new_config, cmd)

        cmd = "crudini --set %s V1_CONTROLLER webui_list \"%s\"" %(
                  self.issu_conf_file, str([str(each[0]) for each in \
                                           self.old_webui_ip_list]))
        self._execute_cmd(self.ssh_new_config, cmd)

        # run this: cd /opt/contrail/bin/issu && ./contrail-issu generate-conf ~/inventory.conf
        # check the /etc/contrailctl/contrail-issu.conf file
        cmd = "%s generate-conf %s" %(self.issu_script, self.issu_conf_file)
        #self._execute_cmd(self.ssh_new_config, cmd)
        i, o, err = self.ssh_new_config.exec_command(cmd)
        op = o.readlines()
        err_msg = err.readlines()
        # run this: cd /opt/contrail/bin/issu && ./contrail-issu migrate-config
        # check the issu pre_sync and run_sync logs in the controller container
        cmd = "%s migrate-config" %(self.issu_script)
        #self._execute_cmd(self.ssh_new_config, cmd)
        i, o, err = self.ssh_new_config.exec_command(cmd)
        op = o.readlines()
        err_msg = err.readlines()

        # This is not creating the BGP peering - setup the BGP peering on old and new
        for cn in self.new_control_list:
            control_ip = self.smgr_obj.get_control_ip(cn)
            cmd = "python /opt/contrail/utils/provision_control.py " +\
                  "--host_name %s --host_ip %s " %(cn['host_name'], control_ip) +\
                  "--api_server_ip %s --api_server_port 8082 " %self.old_api_server +\
                  "--oper add --admin_user admin " +\
                  "--admin_password %s --admin_tenant_name admin " %self.old_api_admin_pwd +\
                  "--router_asn %s" %self.old_router_asn
            self._execute_cmd(self.ssh_old_config, cmd)
        for cn in self.old_control_list:
            control_ip = self.smgr_obj.get_control_ip(cn)
            cmd = "docker exec -i controller "
            cmd = cmd + "python /opt/contrail/utils/provision_control.py " +\
                  "--host_name %s --host_ip %s " %(cn['host_name'], control_ip) +\
                  "--api_server_ip %s --api_server_port 8082 " %self.new_api_server +\
                  "--oper add --admin_user admin " +\
                  "--admin_password %s --admin_tenant_name admin " %self.new_api_admin_pwd +\
                  "--router_asn %s" %self.new_router_asn
            self._execute_cmd(self.ssh_new_config, cmd)
        self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: BGP peering between two cluster is configured")

        # close the FDs
        self.ssh_old_config.close()
        self.ssh_new_config.close()

        # update the cluster status for sync completion
        cluster_data = {"id": self.new_cluster, 
                        "parameters": {
                            "issu": {
                                "issu_clusters_synced": "true",
                                }
                           }
                       }
        self._serverDb.modify_cluster(cluster_data)

    # end _do_issu_sync

    def _do_issu(self):
        '''backend function that picks issu provision job'''

        # Do pre_sync and run issu task
        self._do_issu_sync()

        # start compute upgrade
        self.migrate_computes()

        # remove BGP peering and finalize issu

    # end _do_issu
    def _execute_cmd(self, handl, cmd):
        i, stdout, stderr = handl.exec_command(cmd)
        err = stderr.read()
        op = stdout.read()
        exit_status = stdout.channel.recv_exit_status()
        if err:
            self._smgr_log.log(self._smgr_log.DEBUG,
                               "ISSU: Error executing %s" %cmd)
            self.log_and_raise_exception(err)
        return exit_status

    def _do_finalize_issu(self):
        ''' This is called from backend to finalize issu'''
        # shutdown v1 controllers
        cmd = "%s shutdown-v1-controller %s" %(self.issu_script, self.issu_conf_file)
        i, o, err = self.ssh_new_config.exec_command(cmd)
        op = o.readlines()
        err_msg = err.readlines()
        # run finalize
        cmd = "%s finalize-config" %self.issu_script
        i, o, err = self.ssh_new_config.exec_command(cmd)
        op = o.readlines()
        err_msg = err.readlines()

        # set issu finalize complete flag
        cluster_data = {"id": self.new_cluster,
                        "parameters": {
                            "issu": {
                                "issu_finalized": "true",
                                }
                           }
                       }
        self._serverDb.modify_cluster(cluster_data)

        self._smgr_log.log(self._smgr_log.DEBUG,
                          "ISSU-Finalize: Completed ISSU finalize" \
                          " for cluster %s" %self.new_cluster)

        # end _do_finalize_issu

    def _do_rollback_compute(self):
        if self.compute_server_id:
            computes = self._serverDb.get_server({"id" :
                                 self.compute_server_id}, detail=True)
        elif self.compute_tag == "all_computes":
            servers = self._serverDb.get_server({"cluster_id" :
                                 self.new_cluster}, detail=True)
            computes = self.role_get_servers(servers, "contrail-compute")
        else:
            computes = self.smgr_obj.get_servers_for_tag(self.compute_tag)
        if len(computes) == 0:
            msg = "ISSU-ROLLBACK: No compute nodes found for rollback"
            self.log_and_raise_exception(msg)
        # remove the packages
        for compute in computes:
            # add server rollback flag
            server_data = {"id": compute["id"],
                           "parameters": {
                               "compute-rollback": self.old_cluster
                               }
                          }
            self._serverDb.modify_server(server_data)
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(compute['ip_address'],
                              username = compute.get('username', 'root'),
                              password = compute['password'])
            vrouter_kmod_pkg = self.get_vrouter_pkg(ssh_handl,
                                                    'contrail-vrouter-dkms')
            pkgs = "contrail-setup %s contrail-fabric-utils " \
               "contrail-install-packages contrail-lib contrail-nodemgr " \
               "contrail-setup contrail-utils contrail-vrouter-utils " \
               "python-contrail contrail-openstack-vrouter contrail-nova-vif " \
               "contrail-setup contrail-vrouter-utils" %vrouter_kmod_pkg
            pkgs = pkgs + " contrail-vrouter-agent "\
                          "contrail-vrouter-init"
            cmd = "DEBIAN_FRONTEND=noninteractive apt-get -y remove %s" %pkgs
            inp, op, err = ssh_handl.exec_command(cmd)
            err_str = err.read()
            # remove the sources.list.d entry for new image
            cmd = "rm -rf /etc/apt/sources.list.d/*"
            ssh_handl.exec_command(cmd)
            # remove vrouter and stop supervisor-vrouter
            cmd = "service supervisor-vrouter stop && "\
                  "modprobe -r vrouter"
            ssh_handl.exec_command(cmd)
            ssh_handl.close()
            #if err_str:
            #    self.log_and_raise_exception("ISSU-ROLLBACK: error removing packages %s"
            #                                                             %cmd)
            self._smgr_log.log(self._smgr_log.DEBUG,
                          "ISSU-Rollback: Removed packages from compute" \
                          " on %s" %compute['id'])
        # provision the computes
        self.migrate_all_computes(self.new_cluster,
                                  self.old_cluster,
                                  self.old_image, computes)
        # after provision complte restart vrouter service on compute, done in status thread

    def get_vrouter_pkg(self, ssh_handl, pkg):
        cmd = "dpkg -s %s | grep Version: | cut -d' ' -f2 | cut -d'-' -f2" %pkg
        #execute this command
        inp, op ,err = ssh_handl.exec_command(cmd)
        version = op.read().strip()
        err_str = err.read().strip()
        if version:
            return "contrail-vrouter-dkms"
        if 'is not installed' in err_str or 'is not available' in err_str:
            cmd = "apt-cache pkgnames contrail-vrouter-$(uname -r)"
            inp, op, err = ssh_handl.exec_command(cmd)
            pkg = op.read().strip()
            return pkg

# end IssuClass
