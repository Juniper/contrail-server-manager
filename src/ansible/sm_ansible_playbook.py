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

    def validate_provision_params(self, entity, defaults):

        keys_to_check = ["ansible_playbook", "container_name", "ansible_host",
                         "ansible_user", "ansible_password",
                         "docker_insecure_registries",
                         "docker_registry_insecure", "container_name",
                         "container_image"]

        params = entity.get("parameters", None)
        if params['container_name'] == 'compute':
            return self.STATUS_VALID

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

        if params['container_name'] not in _valid_roles:
            return ("Invalid Role:%s" % params['container_name'])

        return self.STATUS_VALID


    def __init__(self, json_entity, args):
        super(ContrailAnsiblePlayBook, self).__init__()
        inv = {}
        inv["[all:children]"] = []
        controllers = []
        analytics = []
        analyticsdb = []
        lb = []
        agent = []
        for params in json_entity:
            srvrid = params.get("server_id", None)
            parameters = params.get("parameters", None)
            self.current_status = self.validate_provision_params(params, args)
            self.srvrid             = srvrid
            self.server             = parameters["ansible_host"]
            self.pbook_path         = parameters["ansible_playbook"]
            self.role               = parameters["container_name"]
            pbook_dir = os.path.dirname(self.pbook_path)
            if self.current_status != self.STATUS_VALID:
                break
            inv_key = "[" + _inventory_group[self.role] + "]"
            inv[inv_key] = self.server
            if _inventory_group[self.role] not in inv["[all:children]"]:
                inv["[all:children]"].append(_inventory_group[self.role])

            params["config_file_dest"]   = '/etc/contrailctl/' + \
                    _container_names[self.role] + '.conf'
            params["config_file_src"]    = pbook_dir + '/contrailctl/' + \
                    _container_names[self.role] + '.conf'
            #inv["[all:vars]"] = []
            #inv["[all:vars]"].append("docker_install_method="+str(args.docker_install_method))
            #inv["[all:vars]"].append("docker_package_name="+str(args.docker_package_name))
            print "config file is %s" % params["config_file_dest"]

            if self.current_status == self.STATUS_VALID:
                create_conf_file(params["config_file_src"],
                                 parameters[parameters["container_name"]])

        inv_dir = pbook_dir + '/inventory/'
        inv_file = \
            tempfile.NamedTemporaryFile(dir=inv_dir, delete=False).name
        create_inv_file(inv_file, inv)

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
            status_resp = { "server_id" : self.srvrid,
                            "role" : self.role,
                            "state" : self.current_status }
            send_REST_request(self.args.ansible_srvr_ip,
                              self.args.ansible_srvr_port,
                              "playbook_status", urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)
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

            status_resp = { "server_id" : self.srvrid,
                            "role" : self.role,
                            "state" : self.current_status }
            send_REST_request(self.args.ansible_srvr_ip,
                    self.args.ansible_srvr_port,
                              "playbook_status", urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)
            print self.current_status
        else:
            print "Validation Failed"
            status_resp = { "server_id" : self.srvrid,
                            "role" : self.role,
                            "state" : self.current_status }
            self.current_status = self.STATUS_FAILED
            send_REST_request(self.args.ansible_srvr_ip,
                    self.args.ansible_srvr_port,
                              "playbook_status", urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)
        return stats
