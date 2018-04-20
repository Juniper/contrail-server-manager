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
        no_run = parameters["no_run"]
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

            if no_run:
                return

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

