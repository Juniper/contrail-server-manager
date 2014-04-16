#!/usr/bin/env python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : server_manager.py
   Author : Abhay Joshi
   Description : This file contains code that provides REST api interface to
                 configure, get and manage configurations for servers which
                 are part of the contrail cluster of nodes, interacting
                 together to provide a scalable virtual network system.
"""
import os
import glob
import sys
import re
import datetime
import subprocess
import json
import argparse
import bottle
from bottle import route, run, request, abort
import ConfigParser
import paramiko
import base64
import shutil
from urlparse import urlparse, parse_qs
from time import gmtime, strftime
import pdb
import server_mgr_db
import ast

from server_mgr_db import ServerMgrDb as db
from server_mgr_cobbler import ServerMgrCobbler as ServerMgrCobbler
from server_mgr_puppet import ServerMgrPuppet as ServerMgrPuppet

_WEB_HOST = '127.0.0.1'
_WEB_PORT = 9001
_DEF_CFG_DB = 'vns_server_mgr.db'
_DEF_SMGR_BASE_DIR = '/etc/contrail_smgr/'
_DEF_SMGR_CFG_FILE = _DEF_SMGR_BASE_DIR + 'smgr_config.ini'
_DEF_HTML_ROOT_DIR = '/var/www/html/'
_DEF_COBBLER_IP = '127.0.0.1'
_DEF_COBBLER_PORT = None
_DEF_COBBLER_USER = 'cobbler'
_DEF_COBBLER_PASSWD = 'cobbler'
_DEF_POWER_USER = 'ADMIN'
_DEF_POWER_PASSWD = 'ADMIN'
_DEF_POWER_TOOL = 'ipmilan'
_DEF_PUPPET_DIR = '/etc/puppet/'

@bottle.error(403)
def error_403(err):
    return err.body
# end error_403


@bottle.error(404)
def error_404(err):
    return err.body
# end error_404


@bottle.error(409)
def error_409(err):
    return err.body
# end error_409


@bottle.error(500)
def error_500(err):
    return err.body
# end error_500


@bottle.error(503)
def error_503(err):
    return err.body
# end error_503


class VncServerManager():

    '''
    This is the main class that makes use of bottle package to provide rest
    interface for the server manager. This class serves rest APIs and then
    processes cluster, server and nodes classes in accordance with information
    provided in the REST calls.
    '''

    def __init__(self, args_str=None):
        self._args = None
        if not args_str:
            args_str = sys.argv[1:]
        self._parse_args(args_str)

        # Connect to the cluster-servers database
        try:
            self._serverDb = db(self._args.db_name)
        except:
            print ("Error Connecting to Server Database %s"
                   ) % (self._args.db_name)
            exit()

        # Create an instance of cobbler interface class and connect to it.
        try:
            self._smgr_cobbler = ServerMgrCobbler(self._args.smgr_base_dir,
                                                  self._args.cobbler_ip,
                                                  self._args.cobbler_port,
                                                  self._args.cobbler_user,
                                                  self._args.cobbler_passwd)
        except:
            print "Error connecting to cobbler"
            exit()

        # Create an instance of puppet interface class.
        try:
            # TBD - Puppet params to be added.
            self._smgr_puppet = ServerMgrPuppet(self._args.smgr_base_dir,
                                                self._args.puppet_dir)
        except:
            print "Error creating instance of puppet class"
            exit()

        # Read the JSON file, validate for correctness and add the entries to
        # our DB.
        if self._args.server_list is not None:
            try:
                server_file = open(self._args.server_list, 'r')
                json_data = server_file.read()
                server_file.close()
            except IOError:
                print (
                    "Error reading initial config file %s") \
                    % (self._args.server_list)
                exit()
            try:
                self.config_data = json.loads(json_data)
            except Exception as e:
                print repr(e)
                print (
                    "Initial config file %s format error. "
                    "File should be in JSON format") \
                    % (self._args.server_list)
                exit()
            # Validate the config for sematic correctness.
            self._validate_config(self.config_data)
            # Store the initial configuration in our DB
            try:
                self._create_server_manager_config(self.config_data)
            except Exception as e:
                print repr(e)

        self._base_url = "http://%s:%s" % (self._args.listen_ip_addr,
                                           self._args.listen_port)
        self._pipe_start_app = bottle.app()

        # All bottle routes to be defined here...
        # REST calls for GET methods (Get Info about existing records)
        bottle.route('/all', 'GET', self.get_server_mgr_config)
        bottle.route('/cluster', 'GET', self.get_cluster)
        bottle.route('/vns', 'GET', self.get_vns)
        bottle.route('/server', 'GET', self.get_server)
        bottle.route('/image', 'GET', self.get_image)

        # REST calls for PUT methods (Create New Records)
        bottle.route('/all', 'PUT', self.create_server_mgr_config)
        bottle.route('/cluster', 'PUT', self.add_cluster)
        bottle.route('/server', 'PUT', self.add_server)
        bottle.route('/image', 'PUT', self.add_image)
        bottle.route('/image/upload', 'PUT', self.upload_image)
        bottle.route('/vns', 'PUT', self.add_vns)

        # REST calls for DELETE methods (Remove records)
        bottle.route('/cluster', 'DELETE', self.delete_cluster)
        bottle.route('/vns', 'DELETE', self.delete_vns)
        bottle.route('/server', 'DELETE', self.delete_server)
        bottle.route('/image', 'DELETE', self.delete_image)

        # REST calls for POST methods
        bottle.route('/cluster', 'POST', self.modify_cluster)
        bottle.route('/vns', 'POST', self.modify_vns)
        bottle.route('/server', 'POST', self.modify_server)
        bottle.route('/image', 'POST', self.modify_image)
        bottle.route('/server/reimage', 'POST', self.reimage_server)
        bottle.route('/server/provision', 'POST', self.provision_server)
        bottle.route('/server/restart', 'POST', self.restart_server)
        bottle.route('/dhcp_event', 'POST', self.process_dhcp_event)

    def get_pipe_start_app(self):
        return self._pipe_start_app
    # end get_pipe_start_app

    def get_server_ip(self):
        return self._args.listen_ip_addr
    # end get_server_ip

    def get_server_port(self):
        return self._args.listen_port
    # end get_server_port

    # REST API call to get sever manager config - configuration of all
    # clusters, VNSs & all servers is returned.
    def get_server_mgr_config(self):
        config = {}
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Check if request arguments has detail parameter
            detail = ("detail" in query_args)
            config['cluster'] = self._serverDb.get_cluster(detail=detail)
            config['vns'] = self._serverDb.get_vns(detail=detail)
            config['server'] = self._serverDb.get_server(detail=detail)
            config['image'] = self._serverDb.get_image(detail=detail)
        except Exception as e:
            abort(404, repr(e))
        return config
    # end get_server_mgr_config

    # REST API call to get sever manager config - configuration of all
    # clusters, with all servers and roles is returned. This call
    # provides all the configuration as in get_server_mgr_config() call
    # above. This call additionally provides a way of getting all the
    # configuration for a particular cluster.
    def get_cluster(self):
        cluster_id = bottle.request.query.cluster_id
        query_args = parse_qs(urlparse(bottle.request.url).query,
                              keep_blank_values=True)
        # Check if request arguments has detail parameter
        detail = ("detail" in query_args)
        try:
            entity = self._serverDb.get_cluster(cluster_id, detail)
        except Exception as e:
            abort(404, repr(e))
        return {"cluster": entity}
    # end get_cluster

    # REST API call to get sever manager config - configuration of all
    # VNSs, with all servers and roles is returned. This call
    # provides all the configuration as in get_server_mgr_config() call
    # above. This call additionally provides a way of getting all the
    # configuration for a particular vns.
    def get_vns(self):
        vns_id = bottle.request.query.vns_id
        query_args = parse_qs(urlparse(bottle.request.url).query,
                              keep_blank_values=True)
        # Check if request arguments has detail parameter
        detail = ("detail" in query_args)
        try:
            entity = self._serverDb.get_vns(vns_id, detail)
        except Exception as e:
            abort(404, repr(e))
        return {"vns": entity}
    # end get_vns

    # This call returns information about a provided server. If no server
    # if provided, information about all the servers in server manager
    # configuration is returned.
    def get_server(self):
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Check if request arguments has detail parameter
            detail = ("detail" in query_args)
            query_args.pop("detail", None)
            # Now process other parameters there should be only one more
            if len(query_args) == 0:
                match_key = None
                match_value = None
            elif len(query_args) == 1:
                match_key, match_value = query_args.popitem()
                # check that match key is a valid one
                if ((match_key not in (
                        "server_id", "mac", "cluster_id",
                        "rack_id", "pod_id", "vns_id", 'ip')) or
                        (len(match_value) != 1)):
                    abort(404, "Invalid Query arguments")
                match_value = match_value[0]
            else:
                abort(404, "Invalid Query arguments")
            servers = self._serverDb.get_server(match_key, match_value,
                                                detail)
        except Exception as e:
            abort(404, repr(e))
        return {"server": servers}
    # end get_server

    # API Call to list images
    def get_image(self):
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Check if request arguments has detail parameter
            detail = ("detail" in query_args)
            query_args.pop("detail", None)
            # Now process other parameters there should be only one more
            if len(query_args) == 0:
                match_key = None
                match_value = None
            elif len(query_args) == 1:
                match_key, match_value = query_args.popitem()
                # check that match key is a valid one
                if ((match_key not in (
                        "image_id", "image_version")) or
                        (len(match_value) != 1)):
                    abort(404, "Invalid Query arguments")
                match_value = match_value[0]
            else:
                abort(404, "Invalid Query arguments")
            images = self._serverDb.get_image(match_key, match_value,
                                              detail)
        except Exception as e:
            abort(404, repr(e))
        return {"image": images}
    # end get_image

    # API call to add a new cluster to server manager config DB. With the
    # cluster, user can optionally specify information for the servers
    # within the clusters including IP, MAC address for the server and also
    # roles being configured on each.
    def add_cluster(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Error : No cluster specified')
        try:
            clusters = entity.get('cluster', None)
            for cluster in clusters:
                if ('cluster_id' not in cluster):
                    abort(404, 'Error : No cluster_id specified')
                self._serverDb.add_cluster(cluster)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end add_cluster

    # API call to add a new vns to server manager config DB. With the
    # vns, user can optionally specify information for the servers
    # within the vnss including IP, MAC address for the server and also
    # roles being configured on each.
    def add_vns(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Error : No vns specified')
        try:
            vns = entity.get('vns', None)
            for cur_vns in vns:
                if ('vns_id' not in cur_vns):
                    abort(404, 'Error : No vns_id specified')
                self._serverDb.add_vns(cur_vns)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end add_vns

    def config_cluster(self):
        role_compute = {
            "role_id": "compute",
            "role_params": "{"
            "'phy_interface' : 'eth1',"
            "'non_mgmt_ip' : '', 'non_mgmt_gway' : ''}"
        }
        role_control = {
            "role_id": "control",
            "role_params": "{}"
        }
        role_webui = {
            "role_id": "webui",
            "role_params": "{}"
        }
        role_config = {
            "role_id": "config",
            "role_params": "{"
            "'use_certs' : 'False',"
            " 'multi_tenancy' : 'False'"
            "}"
        }
        role_collector = {
            "role_id": "collector",
            "role_params": "{"
            " 'analytics_data_ttl': '168'}"
        }
        role_database = {
            "role_id": "database",
            "role_params": "{"
            " 'database_dir': '/home/cassandra', 'db_initial_token' : ''"
            "}"
        }
        role_openstack = {
            "role_id": "openstack",
            "role_params": "{"
            " 'service_token' : 'contrail123',"
            " 'ks_user' : 'admin', 'ks_passwd' : 'contrail123',"
            " 'ks_tenant' : 'admin',"
            " 'openstack_mgmt_ip' : ''}"
        }
#	role_temp = json.loads(role_str)
        role_params_list = [
            role_compute, role_control, role_webui, role_config,
            role_collector, role_database, role_openstack]
        entity = bottle.request.json

        if (not entity) or ('cluster_id' not in entity):
            abort(404, 'Error: No cluster specified')
        cluster_id = entity['cluster_id']
        cluster_mask = entity['mask']
        cluster_gway = entity['gway']
        cluster_domain = entity['domain']
        vns_id = entity['vns_id']
        cluster_passwd = entity['passwd']

        # Parse Cluster

        # Parse roles
        try:
            roles = entity.get("roles", None)
            host_role = dict()
            for role in roles:
                # Build a dictionary with host attached to roles
                roleItems = role.items()
                for roleItem in roleItems:
                    # Get a dictionary
                    role_name = roleItem[0]
                    host_list = roleItem[1]
                    # print "*********************"
                    # print role_name
                    # print "*********************"

                    for host in host_list:
                        if host not in host_role.keys():
                            host_role[host] = []
                        hosts = host_role[host]
                        hosts.append(role_name)
                           #		host_role[] =
                # print role
        except Exception as e:
            abort(404, repr(e))

        # Parse server
        try:
            servers = entity.get("servers", None)
            for server in servers:
                if (('server_id' not in server) or
                   ('mac' not in server)):
                    abort(404, 'Server MAC or server_id not specified')

                if ('mask' not in server):
                    server['mask'] = cluster_mask

                if ('gway' not in server):
                    server['gway'] = cluster_gway

                if ('domain' not in server):
                    server['domain'] = cluster_domain

                if ('cluster_id' not in server):
                    server['cluster_id'] = cluster_id

                if ('vns_id' not in server):
                    server['vns_id'] = vns_id

                if ('passwd' not in server):
                    server['passwd'] = cluster_passwd

                if server['server_id'] in host_role.keys():
                    server_roles = host_role[server['server_id']]
                    server['roles'] = []
                    for server_role in server_roles:
                        if server_role == "config":
                            server['roles'].append(role_config)
                        elif server_role == "openstack":
                            server['roles'].append(role_openstack)
                        elif server_role == "control":
                            server['roles'].append(role_control)
                        elif server_role == "compute":
                            server['roles'].append(role_compute)
                        elif server_role == "collector":
                            server['roles'].append(role_collector)
                        elif server_role == "webui":
                            server['roles'].append(role_webui)
                        elif server_role == "database":
                            server['roles'].append(role_database)

                self._serverDb.add_server(server)
        except Exception as e:
            abort(404, repr(e))

        return entity

    # API to add a new server to config DB. Along with server parameters,
    # user can also specify the roles to be configured on the server.
    def add_server(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Server MAC or server_id not specified')
        try:
            servers = entity.get("server", None)
            for server in servers:
                if (('server_id' not in server) or ('mac' not in server)):
                    abort(404, 'Server MAC or server_id not specified')
                self._serverDb.add_server(server)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end add_server

    # API Call to add image file to server manager (file is copied at
    # <default_base_path>/images/filename.iso and distro, profile
    # created in cobbler. The ISO is assumed to be available on the Server
    # where SM is running. This function DOES NOT upload image from REST client
    # For that use upload_image call instead.
    def add_image(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Error : No images specified')
        try:
            images = entity.get("image", None)
            for image in images:
                image_id = image.get("image_id", None)
                image_version = image.get("image_version", None)
                # Get Image type
                image_type = image.get("image_type", None)
                image_path = image.get("image_path", None)
                if (not image_id) or (not image_path):
                    abort(404, "image id or location not specified")
                if (image_type not in [
                        "centos", "fedora", "ubuntu",
                        "contrail-ubuntu-repo"]):
                    abort(404, "image type not specified or invalid")
                # For repo, simply copy file to base directory,
                # no cobbler operation is needed.
                if (image_type == "contrail-ubuntu-repo"):
                    extn = ".deb"
                else:
                    extn = ".iso"
                dest = self._args.smgr_base_dir + 'images/' + \
                    image_id + extn
                subprocess.call(["cp", "-f", image_path, dest])
                if (image_type == "contrail-ubuntu-repo"):
                    subprocess.call(
                        ["cp", "-f", dest,
                         self._args.html_root_dir + "contrail/images"])
                else:
                    self._add_image_to_cobbler(image_id, image_type,
                                               image_version, dest)
                image_data = {
                    'image_id': image_id,
                    'image_version': image_version,
                    'image_type': image_type}
                self._serverDb.add_image(image_data)
        except Exception as e:
            abort(404, repr(e))

    # API Call to add image file to server manager (file is copied at
    # <default_base_path>/images/filename.iso and distro, profile
    # created in cobbler. This is similar to function above (add_image),
    # but this call actually upload ISO image from client to the server.
    def upload_image(self):
        image_id = bottle.request.forms.image_id
        image_version = bottle.request.forms.image_version
        image_type = bottle.request.forms.image_type
        if (image_type not in [
                "centos", "fedora", "ubuntu",
                "contrail-ubuntu-repo"]):
            abort(404, "image type not specified or invalid")
        file_name = bottle.request.files.file_name
        if (image_type == "contrail-ubuntu-repo"):
            extn = ".deb"
        else:
            extn = ".iso"
        dest = self._args.smgr_base_dir + 'images/' + \
            image_id + extn
        try:
            if file_name.file:
                with open(dest, 'w') as open_file:
                    open_file.write(file_name.file.read())
            if (image_type == "contrail-ubuntu-repo"):
                subprocess.call(["cp", "-f", dest,
                                 self._args.html_root_dir +
                                 "contrail/images"])
            else:
                self._add_image_to_cobbler(image_id, image_type,
                                           image_version, dest)
            image_data = {
                'image_id': image_id,
                'image_version': image_version,
                'image_type': image_type}
            self._serverDb.add_image(image_data)
            self._add_image_to_cobbler(image_id, image_type,
                                       image_version, dest)
        except Exception as e:
            abort(404, repr(e))
    # End of upload_image

    # Copy to Cobbler as a distro and profile.
    # Distro related stuff. Check if distro for given ISO exists already.
    # The convention we will follow is that distro name is same as ISO
    # file name, without .iso extension. The iso is copied to a directory
    # with the same name under html root directory/contrail/images.
    # e.g. if iso is xyz.iso, we mount this iso under
    # /var/www/html/contrail/images. The distro name is XYZ, the profile
    # name is XYZ-P.
    def _add_image_to_cobbler(self, image_id, image_type,
                              image_version, dest):
        # Mount the ISO
        distro_name = image_id
        copy_path = self._args.html_root_dir + \
            'contrail/images/' + distro_name

        try:
            if ((image_type == "fedora") or (image_type == "centos")):
                kernel_file = "/isolinux/vmlinuz"
                initrd_file = "/isolinux/initrd.img"
                ks_file = self._args.html_root_dir + \
                    "kickstarts/contrail-centos.ks"
                kernel_options = ''
            elif (image_type == "ubuntu"):
                kernel_file = "/install/netboot/ubuntu-installer/amd64/linux"
                initrd_file = (
                    "/install/netboot/ubuntu-installer/amd64/initrd.gz")
                ks_file = self._args.html_root_dir + \
                    "kickstarts/contrail-ubuntu.seed"
                kernel_options = (
                    "lang=english console-setup/layoutcode=us locale=en_US "
                    "auto=true console-setup/ask_detect=false "
                    "priority=critical interface=auto "
                    "console-keymaps-at/keymap=us "
                    "ks=http://%s/kickstarts/contrail-ubuntu.ks ") % (
                    self._args.listen_ip_addr)
            else:
                abort(404, "invalid image type")
            self._mount_and_copy_iso(dest, copy_path, distro_name,
                                     kernel_file, initrd_file)
            # Setup distro information in cobbler
            self._smgr_cobbler.create_distro(
                distro_name, image_type,
                copy_path, kernel_file, initrd_file,
                self._args.listen_ip_addr)

            # Setup profile information in cobbler
            profile_name = distro_name
            self._smgr_cobbler.create_profile(profile_name, distro_name,
                                              image_type, ks_file,
                                              kernel_options)

            # Sync the above information
            self._smgr_cobbler.sync()
        except Exception as e:
            abort(404, repr(e))
    # End of _add_image_to_cobbler

    # API call to delete a cluster from server manager config. Along with
    # cluster, all servers in that cluster and associated roles are also
    # deleted.
    def delete_cluster(self):
        cluster_id = bottle.request.query.cluster_id
        try:
            self._serverDb.delete_cluster(cluster_id)
        except Exception as e:
            abort(404, repr(e))
        return "Cluster deleted"
    # end delete_cluster

    # API call to delete a vns from server manager config. Along with
    # vns, all servers in that vns and associated roles are also
    # deleted.
    def delete_vns(self):
        vns_id = bottle.request.query.vns_id
        try:
            self._serverDb.delete_vns(vns_id)
        except Exception as e:
            abort(404, repr(e))
        return "VNS deleted"
    # end delete_vns

    # API call to delete a server from the configuration.
    def delete_server(self):
        try:
            query_args = parse_qs(urlparse(bottle.request.url).query,
                                  keep_blank_values=True)
            # Get the query argument.
            if len(query_args) == 0:
                abort(404, "No server selection criteria specified")
            elif len(query_args) == 1:
                match_key, match_value = query_args.popitem()
                # check that match key is a valid one
                if ((match_key not in (
                        "server_id", "mac", "cluster_id",
                        "rack_id", "pod_id", "vns_id", "ip")) or
                        (len(match_value) != 1)):
                    abort(404, "Invalid Query arguments")
                match_value = match_value[0]
            else:
                abort(404, "Invalid Query arguments")
            servers = self._serverDb.get_server(match_key, match_value, False)
            self._serverDb.delete_server(match_key, match_value)
            # delete the system entries from cobbler
            for server in servers:
                self._smgr_cobbler.delete_system(server['server_id'])
            # Sync the above information
            self._smgr_cobbler.sync()
        except Exception as e:
            abort(404, repr(e))
        return "Server deleted"
    # end delete_server

    # API Call to delete an ISO image
    def delete_image(self):
        try:
            image_id = bottle.request.query.image_id
            if not image_id:
                abort(404, "Image Id not specified")
            images = self._serverDb.get_image("image_id", image_id, True)
            if not images:
                abort(404, "Image not found")
            image = images[0]
            if (image['image_type'] == 'contrail-ubuntu-repo'):
                # remove the file
                os.remove(self._args.smgr_base_dir + 'images/' +
                          image_id + '.deb')
                os.remove(self._args.html_root_dir +
                          'contrail/images/' +
                          image_id + '.deb')
            else:
                # delete corresponding distro from cobbler
                self._smgr_cobbler.delete_distro(image_id)
                # Sync the above information
                self._smgr_cobbler.sync()
                # remove the file
                os.remove(self._args.smgr_base_dir + 'images/' +
                          image_id + '.iso')
                # Remove the tree copied under cobbler.
                dir_path = self._args.html_root_dir + \
                    'contrail/images/' + image_id
                shutil.rmtree(dir_path)
            # remove the entry from DB
            self._serverDb.delete_image(image_id)
        except Exception as e:
            abort(404, repr(e))
    # End of delete_image

    # API to modify parameters for a server. User can modify IP, MAC, cluster
    # name (moving the server to a different cluster) , roles configured on
    # the server, or server parameters.
    def modify_server(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'Server MAC or server_id not specified')
        try:
            servers = entity.get("server", None)
            for server in servers:
                if (('server_id' not in server) and ('mac' not in server)):
                    abort(404, 'Server MAC or server_id not specified')
                # Restrict modification of certain fields only
                for key in server:
                    if key not in [
                        'server_id',
                        'ip',
                        'mask',
                        'gway',
                        'passwd',
                        'roles',
                        'server_params',
                        'domain']:
                        abort(404, 'invalid field in vns')
                self._serverDb.modify_server(server)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end modify_server

    # API to modify parameters for a VNS.
    def modify_vns(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'no vns specified')
        try:
            vns_list = entity.get("vns", None)
            for vns in vns_list:
                if ('vns_id' not in vns):
                    abort(404, 'vns_id not specified')
                # Restrict modification of certain fields only
                for key in vns:
                    if key not in [
                        'vns_id',
                        'vns_params']:
                        abort(404, 'invalid field in vns')
                self._serverDb.modify_vns(vns)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end modify_vns

    # API to modify parameters for an image.
    def modify_image(self):
        entity = bottle.request.json
        if (not entity):
            abort(404, 'no image specified')
        try:
            images = entity.get("image", None)
            for image in images:
                if ('image_id' not in image):
                    abort(404, 'image_id not specified')
                # Restrict modification of certain fields only
                for key in image:
                    if key not in [
                        'image_id',
                        'image_version']:
                        abort(404, 'invalid field in image')
                self._serverDb.modify_image(image)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end modify_image

    # API to modify parameters for a cluster. Currently no-op, but code
    # will be added later to change other cluster parameters.
    def modify_cluster(self):
        return
    # end modify_cluster

    # API to create the server manager configuration DB from provided JSON
    # file.
    def create_server_mgr_config(self):
        entity = bottle.request.json
        if not entity:
            abort(404, "No JSON config file specified")
        # Validate the config for sematic correctness.
        self._validate_config(entity)
        # Store the initial configuration in our DB
        try:
            self._create_server_manager_config(entity)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end create_server_mgr_config

    # API to process DHCP event from cobbler. This event notifies of a server
    # getting or releasing dynamic IP from cobbler DHCP.
    def process_dhcp_event(self):
        action = bottle.request.query.action
        entity = bottle.request.json
        try:
            self._serverDb.server_discovery(action, entity)
        except Exception as e:
            abort(404, repr(e))
        return entity
    # end process_dhcp_event

    # This call returns information about a provided server.
    # If no server if provided, information about all the servers
    # in server manager configuration is returned.
    def reimage_server(self):
        try:
            entity = bottle.request.json
            # Get image version parameter
            base_image_id = entity.pop("base_image_id", None)
            if not base_image_id:
                abort(404, "No base image id specified")
            repo_image_id = entity.pop("repo_image_id", '')
            req_reimage_params = entity.pop("reimage_params", None)
            # Now process other parameters there should be only one more
            if (req_reimage_params == None):
                if (len(entity) == 0):
                    abort(404, "No servers specified")
                elif len(entity) == 1:
                    match_key, match_value = entity.popitem()
                    # check that match key is a valid one
                    if (match_key not in ("server_id", "mac", "cluster_id",
                                          "rack_id", "pod_id", "vns_id")):
                        abort(404, "Invalid Query arguments")
                else:
                    match_key = None
                    match_value = None
                # end else
            # end if req_reimage_params == None
            images = self._serverDb.get_image("image_id", base_image_id, True)
            base_image = images[0]
            # Check if user specified reimage parameters with
            # the request. If so, allow reimage using those.
            if req_reimage_params:
                if (type(req_reimage_params) != type({})):
                    abort(404, "Incorrect server reimage parameters")
                servers = req_reimage_params.pop("servers", None)
                if ((not servers) or
                    (type(servers) != type([]))):
                    abort(404, "No servers specified")
                for server in servers:
                    if (type(server) != type({})):
                        continue
                    reimage_params = server.copy()
                    if ('server_passwd' not in reimage_params):
                        reimage_params['server_passwd'] = "c0ntrail123"
                    reimage_params['server_passwd'] = self._encrypt_passwd(
                        reimage_params['server_passwd'])
                    if ('server_ifname' not in reimage_params):
                        reimage_params['server_ifname'] = "eth0"
                    if (('server_ip' not in reimage_params) or
                        ('server_id' not in reimage_params) or
                        ('server_mac' not in reimage_params) or
                        ('server_mask' not in reimage_params) or
                        ('server_gway' not in reimage_params) or
                        ('server_domain' not in reimage_params)):
                        abort(404, "missing reimage parameters")
                    self._do_reimage_server(
                        base_image, repo_image_id, reimage_params)
                # end for server in servers
            # end if not servers
            else:
                servers = self._serverDb.get_server(
                    match_key, match_value, detail=True)
                for server in servers:
                    server_params = eval(server['server_params'])
                    # build all parameters needed for re-imaging
                    vns = self._serverDb.get_vns(server['vns_id'],
                                                 detail=True)[0]
                    vns_params = {}
                    if vns['vns_params']:
                        vns_params = eval(vns['vns_params'])
                    if server['passwd']:
                        passwd = server['passwd']
                    elif vns_params:
                        passwd = vns_params['passwd']
                    else:
                        abort(404, "Missing Password")
                    if server['mask']:
                        mask = server['mask']
                    elif vns_params:
                        mask = vns_params['mask']
                    else:
                        abort(404, "Missing Mask")
                    if server['gway']:
                        gway = server['gway']
                    elif vns_params:
                        gway = vns_params['gway']
                    else:
                        abort(404, "Missing Gateway")
                    if server['domain']:
                        domain = server['domain']
                    elif vns_params:
                        domain = vns_params['domain']
                    else:
                        abort(404, "Missing Domain")

                    reimage_params = {}
                    reimage_params['server_id'] = server['server_id']
                    reimage_params['server_ip'] = server['ip']
                    reimage_params['server_mac'] = server['mac']
                    reimage_params['server_passwd'] = self._encrypt_passwd(
                        passwd)
                    reimage_params['server_mask'] = mask
                    reimage_params['server_gway'] = gway
                    reimage_params['server_domain'] = domain
                    reimage_params['server_ifname'] = server_params['ifname']
<<<<<<< HEAD
=======
                    reimage_params['power_type'] = server.get('power_type')
                    if not reimage_params['power_type']:
                        reimage_params['power_type'] = self._args.power_type
                    reimage_params['power_user'] = server.get('power_user')
                    if not reimage_params['power_user']:
                        reimage_params['power_user'] = self._args.power_user
                    reimage_params['power_pass'] = server.get('power_pass')
                    if not reimage_params['power_pass']:
                        reimage_params['power_pass'] = self._args.power_pass
                    reimage_params['power_address'] = server.get(
                        'power_address', '')
                    if base_image['image_type'] == 'esxi5.5':
                        reimage_params['server_license'] = server_params.get(
                            'server_license', '')
                        reimage_params['esx_nicname'] = server_params.get(
                            'esx_nicname', 'vmnic0')
                    # end if
>>>>>>> 4bbba98... Provide IPMI interface (via cobbler) for rebooting servers. Before this
                    self._do_reimage_server(
                        base_image, repo_image_id, reimage_params)
                # end for server in servers
            # end else
        except Exception as e:
            abort(404, repr(e))
        return "server(s) upgraded"
    # end reimage_server

    # API call to power-cycle the server (IMPI Interface)
    def restart_server(self):
        try:
            entity = bottle.request.json
            # Get parameter to check if netboot should be enabled.
            net_boot = entity.pop("net_boot", None)
            if ((not net_boot) or (net_boot != "y")):
                net_boot = "n"
            req_restart_params = entity.pop("restart_params", None)
            # if no restart params are specified, there needs to be
            # server selection criteria provided.
            if req_restart_params:
                if (type(req_restart_params) != type({})):
                    abort(404, "Incorrect server restart parameters")
                servers = req_restart_params.pop("servers", None)
                if ((not servers) or
                    (type(servers) != type([]))):
                    abort(404, "No servers specified")
                reboot_server_list = []
                for server in servers:
                     reboot_server = {
                         'server_id' : server.get('server_id', ''),
                         'domain' : server.get('server_domain', ''),
                         'ip' : server.get('server_ip', ''),
                         'passwd' : server.get('server_passwd', ''),
                         'power_address' : server.get('power_address', '') }
                     reboot_server_list.append(
                         reboot_server)
                # end for server in servers
            else:
                if len(entity) == 0:
                    abort(404, "No servers specified")
                elif len(entity) == 1:
                    match_key, match_value = entity.popitem()
                    # check that match key is a valid one
                    if (match_key not in ("server_id", "mac", "cluster_id",
                                          "rack_id", "pod_id", "vns_id")):
                        abort(404, "Invalid Query arguments")
                else:
                    abort(404, "Invalid Query arguments")
                # end else
                reboot_server_list = []
                servers = self._serverDb.get_server(
                    match_key, match_value, detail=True)
                for server in servers:
                    vns = self._serverDb.get_vns(server['vns_id'],
                                                 detail=True)[0]
                    vns_params = {}
                    if vns['vns_params']:
                        vns_params = eval(vns['vns_params'])

                    if server['passwd']:
                        passwd = server['passwd']
                    elif vns_params:
                        passwd = vns_params['passwd']
                    else:
                        abort(404, "Missing password")

                    if server['domain']:
                        domain = server['domain']
                    elif vns_params:
                        domain = vns_params['domain']
                    else:
                        abort(404, "Missing Domain")

                    # Build list of servers to be rebooted.
                    reboot_server = {
                        'server_id' : server['server_id'],
                        'domain' : domain,
                        'ip' : server['ip'],
                        'passwd' : passwd,
                        'power_address' : server['power_address'] }
                    reboot_server_list.append(
                        reboot_server)
                # end for server in servers
            # end else req_restart_params

            status_msg = self._power_cycle_servers(
                reboot_server_list, net_boot)
        except Exception as e:
            abort(404, repr(e))
        return status_msg
    # end restart_server

    # Function to get all servers in a VNS configured for given role.
    def role_get_servers(self, vns_servers, role_type):
        servers = []
        for server in vns_servers:
            if role_type in server['roles']:
                servers.append(server)
        return servers

    # Function to get map server name to server ip
    # accepts list of server names and returns list of
    # server ips
    def get_server_ip_list(self, server_names, servers):
        server_ips = []
        for server_name in server_names:
            for server in servers:
                if server['server_id'] == server_name:
                    server_ips.append(
                        server['server_ip'])
                    break
                # end if
            # end for server
        # end for server_name
        return server_ips
    # end get_server_ip_list

    # API call to provision server(s) as per roles/roles
    # defined for those server(s). This function creates the
    # puppet manifest file for the server and adds it to site
    # manifest file.
    def provision_server(self):
        try:
            entity = bottle.request.json
            req_provision_params = entity.pop("provision_params", None)
            # if no provision params are specified, there needs to be
            # server selection criteria provided.
            if (req_provision_params == None):
                if (len(entity) == 0):
                    abort(404, "No servers specified")
                elif len(entity) == 1:
                    match_key, match_value = entity.popitem()
                    # check that match key is a valid one
                    if (match_key not in (
                        "server_id", "mac", "cluster_id",
                        "rack_id", "pod_id", "vns_id")):
                        abort(404, "Invalid Query arguments")
                else:
                    match_key = None
                    match_value = None
                # end else
            # end if req_provision_params == None
            # Check if user specified provision params with the
            # request. If so, allow provisioning using those.
            if (req_provision_params):
                if (type(req_provision_params) != type({})):
                    abort(404, "Incorrect server provision parameters")
                servers = req_provision_params.pop("servers", None)
                if ((not servers) or
                    (type(servers) != type([]))):
                    abort(404, "No servers specified")
                roles = req_provision_params.pop("roles", None)
                if ((not roles) or
                    (type(roles) != type ({}))):
                    abort(404, "No roles specified")
                # set default values in provision params
                provision_params = {
                    "database_dir" : "/home/cassandra",
                    "db_initial_token" : "",
                    "openstack_mgmt_ip" : "",
                    "use_certs" : "False",
                    "multi_tenancy" : "False",
                    "service_token" : "contrail123",
                    "ks_user" : "admin",
                    "ks_passwd" : "contrail123",
                    "ks_tenant" : "admin",
                    "openstack_passwd" : "contrail123",
                    "analytics_data_ttl" : "168"
                }
                params = req_provision_params.pop(
                    "params", None)
                if ((not params) or
                    (type(params) != type ({}))):
                    abort(404, "No params specified")
                for key, value in params.iteritems():
                    provision_params[key] = value 
                for key, value in roles.iteritems():
                    if (type(value) != type([])):
                        abort(404, "roles format error")
                    roles[key] = self.get_server_ip_list(
                        value, servers)
                provision_params['roles'] = roles
                for server in servers:
                    provision_params['server_id'] = server[
                        'server_id']
                    provision_params['server_ip'] = server[
                        'server_ip']
                    provision_params['phy_interface'] = server[
                        'ifname']
                    provision_params[
                        'compute_non_mgmt_ip'] = server.get(
                            'compute_non_mgmt_ip', '')
                    provision_params[
                        'compute_non_mgmt_gway'] = server.get(
                            'compute_non_mgmt_gway', '')
                    self._do_provision_server(provision_params)
                return "Server(s) provisioned"
            # end if req_provision_params
            role_servers = {}
            role_ips = {}
            servers = self._serverDb.get_server(match_key, match_value,
                                                detail=True)
            for server in servers:
                server_params = eval(server['server_params'])
                vns = self._serverDb.get_vns(server['vns_id'],
                                             detail=True)[0]
                vns_params = eval(vns['vns_params'])
                # Get all the servers belonging to the VNS that this server
                # belongs too.
                vns_servers = self._serverDb.get_server(
                    match_key="vns_id", match_value=server["vns_id"],
                    detail="True")
                # build roles dictionary for this vns. Roles dictionary will be
                # keyed by role-id and value would be list of servers configured
                # with this role.
                if not role_servers:
                    for role in ['database', 'openstack',
                                 'config', 'control',
                                 'collector', 'webui',
                                 'compute']:
                        role_servers[role] = self.role_get_servers(
                            vns_servers, role)
                        role_ips[role] = [x["ip"] for x in role_servers[role]]
                provision_params = {}
                provision_params['roles'] = role_ips
                provision_params['server_id'] = server['server_id']
                if server['domain']:
                    provision_params['domain'] = server['domain']
                else:
                    provision_params['domain'] = vns_params['domain']
                provision_params['server_ip'] = server['ip']
                provision_params['database_dir'] = vns_params['database_dir']
                provision_params['db_initial_token'] = vns_params['db_initial_token']
                provision_params['openstack_mgmt_ip'] = vns_params['openstack_mgmt_ip']
                provision_params['use_certs'] = vns_params['use_certs']
                provision_params['multi_tenancy'] = vns_params['multi_tenancy']
                provision_params['service_token'] = vns_params['service_token']
                provision_params['ks_user'] = vns_params['ks_user']
                provision_params['ks_passwd'] = vns_params['ks_passwd']
                provision_params['ks_tenant'] = vns_params['ks_tenant']
                provision_params['openstack_passwd'] = vns_params['openstack_passwd']
                provision_params['analytics_data_ttl'] = vns_params['analytics_data_ttl']
                provision_params['phy_interface'] = server_params['ifname']
                provision_params['compute_non_mgmt_ip'] = server_params['compute_non_mgmt_ip']
                provision_params['compute_non_mgmt_gway'] = server_params['compute_non_mgmt_gway']
                self._do_provision_server(provision_params)
        except Exception as e:
            abort(404, repr(e))
        return "server(s) provisioned"
    # end provision_server

    # TBD
    def cleanup(self):
        print "called cleanup"
    # end cleanup

    # Private Methods
    # Parse program arguments.
    def _parse_args(self, args_str):
        '''
        Eg. python vnc_server_manager.py --config_file serverMgr.cfg
                                         --listen_ip_addr 127.0.0.1
                                         --listen_port 8082
                                         --db_name vns_server_mgr.db
                                         --server_list myClusters.json
        '''

        # Source any specified config/ini file
        # Turn off help, so we print all options in response to -h
        conf_parser = argparse.ArgumentParser(add_help=False)

        conf_parser.add_argument(
            "-c", "--config_file",
            help="Specify config file with the parameter values.",
            metavar="FILE")
        args, remaining_argv = conf_parser.parse_known_args(args_str)

        serverMgrCfg = {
            'listen_ip_addr'   : _WEB_HOST,
            'listen_port'      : _WEB_PORT,
            'db_name'          : _DEF_CFG_DB,
            'smgr_base_dir'    : _DEF_SMGR_BASE_DIR,
            'html_root_dir'    : _DEF_HTML_ROOT_DIR,
            'cobbler_ip'       : _DEF_COBBLER_IP,
            'cobbler_port'     : _DEF_COBBLER_PORT,
            'cobbler_user'     : _DEF_COBBLER_USER,
            'cobbler_passwd'   : _DEF_COBBLER_PASSWD,
            'power_user'       : _DEF_POWER_USER,
            'power_pass'       : _DEF_POWER_PASSWD,
            'power_type'       : _DEF_POWER_TOOL,
            'puppet_dir'       : _DEF_PUPPET_DIR
        }

        if args.config_file:
            config_file = args.config_file
        else:
            config_file = _DEF_SMGR_CFG_FILE
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([args.config_file])
            for key in serverMgrCfg.keys():
                serverMgrCfg[key] = dict(config.items("SERVER-MANAGER"))[key]
        except:
            # if config file could not be read, use default values
            pass

        # Override with CLI options
        # Don't surpress add_help here so it will handle -h
        parser = argparse.ArgumentParser(
            # Inherit options from config_parser
            # parents=[conf_parser],
            # print script description with -h/--help
            description=__doc__,
            # Don't mess with format of description
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.set_defaults(**serverMgrCfg)

        parser.add_argument(
            "-i", "--listen_ip_addr",
            help="IP address to provide service on, default %s" % (_WEB_HOST))
        parser.add_argument(
            "-p", "--listen_port",
            help="Port to provide service on, default %s" % (_WEB_PORT))
        parser.add_argument(
            "-d", "--db_name",
            help=(
                "Name where server DB is maintained, default %s"
                % (_DEF_CFG_DB)))
        parser.add_argument(
            "-l", "--server_list",
            help=(
                "Name of JSON file containing list of cluster and servers,"
                " default None"))
        self._args = parser.parse_args(remaining_argv)
        self._args.config_file = args.config_file
    # end _parse_args

    # TBD : Any semantic rules to be added when creating configuration
    # objects would be included here. e.g. checking IP address format
    # for the server etc.
    def _validate_config(self, config_data):
        pass
    # end _validate_config

    # Private method to unmount iso after calling cobbler functions.
    def _unmount_iso(self, mount_path):
        return_code = subprocess.call(["umount", mount_path])
    # end _unmount_iso

    # Private method to mount a given iso before calling cobbler functions.
    def _mount_and_copy_iso(self, full_image_name, copy_path, distro_name,
                            kernel_file, initrd_file):
        try:
            mount_path = self._args.smgr_base_dir + "mnt/"
            self._unmount_iso(mount_path)
            # Make directory where ISO will be mounted
            return_code = subprocess.call(["mkdir", "-p", mount_path])
            if (return_code != 0):
                return return_code
            # Mount the ISO
            return_code = subprocess.call(
                ["mount", "-o", "loop", full_image_name, mount_path])
            if (return_code != 0):
                return return_code
            #  Make directory where files from mounted ISO are copied.
            return_code = subprocess.call(["mkdir", "-p", copy_path])
            if (return_code != 0):
                return return_code
            # Copy the files from mounted ISO.
            shutil.rmtree(copy_path, True)
            shutil.copytree(mount_path, copy_path, True)
            # Need to change mode to kernel and initrd files to read for all.
            kernel_file_full_path = copy_path + kernel_file
            return_code = subprocess.call(
                ["chmod", "755", kernel_file_full_path])
            if (return_code != 0):
                return return_code
            initrd_file_full_path = copy_path + initrd_file
            return_code = subprocess.call(
                ["chmod", "755", initrd_file_full_path])
            if (return_code != 0):
                return return_code
            # Now unmount the ISO
            self._unmount_iso(mount_path)
        except Exception as e:
            raise e
    # end _mount_and_copy_iso

    # Private method to reboot the server after cobbler config is setup.
    # If power address is provided and power management system is configured
    # with cobbler, that is used to power cycle the server, else if SSH
    # connectivity is available to the server, that is used to login and reboot
    # the server.
    def _power_cycle_servers(
        self, reboot_server_list, net_boot="n"):
        success_list = []
        failed_list = []
        power_reboot_list = []
        for server in reboot_server_list:
            try:
                # Enable net boot flag in cobbler for the system.
                # Also if netbooting, delete the old puppet cert. This is
                # temporary. Need # to figure out way for cobbler to do it
                # automatically TBD Abhay
                if (net_boot == "y"):
                    self._smgr_cobbler.enable_system_netboot(
                        server['server_id'])
                    cmd = "puppet cert clean %s.%s" % (
                        server['server_id'], server['domain'])
                    subprocess.call(cmd, shell=True)
                # end if
                if server['power_address']:
                    power_reboot_list.append(
                        server['server_id'])
                else:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(
                        paramiko.AutoAddPolicy())
                    client.connect(
                        server_ip, username='root', password=passwd)
                    stdin, stdout, stderr = client.exec_command('reboot')
                # end else
                # Update Server table to update time.
                update = {'server_id': server['server_id'],
                          'update_time': strftime(
                             "%Y-%m-%d %H:%M:%S", gmtime())}
                self._serverDb.modify_server(update)
                success_list.append(server['server_id'])
            except Exception as e:
                failed_list.append(server['server_id'])
        #end for
        if power_reboot_list:
            try:
                self._smgr_cobbler.reboot_system(
                    power_reboot_list)
                status_msg = (
                    "OK : IPMI reboot operation"
                    " initiated for specified servers")
            except Exception as e:
                status_msg = ("Error : IPMI reboot operation"
                              " failed for some servers")
        else:
            status_msg = (
                "Reboot Successful for (%s),"
                "failed for (%s)" %(
                ",".join(success_list),
                ",".join(failed_list)))
        # End if power_reboot_list
        return status_msg

    # end _power_cycle_servers

    def _encrypt_passwd(self, server_passwd):
        try:
            xyz = subprocess.Popen(
                ["openssl", "passwd", "-1", "-noverify", server_passwd],
                stdout=subprocess.PIPE).communicate()[0]
        except:
            return None
        return xyz

    # Internal private call to upgrade server. This is called by REST
    # API update_server and upgrade_cluster
    def _do_reimage_server(self, base_image,
                           repo_image_id, reimage_params):
        try:
            # Profile name is based on image name.
            profile_name = base_image['image_id']
            # Setup system information in cobbler
            self._smgr_cobbler.create_system(
                reimage_params['server_id'], profile_name, repo_image_id,
                reimage_params['server_mac'], reimage_params['server_ip'],
                reimage_params['server_mask'], reimage_params['server_gway'],
                reimage_params['server_domain'], reimage_params['server_ifname'],
                reimage_params['server_passwd'],
<<<<<<< HEAD
=======
                reimage_params.get('server_license', ''),
                reimage_params.get('esx_nicname', 'vmnic0'),
                reimage_params.get('power_type',self._args.power_type),
                reimage_params.get('power_user',self._args.power_user),
                reimage_params.get('power_pass',self._args.power_pass),
                reimage_params.get('power_address',''),
>>>>>>> 4bbba98... Provide IPMI interface (via cobbler) for rebooting servers. Before this
                base_image, self._args.listen_ip_addr)

            # Sync the above information
            self._smgr_cobbler.sync()

            # Update Server table to add image name
            update = {
                'mac': reimage_params['server_mac'],
                'base_image_id': base_image['image_id'],
                'repo_image_id': repo_image_id}
            self._serverDb.modify_server(update)

            # TBD Need to add a way to confirm that server came up with
            # upgrade OS and also add this info to the DB in server table
            # (version upgraded to and timestamp). Possibly start a process
            # to ping the server and when up, ssh and get contrail version.
        except Exception as e:
            raise e
    # end _do_reimage_server

    # Internal private call to provision server. This is called by REST API
    # provision_server and provision_cluster
    def _do_provision_server(self, provision_params):
        try:
            # Now call puppet to provision the server.
            self._smgr_puppet.provision_server(
                provision_params)

            # TBD Update Server table to stamp provisioned time.
            # update = {'server_id':server_id,
            #          'image_id':image_id}
            # self._serverDb.modify_server(update)

        except Exception as e:
            raise e
    # end _do_provision_server

    def _create_server_manager_config(self, config):
        try:
            clusters = config.get("clusters", None)
            if clusters:
                for cluster in clusters:
                    self._serverDb.add_cluster(cluster)
            vns_list = config.get("vns", None)
            if vns_list:
                for vns in vns_list:
                    self._serverDb.add_vns(vns)
            servers = config.get("servers", None)
            if servers:
                for server in servers:
                    self._serverDb.add_server(server)
        except Exception as e:
            raise e
    # end _create_server_manager_config

# End class VncServerManager()


def main(args_str=None):
    vnc_server_mgr = VncServerManager(args_str)
    pipe_start_app = vnc_server_mgr.get_pipe_start_app()

    server_ip = vnc_server_mgr.get_server_ip()
    server_port = vnc_server_mgr.get_server_port()

    server_mgr_pid = os.getpid()
    pid_file = "/var/run/contrail_smgrd/contrail_smgrd.pid"
    dir = os.path.dirname(pid_file)
    if not os.path.exists(dir):
        os.mkdir(dir)
    f = open(pid_file, "w")
    f.write(str(server_mgr_pid))
    f.close()

    try:
        bottle.run(app=pipe_start_app, host=server_ip, port=server_port)
    except Exception as e:
        # cleanup gracefully
        vnc_server_mgr.cleanup()

# End of main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    main()
# End if __name__
