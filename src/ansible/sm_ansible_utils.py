import os
import sys
import pycurl
import ConfigParser
import subprocess
import json
import yaml
import pdb
import glob
import shutil
import copy
from StringIO import StringIO

#sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
#from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

SM_STATUS_PORT = "9002"
STATUS_VALID = "parameters_valid"
STATUS_IN_PROGRESS = "provision_in_progress"
STATUS_SUCCESS = "provision_completed"
STATUS_FAILED  = "provision_failed"

# Kolla password keys for populating etc/kolla/passwords.yml
kolla_pw_keys = [
	"ceph_cluster_fsid",
	"rbd_secret_uuid",
	"cinder_rbd_secret_uuid",
	"database_password",
	"docker_registry_password",
	"aodh_database_password",
	"aodh_keystone_password",
        "rabbitmq_password",
        "rabbitmq_cluster_cookie",
	"barbican_database_password",
	"barbican_keystone_password",
	"barbican_p11_password",
	"barbican_crypto_key",
	"barbican_crypto_password",
	"keystone_admin_password",
	"keystone_database_password",
	"grafana_database_password",
	"grafana_admin_password",
	"glance_database_password",
	"glance_keystone_password",
	"gnocchi_database_password",
	"gnocchi_keystone_password",
	"karbor_database_password",
	"karbor_keystone_password",
	"karbor_openstack_infra_id",
	"kuryr_keystone_password",
	"nova_database_password",
	"nova_api_database_password",
	"nova_keystone_password",
	"placement_keystone_password",
	"neutron_database_password",
	"neutron_keystone_password",
	"cinder_database_password",
	"cinder_keystone_password",
	"cloudkitty_database_password",
	"cloudkitty_keystone_password",
	"panko_database_password",
	"panko_keystone_password",
	"freezer_database_password",
	"freezer_keystone_password",
	"sahara_database_password",
	"sahara_keystone_password",
	"designate_database_password",
	"designate_pool_manager_database_password",
	"designate_keystone_password",
	"designate_pool_id",
	"designate_rndc_key",
	"swift_keystone_password",
	"swift_hash_path_suffix",
	"swift_hash_path_prefix",
	"heat_database_password",
	"heat_keystone_password",
        "heat_domain_admin_password",
        "murano_database_password",
        "murano_keystone_password",
        "ironic_database_password",
        "ironic_keystone_password",
        "ironic_inspector_database_password",
        "ironic_inspector_keystone_password",
        "magnum_database_password",
        "magnum_keystone_password",
        "mistral_database_password",
        "mistral_keystone_password",
        "trove_database_password",
        "trove_keystone_password",
        "ceilometer_database_password",
        "ceilometer_keystone_password",
        "watcher_database_password",
        "watcher_keystone_password",
        "congress_database_password",
        "congress_keystone_password",
        "rally_database_password",
        "senlin_database_password",
        "senlin_keystone_password",
        "solum_database_password",
        "solum_keystone_password",
        "horizon_secret_key",
        "horizon_database_password",
        "telemetry_secret_key",
        "manila_database_password",
        "manila_keystone_password",
        "octavia_database_password",
        "octavia_keystone_password",
        "octavia_ca_password",
        "searchlight_keystone_password",
        "tacker_database_password",
        "tacker_keystone_password",
        "keepalived_password",
        "haproxy_password",
        "memcache_secret_key"]


# Role strings
CONTROLLER_CONTAINER  = "contrail-controller"
ANALYTICS_CONTAINER   = "contrail-analytics"
ANALYTICSDB_CONTAINER = "contrail-analyticsdb"
AGENT_CONTAINER       = "contrail-agent"
LB_CONTAINER          = "contrail-lb"
BARE_METAL_COMPUTE    = "contrail-compute"
CEPH_CONTROLLER       = "contrail-ceph-controller"
CEPH_COMPUTE          = "contrail-ceph-compute"
VC_PLUGIN             = "contrail-vcenter-plugin"
VCENTER_COMPUTE       = "contrail-vcenter-compute"
OPENSTACK_CONTAINER   = "openstack"
_DEF_BASE_PLAYBOOKS_DIR = "/opt/contrail/server_manager/ansible/playbooks"

# This dictionary is used to co-relate the names of roles and the respective ansible roles

_ansible_role_names = {
                     CONTROLLER_CONTAINER  : 'controller',
                     ANALYTICS_CONTAINER   : 'analytics',
                     ANALYTICSDB_CONTAINER : 'analyticsdb',
                     LB_CONTAINER          : 'lb',
                     BARE_METAL_COMPUTE    : 'bare_metal_agent',
                     CEPH_CONTROLLER       : 'ceph_master',
                     CEPH_COMPUTE          : 'ceph_compute',
                     OPENSTACK_CONTAINER   : 'openstack',
                     VC_PLUGIN             : 'vcenter_plugin'
}

# Add new roles and corresponding container_name here
_container_names = { CONTROLLER_CONTAINER  : 'controller',
                     ANALYTICS_CONTAINER   : 'analytics',
                     ANALYTICSDB_CONTAINER : 'analyticsdb',
                     LB_CONTAINER          : 'lb',
                     AGENT_CONTAINER       : 'agent',
                     BARE_METAL_COMPUTE    : 'agent',
                     CEPH_CONTROLLER       : 'ceph-master',
                     CEPH_COMPUTE          : 'ceph-compute',
                     VC_PLUGIN             : 'vcenterplugin',
                     VCENTER_COMPUTE       : 'vcentercompute',
                     # Dummy - there wont be a container named 'openstack'
                     # This is just for code convenience
                     OPENSTACK_CONTAINER   : 'openstack' 
                     }
_valid_roles = _container_names.keys()

_inventory_group = { CONTROLLER_CONTAINER  : "contrail-controllers",
                     ANALYTICS_CONTAINER   : "contrail-analytics",
                     ANALYTICSDB_CONTAINER : "contrail-analyticsdb",
                     LB_CONTAINER          : "contrail-lb",
                     AGENT_CONTAINER       : "contrail-compute",
                     BARE_METAL_COMPUTE    : "contrail-compute",
                     CEPH_CONTROLLER       : "ceph-controller",
                     CEPH_COMPUTE          : "ceph-compute",
                     VC_PLUGIN             : "contrail-vc-plugin",
                     VCENTER_COMPUTE       : "contrail-vc-compute",
                     OPENSTACK_CONTAINER   : 'openstack' 
                   }

# The values are the variable names used in contrail-ansible to launch the
# docker containers. The values of this dict get into the ansible inventory
#
_container_img_keys = { CONTROLLER_CONTAINER  : "controller_image",
                        ANALYTICS_CONTAINER   : "analytics_image",
                        ANALYTICSDB_CONTAINER : "analyticsdb_image",
                        LB_CONTAINER          : "lb_image",
                        AGENT_CONTAINER       : "agent_image",
                        CEPH_CONTROLLER       : "storage_ceph_controller_image",
                        VCENTER_COMPUTE       : "vcentercompute_image",
                        VC_PLUGIN             : "vcenterplugin_image" }

ansible_valid_tasks = [ 'openstack_bootstrap',
                        'openstack_deploy',
                        'openstack_destroy',
                        'openstack_post_deploy',
                        'openstack_post_deploy_contrail',
                        'contrail_deploy' ]
ansible_default_tasks = [ 'openstack_bootstrap',
                          'openstack_deploy',
                          'openstack_post_deploy',
                          'openstack_post_deploy_contrail',
                          'contrail_deploy' ]

kolla_inv_hosts = {
        '[control]' : [],
        '[network]' : [],
        '[compute]' : [],
        '[storage]' : [],
        '[monitoring]' : []
}


# Some <role>_image_full variables in kolla-ansible do not follow that rule.
# The 'key' for this dict is the entry in _openstack_containers list and the
# value is the actual variable name minus the '_image_full' string. For example
# for the nova-placement-api role, the actual variable is
# "placement_api_image_full"
_openstack_image_exceptions = {
        'nova-placement-api' : 'placement_api',
        'openvswitch-db-server': 'openvswitch_db'
}

# Do not change any string in this list without making sure they do not break
# the _openstack_image_exceptions dictionary above
_openstack_containers = [
  'barbican-api',
  'barbican-worker',
  'barbican-base',
  'barbican-keystone-listener',
  'base',
  'cinder-api',
  'cinder-base',
  'cinder-scheduler',
  'cinder-volume',
  'cinder-backup',
  'cron',
  'fluentd',
  'glance-api',
  'glance-base',
  'glance-registry',
  'haproxy',
  'heat-api-cfn',
  'heat-api',
  'heat-base',
  'heat-engine',
  'horizon',
  'keepalived',
  'keystone-base',
  'keystone-fernet',
  'keystone-ssh',
  'keystone',
  'kolla-toolbox',
  'mariadb',
  'memcached',
  'neutron-base',
  'neutron-dhcp-agent',
  'neutron-l3-agent',
  'neutron-metadata-agent',
  'neutron-openvswitch-agent',
  'neutron-server',
  'nova-api',
  'nova-base',
  'nova-compute-ironic',
  'nova-compute',
  'nova-conductor',
  'nova-consoleauth',
  'nova-libvirt',
  'nova-novncproxy',
  'nova-placement-api',
  'nova-scheduler',
  'nova-ssh',
  'openstack-base',
  'openvswitch-base',
  'openvswitch-db-server',
  'openvswitch-vswitchd',
  'rabbitmq',
  'ironic-pxe',
  'ironic-conductor',
  'ironic-api',
  'ironic-base',
  'ironic-inspector',
  'iscsid',
  'dnsmasq',
  'swift-account',
  'swift-base',
  'swift-container',
  'swift-object-expirer',
  'swift-object',
  'swift-proxy-server',
  'swift-rsyncd'
]

kolla_inv_groups = {
    '[chrony-server:children]' : ['control'],
    '[chrony:children]' : ['network', 'compute', 'storage', 'monitoring'],
    '[collectd:children]' : ['compute'],
    '[baremetal:children]' : ['control'],
    '[grafana:children]' : ['monitoring'],
    '[etcd:children]' : ['control'],
    '[karbor:children]' : ['control'],
    '[kibana:children]' : ['control'],
    '[telegraf:children]' : ['compute', 'control', 'monitoring', 'network',
        'storage'],
    '[elasticsearch:children]' : ['control'],
    '[haproxy:children]' : ['network'],
    '[mariadb:children]' : ['control'],
    '[rabbitmq:children]' : ['control'],
    '[mongodb:children]' : ['control'],
    '[keystone:children]' :['control'],
    '[glance:children]' : ['control'],
    '[nova:children]': ['control'],
    '[neutron:children]' : ['network'],
    '[cinder:children]' : ['control'],
    '[cloudkitty:children]' : ['control'],
    '[freezer:children]' : ['control'],
    '[memcached:children]' : ['control'],
    '[horizon:children]' : ['control'],
    '[swift:children]' : ['control'],
    '[barbican:children]' : ['control'],
    '[heat:children]' : ['control'],
    '[murano:children]' : ['control'],
    '[ceph:children]' : ['control'],
    '[ironic:children]' : ['control'],
    '[influxdb:children]' : ['monitoring'],
    '[magnum:children]' : ['control'],
    '[sahara:children]' : ['control'],
    '[solum:children]' : ['control'],
    '[mistral:children]' : ['control'],
    '[manila:children]' : ['control'],
    '[panko:children]' : ['control'],
    '[gnocchi:children]' : ['control'],
    '[ceilometer:children]' : ['control'],
    '[aodh:children]' : ['control'],
    '[congress:children]' : ['control'],
    '[tacker:children]' : ['control'],
    '[tempest:children]' : ['control'],
    '[senlin:children]' : ['control'],
    '[vmtp:children]' : ['control'],
    '[trove:children]' : ['control'],
    '[watcher:children]' : ['control'],
    '[rally:children]' : ['control'],
    '[searchlight:children]' : ['control'],
    '[octavia:children]' : ['control'],
    '[designate:children]': ['control'],
    '[placement:children]' : ['control'],
    '[glance-api:children]' : ['glance'],
    '[glance-registry:children]' : ['glance'],
    '[nova-api:children]' : ['nova'],
    '[nova-conductor:children]' : ['nova'],
    '[nova-consoleauth:children]' : ['nova'],
    '[nova-novncproxy:children]' : ['nova'],
    '[nova-scheduler:children]' : ['nova'],
    '[nova-spicehtml5proxy:children]' : ['nova'],
    '[nova-compute-ironic:children]' : ['nova'],
    '[nova-serialproxy:children]' : ['nova'],
    '[neutron-server:children]' : ['control'],
    '[neutron-dhcp-agent:children]' : ['neutron'],
    '[neutron-l3-agent:children]' : ['neutron'],
    '[neutron-lbaas-agent:children]' : ['neutron'],
    '[neutron-metadata-agent:children]' : ['neutron'],
    '[neutron-vpnaas-agent:children]' : [],
    '[ceph-mon:children]' : ['ceph'],
    '[ceph-rgw:children]' : ['ceph'],
    '[ceph-osd:children]' : ['storage'],
    '[cinder-api:children]' : ['cinder'],
    '[cinder-backup:children]' : ['storage'],
    '[cinder-scheduler:children]' : ['cinder'],
    '[cinder-volume:children]' : ['storage'],
    '[cloudkitty-api:children]' : ['cloudkitty'],
    '[cloudkitty-processor:children]' : ['cloudkitty'],
    '[freezer-api:children]' : ['freezer'],
    '[iscsid:children]': ['compute', 'storage', 'ironic-conductor'],
    '[tgtd:children]' : ['storage'],
    '[karbor-api:children]' : ['karbor'],
    '[karbor-protection:children]' : ['karbor'],
    '[karbor-operationengine:children]' : ['karbor'],
    '[manila-api:children]' : ['manila'],
    '[manila-scheduler:children]' : ['manila'],
    '[manila-share:children]' : ['network'],
    '[manila-data:children]' : ['manila'],
    '[swift-proxy-server:children]' : ['swift'],
    '[swift-account-server:children]' : ['storage'],
    '[swift-container-server:children]' : ['storage'],
    '[swift-object-server:children]' : ['storage'],
    '[barbican-api:children]' : ['barbican'],
    '[barbican-keystone-listener:children]' : ['barbican'],
    '[barbican-worker:children]' : ['barbican'],
    '[trove-api:children]' : ['trove'],
    '[trove-conductor:children]' : ['trove'],
    '[trove-taskmanager:children]' : ['trove'],
    '[heat-api:children]' : ['heat'],
    '[heat-api-cfn:children]' : ['heat'],
    '[heat-engine:children]' : ['heat'],
    '[murano-api:children]' : ['murano'],
    '[murano-engine:children]' : ['murano'],
    '[ironic-api:children]' : ['ironic'],
    '[ironic-conductor:children]' : ['ironic'],
    '[ironic-inspector:children]' : ['ironic'],
    '[ironic-pxe:children]' : ['ironic'],
    '[magnum-api:children]' : ['magnum'],
    '[magnum-conductor:children]' : ['magnum'],
    '[solum-api:children]' : ['solum'],
    '[solum-worker:children]' : ['solum'],
    '[solum-deployer:children]' : ['solum'],
    '[solum-conductor:children]' : ['solum'],
    '[mistral-api:children]' : ['mistral'],
    '[mistral-executor:children]' : ['mistral'],
    '[mistral-engine:children]' : ['mistral'],
    '[aodh-api:children]' : ['aodh'],
    '[aodh-evaluator:children]' : ['aodh'],
    '[aodh-listener:children]' : ['aodh'],
    '[aodh-notifier:children]' : ['aodh'],
    '[panko-api:children]' : ['panko'],
    '[gnocchi-api:children]' : ['gnocchi'],
    '[gnocchi-statsd:children]' : ['gnocchi'],
    '[gnocchi-metricd:children]' : ['gnocchi'],
    '[sahara-api:children]' : ['sahara'],
    '[sahara-engine:children]' : ['sahara'],
    '[ceilometer-api:children]' : ['ceilometer'],
    '[ceilometer-central:children]' : ['ceilometer'],
    '[ceilometer-notification:children]' : ['ceilometer'],
    '[ceilometer-collector:children]' : ['ceilometer'],
    '[ceilometer-compute:children]' : ['compute'],
    '[congress-api:children]' : ['congress'],
    '[congress-datasource:children]' : ['congress'],
    '[congress-policy-engine:children]' : ['congress'],
    '[multipathd:children]' : ['compute'],
    '[watcher-api:children]' : ['watcher'],
    '[watcher-engine:children]' : ['watcher'],
    '[watcher-applier:children]' : ['watcher'],
    '[senlin-api:children]' : ['senlin'],
    '[senlin-engine:children]' : ['senlin'],
    '[searchlight-api:children]' : ['searchlight'],
    '[searchlight-listener:children]' : ['searchlight'],
    '[octavia-api:children]' : ['octavia'],
    '[octavia-health-manager:children]' : ['octavia'],
    '[octavia-housekeeping:children]' : ['octavia'],
    '[octavia-worker:children]' : ['octavia'],
    '[designate-api:children]' : ['designate'],
    '[designate-central:children]' : ['designate'],
    '[designate-mdns:children]' : ['designate'],
    '[designate-worker:children]' : ['designate'],
    '[designate-sink:children]' : ['designate'],
    '[designate-backend-bind9:children]' : ['designate'],
    '[placement-api:children]' : ['placement']
}

class SMAnsibleUtils():
    def __init__(self, logger):
        self.logger = logger

    def merge_dict(self, d1, d2):
        for k,v2 in d2.items():
            v1 = d1.get(k) # returns None if v1 has no value for this key
            if ( isinstance(v1, dict) and
                 isinstance(v2, dict) ):
                self.merge_dict(v1, v2)
            elif v1:
                #do nothing, Retain value
                #msg = "%s already present in dict d1," \
                #    "Retaining value %s against %s" % (k, v1, v2)
                #if self.logger:
                #    self.logger.log(self.logger.DEBUG, msg)
                pass
            else:
                #do nothing, Retain value
                #msg = "adding %s:%s" % (k, v1)
                #if self.logger:
                #    self.logger.log(self.logger.DEBUG, msg)
                d1[k] = copy.deepcopy(v2)

    def hosts_in_kolla_inventory(self, inventory):
        hosts = []
        for k in kolla_inv_hosts:
            if k in inventory.keys():
                for ip in inventory[k]:
                    h = ip.split()
                    if h[0] not in hosts:
                        hosts.append(h[0])
        return hosts

    def hosts_in_inventory(self, inventory):
        hosts = []
        for role in _valid_roles:
            grp = "[" + _inventory_group[role] + "]"
            if grp in inventory.keys():
                for ip in inventory[grp]:
                    h = ip.split()
                    if h[0] not in hosts:
                        hosts.append(h[0])
        return hosts

    def send_REST_request(self, ip, port, endpoint, payload,
                          method='POST', urlencode=False):
        try:
            response = StringIO()
            headers = ["Content-Type:application/json"]
            url = "http://%s:%s/%s" %(ip, port, endpoint)
            conn = pycurl.Curl()
            if method == "PUT":
                conn.setopt(pycurl.CUSTOMREQUEST, method)
                if urlencode == False:
                    first = True
                    for k,v in payload.iteritems():
                        if first:
                            url = url + '?'
                            first = False
                        else:
                            url = url + '&'
                        url = url + ("%s=%s" % (k,v))
                else:
                    url = url + '?' + payload
            if self.logger:
                self.logger.log(self.logger.INFO,
                                "Sending post request to %s" % url)
            conn.setopt(pycurl.URL, url)
            conn.setopt(pycurl.HTTPHEADER, headers)
            conn.setopt(pycurl.POST, 1)
            if urlencode == False:
                conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
            conn.setopt(pycurl.WRITEFUNCTION, response.write)
            conn.perform()
            return response.getvalue()
        except:
            return None
    
    def create_inv_file(self, fname, dictionary):
        with open(fname, 'w') as invfile:
            for key, value in dictionary.items():
                if isinstance(value, str):
                    invfile.write(key)
                    invfile.write('\n')
                    invfile.write(value)
                    invfile.write('\n')
                    invfile.write('\n')
                if isinstance(value, list):
                    invfile.write(key)
                    invfile.write('\n')
                    for item in value:
                        invfile.write(item)
                        invfile.write('\n')
                    invfile.write('\n')
                if isinstance(value, dict):
                    invfile.write(key)
                    invfile.write('\n')
                    for k, v in value.items():
                        if isinstance(v, str) or isinstance(v, bool):
                            invfile.write(k+"=")
                            invfile.write(str(v))
                            invfile.write('\n')
                            invfile.write('\n')
                        if isinstance(v, list) or isinstance(v, dict):
                            invfile.write(k+"=")
                            invfile.write(str(v))
                            invfile.write('\n')
                            invfile.write('\n')
    
    
    '''
    Function to verify that SM Lite compute has completed provision after reboot
    '''
    def ansible_verify_provision_complete(self, smlite_non_mgmt_ip):
        try:
            cmd = ("lsmod | grep vrouter")
            output = subprocess.check_output(cmd, shell=True)
            if "vrouter" not in output:
                return False
            cmd = ("ifconfig vhost0 | grep %s" %(smlite_non_mgmt_ip))
            output = subprocess.check_output(cmd, shell=True)
            if str(smlite_non_mgmt_ip) not in output:
                return False
            return True
        except subprocess.CalledProcessError as e:
            raise e
        except Exception as e:
            raise e
    
    '''
    Function to check if the contrail-networking-openstack-extra tgz should be removed
    and not be part of the repo
    '''
    def is_remove_openstack_extra(self, package_path, package_name, package_type, openstack_sku):
        # remove the openstack extra package as we don't need it as part of 
        # the repo for contrail-cloud-docker image
        if package_name == "contrail-networking-docker" and \
             package_type == "contrail-cloud-docker-tgz":
            return True
        
        # remove the openstack extra package as we don't need it as part of 
        # the repo for contrail-networking-docker image if the openstack sku is liberty
        if package_type == "contrail-networking-docker-tgz" \
           and package_name == "contrail-networking-openstack-extra" \
           and openstack_sku == "liberty":
            return True
        return False
    
    '''
    Remove files not related to openstack sku
    '''
    def manipulate_openstack_extra_tgz(self, package_path, package_name, openstack_sku):
        file_to_be_removed = []
        folder_path = str(package_path)+"/"+str(package_name)
        dirs = os.listdir(folder_path)
        for file in dirs:
            if openstack_sku not in file and "common" not in file:
                  file_to_be_removed.append("/"+file+"*")
        for file in file_to_be_removed:
            cmd = "rm " + folder_path + file
            subprocess.check_call(cmd, shell=True)
    
    '''
    Functions to create a repo and unpack from contrail-docker-cloud package
    Create debian repo for openstack and contrail packages in container tgz
    
    '''
    
    def untar_package_to_folder(self, mirror,package_path, package_type, openstack_sku):
        folder_list = []
        cleanup_package_list = []
        puppet_package = None
        ansible_package = None
        docker_images_package_list = []
        openstack_images_package_list = []
        search_package = package_path+"/*.tgz"
        package_list = glob.glob(search_package)
        if package_list:
            for package in package_list:
                package_name = str(package).partition(package_path+"/")[2]
                package_name = str(package_name).partition('_')[0]
                if package_name not in ['contrail-ansible', 'contrail-puppet', 'contrail-vcenter-docker-images',
                  'contrail-docker-images','contrail-cloud-docker-images', 'openstack-docker-images']:
                    cmd = "mkdir -p %s/%s" %(package_path,package_name)
                    subprocess.check_call(cmd, shell=True)
                    cmd = "tar -xvzf %s -C %s/%s > /dev/null" %(package, package_path, package_name)
                    subprocess.check_call(cmd, shell=True)
                    folder_path = str(package_path)+"/"+str(package_name)
                    if self.is_remove_openstack_extra(package_path, package_name, package_type,openstack_sku):
                       cmd = "rm "+ folder_path + "/" + "contrail-networking-openstack-extra*"
                       subprocess.check_call(cmd, shell=True)
                    if package_type == "contrail-networking-docker-tgz" \
                       and package_name == "contrail-networking-openstack-extra" \
                       and openstack_sku != "liberty":
                        self.manipulate_openstack_extra_tgz(package_path, package_name, openstack_sku)
                    folder_list.append(folder_path)
                elif package_name == "contrail-docker-images" or package_name == "contrail-cloud-docker-images" or \
                 package_name == "contrail-vcenter-docker-images":
                    docker_images_package_list.append(package)
                elif package_name == "openstack-docker-images":
                    openstack_images_package_list.append(package)
                cleanup_package_list.append(package)
    
        search_puppet_package = package_path+"/contrail-puppet*.tar.gz"
        puppet_package_path = glob.glob(search_puppet_package)
        if puppet_package_path:
            puppet_package = puppet_package_path[0]
    
        search_ansible_package = package_path+"/contrail-ansible*.tar.gz"
        ansible_package_path = glob.glob(search_ansible_package)
        if ansible_package_path:
            ansible_package = ansible_package_path[0]
    
        deb_package = package_path+"/*.deb"
        deb_package_list = glob.glob(deb_package)
        if deb_package_list:
            cmd = "mv %s/*.deb %s/contrail-repo/ > /dev/null" %(package_path, str(mirror))
            subprocess.check_call(cmd, shell=True)
        return folder_list, cleanup_package_list, puppet_package, ansible_package, docker_images_package_list, openstack_images_package_list
    
    def unpack_ansible_playbook(self, ansible_package,mirror,image_id):
        # create ansible playbooks dir from the image tar
        ansible_playbooks_default_dir = _DEF_BASE_PLAYBOOKS_DIR
        cmd = ("mkdir -p %s" % (ansible_playbooks_default_dir+"/"+image_id))
        subprocess.check_call(cmd, shell=True)
        playbooks_version = str(ansible_package).partition('contrail-ansible-')[2].rpartition('.tar.gz')[0]
        cmd = (
            "tar -xvzf %s -C %s > /dev/null" %(ansible_package, ansible_playbooks_default_dir+"/"+image_id))
        subprocess.check_call(cmd, shell=True)
        return playbooks_version
    
    def unpack_containers(self, docker_images_package_list,mirror):
        for docker_images_package in docker_images_package_list:
            cmd = 'tar -xvzf %s -C %s/contrail-docker/ > /dev/null' % (docker_images_package,mirror)
        subprocess.check_call(cmd, shell=True)
    
    def unpack_openstack_containers(self, openstack_images_package_list,mirror):
        for openstack_images_package in openstack_images_package_list:
            cmd = 'tar -xvzf %s -C %s/contrail-openstack-containers/ > /dev/null' % (openstack_images_package,mirror)
        subprocess.check_call(cmd, shell=True)

    # Wrapper function for add_puppet_modules for contrail-docker-cloud image
    def unpack_puppet_manifests(self, puppet_package,mirror):
        cmd = ("cp %s %s/contrail-puppet/contrail-puppet-manifest.tgz" % (puppet_package, mirror))
        subprocess.check_call(cmd, shell=True)
        puppet_package_path = mirror+"/contrail-puppet/contrail-puppet-manifest.tgz"
        return puppet_package_path
    
    # Create debian repo for openstack and contrail packages in container tgz
    def _create_container_repo(self, image_id, image_type, image_version, dest, pkg_type,openstack_sku,args):
        puppet_manifest_version = ""
        image_params = {}
        tgz_image = False
        try:
            # create a repo-dir where we will create the repo
            mirror = args.html_root_dir+"contrail/repo/"+image_id
            cmd = "/bin/rm -fr %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            cmd = "mkdir -p %s" %(mirror)
            subprocess.check_call(cmd, shell=True)
            # change directory to the new one created
            cwd = os.getcwd()
            os.chdir(mirror)
            # Extract .tgz of other packages from the repo
            cmd = 'file %s'%dest
            output = subprocess.check_output(cmd, shell=True)
            #If the package is tgz or debian extract it appropriately
            if output:
                if 'gzip compressed data' in output:
                    cmd = ("tar -xvzf %s -C %s > /dev/null" %(dest,mirror))
                    subprocess.check_call(cmd, shell=True)
                else:
                    raise Exception
            else:
                raise Exception

            cmd = "mkdir -p %s/contrail-repo %s/contrail-docker %s/contrail-puppet %s/contrail-openstack-containers" %(mirror,mirror,mirror,mirror)
            subprocess.check_call(cmd, shell=True)
            cleanup_package_list = []
            folder_list = []
            folder_list.append(str(mirror))
            ansible_package = None
            puppet_package = None
            docker_images_package_list = []
            playbooks_version = None
    
            for folder in folder_list:
                new_folder_list, new_cleanup_list, puppet_package_path, ansible_package, docker_images_package_list, openstack_images_package_list = \
                  self.untar_package_to_folder(mirror,str(folder), pkg_type, openstack_sku)
                if folder == mirror:
                    cleanup_package_list = new_folder_list + new_cleanup_list
                folder_list += new_folder_list
                if puppet_package_path:
                    puppet_package = self.unpack_puppet_manifests(puppet_package_path,mirror)
                if ansible_package:
                    playbooks_version = self.unpack_ansible_playbook(ansible_package,mirror,image_id)
                if docker_images_package_list != []:
                    self.unpack_containers(docker_images_package_list,mirror)
                if openstack_images_package_list != []:
                    self.unpack_openstack_containers(openstack_images_package_list,mirror)
                if image_type == 'contrail-centos-package':
                    for filename in glob.glob(os.path.join(folder, '*.rpm')):
                        shutil.copy(filename, mirror + '/contrail-repo')

            if image_type == 'contrail-centos-package':
                string_partition = '-centos'
                cmd = 'createrepo  %s/contrail-repo > /dev/null' % mirror
                subprocess.check_call(cmd, shell=True)
                #for filename in glob.glob(os.path.join(mirror + '/contrail-repo', '*.rpm')):
                    #shutil.copy2(filename, mirror)
                #shutil.copytree(mirror + '/contrail-repo/repodata', mirror + '/repodata')
            else:
                string_partition = '-u'
                cmd = ("cp -v -a /opt/contrail/server_manager/reprepro/conf %s/" % mirror)
                subprocess.check_call(cmd, shell=True)
                cmd = ("reprepro includedeb contrail %s/contrail-repo/*.deb" % mirror)
                subprocess.check_call(cmd, shell=True)
                cleanup_package_list.append(mirror+"/contrail-repo")

            # Add containers from tar file
            container_base_path = mirror+"/contrail-docker"
            containers_list = glob.glob(container_base_path+"/*.tar.gz")
            image_params["containers"] = []
            for container in containers_list:
                container_details = {}
                container_path = str(container)
                role = container_path.partition(str(container_base_path)+'/')[2].rpartition(string_partition)[0]
                if str(role) in _valid_roles:
                    container_dict = {"role": role, "container_path": container_path}
                    image_params["containers"].append(container_dict.copy())
            cleanup_package_list.append(mirror+"/contrail-docker")
            cleanup_package_list.append(mirror+"/contrail-puppet")

            # Add openstack containers from tar file
            ops_string_partition = 'ubuntu-binary-'
            ops_container_base_path = mirror+"/contrail-openstack-containers"
            ops_containers_list = glob.glob(ops_container_base_path+"/*.tar.gz")
            for ops_container in ops_containers_list:
                ops_container_details = {}
                ops_container_path = str(ops_container)
                role = ops_container_path.partition(str(ops_container_base_path)+'/')[2].rpartition(ops_string_partition)[2]
                role = role.rpartition(".tar.gz")[0]
                container_dict = {"role": role, "container_path": ops_container_path}
                image_params["containers"].append(container_dict.copy())
            cleanup_package_list.append(mirror+"/contrail-openstack-containers")

            image_params["cleanup_list"] = cleanup_package_list
            # change directory back to original
            os.chdir(cwd)
            return puppet_package, playbooks_version, image_params
        except Exception as e:
            raise(e)
    # end _create_container_repo

