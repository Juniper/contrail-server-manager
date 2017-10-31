import os
import sys
import urllib
import ConfigParser
from datetime import datetime
from ansible.plugins.callback import CallbackBase

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
from server_mgr_logger import SMProvisionLogger as ServerMgrProvlogger

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from sm_ansible_utils import *
from sm_ansible_utils import SM_STATUS_PORT
from sm_ansible_utils import STATUS_SUCCESS
from sm_ansible_utils import STATUS_FAILED

class PlayLogger:
    default_config = dict()
    """
    Store log output in a single object
    One object per Ansible run
    """
    def __init__(self, cluster_id):
        self.log = ''
        self.runtime = 0
        self.defaults_file = "/etc/contrail/sm-client-config.ini"
        config = ConfigParser.SafeConfigParser()
        config.read([self.defaults_file])
        self.default_config["smgr"] = dict(config.items("SERVER-MANAGER"))
        self.smgr_ip = self.default_config["smgr"]["listen_ip_addr"]
        self._sm_prov_logger = None
        f = open("/var/log/contrail-server-manager/debug.log", "a")
        f.write("Ansible callback init - smgr_ip: %s" % self.smgr_ip)
        try:
            self._sm_logger = ServerMgrlogger()
            if cluster_id:
                self._sm_prov_logger = ServerMgrProvlogger(cluster_id)
            else:
                self._sm_logger.log(self._sm_logger.ERROR,
                   "cluster_id not found in inventory - provision specific "\
                   "logging will not be done")
        except:
            f = open("/var/log/contrail-server-manager/debug.log", "a")
            f.write("Ansible Callback Init - ServerMgrlogger init failed\n")
            f.close()


    def append(self, log_line):
        self.log += log_line+"\n"
        if self._sm_prov_logger:
            self._sm_prov_logger.log("info", log_line)
        self._sm_logger.log(self._sm_logger.INFO, log_line)

    def banner(self, msg):
        width = 78 - len(msg)
        if width < 3:
            width = 3
        filler = "*" * width
        return "\n%s %s " % (msg, filler)

class CallbackModule(CallbackBase):
    """
    Reference
    https://github.com/ansible/ansible/blob/v2.0.0.2-1/lib/ansible/plugins/callback/default.py
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stored'
    CALLBACK_NAME = 'syslog'

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.start_time = datetime.now()

    # Send provision status updates based on strategically placed tasks whose
    # name contains the magic word "sm_status_report". Sends the last word of
    # the task name as the status when that task executes 'ok'
    def report_status_using_task_name(self, result):
        tname = result._task.get_name()
        tlist = tname.split()
        if 'sm_status_report' in tname:
            status_resp = { "server_id" : result._host.get_name(),
                    "state" : tlist[-1] }
            SMAnsibleUtils(self.logger._sm_logger).send_REST_request(self.logger.smgr_ip,
                              SM_STATUS_PORT,
                              "ansible_status", urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        err_str = ""
        if ignore_errors:
            err_str = "ignored error"
        else:
            err_str = "fatal"

        delegated_vars = result._result.get('_ansible_delegated_vars', None)

        # Catch an exception
        # This may never be called because default handler deletes
        # the exception, since Ansible thinks it knows better
        if 'exception' in result._result:
            # Extract the error message and log it
            error = result._result['exception'].strip().split('\n')[-1]
            self.logger.append(error)

            # Remove the exception from the result so it's not shown every time
            del result._result['exception']

        # Else log the reason for the failure
        if result._task.loop and 'results' in result._result:
            # item_on_failed, item_on_skipped, item_on_ok
            self._process_items(result)
        else:
            if delegated_vars:
                self.logger.append("%s: [%s -> %s]: FAILED! => %s" %
                        (err_str, result._host.get_name(),
                         delegated_vars['ansible_host'],
                         self._dump_results(result._result)))
            else:
                self.logger.append("%s: [%s]: FAILED! => (item - %s) %s" %
                        (err_str, result._host.get_name(),
                            self._get_item(result._result),
                         self._dump_results(result._result)))

    def v2_runner_item_on_ok(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if result._task.action in ('include', 'include_role'):
            return
        elif result._result.get('changed', False):
            msg = 'changed'
        else:
            msg = 'ok'

        if delegated_vars:
            msg += ": [%s -> %s]" % (result._host.get_name(),
                    delegated_vars['ansible_host'])
        else:
            msg += ": [%s]" % result._host.get_name()

        msg += " => (item=%s)" % (self._get_item(result._result))

        if (self._display.verbosity > 0 or \
                '_ansible_verbose_always' in result._result) and \
                not '_ansible_verbose_override' in result._result:
            msg += " => %s" % self._dump_results(result._result)
        self.logger.append(msg)

    def v2_playbook_on_handler_task_start(self, task):
        self.logger.append("RUNNING HANDLER [%s]" % task.get_name().strip())

    def v2_runner_item_on_failed(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if 'exception' in result._result:
            msg = "An exception occurred during task execution. \
                    The full traceback is:\n" + result._result['exception']
            self.logger.append(msg)

        msg = "fatal: "
        if delegated_vars:
            msg += "[%s -> %s]" % (result._host.get_name(), \
                    delegated_vars['ansible_host'])
        else:
            msg += "[%s]" % (result._host.get_name())

        if "stderr" in result._result:
            self.logger.append(msg + str(result._result['stderr']))
        else:
            self.logger.append(msg + " (item=%s) => %s" %
                    (self._get_item(result._result),
                        self._dump_results(result._result)))
        self._handle_warnings(result._result)

    def v2_runner_on_ok(self, result):
        self._clean_results(result._result, result._task.action)
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if result._task.action == 'include':
            return
        elif result._result.get('changed', False):
            if delegated_vars:
                msg = "changed: [%s -> %s]" % (result._host.get_name(),
                                               delegated_vars['ansible_host'])
            else:
                msg = "changed: [%s]" % result._host.get_name()
        else:
            if delegated_vars:
                msg = "ok: [%s -> %s]" % (result._host.get_name(),
                                          delegated_vars['ansible_host'])
            else:
                msg = "ok: [%s]" % result._host.get_name()

        if result._task.loop and 'results' in result._result:
            # item_on_failed, item_on_skipped, item_on_ok
            self._process_items(result)
        else:
            self.logger.append(msg)
        self.report_status_using_task_name(result)


    def v2_runner_on_skipped(self, result):
        if result._task.loop and 'results' in result._result:
            # item_on_failed, item_on_skipped, item_on_ok
            self._process_items(result)
        else:
            msg = "skipping: [%s]" % result._host.get_name()
            self.logger.append(msg)

    def v2_runner_on_unreachable(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if delegated_vars:
            self.logger.append("fatal: [%s -> %s]: UNREACHABLE! => %s" %
                    (result._host.get_name(), delegated_vars['ansible_host'],
                     self._dump_results(result._result)))
        else:
            self.logger.append("fatal: [%s]: UNREACHABLE! => %s" %
                (result._host.get_name(), self._dump_results(result._result)))

    def v2_runner_on_no_hosts(self, task):
        self.logger.append("skipping: no hosts matched")

    def v2_playbook_on_task_start(self, task, is_conditional):
        self.logger.append("TASK [%s]" % task.get_name().strip())

    def v2_playbook_on_play_start(self, play):
        name = play.get_name().strip()
        vm = play.get_variable_manager()
        inv = vm._inventory
        vars = vm.get_vars(inv._loader, play)
        host_vars = vars['vars']['hostvars']
        cluster_id = host_vars[host_vars.keys()[0]].get('cluster_id', None)
        self.logger = PlayLogger(cluster_id)
        self.logger.append("CLUSTER = %s" % str(cluster_id))
        if not name:
            msg = "PLAY"
        else:
            msg = "PLAY [%s]" % name

        self.logger.append(msg)

    def v2_playbook_item_on_ok(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if result._task.action == 'include':
            return
        elif result._result.get('changed', False):
            if delegated_vars:
                msg = "changed: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "changed: [%s]" % result._host.get_name()
        else:
            if delegated_vars:
                msg = "ok: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "ok: [%s]" % result._host.get_name()

        msg += " => (item=%s)" % (result._result['item'])

        self.logger.append(msg)

    def v2_playbook_item_on_failed(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if 'exception' in result._result:
            # Extract the error message and log it
            error = result._result['exception'].strip().split('\n')[-1]
            self.logger.append(error)

            # Remove the exception from the result so it's not shown every time
            del result._result['exception']

        if delegated_vars:
            self.logger.append("failed: [%s -> %s] => (item=%s) => %s" %
                    (result._host.get_name(), delegated_vars['ansible_host'],
                        result._result['item'],
                        self._dump_results(result._result)))
        else:
            if 'stderr' in result._result:
                self.logger.append("failed: [%s] => (item = %s) \
                        => (stderr = %s)" % (result._host.get_name(), 
                            result._result['item'],
                            result._result['stderr']))
            else:
                self.logger.append("failed: [%s] => (item = %s) => %s" %
                    (result._host.get_name(), result._result['item'],
                        self._dump_results(result._result)))

    def v2_playbook_item_on_skipped(self, result):
        msg = "skipping: [%s] => (item=%s) " % (result._host.get_name(), result._result['item'])
        self.logger.append(msg)

    def v2_playbook_on_stats(self, stats):
        run_time = datetime.now() - self.start_time
        self.logger.runtime = run_time.seconds  # returns an int, unlike run_time.total_seconds()

        hosts = sorted(stats.processed.keys())
        for h in hosts:
            t = stats.summarize(h)

            msg = "PLAY RECAP [%s] : %s %s %s %s %s" % (
                h,
                "ok: %s" % (t['ok']),
                "changed: %s" % (t['changed']),
                "unreachable: %s" % (t['unreachable']),
                "skipped: %s" % (t['skipped']),
                "failed: %s" % (t['failures']),
            )

            if int(t['failures']) == 0:
                status_resp = { "server_id" : h,
                                "state" : STATUS_SUCCESS }
            else:
                status_resp = { "server_id" : h,
                        "state" : STATUS_FAILED }

            SMAnsibleUtils(self.logger._sm_logger).send_REST_request(self.logger.smgr_ip,
                              SM_STATUS_PORT,
                              "ansible_status", urllib.urlencode(status_resp),
                              method='PUT', urlencode=True)

            self.logger.append(msg)

    def record_logs(self):
        """
        Special callback added to this callback plugin
        Called from sm_ansible_playbook object
        """
        #FIXME: Use config file to determine log file
        f = open("/var/log/contrail-server-manager/debug.log", "a")
        f.write(self.logger.log)
        return 0

