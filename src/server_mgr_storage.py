import sys
import pdb
import time
import subprocess
import uuid
from sm_ansible_utils import CEPH_COMPUTE
from sm_ansible_utils import CEPH_CONTROLLER
from server_mgr_utils import *

def get_new_ceph_key():
    cmd = 'ceph-authtool -p -C --gen-print-key'
    output = subprocess.check_output(cmd, shell=True)
    return output[:-1]
# end get_new_ceph_key

def generate_storage_keys(cluster):
    params = cluster.get("parameters", {})
    if params == None:
        return;

    if "provision" in params:
        provision_params = params.get("provision", {})
        contrail_params = provision_params.get("contrail", {})
        provision_params["contrail"] = contrail_params
        storage_params = contrail_params.get("storage", {})
        contrail_params["storage"] = storage_params

        storage_fsid       = str(uuid.uuid4())
        storage_virsh_uuid = str(uuid.uuid4())
        storage_mon_key = get_new_ceph_key()
        storage_osd_key = get_new_ceph_key()
        storage_adm_key = get_new_ceph_key()
        if 'storage_monitor_secret' not in storage_params:
            storage_params['storage_monitor_secret'] = storage_mon_key
        if 'osd_bootstrap_key' not in storage_params:
            storage_params['osd_bootstrap_key']      = storage_osd_key
        if 'storage_admin_key' not in storage_params:
            storage_params['storage_admin_key']      = storage_adm_key
        storage_params['storage_fsid']               = storage_fsid
        #TODO Not used anymore ?
        storage_params['storage_virsh_uuid'] = storage_virsh_uuid

# end generate_storage_keys

# build_storage_config
def build_storage_config(self, server, cluster, role_servers,
                        cluster_servers, contrail_params):
    cluster_params = cluster.get("parameters", {})
    #cluster['parameters'] = cluster_params
    cluster_provision_params = cluster_params.get("provision", {})
    cluster_params['provision'] = cluster_provision_params
    cluster_contrail_params = cluster_provision_params.get("contrail", {})
    cluster_provision_params['contrail'] = cluster_contrail_params
    cluster_storage_params = cluster_contrail_params.get("storage", {})
    cluster_contrail_params['storage'] = cluster_storage_params

    contrail_params['storage'] = {}
    total_osd = int(0)
    num_storage_hosts = int(0)
    storage_mon_host_ip_set = set()
    storage_mon_hostname_set = set()
    storage_chassis_config_set = set()
    pool_names = set()
    storage_servers = {}
    storage_role_present = 0

    for storage_server in cluster_servers:
        if CEPH_COMPUTE in eval(storage_server.get('roles', '[]')) or \
            CEPH_CONTROLLER in eval(storage_server.get('roles', '[]')):
            storage_role_present = 1

    if storage_role_present == 0:
        return

    if 'live_migration_host' in cluster_storage_params:
        live_migration_host = cluster_storage_params['live_migration_host']
    else:
        live_migration_host = ''
    live_migration_ip = ""

    # create pool secrets
    if 'pool_secret' not in cluster_storage_params:
        cluster_storage_params['pool_secret'] = {}
    if 'pool_keys' not in cluster_storage_params:
        cluster_storage_params['pool_keys'] = {}
    if 'volumes' not in cluster_storage_params['pool_secret']:
        cluster_storage_params['pool_secret']['volumes'] = str(uuid.uuid4())
    if 'volumes' not in cluster_storage_params['pool_keys']:
        cluster_storage_params['pool_keys']['volumes'] = get_new_ceph_key()
    if 'images' not in cluster_storage_params['pool_secret']:
        cluster_storage_params['pool_secret']['images'] = str(uuid.uuid4())
    if 'images' not in cluster_storage_params['pool_keys']:
        cluster_storage_params['pool_keys']['images'] = get_new_ceph_key()
    if 'last_osd_num' not in cluster_storage_params:
        cluster_storage_params['last_osd_num'] = int(0)
        last_osd_num = int(0)
    else:
        last_osd_num = cluster_storage_params['last_osd_num']

    # copy role_servers as we append the variable with the container
    # based roles
    storage_servers = list(role_servers['storage-compute'])
    for storage_server in cluster_servers:
        if CEPH_COMPUTE in eval(storage_server.get('roles', '[]')):
            storage_servers.append(storage_server)

    for role_server in storage_servers:
        server_params  = eval(role_server.get("parameters", {}))
        server_provision_params = server_params.get("provision", {})
        server_params['provision'] = server_provision_params
        server_contrail_params = server_provision_params.get("contrail_4", {})
        server_provision_params['contrail_4'] = server_contrail_params
        storage_params  = server_contrail_params.get("storage", {})
        server_contrail_params['storage'] = storage_params

        pool_present = 0
        # Calculate total osd number, unique pools, unique osd number
        # for osd disks
        if (('storage_osd_disks' in storage_params) and
            (len(storage_params['storage_osd_disks']) > 0)):
            total_osd += len(storage_params['storage_osd_disks'])
            num_storage_hosts += 1

            for disk in storage_params['storage_osd_disks']:
                disksplit = disk.split(':')
                diskcount = disk.count(':')
                # add virsh secret for unique volumes_hdd_ pools
                # add corresponding ceph key for unique volumes_hdd_ pools
                if (diskcount == 2 and disksplit[2][0] == 'P'):
                    if ('volumes_hdd_' + disksplit[2]) not in \
                                cluster_storage_params['pool_secret']:
                        cluster_storage_params['pool_secret'] \
                            ['volumes_hdd_' + disksplit[2]] = \
                                                        str(uuid.uuid4())
                    if ('volumes_hdd_' + disksplit[2]) not in \
                                cluster_storage_params['pool_keys']:
                        cluster_storage_params['pool_keys'] \
                            ['volumes_hdd_' + disksplit[2]] = \
                                                        get_new_ceph_key()
                    pool_present = 1
                elif (diskcount == 1 and disksplit[1][0] == 'P'):
                    if ('volumes_hdd_' + disksplit[1]) not in \
                                cluster_storage_params['pool_secret']:
                        cluster_storage_params['pool_secret'] \
                            ['volumes_hdd_' + disksplit[1]] = \
                                                        str(uuid.uuid4())
                    if ('volumes_hdd_' + disksplit[1]) not in \
                                cluster_storage_params['pool_keys']:
                        cluster_storage_params['pool_keys'] \
                            ['volumes_hdd_' + disksplit[1]] = \
                                                        get_new_ceph_key()
                    pool_present = 1
                # find unique osd number for each disk and add to dict
                diskname = disksplit[0]
                if 'osd_int_num' not in storage_params:
                    storage_params['osd_int_num'] = {}
                if diskname not in storage_params['osd_int_num']:
                    storage_params['osd_int_num'][diskname] = last_osd_num
                    last_osd_num += 1
                elif last_osd_num < storage_params['osd_int_num'][diskname]:
                    last_osd_num = storage_params['osd_int_num'][diskname] + 1
                if 'osd_num' not in storage_params:
                    storage_params['osd_num'] = {}
                storage_params['osd_num'][disk] = \
                                    storage_params['osd_int_num'][diskname]
            # end for disk
        # end if

        pool_ssd_present = 0
        # Calculate total osd number, unique pools, unique osd number
        # for osd ssd disks
        if (('storage_osd_ssd_disks' in storage_params) and
            (len(storage_params['storage_osd_ssd_disks']) > 0)):
            # if ssd disks are present and hdd Pools are not present
            # add virsh secret and ceph key for volumes_hdd
            if pool_present == 0 and \
                    'volumes_hdd' not in cluster_storage_params['pool_secret']:
                cluster_storage_params['pool_secret']['volumes_hdd'] = \
                                                        str(uuid.uuid4())
            if pool_present == 0 and \
                    'volumes_hdd' not in cluster_storage_params['pool_keys']:
                cluster_storage_params['pool_keys']['volumes_hdd'] = \
                                                        get_new_ceph_key()
            total_osd += len(storage_params['storage_osd_ssd_disks'])

            for disk in storage_params['storage_osd_ssd_disks']:
                disksplit = disk.split(':')
                diskcount = disk.count(':')
                # add virsh secret for unique volumes_ssd_ pools
                # add corresponding ceph key for unique volumes_ssd_ pools
                if (diskcount == 2 and disksplit[2][0] == 'P'):
                    if ('volumes_ssd_' + disksplit[2]) not in \
                                cluster_storage_params['pool_secret']:
                        cluster_storage_params['pool_secret'] \
                                ['volumes_ssd_' + disksplit[2]] = \
                                                        str(uuid.uuid4())
                    if ('volumes_ssd_' + disksplit[2]) not in \
                                cluster_storage_params['pool_keys']:
                        cluster_storage_params['pool_keys'] \
                                ['volumes_ssd_' + disksplit[2]] = \
                                                        get_new_ceph_key()
                    pool_ssd_present = 1
                elif (diskcount == 1 and disksplit[1][0] == 'P'):
                    if ('volumes_ssd_' + disksplit[1]) not in \
                                cluster_storage_params['pool_secret']:
                        cluster_storage_params['pool_secret'] \
                                ['volumes_ssd_' + disksplit[1]] = \
                                                        str(uuid.uuid4())
                    if ('volumes_ssd_' + disksplit[1]) not in \
                                cluster_storage_params['pool_keys']:
                        cluster_storage_params['pool_keys'] \
                                ['volumes_ssd_' + disksplit[1]] = \
                                                        get_new_ceph_key()
                    pool_ssd_present = 1
                # find unique osd number for each disk and add to dict
                diskname = disksplit[0]
                if 'osd_ssd_int_num' not in storage_params:
                    storage_params['osd_ssd_int_num'] = {}
                if diskname not in storage_params['osd_ssd_int_num']:
                    storage_params['osd_ssd_int_num'][diskname] = last_osd_num
                    last_osd_num += 1
                elif last_osd_num < storage_params['osd_ssd_int_num'][diskname]:
                    last_osd_num = storage_params['osd_ssd_int_num'][diskname] + 1
                if 'osd_ssd_num' not in storage_params:
                    storage_params['osd_ssd_num'] = {}
                storage_params['osd_ssd_num'][disk] = \
                                    storage_params['osd_ssd_int_num'][diskname]
            # end for disk
            # if ssd disk is present and pool is not present
            # add virsh secret and ceph_key for volumes_ssd pool
            if pool_ssd_present == 0 and \
                    'volumes_ssd' not in cluster_storage_params['pool_secret']:
                cluster_storage_params['pool_secret']['volumes_ssd'] = \
                                                        str(uuid.uuid4())
            if pool_ssd_present == 0 and \
                    'volumes_ssd' not in cluster_storage_params['pool_keys']:
                cluster_storage_params['pool_keys']['volumes_ssd'] = \
                                                        get_new_ceph_key()
        # end if

        if role_server['host_name'] == live_migration_host:
            live_migration_ip = self.get_control_ip(role_server)
        if storage_params.get('storage_chassis_id', ""):
            storage_host_chassis = (
                role_server['host_name'] + ':' + \
                            storage_params['storage_chassis_id'])
            storage_chassis_config_set.add(storage_host_chassis)
        # end if

        #storage_params['contrail_4_invisible'] = '1'
        # save back server db as modification are done
        role_server['parameters'] = unicode(server_params)
        self._serverDb.modify_server(role_server)
    # end for role_server

    # save back changes to clusterdb
    if ('storage_fsid' in cluster_params) and \
            ('storage_fsid' not in cluster_storage_params):
        cluster_storage_params['storage_fsid'] = \
                                    cluster_params['storage_fsid']
    if ('storage_virsh_uuid' in cluster_params) and \
            ('storage_virsh_uuid' not in cluster_storage_params):
        cluster_storage_params['storage_virsh_uuid'] = \
                                    cluster_params['storage_virsh_uuid']
    cluster_storage_params['storage_hosts'] = num_storage_hosts
    cluster_storage_params['last_osd_num']    = last_osd_num
    self._serverDb.modify_cluster(cluster)


    # copy role_servers as we append the variable with the container
    # based roles
    storage_servers  = list(role_servers['storage-master'])
    for storage_server in cluster_servers:
        if CEPH_CONTROLLER in eval(storage_server.get('roles', '[]')):
            storage_servers.append(storage_server)
    for x in storage_servers:
        storage_mon_host_ip_set.add(self.get_control_ip(x))
        storage_mon_hostname_set.add(x['host_name'])
    # end for

    contrail_params['storage']['storage_num_osd']       = total_osd
    contrail_params['storage']['storage_num_hosts']     = num_storage_hosts
    if (num_storage_hosts > 0) :
      contrail_params['storage']['enabled']             = '1'
      contrail_params['storage']['storage_enabled']     = 1
    else:
      contrail_params['storage']['enabled']             = '0'
      contrail_params['storage']['storage_enabled']     = 0
    contrail_params['storage']['live_migration_ip']     = live_migration_ip
    contrail_params['storage']['storage_fsid']          = \
                        cluster_storage_params['storage_fsid']
    contrail_params['storage']['storage_virsh_uuid']    = \
                        cluster_storage_params['storage_virsh_uuid']
    contrail_params['storage']['storage_ip_list']       = \
                        list(storage_mon_host_ip_set)
    contrail_params['storage']['storage_monitor_hosts'] = \
                        list(storage_mon_host_ip_set)
    contrail_params['storage']['storage_hostnames']     = \
                        list(storage_mon_hostname_set)
    contrail_params['storage']['virsh_uuids']           = \
                        dict(cluster_storage_params['pool_secret'])


    pool_data = {}
    for pool_name in cluster_storage_params['pool_keys']:
        if pool_name != "images" :
          pool_names.add("rbd-disk-" + pool_name)
        pool_data[pool_name] = {}
        pool_data[pool_name]['pname'] = pool_name
        pool_data[pool_name]['key'] = cluster_storage_params['pool_keys'][pool_name]
        pool_data[pool_name]['uuid'] = cluster_storage_params['pool_secret'][pool_name]

    contrail_params['storage']['pool_data'] = { 'literal': True, 'data': pool_data}
    contrail_params['storage']['pool_names'] = list(pool_names)

    roles = eval(server.get("roles", "[]"))
    if ('storage-master' in roles):
        contrail_params['storage']['storage_chassis_config'] = \
                        list(storage_chassis_config_set)
    control_network = self.storage_get_control_network_mask(
                        server, cluster, role_servers, cluster_servers)
    contrail_params['storage']['storage_cluster_network'] = control_network

# end build_storage_config

def get_cluster_contrail_cfg_section(cluster, section):
    params = cluster.get("parameters", {})
    if params:
        prov = params.get("provision", {})
        if prov:
            cont = prov.get("contrail", {})
            if section in cont.keys():
                return cont[section]
    return {}

def get_server_contrail_4_cfg_section(server, section):
    params = eval(server.get("parameters", {}))
    if params:
        prov = params.get("provision", {})
        if prov:
            cont = prov.get("contrail_4", {})
            if section in cont.keys():
                return cont[section]
    return {}

def get_calculated_storage_ceph_cfg_dict(cluster, cluster_srvrs, pkg=None):
    storage_cfg = dict()
    disk_cfg = dict()
    storage_role_present = 0

    for storage_server in cluster_srvrs:
        if CEPH_COMPUTE in eval(storage_server.get('roles', '[]')) or \
            CEPH_CONTROLLER in eval(storage_server.get('roles', '[]')):
            storage_role_present = 1

    if storage_role_present == 0:
        return storage_cfg

    cluster_storage_params = get_cluster_contrail_cfg_section(cluster,
                                                                'storage')
    if cluster_storage_params == {} or \
        cluster_storage_params['storage_hosts'] == 0:
        return storage_cfg

    storage_cfg['fsid']        = cluster_storage_params['storage_fsid']
    storage_cfg['pool_secret'] = cluster_storage_params['pool_secret']
    storage_cfg['pool_keys']   = cluster_storage_params['pool_keys']
    storage_cfg['mon_key']     = cluster_storage_params['storage_monitor_secret']
    storage_cfg['osd_key']     = cluster_storage_params['osd_bootstrap_key']
    storage_cfg['adm_key']     = cluster_storage_params['storage_admin_key']

    for storage_server in cluster_srvrs:
        if CEPH_COMPUTE in eval(storage_server.get('roles', '[]')):
            db_utils = DbUtils()
            server_storage_params = db_utils.get_contrail_4(storage_server)['storage']
            if server_storage_params == {}:
                continue
            disk_cfg[storage_server['id']] = {}
            if 'osd_num' in server_storage_params:
                disk_cfg[storage_server['id']]['osd_info'] = \
                                    server_storage_params['osd_num']
            if 'osd_ssd_num' in server_storage_params:
                disk_cfg[storage_server['id']]['osd_ssd_info'] = \
                                    server_storage_params['osd_ssd_num']
            if 'storage_chassis_id' in server_storage_params:
                disk_cfg[storage_server['id']]['chassis_id'] = \
                                    server_storage_params['storage_chassis_id']

    storage_cfg['osd_info'] = disk_cfg
    return storage_cfg
#end get_calculated_storage_ceph_cfg_dict
