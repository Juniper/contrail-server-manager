import os
import sys
from datetime import datetime
from ansible.plugins.callback import CallbackBase

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

class PlayLogger:
    """
    Store log output in a single object
    One object per Ansible run
    """
    def __init__(self):
        self.log = ''
        self.runtime = 0
        try:
            self._sm_logger = ServerMgrlogger()
        except:
            f = open("/var/log/contrail-server-manager/debug.log", "a")
            f.write("Ansible Callback Init - ServerMgrlogger init failed\n")
            f.close()


    def append(self, log_line):
        self.log += log_line+"\n"
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
        self.logger = PlayLogger()
        self.start_time = datetime.now()

    def v2_runner_on_failed(self, result, ignore_errors=False):
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
                self.logger.append("fatal: [%s -> %s]: FAILED! => %s" % 
                        (result._host.get_name(), 
                         delegated_vars['ansible_host'], 
                         self._dump_results(result._result)))
            else:
                self.logger.append("fatal: [%s]: FAILED! => %s" % 
                        (result._host.get_name(), 
                         self._dump_results(result._result)))


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
            self.logger.append("failed: [%s -> %s] => (item=%s) => %s" % (result._host.get_name(), delegated_vars['ansible_host'], result._result['item'], self._dump_results(result._result)))
        else:
            self.logger.append("failed: [%s] => (item=%s) => %s" % (result._host.get_name(), result._result['item'], self._dump_results(result._result)))

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

