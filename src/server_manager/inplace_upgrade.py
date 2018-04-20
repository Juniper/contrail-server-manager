import argparse
import subprocess
import paramiko
import time
import sys
import logging
from server_mgr_utils import *

PROV_TIMEOUT = 3600
logging.basicConfig(format='%(asctime)s %(message)s',
                    filename='/var/log/contrail/inplace_upgrade.log',
                                                  level=logging.INFO)
DEF_SERVER_DB_LOCATION = "/etc/contrail_smgr/smgr_data.db"

class Utils():
    @staticmethod
    def exec_local(command):
        output = subprocess.check_output(command, shell = True)
        logging.info("executing command %s on SM" %command)
        return output

    @staticmethod
    def exec_remote(server, command):
        serverDb = db(DEF_SERVER_DB_LOCATION)
        smutil = ServerMgrUtil()
        ssh_handle = paramiko.SSHClient()
        ssh_handle.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_handle.connect(server['ip_address'],
                               username = 'root',
                               password = smutil.get_password(server,serverDb))
        i, o, err = ssh_handle.exec_command(command)
        logging.info("executing command %s on %s" %(command, server['id']))
        op = o.read()
        err = err.read()
        ssh_handle.close()
        return op
# end Utils

def get_details(cluster_name):
    cmd = 'server-manager display server --cluster_id %s --select \
           id,ip_address,roles,password -s --json' %cluster_name
    server_json_dump = Utils.exec_local(cmd)
    servers = eval(server_json_dump)['server']
    return servers

def validate_roles(servers):
    valid_roles = ['contrail-controller',
                   'contrail-lb',
                   'contrail-analytics',
                   'contrail-analyticsdb',
                   'contrail-compute',
                   'openstack']
    for each in servers:
        if not set(each['roles']).issubset(valid_roles):
            logging.info("Server %s-%s doesnt have valid 4.0 role"
                                   %(each['id'], each['ip_address']))
            sys.exit("Server %s-%s doesnt have valid 4.0 role"
                                   %(each['id'], each['ip_address']))

def stop_svcs(servers):
    services = ['supervisor-analytics', 'supervisor-support-service', 
                'supervisor-database', 'contrail-database', 'supervisor-webui', 
                'supervisor-config', 'supervisor-control', 'haproxy', 
                'redis-server', 'memcached', 'neutron-server', 'zookeeper',
                'keepalived']
    for each in servers:
        if 'openstack' in each['roles']:
            continue
        cmd = 'kill $(pidof epmd)'
        Utils.exec_remote(each, cmd)
        for svc in services:
            cmd = 'service %s stop' %svc
            Utils.exec_remote(each, cmd)

def wait_provision_complete(servers):
    elapsed_time = 0
    prov_complete = False
    interval = 30
    while elapsed_time < PROV_TIMEOUT:
        time.sleep(interval)
        elapsed_time = elapsed_time + interval
        for server in servers:
            cmd = "server-manager status server --server_id %s | grep %s \
                          |awk '{print $4}'" %(server['id'], server['id'])
            op = Utils.exec_local(cmd)
            print "provision status for server %s is %s" %(server['id'], op)
            if op.strip() == "provision_failed":
                sys.exit("provisioning failed for server %s" %server['id'])
            if op.strip() != "provision_completed":
                break
        if op.strip() == "provision_completed":
            prov_complete = True
            break
    return prov_complete

def start_cassandra(server):
    cmd = "sed -i 's/rpc_port:.*/rpc_port: 29160/g' /etc/cassandra/cassandra.yaml"
    Utils.exec_remote(server, cmd)
    cmd = "sed -i 's/storage_port:.*/storage_port: 27000/g' /etc/cassandra/cassandra.yaml"
    Utils.exec_remote(server, cmd)
    cmd = "sed -i 's/ssl_storage_port:.*/ssl_storage_port: 27001/g' /etc/cassandra/cassandra.yaml"
    Utils.exec_remote(server, cmd)
    cmd = "sed -i 's/native_transport_port:.*/native_transport_port: 29042/g' /etc/cassandra/cassandra.yaml"
    Utils.exec_remote(server, cmd)
    cmd = 'service cassandra restart'
    Utils.exec_remote(server, cmd)

def run_sync(server):
    # fix rpc ip and port
    #server = {'password': 'c0ntrail123', 'ip_address': '192.168.100.102', 'id': 'ctrl2-a1s9', 'roles': ['contrail-controller', 'contrail-analytics', 'contrail-analyticsdb']}
    config_file = "/etc/contrail/upgrade.conf"
    cmd = "grep ^rpc_address /etc/cassandra/cassandra.yaml |awk '{print $2}'"
    old_cass_ip = Utils.exec_remote(server, cmd).strip()
    cmd  = "grep ^rpc_port /etc/cassandra/cassandra.yaml |awk '{print $2}'"
    old_cass_port = Utils.exec_remote(server, cmd).strip()
    cmd_dock = 'docker exec -i controller '
    cmd = cmd_dock + "grep ^rpc_address /etc/cassandra/cassandra.yaml"
    new_cass_ip = Utils.exec_remote(server, cmd).split()[1].strip()
    cmd = cmd_dock + "grep ^rpc_port /etc/cassandra/cassandra.yaml"
    new_cass_port = Utils.exec_remote(server, cmd).split()[1].strip()
    cmd = cmd_dock + "touch %s" %config_file
    Utils.exec_remote(server, cmd)
    cmd = cmd_dock + "openstack-config --set %s DEFAULTS %s %s:%s" %(config_file,
                       'old_cassandra_address_list', old_cass_ip, old_cass_port)
    Utils.exec_remote(server, cmd)
    cmd = cmd_dock + "openstack-config --set %s DEFAULTS %s %s:%s" %(config_file,
                       'new_cassandra_address_list', new_cass_ip, new_cass_port)
    Utils.exec_remote(server, cmd)
    cmd = cmd_dock + "contrail-issu-pre-sync -c %s" %config_file
    op = Utils.exec_remote(server, cmd)
    if not 'Done syncing dm keyspace' in op:
        sys.exit("problem syncing keyspaces from old cluster")
    cmd = "service cassandra stop"
    Utils.exec_remote(server, cmd)

def main():
    '''script for upgrading 3.2 cluster to 4.0
       user adds the cluster/server in the SM
       user runs this script with cluster name and image args'''
    parser = argparse.ArgumentParser()
    parser.add_argument('cluster_name', help = 'cluster to be upgraded.'
                            'The cluster and servers should be existing in SM')
    parser.add_argument('image_name', help = 'version to upgrade to')
    args = parser.parse_args()
    logging.info('starting')
    server_json_dump = get_details(args.cluster_name)
    validate_roles(server_json_dump)
    stop_svcs(server_json_dump)
    # run SM provision
    cmd = "server-manager provision -F --cluster_id %s %s" %(args.cluster_name,
                                                            args.image_name)
    op = Utils.exec_local(cmd)
    if eval(op)['return_code'] != "0":
        logging.info("4.0 Provisioning command failed\n. %s" %op)
        sys.exit("4.0 Provisioning command failed\n. %s" %op)
    if not wait_provision_complete(server_json_dump):
        logging.info("4.0 Provisioning timed out")
        sys.exit("4.0 Provisioning timed out")
    # start underlay cassandra and sync up the DB
    sync_server = {}
    for each in server_json_dump:
        if "contrail-controller" in each['roles']:
            start_cassandra(each)
            sync_server = each
    if not sync_server.keys():
        logging.info("no contrail-controller role found")
        sys.exit("no contrail-controller role found")
    run_sync(sync_server)
# end main

if __name__ == "__main__":
    main()

