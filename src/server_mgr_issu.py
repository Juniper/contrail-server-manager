import paramiko
from server_mgr_main import VncServerManager

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
        self.compute_tag = entity.get('compute_tag', None)
        self.setup_params()
        if self.check_issu_cluster_status(self.new_cluster):
            self.set_configured_params()
        self.issu_svc_file = "/etc/supervisor/conf.d/contrail-issu.conf"
        self.issu_conf_file = "/etc/contrail/contrail-issu.conf"

    def setup_params(self):
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
        self.new_config_list = self.role_get_servers(self.new_servers, 
                                                              'config')
        self.old_control_list = self.role_get_servers(self.old_servers, 
                                                             'control')
        self.new_control_list = self.role_get_servers(self.new_servers, 
                                                             'control')
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
        self.ssh_new_config = paramiko.SSHClient()
        self.ssh_new_config.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_new_config.connect(self.new_config_ip,
                               username = self.new_config_username,
                               password = self.new_config_password)
        self.old_config_ip_list = []
        for server in self.old_config_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.old_config_ip_list.append(tup)
        self.new_config_ip_list = []
        for server in self.new_config_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.new_config_ip_list.append(tup)
        self.old_control_ip_list = []
        for server in self.old_control_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.old_control_ip_list.append(tup)
        self.old_webui_ip_list = []
        self.old_webui_list = self.role_get_servers(self.old_servers,
                                                               'webui')
        for server in self.old_webui_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.old_webui_ip_list.append(tup)
        self.old_collector_ip_list = []
        self.old_collector_list = self.role_get_servers(self.old_servers,
                                                            'collector')
        for server in self.old_collector_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.old_collector_ip_list.append(tup)
        self.cluster_synced = self.set_cluster_issu_params()
        if self.cluster_synced == "true":
            cluster_params = eval(new_cluster_det['parameters'])
            issu_params = cluster_params.get("issu", {})
            self.issu_task_master = issu_params['issu_task_master']
        self.openstack_ip_list = []
        self.openstack_list = self.role_get_servers(self.old_servers,
                                                            'openstack')
        for server in self.openstack_list:
            tup = (server['ip_address'], server.get('username', 'root'),
                                                     server['password'])
            self.openstack_ip_list.append(tup)

        # end setup_params

    def set_configured_params(self):
        self.old_cass_server = self.get_set_config_parameters(self.ssh_old_config,
                                            "/etc/contrail/contrail-api.conf",
                                                      "cassandra_server_list")
        self.new_cass_server = self.get_set_config_parameters(self.ssh_new_config,
                                            "/etc/contrail/contrail-api.conf",
                                                      "cassandra_server_list")
        self.old_zk_server = self.get_set_config_parameters(self.ssh_old_config,
                                          "/etc/contrail/contrail-api.conf",
                                                             "zk_server_ip")
        self.new_zk_server = self.get_set_config_parameters(self.ssh_new_config,
                                         "/etc/contrail/contrail-api.conf",
                                                            "zk_server_ip")
        self.old_rabbit_server = self.get_set_config_parameters(self.ssh_old_config,
                                              "/etc/contrail/contrail-api.conf",
                                                                "rabbit_server")
        self.new_rabbit_server = self.get_set_config_parameters(self.ssh_new_config,
                                              "/etc/contrail/contrail-api.conf",
                                                                "rabbit_server")
        self.new_api_info = '\'{"%s": [("%s"), ("%s")]}\'' %(
                        self.new_config_ip, self.new_config_username, 
                                                  self.new_config_password)


    def do_issu(self):
        if not self.issu_check_clusters():
            # cluster needs provisioning
            msg = "ISSU: New cluster %s needs provisioning" %(
                                             self.new_cluster)
            self._smgr_log.log(self._smgr_log.DEBUG, msg)
            provision_status = self.provision_server(issu_flag = True)
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
                                "issu_task_master": (self.new_config_ip,
                                                     self.new_config_username,
                                                     self.new_config_password)
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

    def migrate_all_computes(self):
        servers = self._serverDb.get_server({"cluster_id" : 
                                               self.old_cluster}, detail=True)
        computes = []
        for server in servers:
            if "compute" in server["roles"]:
                computes.append(server)
                # change the cluster_id for the compute
                server_data = {"id": server["id"],
                               "cluster_id": self.new_cluster}
                self._serverDb.modify_server(server_data)
        if len(computes) == 0:
            msg = "ISSU: No compute nodes found in cluster %s" % \
                            (self.old_cluster)
            self.log_and_raise_exception(msg)
        compute_data = {}
        compute_data['server_packages'] = []
        compute_data['servers'] = []
        for compute in computes:
            req_json = {'id': compute['id'],
                        'package_image_id': self.new_image}
            ret_data = self.validate_smgr_provision(
                                "PROVISION", req_json, issu_flag=True)
            if ret_data['status'] == 0:
                compute_data['status'] = 0
                compute_data['cluster_id'] = ret_data['cluster_id']
                compute_data['package_image_id'] = ret_data['package_image_id']
                compute_data['server_packages'].append(
                                                ret_data['server_packages'][0])
                compute_data['servers'].append(
                                        ret_data['servers'][0])
            else:
                msg = "ISSU: Error validating request for server %s" % \
                                                            compute['id']
                self.log_and_raise_exception(msg)
        provision_server_list, role_sequence, provision_status = \
                                     self.prepare_provision(compute_data)
        provision_item = ('provision', provision_server_list, new_cluster, 
                                                                 role_sequence)
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
            self.migrate_all_computes()
            return
        # provision tagged computes
        req_json = {'tag': self.compute_tag,
                    'package_image_id': self.new_image}
        ret_data = self.validate_smgr_provision(
                            "PROVISION", req_json, issu_flag=True)
        if ret_data['status'] != 0:
            msg = "ISSU: Error validating request for tag %s" % \
                                                 self.compute_tag
            self.log_and_raise_exception(msg)
        provision_server_list, role_sequence, provision_status = \
                                     self.prepare_provision(compute_data)
        provision_item = ('provision', provision_server_list, new_cluster,
                                                           role_sequence)
        self._reimage_queue.put_nowait(provision_item)
        self._smgr_log.log(self._smgr_log.DEBUG,
                          "ISSU: computes provision queued. " \
                          "Number of servers for tag %s provisioned is %d:" % \
                          (self.compute_tag, len(provision_server_list)))
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
                              action = "get", value = None):
        if action == "get":
            cmd = "openstack-config --get %s %s %s" %(
                                      filename, section, param)
        else:
            cmd = "openstack-config --set %s %s %s %s" %(
                               filename, section, param, value)
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

        # form BGP peering between controllers across two clusters
        if self.cluster_synced == "true":
            self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: Clusters are already synced for Cluster %s" \
                                                    %self.new_cluster)
            return

        for cn in self.new_control_list:
            control_ip = self.get_control_ip(cn)
            cmd = "python /opt/contrail/utils/provision_control.py " +\
                  "--host_name %s --host_ip %s " %(cn['host_name'], control_ip) +\
                  "--api_server_ip %s --api_server_port 8082 " %self.old_api_server +\
                  "--oper add --admin_user admin " +\
                  "--admin_password %s --admin_tenant_name admin " %self.old_api_admin_pwd +\
                  "--router_asn %s" %self.old_router_asn
            self.ssh_old_config.exec_command(cmd)
        for cn in self.old_control_list:
            control_ip = self.get_control_ip(cn)
            cmd = "python /opt/contrail/utils/provision_control.py " +\
                  "--host_name %s --host_ip %s " %(cn['host_name'], control_ip) +\
                  "--api_server_ip %s --api_server_port 8082 " %self.new_api_server +\
                  "--oper add --admin_user admin " +\
                  "--admin_password %s --admin_tenant_name admin " %self.new_api_admin_pwd +\
                  "--router_asn %s" %self.new_router_asn
            self.ssh_new_config.exec_command(cmd)
        self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: BGP peering between two cluster is configured")
        # disable all but contrail-api, discovery and ifmap on new cluster CFGM
        cmd = 'openstack-config --set /etc/contrail/supervisord_config.conf include files "/etc/contrail/supervisord_config_files/contrail-api.ini  /etc/contrail/supervisord_config_files/contrail-discovery.ini /etc/contrail/supervisord_config_files/ifmap.ini"'
        self.ssh_new_config.exec_command(cmd)
        self.ssh_new_config.exec_command("service supervisor-config restart")

        # stop haproxy on the openstack node
        # ssh_new_config.exec_command("service haproxy stop")
        self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: Prepared for pre_sync")
        '''
        {
        'old_rabbit_user': 'guest',
        'old_rabbit_password': 'guest',
        'old_rabbit_ha_mode': False,
        'old_rabbit_q_name' : 'vnc-config.issu-queue',
        'old_rabbit_vhost' : None,
        'old_rabbit_port' : '5672',
        'new_rabbit_user': 'guest',
        'new_rabbit_password': 'guest',
        'new_rabbit_ha_mode': False,
        'new_rabbit_q_name': 'vnc-config.issu-queue',
        'new_rabbit_vhost' : '',
        'new_rabbit_port': '5672',
        'odb_prefix' : '',
        'ndb_prefix': '',
        'reset_config': None,
        'old_cassandra_address_list': '192.168.100.102:9160',
        'old_zookeeper_address_list': '192.168.100.102:2181',
        'old_rabbit_address_list': '192.168.100.102',
        'new_cassandra_address_list': '192.168.100.121:9160',
        'new_zookeeper_address_list': '192.168.100.121:2181',
        'new_rabbit_address_list': '192.168.100.121',
        #'new_api_info' : '{"192.168.100.121": [("root"), ("4336B39CF8ED")]}'
        'new_api_info' : '{"192.168.100.121": [("root"), ("c0ntrail123")]}'
        }
        '''

        # run contrail-issu-pre-sync on new config
        self.ssh_new_config.exec_command("touch %s" %self.issu_conf_file)
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_user", value = "guest", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_password", value = "guest", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_ha_mode", value = "False", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_q_name", value = "vnc-config.issu-queue", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_vhost", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "old_rabbit_port", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_user", value = "guest", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_password", value = "guest", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_ha_mode", value = "False", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_q_name", value = "vnc-config.issu-queue", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_vhost", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_rabbit_port", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "odb_prefix", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "ndb_prefix", value = "''", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, 
                                 "old_cassandra_address_list", value = self.old_cass_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, 
                                   "old_zookeeper_address_list", value = self.old_zk_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file,
                                  "old_rabbit_address_list", value = self.old_rabbit_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file,
                                 "new_cassandra_address_list", value = self.new_cass_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, 
                                   "new_zookeeper_address_list", value = self.new_zk_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, 
                                  "new_rabbit_address_list", value = self.new_rabbit_server, action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_conf_file, "new_api_info",
                                                        value = self.new_api_info, action = "set")

        inp, op, err = self.ssh_new_config.exec_command("contrail-issu-pre-sync -c %s" %self.issu_conf_file)
        err_str = err.read()
        op_str = op.read()
        if err_str:
            self.log_and_raise_exception(err_str)
        self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: executed contrail-issu-pre-sync\n %s" %op_str)

        # run issu task now, this creates rabbit client
        self.ssh_new_config.exec_command("touch %s" %self.issu_svc_file)
        command = "'contrail-issu-run-sync -c %s'" %self.issu_conf_file
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "command", value = command,
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "numprocs", value = 1,
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "process_name", 
                                    value = "'%(process_num)s'",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "redirect_stderr", value = "true",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "stdout_logfile", 
                 value = "'/var/log/issu-contrail-run-sync-%(process_num)s-stdout.log'",
                                      section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "stderr_logfile", 
                                                       value = "/dev/null",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "priority", value = 440,
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "autostart", value = "true",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "killasgroup", value = "false",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "stopsignal", value = "KILL",
                                    section = "program:contrail-issu", action = "set")
        self.get_set_config_parameters(self.ssh_new_config, self.issu_svc_file, "exitcodes", value = 0,
                                    section = "program:contrail-issu", action = "set")
        '''
        cmd = "openstack-config --set /etc/supervisor/conf.d/contrail-issu.conf program:contrail-issu"
        ssh_new_config.exec_command("%s command 'contrail-issu-run-sync %s'" %(cmd, cmd_args))
        ssh_new_config.exec_command("%s numprocs 1" %(cmd))
        ssh_new_config.exec_command("%s process_name '%%(process_num)s'" %cmd)
        ssh_new_config.exec_command("%s redirect_stderr true" %(cmd))
        ssh_new_config.exec_command("%s stdout_logfile  '/var/log/issu-contrail-run-sync-%%(process_num)s-stdout.log'" %cmd)
        ssh_new_config.exec_command("%s stderr_logfile '/dev/null'" %cmd)
        ssh_new_config.exec_command("%s priority 440" %(cmd))
        ssh_new_config.exec_command("%s autostart true" %(cmd))
        ssh_new_config.exec_command("%s killasgroup false" %(cmd))
        ssh_new_config.exec_command("%s stopsignal KILL" %(cmd))
        ssh_new_config.exec_command("%s exitcodes 0" %(cmd))
        '''

        inp, op, err = self.ssh_new_config.exec_command("service supervisor restart")
        err_str = err.read()
        if err_str:
            self.log_and_raise_exception(err_str)
        self._smgr_log.log(self._smgr_log.DEBUG,
                  "ISSU: Started ISSU task on controller %s" \
                                               %self.new_config_ip) 
        # start haproxy on the openstack node
        #ssh_new_config.exec_command("service haproxy start")

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

        # TBD need verification that issu rabbit client is connected to both clusters

        # start compute upgrade
        self.migrate_computes()

        # remove BGP peering and finalize issu

    # end _do_issu

    def _do_finalize_issu(self):
        ''' This is called from backend to finalize issu'''
        # shutoff old_controller nodes issu_contrail_stop_old_node
        for each in self.old_config_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            ssh_handl.exec_command("service supervisor-config stop")
            ssh_handl.exec_command("service neutron-server stop")
            # TBD rabbitmq-server could be another node
            ssh_handl.exec_command("service rabbitmq-server stop")
            ssh_handl.close()
        for each in self.old_control_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            ssh_handl.exec_command("service supervisor-control stop")
            ssh_handl.close()
        for each in self.old_webui_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            ssh_handl.exec_command("service supervisor-webui stop")
            ssh_handl.close()
        for each in self.old_collector_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            ssh_handl.exec_command("service supervisor-analytics stop")
            ssh_handl.close()
        
        # issu_post_sync
        ssh_issu_task_master = paramiko.SSHClient()
        ssh_issu_task_master.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_issu_task_master.connect(self.issu_task_master[0],
                                     username = self.issu_task_master[1],
                                     password = self.issu_task_master[2])
        ssh_issu_task_master.exec_command(
                                      "rm -f %s" %(self.issu_svc_file))
        inp, op, err = ssh_issu_task_master.exec_command(
                                               "service supervisor restart")
        err_str = err.read()
        if err_str:
            self.log_and_raise_exception(err_str)
        inp, op, err = ssh_issu_task_master.exec_command(
                                        "contrail-issu-post-sync -c %s" %(
                                                      self.issu_conf_file))
        err_str = err.read()
        if err_str:
            self.log_and_raise_exception(err_str)
        inp, op, err = ssh_issu_task_master.exec_command(
                                          "contrail-issu-zk-sync -c %s" %(
                                                      self.issu_conf_file))
        err_str = err.read()
        if err_str:
            self.log_and_raise_exception(err_str)

        # issu_contrail_post_new_control
        for each in self.new_config_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            cmd = "openstack-config --set /etc/contrail/supervisord_config.conf" +\
                  " include files \"/etc/contrail/supervisord_config_files/*.ini\""
            ssh_handl.exec_command("cmd")
            ssh_handl.exec_command("service supervisor-config stop")
            ssh_handl.close()

        # issu_contrail_migrate_nb
        for each in self.openstack_ip_list:
            ssh_handl = paramiko.SSHClient()
            ssh_handl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_handl.connect(each[0], username = each[1], password = each[2])
            # TBD need to reconfigure openstack node to point new cluster
            ssh_handl.close()

        # issu_contrail_finalize_config_node
        # issu_prune_old_config'
        #cmd = ''
        #cmd = "python /opt/contrail/utils/provision_config_node.py"
        #cmd += " --api_server_ip %s" % self.issu_task_master
        #cmd += " --host_name %s" % 
        #cmd += " --host_ip %s" % tgt_ip
        #cmd += " --oper %s" % oper
        #cmd += " --admin_user %s --admin_password %s --admin_tenant_name %s"
        # execute('issu_prune_old_collector')
        # execute('issu_prune_old_control')
        # execute('issu_prune_old_database')
        # execute('issu_prov_config')
        # execute('issu_prov_collector')
        # execute('issu_prov_database')

        # end _do_finalize_issu

# end IssuClass
