import os
import sys
import urllib
import multiprocessing
import ConfigParser
import tempfile
from collections import namedtuple

from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor

from sm_ansible_utils import *
from sm_ansible_utils import _valid_roles
from sm_ansible_utils import _inventory_group
from sm_ansible_utils import _container_names
from sm_ansible_utils import SM_STATUS_PORT
from sm_ansible_utils import STATUS_IN_PROGRESS
from sm_ansible_utils import STATUS_VALID
from sm_ansible_utils import STATUS_SUCCESS
from sm_ansible_utils import STATUS_FAILED

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
        lb = []
        agent = []
        inv_file = None
        self.hosts_in_inv = json_entity[0]["hosts_in_inv"]
        cluster_id = json_entity[0]["cluster_id"]
        parameters = json_entity[0]["parameters"]
        inventory = parameters["inventory"]
        self.current_status = self.validate_provision_params(inventory, args)
        self.pbook_path         = inventory["[all:vars]"]["ansible_playbook"]
        pbook_dir = os.path.dirname(self.pbook_path)

        inv_dir = pbook_dir + '/inventory/'
        inv_file = inv_dir + cluster_id + ".inv"
        create_inv_file(inv_file, inventory)

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

    def update_status(self):
        for h in self.hosts_in_inv:
            status_resp = { "server_id" : h,
                            "state" : self.current_status }
            send_REST_request(self.args.ansible_srvr_ip,
                              SM_STATUS_PORT, "ansible_status", 
                              urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

    def run(self):
        #import pdb; pdb.set_trace()
        stats = None
        if self.current_status == STATUS_VALID:
            self.current_status = STATUS_IN_PROGRESS
            
            self.update_status()
            rv = self.pb_executor.run()
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
