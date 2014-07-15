#!/usr/bin/python

import sys
import pdb
import xmlrpclib
import threading
import time
import subprocess
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger
import cobbler.api as capi

_DEF_COBBLER_IP = '127.0.0.1'
_DEF_COBBLER_PORT = ''
_DEF_USERNAME = 'cobbler'
_DEF_PASSWORD = 'cobbler'
_DEF_BASE_DIR = '/etc/contrail/'
_CONTRAIL_CENTOS_REPO = 'contrail-centos-repo'


class cobTokenCheckThread(threading.Thread):

    ''' Class to run function that keeps validating the cobbler token
        periodically (every 30 minutes) on a new thread. '''

    def __init__(self, timer, server, token):
        threading.Thread.__init__(self)
        self._timer = timer
        self._server = server
        self._token = token

    def run(self):
        _check_cobbler_token(self._timer, self._server,
                             self._token)


def _check_cobbler_token(timer, server, token):
    ''' This function keeps checking and validating the cobbler token
        periodically. It's called on a new thread and keep running
        for ever. '''
    try:
        while True:
            time.sleep(timer)
            server.token_check(token)
    except:
        print "Error in check cobbler token thread"


class ServerMgrCobbler:

    _cobbler_ip = _DEF_COBBLER_IP
    _cobbler_port = _DEF_COBBLER_PORT
    _cobbler_username = _DEF_USERNAME
    _cobbler_password = _DEF_PASSWORD
    _server = None
    _token = None
    # 30 minute timer to keep validating the cobbler token
    _COB_TOKEN_CHECK_TIMER = 1800

    def __init__(self, base_dir=_DEF_BASE_DIR,
                 ip_address=_DEF_COBBLER_IP,
                 port=_DEF_COBBLER_PORT,
                 username=_DEF_USERNAME,
                 password=_DEF_PASSWORD):

        self._smgr_log = ServerMgrlogger()
        self._smgr_log.log(self._smgr_log.DEBUG, "ServerMgrCobbler Init")


        # Store the passed in values
        self._cobbler_ip = ip_address
        self._cobbler_port = port
        self._cobbler_username = username
        self._cobbler_password = password
        try:
            if self._cobbler_port:
                self._server = xmlrpclib.Server(
                    "http://" +
                    self._cobbler_ip + ":" +
                    self._cobbler_port + "/cobbler_api")
            else:
                self._server = xmlrpclib.Server(
                    "http://" +
                    self._cobbler_ip + "/cobbler_api")
            self._token = self._server.login(self._cobbler_username,
                                             self._cobbler_password)

            # Copy contrail centos repo to cobber repos, so that target
            # systems can install and run puppet agent from kickstart.
            repo = self._server.find_repo({"name": _CONTRAIL_CENTOS_REPO})
            if repo:
                rid = self._server.get_repo_handle(
                    _CONTRAIL_CENTOS_REPO, self._token)
            else:
                rid = self._server.new_repo(self._token)
            self._server.modify_repo(rid, "arch", "x86_64", self._token)
            repo_dir = base_dir + "contrail-centos-repo"
            self._server.modify_repo(
                rid, "name", _CONTRAIL_CENTOS_REPO, self._token)
            self._server.modify_repo(rid, "mirror", repo_dir, self._token)
            self._server.modify_repo(rid, "keep_updated", True, self._token)
            self._server.modify_repo(rid, "priority", "99", self._token)
            self._server.modify_repo(rid, "rpm_list", [], self._token)
            self._server.modify_repo(rid, "yumopts", {}, self._token)
            self._server.modify_repo(rid, "mirror_locally", True, self._token)
            self._server.modify_repo(rid, "environment", {}, self._token)
            self._server.modify_repo(rid, "comment", "...", self._token)
            self._server.save_repo(rid, self._token)
            # Issue cobbler reposync for this repo
            cmd = "cobbler reposync --only=" + _CONTRAIL_CENTOS_REPO
            subprocess.call(cmd, shell=True)
            # Start a thread to keep cobbler token active. Comment out when
            # needed for testing...
            thread1 = cobTokenCheckThread(
                self._COB_TOKEN_CHECK_TIMER, self._server, self._token)
            # Make the thread as daemon
            thread1.daemon = True
            thread1.start()
        except Exception as e:
            raise e
    # End of __init__

    def create_distro(self, distro_name, image_type, path,
                      kernel_file, initrd_file, cobbler_ip_address):
        try:
            # If distro already exists in cobbler, nothing to do.
            distro = self._server.find_distro({"name":  distro_name})
            if distro:
                return
            distro_id = self._server.new_distro(self._token)
            self._server.modify_distro(distro_id, 'name',
                                       distro_name, self._token)
            self._server.modify_distro(distro_id, 'kernel',
                                       path + kernel_file, self._token)
            self._server.modify_distro(distro_id, 'initrd',
                                       path + initrd_file, self._token)
            if ((image_type == 'centos') or (image_type == 'fedora')):
                self._server.modify_distro(
                    distro_id, 'ksmeta',
                    'tree=http://' + cobbler_ip_address +
                    '/contrail/images/' + distro_name,
                    self._token)
            if (image_type == 'ubuntu'):
                self._server.modify_distro(distro_id, 'arch',
                                           'x86_64', self._token)
                self._server.modify_distro(distro_id, 'breed',
                                           'ubuntu', self._token)
                self._server.modify_distro(distro_id, 'os_version',
                                           'precise', self._token)
            elif ((image_type == 'esxi5.1') or
                  (image_type == 'esxi5.5')):
                if (image_type == 'esxi5.1'):
                    os_version = 'esxi51'
                else:
                    os_version = 'esxi55'
                self._server.modify_distro(
                    distro_id, 'ksmeta',
                    'tree=http://' + cobbler_ip_address +
                    '/contrail/images/' + distro_name,
                    self._token)
                self._server.modify_distro(
                    distro_id, 'arch', 'x86_64', self._token)
                self._server.modify_distro(
                    distro_id, 'breed', 'vmware', self._token)
                self._server.modify_distro(
                    distro_id, 'os_version', os_version, self._token)
                self._server.modify_distro(
                    distro_id, 'boot_files',
                    '$local_img_path/*.*=' + path + '/*.*',
                    self._token)
                self._server.modify_distro(
                    distro_id, 'template_files',
                    '/etc/cobbler/pxe/bootcfg_%s.template=' %(
                        os_version) +
                    '$local_img_path/cobbler-boot.cfg',
                    self._token)
            else:
                pass
            self._server.save_distro(distro_id, self._token)
        except Exception as e:
            raise e
    # End of create_distro

    def create_profile(self, profile_name,
                       distro_name, image_type, ks_file, kernel_options,
                        ks_meta):
        try:
            # If profile exists, nothing to do, jus return.
            profile = self._server.find_profile({"name":  profile_name})
            if profile:
                return
            profile_id = self._server.new_profile(self._token)
            self._server.modify_profile(profile_id, 'name',
                                        profile_name, self._token)
            self._server.modify_profile(profile_id, "distro",
                                        distro_name, self._token)
            self._server.modify_profile(profile_id, "kickstart",
                                        ks_file, self._token)
            self._server.modify_profile(profile_id, "kernel_options",
                                        kernel_options, self._token)
            self._server.modify_profile(profile_id, "ks_meta",
                                        ks_meta, self._token)
            if ((image_type == "centos") or (image_type == "fedora")):
                repo_list = [_CONTRAIL_CENTOS_REPO]
                self._server.modify_profile(profile_id, "repos",
                                            repo_list, self._token)
            self._server.save_profile(profile_id, self._token)
        except Exception as e:
            raise e
    # End of create_profile

    def create_repo(self, repo_name, mirror):
        try:
            repo = self._server.find_repo({"name": repo_name})
            if repo:
                rid = self._server.get_repo_handle(
                    repo_name, self._token)
            else:
                rid = self._server.new_repo(self._token)
            self._server.modify_repo(rid, "arch", "x86_64", self._token)
            self._server.modify_repo(
                rid, "name", repo_name, self._token)
            self._server.modify_repo(rid, "mirror", mirror, self._token)
            self._server.modify_repo(rid, "mirror_locally", True, self._token)
            self._server.save_repo(rid, self._token)
            # Issue cobbler reposync for this repo
            cmd = "cobbler reposync --only=" + repo_name
            subprocess.call(cmd, shell=True)
        except Exception as e:
            raise e
    # End of create_repo

    def create_system(self, system_name, profile_name, package_image_id,
                      mac, ip, subnet, gway, system_domain,
                      ifname, enc_passwd, server_license, esx_nicname,
                      power_type, power_user, power_pass, power_address,
                      base_image, server_ip):
        try:
            system = self._server.find_system({"name":  system_name})
            if system:
                system_id = self._server.get_system_handle(
                    system_name, self._token)
            else:
                system_id = self._server.new_system(self._token)
                self._server.modify_system(system_id, 'name',
                                           system_name, self._token)
            self._server.modify_system(
                system_id, "hostname", system_name, self._token)
            self._server.modify_system(
                system_id, "power_type", power_type, self._token)
            self._server.modify_system(
                system_id, "power_user", power_user, self._token)
            self._server.modify_system(
                system_id, "power_pass", power_pass, self._token)
            self._server.modify_system(
                system_id, "power_address", power_address, self._token)
            # For centos, create a sub-profile that has the repo for
            # package_image_id also made available for this system.
            if ((base_image['image_type'] == "centos") and
                (package_image_id)):
                sub_profile_name = profile_name + "-" + package_image_id
                sub_profile = self._server.find_profile(
                    {"name":  sub_profile_name})
                if not sub_profile:
                    sub_profile_id = self._server.new_subprofile(self._token)
                    self._server.modify_profile(
                        sub_profile_id, 'name',
                        sub_profile_name, self._token)
                    self._server.modify_profile(
                        sub_profile_id, 'parent',
                        profile_name, self._token)
                    repos = [
                        package_image_id,
                        _CONTRAIL_CENTOS_REPO ]
                    self._server.modify_profile(
                        sub_profile_id, 'repos',
                        repos, self._token)
                    self._server.save_profile(
                        sub_profile_id, self._token)
                # end if sub_profile
            else:
                sub_profile_name = profile_name
            #end if
            self._server.modify_system(
                system_id, "profile", sub_profile_name, self._token)
            interface = {}
            if mac:
                interface['macaddress-%s' % (ifname)] = mac
            if ip:
                interface['ipaddress-%s' % (ifname)] = ip
            if system_domain:
                interface['dnsname-%s' %
                          (ifname)] = system_name + '.' + system_domain
            self._server.modify_system(system_id, 'modify_interface',
                                       interface, self._token)
            ks_metadata = 'passwd=' + enc_passwd
            ks_metadata += ' ip_address=' + ip
            ks_metadata += ' system_name=' + system_name
            ks_metadata += ' system_domain=' + system_domain
            if package_image_id:
                ks_metadata += ' contrail_repo_name=' + \
                    package_image_id
            if ((base_image['image_type'] == 'esxi5.1') or
                (base_image['image_type'] == 'esxi5.5')):
                ks_metadata += ' server_license=' + server_license
                ks_metadata += ' esx_nicname=' + esx_nicname

                # temporary patch to have kickstart work for esxi. ESXi seems
                # to take kickstart from profile instead of system. So need to copy
                # ks_meta parameters at profile level too. This is a hack that would
                # be removed later - TBD Abhay
                profile = self._server.find_profile({"name":  profile_name})
                if profile:
                    profile_id = self._server.get_profile_handle(
                        profile_name, self._token)
                    self._server.modify_profile(
                        profile_id, 'ksmeta', ks_metadata, self._token)
                # end hack workaround
            #end if



            self._server.modify_system(system_id, 'ksmeta',
                                       ks_metadata, self._token)

            if (base_image['image_type'] == "ubuntu"):
                kernel_options = 'system_name=' + system_name
                kernel_options += ' system_domain=' + system_domain
                kernel_options += ' ip_address=' + ip
                kernel_options += ' server=' + server_ip
                if package_image_id:
                    kernel_options += ' contrail_repo_name=' + \
                        package_image_id
                self._server.modify_system(system_id, 'kernel_options',
                                           kernel_options, self._token)

            # Note : netboot is not enabled for the system yet. This is done
            # when API to power-cycle the server is called. For now set
            # net_enabled to False
            self._server.modify_system(
                system_id, 'netboot_enabled', False, self._token)
            self._server.save_system(system_id, self._token)
            #self._server.sync(self._token)
        except Exception as e:
            raise e
    # End of create_system

    def enable_system_netboot(self, system_name):
        try:
            system = self._server.find_system({"name":  system_name})
            if not system:
                raise Exception(
                    "cobbler error : System %s not found" % system_name)
            system_id = self._server.get_system_handle(
                system_name, self._token)
            self._server.modify_system(
                system_id, 'netboot_enabled', True, self._token)
            self._server.save_system(system_id, self._token)
            #Sync per every system is long
            #Do it at end
            #self._server.sync(self._token)
        except Exception as e:
            raise e
    # End of enable_system_netboot

    def reboot_system(self, reboot_system_list):
        try:
            power = {
                "power" : "reboot",
                "systems" : reboot_system_list }
            self._smgr_log.log(self._smgr_log.DEBUG, "reboot_system list is %s" % reboot_system_list)
            self._smgr_log.log(self._smgr_log.DEBUG, "Reboot System Start")
            task_id = self._server.background_power_system(power, self._token)
            self._smgr_log.log(self._smgr_log.DEBUG, "Reboot System End")

            # Alternate way using direct cobbler api, not needed, but commented
            # and kept for reference.
            # system = self._capi_handle.get_item(
            #     "system", system_name)
            # if not system:
            #     raise Exception(
            #         "cobbler error : System %s not found" % system_name)
            # else:
            #     self._capi_handle.reboot(system)
        except Exception as e:
            raise e
    # End of reboot_system

    def delete_distro(self, distro_name):
        try:
            self._server.remove_distro(distro_name, self._token)
        except Exception as e:
            pass
    # End of delete_distro

    def delete_repo(self, repo_name):
        try:
            self._server.remove_repo(repo_name, self._token)
        except Exception as e:
            pass
    # End of delete_repo

    def delete_profile(self, profile_name):
        try:
            self._server.remove_profile(profile_name, self._token)
        except Exception as e:
            pass
    # End of delete_profile

    def delete_system(self, system_name):
        try:
            system = self._server.find_system({"name":  system_name})
            if system:
                self._server.remove_system(system_name, self._token)
        except Exception as e:
            raise e
    # End of delete_system

    def sync(self):
        try:
            self._server.sync(self._token)
        except Exception as e:
            raise e
    # End of sync

# End class ServerMgrCobbler

if __name__ == "__main__":
    pass
