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

"""
    wrapper class inspired from
    http://docs.ansible.com/ansible/developing_api.html
"""
class ContrailAnsiblePlayBook(multiprocessing.Process):

    STATUS_VALID = "Parameters_Valid"
    STATUS_IN_PROGRESS = "In_Progress"
    STATUS_FILE_NOT_FOUND = "Playbook_Path_Error"
    STATUS_SUCCESS = "Provision_Success"
    STATUS_FAILED  = "Provision_Failed"

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
                    return ("%s not defined in parameters" % x)

        for k,v in vars(defaults).iteritems():
            if not k in params.keys():
                params[k] = v

        pbook     = params['ansible_playbook']
        try:
            with open(pbook) as file:
                pass
        except IOError as e:
            return ("Playbook not found : %s" % pbook)

        return self.STATUS_VALID


    def __init__(self, json_entity, args):
        super(ContrailAnsiblePlayBook, self).__init__()
        controllers = []
        analytics = []
        analyticsdb = []
        lb = []
        agent = []
        inv_file = None
        for params in json_entity:
            srvrid = params.get("server_id", None)
            parameters = params.get("parameters", None)
            inventory = parameters["inventory"]
            self.current_status = self.validate_provision_params(inventory, args)
            self.srvrid             = srvrid
            self.pbook_path         = inventory["[all:vars]"]["ansible_playbook"]
            pbook_dir = os.path.dirname(self.pbook_path)
            if self.current_status != self.STATUS_VALID:
                break

        inv_dir = pbook_dir + '/inventory/'
        inv_file = \
            tempfile.NamedTemporaryFile(dir=inv_dir, delete=False).name
        create_inv_file(inv_file, inventory)

        self.var_mgr            = VariableManager()
        self.ldr                = DataLoader()
        self.var_mgr.extra_vars = params['parameters']
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

    def run(self):
        #import pdb; pdb.set_trace()
        stats = None
        if self.current_status == self.STATUS_VALID:
            self.current_status = self.STATUS_IN_PROGRESS
            rv = self.pb_executor.run()
            print "RUN DONE"
            stats = self.pb_executor._tqm._stats

            run_success = True
            hosts = sorted(stats.processed.keys())
            for h in hosts:
                t = stats.summarize(h)
                if t['unreachable'] > 0 or t['failures'] > 0:
                    run_success = False

            # send callback to the function "record_logs" in the callback
            # plugin in the plugins directory
            self.pb_executor._tqm.send_callback('record_logs')

            if rv == 0:
                self.current_status = self.STATUS_SUCCESS
            else:
                self.current_status = self.STATUS_FAILED

            print self.current_status
        else:
            print "Validation Failed"
            self.current_status = self.STATUS_FAILED
        return stats
