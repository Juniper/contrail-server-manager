import os
import sys
import urllib
import multiprocessing
import ConfigParser
import tempfile
import yaml
import re
from collections import namedtuple

from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.utils.display import Display

from sm_ansible_utils import *
from sm_ansible_utils import _valid_roles
from sm_ansible_utils import _inventory_group
from sm_ansible_utils import _container_names
from sm_ansible_utils import SM_STATUS_PORT
from sm_ansible_utils import STATUS_IN_PROGRESS
from sm_ansible_utils import STATUS_VALID
from sm_ansible_utils import STATUS_SUCCESS
from sm_ansible_utils import STATUS_FAILED

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger


############## REFACTOR BEGIN - CODE BELOW CAN BE DELETED AFTER TESTING ##########
"""
    wrapper class inspired from
    http://docs.ansible.com/ansible/developing_api.html
"""
class ContrailAnsiblePlayBook(multiprocessing.Process):

    def validate_provision_params(self, inv, defaults):

        keys_to_check = ["ansible_playbook",
                         "docker_insecure_registries",
                         "docker_registry_insecure"]

        params = inv.get("[all:vars]", None)
        if params == None:
            return ("[all:vars] not defined")

        for x in keys_to_check:
            if not x in params.keys():
                if x == "docker_insecure_registries":
                    params['docker_insecure_registries'] = \
                     defaults.docker_insecure_registries
                elif x == 'docker_registry_insecure':
                    params['docker_registry_insecure'] = \
                     defaults.docker_registry_insecure
                elif x == 'ansible_playbook':
                    params['ansible_playbook'] = \
                     defaults.ansible_playbook
                else:
                    return ("%s not defined in inventory" % x)

        for k,v in vars(defaults).iteritems():
            if not k in params.keys():
                params[k] = v

        pbook     = params['ansible_playbook']
        try:
            with open(pbook) as file:
                pass
        except IOError as e:
            return ("Playbook not found : %s" % pbook)

        return STATUS_VALID


    def __init__(self, json_entity, args):
        super(ContrailAnsiblePlayBook, self).__init__()
        self.hosts_in_inv = json_entity[0]["hosts_in_inv"]
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]
        inventory = parameters["inventory"]
        self.current_status = self.validate_provision_params(inventory, args)
        self.pbook_path         = inventory["[all:vars]"]["ansible_playbook"]
        pbook_dir = os.path.dirname(self.pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        inv_file = inv_dir + cluster_id + ".inv"
        SMAnsibleUtils(None).create_inv_file(inv_file, inventory)

        self.var_mgr            = VariableManager()
        self.ldr                = DataLoader()
        self.args               = args
        self.inventory          = Inventory(loader=self.ldr,
                                            variable_manager=self.var_mgr,
                                            host_list=inv_file)
        self.var_mgr.set_inventory(self.inventory)

        Options = namedtuple('Options', ['connection', 'forks', 'module_path',
                             'become', 'become_method', 'become_user', 'check',
                             'listhosts', 'listtasks', 'listtags', 'syntax',
                             'verbosity'])
        self.options = Options(connection='ssh', forks=100, module_path=None,
                               become=True,
                               become_method='sudo', become_user='root',
                               check=False, listhosts=None, listtasks=None,
                               listtags=None, syntax=None, verbosity=None)

        self.pws         = {}
        self.pb_executor = PlaybookExecutor(playbooks=[self.pbook_path],
                                            inventory=self.inventory,
                                            variable_manager=self.var_mgr,
                                            loader=self.ldr,
                                            options=self.options,
                                            passwords=self.pws)
        try:
            self._sm_logger = ServerMgrlogger()
        except:
            f = open("/var/log/contrail-server-manager/debug.log", "a")
            f.write("Ansible Callback Init - ServerMgrlogger init failed\n")
            f.close()


    def update_status(self):
        for h in self.hosts_in_inv:
            status_resp = { "server_id" : h,
                            "state" : self.current_status }
            SMAnsibleUtils(self._sm_logger).send_REST_request(self.args.ansible_srvr_ip,
                              SM_STATUS_PORT, "ansible_status", 
                              urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

    def run(self):
        #import pdb; pdb.set_trace()
        stats = None
        if self.current_status == STATUS_VALID:
            self.current_status = STATUS_IN_PROGRESS
            
            self.update_status()
            try:
                rv = self.pb_executor.run()
            except Exception as e:
                self._sm_logger.log(self._sm_logger.ERROR, e)
                self.current_status = STATUS_FAILED
                self.update_status()
                return None

            stats = self.pb_executor._tqm._stats

            if rv == 0:
                self.current_status = STATUS_SUCCESS
            else:
                self.current_status = STATUS_FAILED

            # No need to update_status here. Per node status gets sent from
            # sm_ansible_callback.py

        else:
            self.update_status()
        return stats

class ContrailOpenstackPlayBook(multiprocessing.Process):

    def __init__(self, json_entity, args):
        super(ContrailOpenstackPlayBook, self).__init__()
        try:
            self._sm_logger = ServerMgrlogger()
        except:
            f = open("/var/log/contrail-server-manager/debug.log", "a")
            f.write("Ansible Callback Init - ServerMgrlogger init failed\n")
            f.close()

        # Initialize some common stuff...
        self.json_entity  = json_entity
        self.args         = args
        self.hosts_in_inv = json_entity[0]["hosts_in_inv"]
        self.tasks        = re.split(r'[,\ ]+', json_entity[0]["tasks"])

    def extra_vars_for_action(self, action, kolla_vars_dir):
        ev = { 'action': action }
        with open(kolla_vars_dir + '/../etc/kolla/globals.yml') as info:
            ev.update(yaml.load(info))
        with open(kolla_vars_dir + '/../etc/kolla/passwords.yml') as info:
            ev.update(yaml.load(info))
        return ev

    def set_options_for_action(self, action, ev):
        Options = namedtuple('Options', ['connection', 'forks', 'module_path',
                             'become', 'become_method', 'become_user', 'check',
                             'listhosts', 'listtasks', 'listtags', 'syntax',
                             'verbosity', 'extra_vars'])
        op = Options(connection='ssh', forks=100,
                     module_path=None, become=True, become_method='sudo',
                     become_user='root', check=False, listhosts=None,
                     listtasks=None, listtags=None, syntax=None,
                     verbosity=None, extra_vars=ev)
        if action == 'bootstrap-servers':
            self.bs_options = op
        elif action == 'deploy':
            self.deploy_options = op
        elif action == 'post-deploy':
            self.post_deploy_options = op
        elif action == 'post-deploy-contrail':
            self.post_deploy_contrail_options = op
        elif action == 'kolla-destroy':
            self.kolla_destroy_options = op
        else:
            self._sm_logger.log(self._sm_logger.ERROR,
                    "Action %s is not valid" % action)

    def init_kolla_destroy_playbook(self):
        json_entity = self.json_entity
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]

        self.kolla_destroy_pbook_path = parameters["kolla_destroy_pb"]
        pbook_dir = os.path.dirname(self.kolla_destroy_pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        kolla_inv_file = inv_dir + cluster_id + "_kolla.inv"
        SMAnsibleUtils(None).create_inv_file(kolla_inv_file, \
                parameters['kolla_inv'])

        self.kolla_destroy_var_mgr   = VariableManager()
        self.kolla_destroy_inventory = Inventory(loader=DataLoader(),
                                    variable_manager=self.kolla_destroy_var_mgr,
                                    host_list=kolla_inv_file)
        ev = self.extra_vars_for_action('destroy', pbook_dir)
        self.set_options_for_action('destroy', ev)

        self.kolla_destroy_var_mgr.set_inventory(self.kolla_destroy_inventory)
        self.kolla_destroy_var_mgr.extra_vars = ev
        self.kolla_destroy_pb_executor = \
                PlaybookExecutor(playbooks=[self.kolla_destroy_pbook_path],
                                  inventory=self.kolla_destroy_inventory,
                                 variable_manager=self.kolla_destroy_var_mgr,
                                 loader=DataLoader(),
                                 options=self.kolla_destroy_options,
                                 passwords={})

    def init_kolla_post_deploy_playbook(self):
        json_entity = self.json_entity
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]

        pbook_dir = os.path.dirname(self.bs_pbook_path)
        self.post_deploy_pbook_path = pbook_dir + '/post-deploy.yml'

        inv_dir = pbook_dir + '/inventory/'
        kolla_inv_file = inv_dir + cluster_id + "_kolla.inv"
        SMAnsibleUtils(None).create_inv_file(kolla_inv_file, \
                parameters['kolla_inv'])

        self.post_deploy_var_mgr   = VariableManager()
        self.post_deploy_inventory = Inventory(loader=DataLoader(),
                                      variable_manager=self.post_deploy_var_mgr,
                                      host_list=kolla_inv_file)
        ev = self.extra_vars_for_action('post-deploy', pbook_dir)
        self.set_options_for_action('post-deploy', ev)

        self.post_deploy_var_mgr.set_inventory(self.post_deploy_inventory)
        self.post_deploy_var_mgr.extra_vars = ev
        self.post_deploy_pb_executor = \
                PlaybookExecutor(playbooks=[self.post_deploy_pbook_path],
                                 inventory=self.post_deploy_inventory,
                                 variable_manager=self.post_deploy_var_mgr,
                                 loader=DataLoader(),
                                 options=self.post_deploy_options,
                                 passwords={})


    def init_kolla_deploy_playbook(self):
        json_entity = self.json_entity
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]

        self.deploy_pbook_path = parameters["kolla_deploy_pb"]
        pbook_dir = os.path.dirname(self.bs_pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        kolla_inv_file = inv_dir + cluster_id + "_kolla.inv"
        SMAnsibleUtils(None).create_inv_file(kolla_inv_file, \
                parameters['kolla_inv'])

        self.deploy_var_mgr   = VariableManager()
        self.deploy_inventory = Inventory(loader=DataLoader(),
                                      variable_manager=self.deploy_var_mgr,
                                      host_list=kolla_inv_file)
        ev = self.extra_vars_for_action('deploy', pbook_dir)
        self.set_options_for_action('deploy', ev)

        self.deploy_var_mgr.set_inventory(self.deploy_inventory)
        self.deploy_var_mgr.extra_vars = ev
        self.deploy_pb_executor = \
                PlaybookExecutor(playbooks=[self.deploy_pbook_path],
                                 inventory=self.deploy_inventory,
                                 variable_manager=self.deploy_var_mgr,
                                 loader=DataLoader(),
                                 options=self.deploy_options,
                                 passwords={})

    def init_kolla_bootstrap_playbook(self):
        json_entity = self.json_entity
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]

        self.bs_pbook_path = parameters["kolla_bootstrap_pb"]
        pbook_dir = os.path.dirname(self.bs_pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        kolla_inv_file = inv_dir + cluster_id + "_kolla.inv"
        SMAnsibleUtils(None).create_inv_file(kolla_inv_file, \
                parameters['kolla_inv'])

        self.bs_var_mgr   = VariableManager()
        self.bs_inventory = Inventory(loader=DataLoader(),
                                      variable_manager=self.bs_var_mgr,
                                      host_list=kolla_inv_file)
        ev = self.extra_vars_for_action('bootstrap-servers', pbook_dir)
        self.set_options_for_action('bootstrap-servers', ev)

        self.bs_var_mgr.set_inventory(self.bs_inventory)
        self.bs_var_mgr.extra_vars = ev
        self.bs_pb_executor = \
                PlaybookExecutor(playbooks=[self.bs_pbook_path],
                                            inventory=self.bs_inventory,
                                            variable_manager=self.bs_var_mgr,
                                            loader=DataLoader(),
                                            options=self.bs_options,
                                            passwords={})

    def init_contrail_playbook(self):
        json_entity = self.json_entity
        args        = self.args
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]
        inventory  = parameters['inventory']
        self.current_status = self.validate_provision_params(inventory, args)
        self.pbook_path     = inventory["[all:vars]"]["ansible_playbook"]
        pbook_dir = os.path.dirname(self.pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        inv_file = inv_dir + cluster_id + ".inv"
        SMAnsibleUtils(None).create_inv_file(inv_file, parameters['inventory'])

        self.ldr                = DataLoader()
        self.var_mgr            = VariableManager()
        self.inventory          = Inventory(loader=self.ldr,
                                            variable_manager=self.var_mgr,
                                            host_list=inv_file)
        self.var_mgr.set_inventory(self.inventory)

        Options = namedtuple('Options', ['connection', 'forks', 'module_path',
                             'become', 'become_method', 'become_user', 'check',
                             'listhosts', 'listtasks', 'listtags', 'syntax',
                             'verbosity'])
        self.options = Options(connection='ssh', forks=100, module_path=None,
                               become=True,
                               become_method='sudo', become_user='root',
                               check=False, listhosts=None, listtasks=None,
                               listtags=None, syntax=None, verbosity=None)

        self.pb_executor = PlaybookExecutor(playbooks=[self.pbook_path],
                                            inventory=self.inventory,
                                            variable_manager=self.var_mgr,
                                            loader=self.ldr,
                                            options=self.options,
                                            passwords={})

    def init_kolla_post_deploy_contrail_playbook(self):
        json_entity = self.json_entity
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]

        self.deploy_pbook_path = parameters["kolla_deploy_pb"]
        pbook_dir = os.path.dirname(self.bs_pbook_path)
        self.post_deploy_contrail_pbook_path = pbook_dir + \
                '/post-deploy-contrail.yml'

        inv_dir = pbook_dir + '/inventory/'
        kolla_inv_file = inv_dir + cluster_id + "_kolla.inv"
        SMAnsibleUtils(None).create_inv_file(kolla_inv_file, \
                parameters['kolla_inv'])

        self.post_deploy_contrail_var_mgr   = VariableManager()
        self.post_deploy_contrail_inventory = Inventory(loader=DataLoader(),
                                      variable_manager=self.post_deploy_contrail_var_mgr,
                                      host_list=kolla_inv_file)
        ev = self.extra_vars_for_action('post-deploy-contrail', pbook_dir)
        self.set_options_for_action('post-deploy-contrail', ev)

        self.post_deploy_contrail_var_mgr.set_inventory(self.post_deploy_contrail_inventory)
        self.post_deploy_contrail_var_mgr.extra_vars = ev
        self.post_deploy_contrail_pb_executor = \
                PlaybookExecutor(playbooks=[self.post_deploy_contrail_pbook_path],
                                 inventory=self.post_deploy_contrail_inventory,
                                 variable_manager=self.post_deploy_contrail_var_mgr,
                                 loader=DataLoader(),
                                 options=self.post_deploy_contrail_options,
                                 passwords={})



    def validate_provision_params(self, inv, defaults):

        keys_to_check = ["ansible_playbook",
                         "docker_insecure_registries",
                         "docker_registry_insecure"]

        params = inv.get("[all:vars]", None)
        if params == None:
            return ("[all:vars] not defined")

        for x in keys_to_check:
            if not x in params.keys():
                if x == "docker_insecure_registries":
                    params['docker_insecure_registries'] = \
                     defaults.docker_insecure_registries
                elif x == 'docker_registry_insecure':
                    params['docker_registry_insecure'] = \
                     defaults.docker_registry_insecure
                elif x == 'ansible_playbook':
                    params['ansible_playbook'] = \
                     defaults.ansible_playbook
                else:
                    return ("%s not defined in inventory" % x)

        for k,v in vars(defaults).iteritems():
            if not k in params.keys():
                params[k] = v

        pbook     = params['ansible_playbook']
        try:
            with open(pbook) as file:
                pass
        except IOError as e:
            return ("Playbook not found : %s" % pbook)

        return STATUS_VALID

    def update_status(self):
        for h in self.hosts_in_inv:
            status_resp = { "server_id" : h,
                            "state" : self.current_status }
            SMAnsibleUtils(self._sm_logger).send_REST_request(self.args.ansible_srvr_ip,
                              SM_STATUS_PORT, "ansible_status", 
                              urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

    def run_os_bootstrap_pb(self):
        try:
            self.init_kolla_bootstrap_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                    "Starting bootstrap playbook %s" % self.bs_pbook_path)
            rv = self.bs_pb_executor.run()
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = None
        return rv

    def run_os_deploy_pb(self):
        try:
            self.init_kolla_deploy_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                "Starting deploy playbook %s" % self.deploy_pbook_path)
            rv = self.deploy_pb_executor.run()
            if rv == 0:
                self.current_status = STATUS_IN_PROGRESS
            else:
                self.current_status = STATUS_FAILED
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = None


    def run_os_post_deploy_pb(self):
        try:
            self.init_kolla_post_deploy_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                "Starting post deploy playbook %s" % self.post_deploy_pbook_path)
            rv = self.post_deploy_pb_executor.run()
            if rv == 0:
                self.current_status = STATUS_IN_PROGRESS
            else:
                self.current_status = STATUS_FAILED
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = None
        return rv

    def run_os_post_deploy_pb(self):
        try:
            self.init_kolla_post_deploy_contrail_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                "Starting post deploy contrail playbook %s" % self.post_deploy_contrail_pbook_path)
            rv = self.post_deploy_contrail_pb_executor.run()
            if rv == 0:
                self.current_status = STATUS_IN_PROGRESS
            else:
                self.current_status = STATUS_FAILED
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = -1
        return rv

    def run_os_destroy_pb(self):
        try:
            self.init_kolla_destroy_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                "Starting kolla destroy playbook %s" % self.kolla_destroy_pbook_path)
            rv = self.kolla_destroy_pb_executor.run()
            if rv == 0:
                self.current_status = STATUS_IN_PROGRESS
            else:
                self.current_status = STATUS_FAILED
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = -1
        return rv

    def run_contrail_deploy_pb(self):
        try:
            self.init_contrail_playbook()
            self._sm_logger.log(self._sm_logger.INFO, 
                "Starting contrail playbook %s" % self.pbook_path)
            rv = self.pb_executor.run()
        except Exception as e:
            self._sm_logger.log(self._sm_logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status()
            rv = -1
        return rv


    def run(self):
        stats = None

        self._sm_logger.log(self._sm_logger.INFO, "Executing tasks: %s" % self.tasks)
        if 'openstack_bootstrap' in self.tasks:
            rv = self.run_os_bootstrap_pb()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status()
                return None
        if 'openstack_deploy' in self.tasks:
            rv = self.run_os_deploy_pb()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status()
                return None
        if 'openstack_post_deploy' in self.tasks:
            rv = self.run_os_post_deploy_pb()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status()
                return None
        if 'openstack_destroy' in self.tasks:
            rv = self.run_os_destroy_pb()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status()
                return None
        if 'contrail_deploy' in self.tasks:
            rv = self.run_contrail_deploy_pb()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status()
                return None
            else:
                stats = self.pb_executor._tqm._stats

        if rv == 0:
            self.current_status = STATUS_SUCCESS
        else:
            self.current_status = STATUS_FAILED

        # No need to update_status here. Per node status gets sent from
        # sm_ansible_callback.py

        #else:
        #    self.update_status()
        return stats

############## REFACTOR END - CODE ABOVE CAN BE DELETED AFTER TESTING ##########

#    wrapper class inspired from
#    http://docs.ansible.com/ansible/developing_api.html
# This class runs openstack playbooks followed by contrail ansible playbooks to
# deploy openstack and contrail nodes in sequence.
class ContrailAnsiblePlaybooks(multiprocessing.Process):

    def __init__(self, json_entity, args):
        super(ContrailAnsiblePlaybooks, self).__init__()
        try:
            self.logger = ServerMgrlogger()
        except:
            f = open("/var/log/contrail-server-manager/debug.log", "a")
            f.write("Ansible Callback Init - ServerMgrlogger init failed\n")
            f.close()

        #Initialize common stuff
        self.json_entity  = json_entity
        self.args         = args
        self.hosts_in_inv = json_entity[0]["hosts_in_inv"]
        if "kolla_inv" in json_entity[0]["parameters"]:
            self.hosts_in_kolla_inv = \
                    SMAnsibleUtils(self.logger).hosts_in_kolla_inventory(\
                        json_entity[0]['parameters']['kolla_inv'])

        self.tasks        = re.split(r'[,\ ]+', json_entity[0]["tasks"])

        #Initialize vars required for Ansible Playbook APIs
        self.options      = None
        self.extra_vars   = None
        self.pbook_path   = None
        self.var_mgr      = None
        self.inventory    = None
        self.pb_executor  = None

    def update_status(self, kolla=False):
        if kolla:
            hosts = self.hosts_in_kolla_inv
        else:
            hosts = self.hosts_in_inv

        for h in hosts:
            status_resp = { "server_id" : h,
                            "state" : self.current_status }
            SMAnsibleUtils(self.logger).send_REST_request(self.args.ansible_srvr_ip,
                              SM_STATUS_PORT, "ansible_status", 
                              urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

    def validate_provision_params(self, inv, defaults):

        keys_to_check = ["ansible_playbook",
                         "docker_insecure_registries",
                         "docker_registry_insecure"]

        params = inv.get("[all:vars]", None)
        if params == None:
            return ("[all:vars] not defined")

        for x in keys_to_check:
            if not x in params.keys():
                if x == "docker_insecure_registries":
                    params['docker_insecure_registries'] = \
                     defaults.docker_insecure_registries
                elif x == 'docker_registry_insecure':
                    params['docker_registry_insecure'] = \
                     defaults.docker_registry_insecure
                elif x == 'ansible_playbook':
                    params['ansible_playbook'] = \
                     defaults.ansible_playbook
                else:
                    return ("%s not defined in inventory" % x)

        for k,v in vars(defaults).iteritems():
            if not k in params.keys():
                params[k] = v

        pbook     = params['ansible_playbook']
        try:
            with open(pbook) as file:
                pass
        except IOError as e:
            return ("Playbook not found : %s" % pbook)

        return STATUS_VALID

    def create_kolla_param_files(self, pw, glbl, pbook_dir):
        self.logger.log(self.logger.INFO,"Changing globals and passwords files")
        pw_file_name = pbook_dir + '/../etc/kolla/passwords.yml'
        try:
            with open(pw_file_name) as kolla_pws:
                #SMAnsibleUtils(self.logger).merge_dict(pw, yaml.load(kolla_pws))
                self.logger.log(self.logger.INFO,
                    "Creating %s" % (pw_file_name))
        except IOError as e :
            self.logger.log(self.logger.INFO,
                    "%s : Creating %s" % (e, pw_file_name))
        finally:
            with open(pw_file_name, 'w+') as kolla_pws:
                yaml.dump(pw, kolla_pws, explicit_start=True,
                        default_flow_style=False, width=1000)

        gl_file_name = pbook_dir + '/../etc/kolla/globals.yml'
        try:
            with open(gl_file_name) as kolla_globals:
                #SMAnsibleUtils(self.logger).merge_dict(glbl,
                #               yaml.load(kolla_globals))
                self.logger.log(self.logger.INFO,
                    "Creating %s" % (gl_file_name))
        except IOError as e :
            self.logger.log(self.logger.INFO,
                    "%s : Creating %s" % (e, gl_file_name))
        finally:
            with open(gl_file_name, 'w+') as kolla_globals:
                yaml.dump(glbl, kolla_globals, explicit_start=True,
                          default_flow_style=False, width=1000)


    def run_playbook(self, pb, kolla, action):
        cluster_id = self.json_entity[0]["cluster_id"]
        parameters = self.json_entity[0]["parameters"]
        self.pbook_path = parameters[pb]
        pbook_dir = os.path.dirname(self.pbook_path)
        inv_dir = pbook_dir + '/inventory/'

        ev = None
        try:
            if kolla:
                inv_file = inv_dir + cluster_id + "_kolla.inv"
                inv_dict = parameters["kolla_inv"]
                kolla_pwds = parameters['kolla_passwords']
                kolla_vars = parameters['kolla_globals']
                self.create_kolla_param_files(kolla_pwds, kolla_vars, pbook_dir)
                ev = { 'action': action }
                with open(pbook_dir + '/../etc/kolla/globals.yml') as info:
                    ev.update(yaml.load(info))
                with open(pbook_dir + '/../etc/kolla/passwords.yml') as info:
                    ev.update(yaml.load(info))
            else:
                inv_file = inv_dir + cluster_id + ".inv"
                inv_dict = parameters["inventory"]
                self.current_status = self.validate_provision_params(inv_dict, self.args)

            Options = namedtuple('Options', ['connection', 'forks', 'module_path',
                             'become', 'become_method', 'become_user', 'check',
                             'listhosts', 'listtasks', 'listtags', 'syntax',
                             'verbosity', 'extra_vars'])
            self.options = Options(connection='ssh', forks=100, module_path=None,
                               become=True,
                               become_method='sudo', become_user='root',
                               check=False, listhosts=None, listtasks=None,
                               listtags=None, syntax=None, verbosity=None,
                               extra_vars=ev)

            self.logger.log(self.logger.INFO, "Creating inventory %s for playbook %s" %
                    (inv_file, self.pbook_path))
            SMAnsibleUtils(None).create_inv_file(inv_file, inv_dict)
            self.logger.log(self.logger.INFO, "Created inventory %s for playbook %s" %
                    (inv_file, self.pbook_path))
            self.var_mgr = VariableManager()
            self.inventory = Inventory(loader=DataLoader(),
                                       variable_manager=self.var_mgr,
                                       host_list=inv_file)
            self.var_mgr.set_inventory(self.inventory)
            if kolla:
                self.var_mgr.extra_vars = ev
            self.pb_executor = PlaybookExecutor(playbooks=[self.pbook_path],
                    inventory=self.inventory, variable_manager=self.var_mgr,
                    loader=DataLoader(), options=self.options, passwords={})
            self.logger.log(self.logger.INFO, "Starting playbook %s" %
                    self.pbook_path)

            # Update status before every playbook run
            if kolla:
                self.current_status = "openstack_" + action
            else:
                self.current_status = action
            self.update_status(kolla)

            rv = self.pb_executor.run()
            if rv != 0:
                self.current_status = STATUS_FAILED
                self.update_status(kolla)
                self.logger.log(self.logger.ERROR,
                        "Playbook Failed: %s" % self.pbook_path)
                rv = None
            else:
                rv = self.pb_executor._tqm._stats
        except Exception as e:
            self.logger.log(self.logger.ERROR, e)
            self.current_status = STATUS_FAILED
            self.update_status(kolla)
            rv = None
        return rv

    def run(self):
        self.logger.log(self.logger.INFO,
            "Executing Ansible Playbook Actions: %s" % self.tasks)
        if 'openstack_bootstrap' in self.tasks:
            rv = self.run_playbook("kolla_bootstrap_pb", True,
                "bootstrap-servers")
            if rv == None:
                return rv

        if 'openstack_deploy' in self.tasks:
            rv = self.run_playbook("kolla_deploy_pb", True, "deploy")
            if rv == None:
                return rv

        if 'openstack_post_deploy' in self.tasks:
            rv = self.run_playbook("kolla_post_deploy_pb", True, "post-deploy")
            if rv == None:
                return rv

        if 'openstack_destroy' in self.tasks:
            rv = self.run_playbook("kolla_destroy_pb", True, "destroy")
            if rv == None:
                return rv

        if 'contrail_deploy' in self.tasks:
            rv = self.run_playbook("contrail_deploy_pb", False,
                    "contrail-deploy")
            if rv == None:
                return rv

        # This has to happen after contrail_deploy
        if 'openstack_post_deploy_contrail' in self.tasks:
            rv = self.run_playbook("kolla_post_deploy_contrail_pb", True,
                    "post-deploy-contrail")
            if rv == None:
                return rv

