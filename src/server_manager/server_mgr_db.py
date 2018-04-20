#!/usr/bin/python

import sqlite3 as lite
import os
import sys
import pdb
import uuid
import subprocess
from netaddr import *
from server_mgr_err import *
from server_mgr_utils import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

def_server_db_file = 'smgr_data.db'
cluster_table = 'cluster_table'
server_table = 'server_table'
image_table = 'image_table'
inventory_table = 'inventory_table'
server_status_table = 'status_table'
server_tags_table = 'server_tags_table'
dhcp_subnet_table = 'dhcp_subnet_table'
dhcp_hosts_table = 'dhcp_hosts_table'
hw_data_table='hw_data_table'

_DUMMY_STR = "DUMMY_STR"


class ServerMgrDb:

    # Input: Specify table name by giving the object name and '_table' will be added by
    # this function while looking for the table
    # Output: Dict of columns, if table matches. Otherwise, empty list will be returned
    def get_table_columns(self, table_name):
        table_columns = {}
        if not table_name:
            return table_columns
        db_table_name = table_name+'_table'
        with self._con:
            cursor = self._con.cursor()
            table_info_cmd = "PRAGMA table_info(%s)" % db_table_name
            cursor.execute(table_info_cmd)
            column_info_table = cursor.fetchall()
            if cursor.description and column_info_table:
                output_header_info = [x[0] for x in cursor.description]
                if 'name' in output_header_info and 'type' in output_header_info:
                    table_columns['header'] = {'column name': 'type'}
                    name_index = output_header_info.index('name')
                    type_index = output_header_info.index('type')
                    columns = {}
                    for column_info in column_info_table:
                        columns[str(column_info[name_index])] = str(column_info[type_index])
                    table_columns['columns'] = columns
            return table_columns
    # end get_table_columns

    def _add_table_column(self, cursor, table, column, column_type):
        try:
            cmd = "ALTER TABLE " + table + " ADD COLUMN " + column + " " + column_type
            cursor.execute(cmd)
        except lite.OperationalError:
            pass
    # end _add_table_column

    def log_and_raise_exception(self, msg, err_code = ERR_OPR_ERROR):
         self._smgr_log.log(self._smgr_log.ERROR, msg)
         raise ServerMgrException(msg, err_code)

    def __init__(self, db_file_name=def_server_db_file):
        try:
            self._smgr_log = ServerMgrlogger()
            self._con = lite.connect(db_file_name)
            with self._con:
                cursor = self._con.cursor()
                # Create cluster table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + cluster_table +
                               """ (id TEXT PRIMARY KEY,
                                    parameters TEXT,
                                    email TEXT)""")
                # Create image table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               image_table + """ (id TEXT PRIMARY KEY,
                    version TEXT, type TEXT, path TEXT,
                    parameters TEXT)""")
                # Create status table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               server_status_table + """ (id TEXT PRIMARY KEY,
                            server_status TEXT)""")
                # Create server table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + server_table +
                    """ (mac_address TEXT PRIMARY KEY NOT NULL,
                         id TEXT, host_name TEXT, static_ip varchar default 'N',
                         ip_address TEXT, subnet_mask TEXT, gateway TEXT, domain TEXT,
                         cluster_id TEXT,  base_image_id TEXT,
                         package_image_id TEXT, password TEXT,
                         last_update TEXT, discovered varchar default 'false',
                         parameters TEXT, roles TEXT, ipmi_username TEXT,
                         ipmi_password TEXT, ipmi_address TEXT,
                         ipmi_type TEXT, intf_control TEXT,
                         intf_data TEXT, intf_bond TEXT,
                         email TEXT, status TEXT,
                         tag1 TEXT, tag2 TEXT, tag3 TEXT,
                         tag4 TEXT, tag5 TEXT, tag6 TAXT, tag7 TEXT,
                         network TEXT, contrail TEXT, top_of_rack TEXT,
                         UNIQUE (id))""")
                # Create inventory table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + inventory_table +
                    """ (fru_description TEXT PRIMARY KEY NOT NULL,
                         id TEXT, board_serial_number TEXT, chassis_type TEXT,
                         chassis_serial_number TEXT, board_mfg_date TEXT,
                         board_manufacturer TEXT, board_product_name TEXT,
                         board_part_number TEXT, product_manfacturer TEXT,
                         product_name TEXT, product_part_number TEXT,
                         UNIQUE (fru_description))""")
                # Create DHCP subnet table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + dhcp_subnet_table +
                    """ (subnet_address TEXT PRIMARY KEY NOT NULL,
                         subnet_gateway TEXT, subnet_mask TEXT, dns_server_list TEXT,
                         search_domains_list TEXT, subnet_domain TEXT,
                         dhcp_range TEXT, default_lease_time INTEGER, max_lease_time INTEGER,
                         UNIQUE (subnet_address))""")
                # Create DHCP hosts table 
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + dhcp_hosts_table +
                    """ (host_fqdn TEXT PRIMARY KEY NOT NULL,
                         ip_address TEXT NOT NULL, mac_address TEXT NOT NULL, host_name TEXT,
                         UNIQUE (host_fqdn))""")
                # Create server tags table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + server_tags_table +
                    """ (tag_id TEXT PRIMARY KEY NOT NULL,
                         value TEXT,
                         UNIQUE (tag_id),
                         UNIQUE (value))""")

                cursor.execute("CREATE TABLE IF NOT EXISTS " + hw_data_table +
                               """ (uuid TEXT PRIMARY KEY NOT NULL,
                                    basic_hw TEXT,
                                    full_hw TEXT,
                                    sm_json TEXT,
                                    sid TEXT)""")
                # Add columns for image_table
                self._add_table_column(cursor, image_table, "category", "TEXT")
                # Add columns for cluster_table
                self._add_table_column(cursor, cluster_table, "base_image_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "package_image_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "provisioned_id", "TEXT")
                self._add_table_column(cursor, cluster_table, "provision_role_sequence", "TEXT")
                # Add columns for server_table
                self._add_table_column(cursor, server_table, "reimaged_id", "TEXT")
                self._add_table_column(cursor, server_table, "provisioned_id", "TEXT")
                self._add_table_column(cursor, server_table, "network", "TEXT")
                self._add_table_column(cursor, server_table, "top_of_rack", "TEXT")
                self._add_table_column(cursor, server_table, "contrail", "TEXT")
                self._add_table_column(cursor, server_table, "ssh_public_key", "TEXT")
                self._add_table_column(cursor, server_table, "ssh_private_key", "TEXT")
                self._add_table_column(cursor, server_table, "ipmi_interface", "TEXT")

            self._smgr_log.log(self._smgr_log.DEBUG, "Created tables")

            # During init, we check if any of the Cluster in DB are missing any Storage Parameters (Generated UUIDs)
            cluster_list = self._get_items(cluster_table, None,
                                       None, True, None)
            for cluster in cluster_list:
                # Check if storage parameters are present in Cluster, else generate them
                if 'storage_fsid' not in set(eval(cluster['parameters'])) or 'storage_virsh_uuid' not in set(eval(
                        cluster['parameters'])):
                    self.update_cluster_uuids(cluster)

            self.update_image_table()
            self.update_server_table()
        except Exception as e:
            raise e
    # End of __init__

    def update_image_version(self, image):
        if not image:
           return

        parameters = image.get('parameters',"")
        if parameters:
            parameters = eval(parameters)

        # if version is not there or NO_VERSION (not found) laster time, try
        # to find the version using dpkg-deb
        if (parameters and 'version' in parameters and parameters['version'] != ''):
            # version is already found, no action needed
            if parameters['version'] != 'NO_VERSION':
                return

        # only ubuntu packages are processed for finding version
        if not (image['type'] == 'contrail-storage-ubuntu-package' or image['type'] == 'contrail-ubuntu-package'):
           return

        # following used for getting details about ubuntu package
        # dpkg-deb -f /path/to/package.deb Version
        extn = os.path.splitext(image['path'])[1]
        image_path = '/etc/contrail_smgr/images/' + image['id'] + extn
        self._smgr_log.log(self._smgr_log.DEBUG, "update_image_version path : %s" %image_path)
        version = subprocess.check_output(['dpkg-deb', '-f',image_path,'Version'])
        parameters['version'] = version.strip('\n')

        image['parameters'] = parameters
        self.modify_image(image)
    ##End of update_image_version

    def update_server_table(self):
        servers = self.get_server(detail=True)
        for server in servers:
          host_name = server.get('host_name', "")
          server_id = server.get('id',"")
          self._smgr_log.log(self._smgr_log.DEBUG, "SERVER_ID : %s, host => %s" %(server['id'], host_name))
          # dhcp based server discovery will have server id as empty
          #if both the host_name and server_id are not set just bail out
          if host_name in [None,""] and server_id in [None, ""]:
              break
          if server_id == None or server_id == "":
            continue
          if host_name is None or host_name == "":
              server['host_name'] = server_id.lower()
          else :
              server['host_name'] = host_name.lower()

          self._smgr_log.log(self._smgr_log.DEBUG, "SERVER_ID : %s, host => %s" %(server['id'], server['host_name']))
          update = {'id': server_id, 'host_name': server['host_name'] }
          self.modify_server(update)

    ## End of update_server_table

    def update_image_table(self):
        images = self.get_image(None, detail=True)
        for image in images:
            self.update_image_version(image)

    def get_subnet_mask(self, server):
        subnet_mask = server.get('subnet_mask', None)
        if not subnet_mask:
            cluster = server.get('cluster', None)
            if cluster:
                subnet_mask = cluster.get('subnet_mask', None)
        return subnet_mask
    # End get_subnet_mask

    def get_server_domain(self, server_id):
        server_domain = ""
        if not server_id:
            return server_domain
        servers = self.get_server(
            {"id" : server_id}, detail=True)
        if not servers:
            msg = "No server found with server_id " + server_id
            self._smgr_log.log(self._smgr_log.ERROR, msg)
            return server_domain
        server = servers[0]
        server_domain = server.get('domain', "")
        if not server_domain:
            cluster_id = server.get('cluster_id', "")
            if not cluster_id:
                msg = "No domain found for server_id " + server_id
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
            clusters = self.get_cluster(
                {"id" : cluster_id}, detail=True)
            if not clusters:
                msg = "No domain found for server_id %s, no cluster for cluster_id %s," \
                    % (server_id, cluster_id)
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
            cluster = clusters[0]
            cluster_params = eval(cluster['parameters'])
            server_domain = cluster_params.get('domain', "")
            if not server_domain:
                msg = "No domain found for server_id %s, cluster_id %s" \
                    % (server_id, cluster_id)
                self._smgr_log.log(self._smgr_log.ERROR, msg)
                return server_domain
        return server_domain
    # End get_server_domain

    def delete_tables(self):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.executescript("""
                DELETE FROM """ + cluster_table + """;
                DELETE FROM """ + server_table + """;
                DELETE FROM """ + server_tags_table + """;
                DELETE FROM """ + server_status_table + """;
                DELETE FROM """ + inventory_table + """;
                DELETE FROM """ + dhcp_subnet_table + """;
                DELETE FROM """ + dhcp_hosts_table + """;
                DELETE FROM """ + hw_data_table + """;
                DELETE FROM """ + image_table + ";")
        except:
            raise e
    # End of delete_tables

    def get_server_id(self, server_mac):
        try:
            if server_mac:
                server_mac = str(EUI(server_mac)).replace("-", ":")
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT id FROM " +
                               server_table + " WHERE mac_address=?",
                              (server_mac,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None
    # end get_server_id

    # Below function returns value corresponding to tag_id from
    # server_tags_table
    def get_server_tag(self, tag_id):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT value FROM " +
                               server_tags_table + " WHERE tag_id=?",
                              (tag_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None
    # end get_server_tag

    def get_server_mac(self, id):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT mac_address FROM " +
                               server_table + " WHERE id=?",
                              (id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None

    def _add_row(self, table_name, dict):
        try:
            keys, values = zip(*dict.items())
            insert_str = "INSERT OR IGNORE INTO %s (%s) values (%s)" \
                % (table_name,
                   (",".join(keys)),
                   (",".join('?' * len(keys))))
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(insert_str, values)
        except Exception as e:
            raise e
    # end _add_row

    # Generic function to delete rows matching given criteria
    # from given table.
    # Match dict is dictionary of columns and values to match for.
    # unmatch dict is not of dictionaty of columns and values to match for.
    def _delete_row(self, table_name,
                    match_dict=None, unmatch_dict=None):
        try:
            delete_str = "DELETE FROM %s" %(table_name)
            # form a string to provide to where match clause
            match_list = []
            where = None
            if match_dict:
                where = match_dict.get("where", None)

            if where:
                delete_str += " WHERE " + where
            else:
                if match_dict:
                    match_list = ["%s = \'%s\'" %(
                            k,v) for k,v in match_dict.iteritems()]
                if unmatch_dict:
                    match_list += ["%s != \'%s\'" %(
                            k,v) for k,v in unmatch_dict.iteritems()]
                if match_list:
                    match_str = " and ".join(match_list)
                    delete_str+= " WHERE " + match_str

            with self._con:
                cursor = self._con.cursor()
                cursor.execute(delete_str)
        except Exception as e:
            raise e
    # End _delete_row

    def _modify_row(self, table_name, dict,
                    match_dict=None, unmatch_dict=None):
        try:
            keys, values = zip(*dict.items())
            modify_str = "UPDATE %s SET " % (table_name)
            update_list = ",".join(key + "=?" for key in keys)
            modify_str += update_list
            match_list = []
            if match_dict:
                match_list = ["%s = ?" %(
                    k) for k in match_dict.iterkeys()]
                match_values = [v for v in match_dict.itervalues()]
            if unmatch_dict:
                match_list += ["%s != ?" %(
                    k) for k in unmatch_dict.iterkeys()]
                match_values += [v for v in unmatch_dict.itervalues()]
            if match_list:
                match_str = " and ".join(match_list)
                match_values_str = ",".join(match_values)
                modify_str += " WHERE " + match_str
                values += (match_values_str,)
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(modify_str, values)
        except Exception as e:
            raise e

    def _get_items(
        self, table_name, match_dict=None,
        unmatch_dict=None, detail=False, always_fields=None):
        try:
            with self._con:
                cursor = self._con.cursor()
                if detail:
                    sel_cols = "*"
                else:
                    sel_cols = ",".join(always_fields)
                select_str = "SELECT %s FROM %s" % (sel_cols, table_name)
                # form a string to provide to where match clause
                match_list = []
                where = None
                if match_dict:
                    where = match_dict.get("where", None)
                if where:
                    select_str += " WHERE " + where
                else:
                    if match_dict:
                        match_list = ["%s = \'%s\'" %(
                                k,v) for k,v in match_dict.iteritems()]
                    if unmatch_dict:
                        match_list += ["%s != \'%s\'" %(
                                k,v) for k,v in unmatch_dict.iteritems()]
                    if match_list:
                        match_str = " and ".join(match_list)
                        select_str+= " WHERE " + match_str
                cursor.execute(select_str)
            rows = [x for x in cursor]
            cols = [x[0] for x in cursor.description]
            items = []
            for row in rows:
                item = {}
                for prop, val in zip(cols, row):
                    item[prop] = val
                items.append(item)
            return items
        except Exception as e:
            raise e
    # End _get_items

    def add_cluster(self, cluster_data):
        try:
            # covert all unicode strings in dict
            cluster_data = ServerMgrUtil.convert_unicode(cluster_data)
            # Store cluster_parameters dictionary as a text field
            if 'parameters' in cluster_data:
                cluster_parameters = cluster_data.pop("parameters")
                cluster_parameters = DictUtils.remove_none_from_dict(cluster_parameters)
                if not cluster_parameters:
                    cluster_parameters = {}
                cluster_data['parameters'] = str(cluster_parameters)
            # Store provision sequence list as a text field
            provision_role_sequence = cluster_data.pop("provision_role_sequence",
                                                       None)
            if provision_role_sequence is not None:
                cluster_data['provision_role_sequence'] = str(provision_role_sequence)
            # Store email list as text field
            email = cluster_data.pop("email", None)
            if email is not None:
                cluster_data['email'] = str(email)
            self._add_row(cluster_table, cluster_data)
        except Exception as e:
            raise e
    # End of add_cluster

    def add_inventory(self, fru_data):
        try:
            fru_data = dict(fru_data)
            if fru_data and 'id' in fru_data:
                self._add_row(inventory_table, fru_data)
                self._smgr_log.log(self._smgr_log.DEBUG, "ADDED FRU INFO FOR " + fru_data['id'])
        except Exception as e:
            return e.message
        return 0
    # End of add_inventory

    #hw_data must contain, uuid, dict of basic_hw, detail_hw
    def add_hw_data(self, hw_data):
        try:
             self._add_row(hw_data_table, hw_data)
             self._smgr_log.log(self._smgr_log.DEBUG, "ADD DETAILS" + hw_data['uuid'])

        except Exception as e:
            return e.message

    def add_dhcp_subnet(self, dhcp_subnet_config):
        try:
            dhcp_subnet_config = dict(dhcp_subnet_config)
            if dhcp_subnet_config and self.validate_dhcp_add("subnet", dhcp_subnet_config):
                dhcp_subnet_config = {k:str(v) for k,v in dhcp_subnet_config.iteritems()}
                self._add_row(dhcp_subnet_table, dhcp_subnet_config)
                self._smgr_log.log(self._smgr_log.DEBUG, "ADDED DHCP SUBNET CONFIG FOR SUBNET " + dhcp_subnet_config['subnet_address'])
        except Exception as e:
            return e.message
        return 0
    # End of add_dhcp_subnet

    def add_dhcp_host(self, dhcp_host_config):
        try:
            dhcp_host_config = dict(dhcp_host_config)
            if dhcp_host_config and self.validate_dhcp_add("host", dhcp_host_config):
                self._add_row(dhcp_hosts_table, dhcp_host_config)
                self._smgr_log.log(self._smgr_log.DEBUG, "ADDED DHCP HOST CONFIG FOR HOST FQDN " + dhcp_host_config['host_fqdn'])
        except Exception as e:
            return e.message
        return 0
    # End of add_dhcp_host

    def add_server(self, server_data):
        try:
            # covert all unicode strings in dict
            server_data = ServerMgrUtil.convert_unicode(server_data)
            if 'mac_address' in server_data and server_data['mac_address']:
                server_data['mac_address'] = str(
                    EUI(server_data['mac_address'])).replace("-", ":")


            host_name = server_data.pop('host_name', None)
            if host_name is None or host_name == "":
                host_name = server_data['id'].lower()

            if host_name:
                server_data['host_name'] = str(host_name).lower()

            msg = "ADD-SERVER: ID=> %s : %s:%s" %(server_data['id'],server_data['host_name'], host_name)
            self._smgr_log.log(self._smgr_log.ERROR, msg)

            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                self.check_obj(
                    "cluster", {"id" : cluster_id})
            if roles is not None:
                server_data['roles'] = str(roles)
            intf_control = server_data.pop("control_data_network", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_bond = server_data.pop("bond_interface", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)
            #Add network
            if 'network' in server_data:
                network = server_data.pop('network')
                network = DictUtils.remove_none_from_dict(network)
                if not network:
                    network = {}
                server_data['network'] = str(network)
            #Add top_of_rack configuration 
            if 'top_of_rack' in server_data:
                top_of_rack_data_str = str(server_data.pop("top_of_rack", None))
                server_data['top_of_rack'] = top_of_rack_data_str 
            #Add contrail
            if 'contrail' in server_data:
                contrail = server_data.pop('contrail')
                contrail = DictUtils.remove_none_from_dict(contrail)
                if not contrail:
                    contrail = {}
                server_data['contrail'] = str(contrail)
            # Store email list as text field
            email = server_data.pop("email", None)
            if email:
                server_data['email'] = str(email)
            # store tags if any
            server_tags = server_data.pop("tag", None)
            if server_tags is not None:
                tags_dict = self.get_server_tags(detail=True)
                rev_tags_dict = dict((v,k) for k,v in tags_dict.iteritems())
                for k,v in server_tags.iteritems():
                    server_data[rev_tags_dict[k]] = v
            # Store server_params dictionary as a text field
            if 'parameters' in server_data:
                server_parameters = server_data.pop('parameters')
                server_parameters = DictUtils.remove_none_from_dict(server_parameters)
                if not server_parameters:
                    server_parameters = {}
                server_data['parameters'] = str(server_parameters)
            self._add_row(server_table, server_data)
        except Exception as e:
            raise e
        return 0
    # End of add_server

    # This function for adding server tag is slightly different
    # compared with add function for other tables. The tag_data
    # contains tag information for all tags.
    # This function is always called with complete list of tags
    # so, clear the table first.
    def add_server_tags(self, tag_data):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.executescript("""
                DELETE FROM """ + server_tags_table + ";")
            for key,value in tag_data.iteritems():
                row_data = {
                    'tag_id' : key,
                    'value' : value }
                self._add_row(server_tags_table, row_data)
        except Exception as e:
            raise e
    # End of add_server_tags

    def server_discovery(self, action, entity):
        try:
            if 'mac_address' in entity:
                entity['mac_address'] = str(EUI(entity['mac_address'])).replace("-", ":")
            mac_address = entity.get("mac_address", None)
            if action.lower() == "add":
                # If this server is already present in our table,
                # update IP address if DHCP was not static.
                servers = self._get_items(
                    server_table, {"mac_address" : mac_address},detail=True)
                if servers:
                    server = servers[0]
                    self._modify_row(
                        server_table, entity,
                        {"mac_address": mac_address}, {})
                    return
                # Adding network and contrail blocks
                entity['parameters'] = "{}"
                entity['network'] = "{}"
                entity['contrail'] = "{}"
                entity['discovered'] = "true"
                entity['status'] = "server_discovered"
                self._add_row(server_table, entity)
            elif action.lower() == "delete":
                servers = self.get_server({"mac_address" : mac_address}, detail=True)
                if ((servers) and (servers[0]['discovered'] == "true")):
                    self._delete_row(server_table,
                                     {"mac_address" : mac_address})
            else:
                return
        except Exception as e:
            return
    # End of server_discovery

    def add_image(self, image_data):
        try:
            # covert all unicode strings in dict
            image_data = ServerMgrUtil.convert_unicode(image_data)
            # Store image_parameters dictionary as a text field
            image_parameters = image_data.pop("parameters", None)
            if image_parameters is not None:
                image_data['parameters'] = str(image_parameters)
            self._add_row(image_table, image_data)
        except Exception as e:
            raise e
    # End of add_image

    def delete_cluster(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("cluster", match_dict, unmatch_dict)
            cluster_id = match_dict.get("id", None)
            servers = None
            if cluster_id:
                servers = self.get_server({'cluster_id' : cluster_id}, detail=True)
            if servers:
                msg = ("Servers are present in this cluster, "
                        "remove cluster association, prior to cluster delete.")
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            self._delete_row(cluster_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_cluster

    def check_obj(self, type,
                  match_dict=None, unmatch_dict=None, raise_exception=True):
        if type == "server":
            cb = self.get_server
            db_obj = cb(match_dict, unmatch_dict, detail=False)
        elif type == "cluster":
            cb = self.get_cluster
            db_obj = cb(match_dict, unmatch_dict, detail=False)
        elif type == "image":
            cb = self.get_image
            db_obj = cb(match_dict, unmatch_dict, detail=False)
        elif type == "dhcp_subnet":
            cb = self.get_dhcp_subnet
            db_obj = cb(match_dict, unmatch_dict)
        elif type == "dhcp_host":
            cb = self.get_dhcp_host
            db_obj = cb(match_dict, unmatch_dict)
        elif type == "hw_data":
            cb = self.get_hw_data
            db_obj = cb(match_dict, unmatch_dict)

        if not db_obj:
            msg = "%s not found for match_dict %s" % (type,match_dict)
            if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            return False
        return True
    #end of check_obj

    def get_cidr(self, subnet_address, subnet_mask):
        ip = IPNetwork(str(subnet_address)+'/'+str(subnet_mask))
        return str(subnet_address) + "/" + str(ip.prefixlen)

    def validate_dhcp_add(self, obj_type, obj_dict, raise_exception=True):
        if not obj_dict:
            msg = "Valid dictionary not given to add DHCP element"
            if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            return False

        if obj_type == "subnet":
          try:
            if "subnet_address" not in obj_dict:
              msg = "Primary key subnet address not present for DHCP subnet, cannot add this object: %s" % (obj_dict)
              if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
              return False
            else:
              valid_subnet_address = IPAddress(obj_dict['subnet_address'])
              valid_subnet_gateway = IPAddress(obj_dict['subnet_gateway'])
              valid_subnet_range = IPNetwork(self.get_cidr(obj_dict["subnet_address"], obj_dict["subnet_mask"]))
          except Exception as e:
            self.log_and_raise_exception(e.message, ERR_OPR_ERROR)
            raise e
        elif obj_type == "host":
          if "host_fqdn" not in obj_dict:
            msg = "Primary key subnet address not present for DHCP host, cannot add this object: %s" % (obj_dict)
            if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            return False
          try:
            valid_ip_address = IPAddress(obj_dict['ip_address'])
          except Exception as e:
            self.log_and_raise_exception(e.message, ERR_OPR_ERROR)
            raise e
        return True
    #end of validate_dhcp_add

    def validate_dhcp_delete(self, obj_type, match_dict=None, unmatch_dict=None, raise_exception=True):
        if obj_type == "subnet":
            cb = self.get_dhcp_subnet
        elif obj_type == "host": 
            cb = self.get_dhcp_host
        db_obj = cb(match_dict, unmatch_dict)
        if not db_obj:
            msg = "Host or Subnet matching the parameters %s not found." %(match_dict)
            if raise_exception:
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            return False
        if obj_type == "subnet":
            subnet_obj = db_obj[0]
            # Get all servers to check if any are under this subnet
            servers = self.get_server(detail=True) 
            for server in servers:
                if IPAddress(server['ip_address']) in IPNetwork(self.get_cidr(subnet_obj["subnet_address"], subnet_obj["subnet_mask"])):
                    msg = "Server with ID %s is under the subnet %s being deleted. \
                        Please delete this server first" % (str(server['id']), str(subnet_obj["subnet_address"]))
                    if raise_exception:
                        self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                    return False
        elif obj_type == "host":
            host_obj = db_obj[0]
            # Get all servers to check if any are under this subnet
            servers = self.get_server(detail=True)
            for server in servers:
                if server['ip_address'] == str(host_obj['ip_address']):
                    msg = "Server with ID %s had been added with IP address of the DHCP node. \
                        Please delete the server first" % (str(server['id']))
                    if raise_exception:
                        self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                    return False
        return True
    #end of validate_dhcp_delete
 
    def delete_server(self, match_dict=None, unmatch_dict=None):
        try:
            if match_dict and match_dict.get("mac_address", None):
                if match_dict["mac_address"]:
                    match_dict["mac_address"] = str(
                        EUI(match_dict["mac_address"])).replace("-", ":")
            if unmatch_dict and unmatch_dict.get("mac_address", None):
                if unmatch_dict["mac_address"]:
                    unmatch_dict["mac_address"] = str(
                        EUI(unmatch_dict["mac_address"])).replace("-", ":")
            self.check_obj("server", match_dict, unmatch_dict)
            self._delete_row(server_table,
                             match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_server

    def delete_server_tag(self, match_dict=None, unmatch_dict=None):
        try:
            self._delete_row(server_tags_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_server_tag

    def delete_image(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("image", match_dict, unmatch_dict)
            self._delete_row(image_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_image

    def delete_dhcp_subnet(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("dhcp_subnet", match_dict, unmatch_dict)
            if self.validate_dhcp_delete("subnet", match_dict, unmatch_dict):
                self._delete_row(dhcp_subnet_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_dhcp_subnet

    def delete_dhcp_host(self, match_dict=None, unmatch_dict=None):
        try:
            self.check_obj("dhcp_host", match_dict, unmatch_dict)
            if self.validate_dhcp_delete("host", match_dict, unmatch_dict):
                self._delete_row(dhcp_hosts_table, match_dict, unmatch_dict)
        except Exception as e:
            raise e
    # End of delete_dhcp_host

    def modify_cluster(self, cluster_data):
        try:
            # covert all unicode strings in dict
            cluster_data = ServerMgrUtil.convert_unicode(cluster_data)
            cluster_id = cluster_data.get('id', None)
            if not cluster_id:
                raise Exception("No cluster id specified")
            self.check_obj("cluster", {"id" : cluster_id})
            db_cluster = self.get_cluster(
                {"id" : cluster_id}, detail=True)
            if not db_cluster:
                msg = "%s is not valid" % cluster_id
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)

            # Modify cluster parameters
            if 'parameters' in cluster_data:
                cluster_params = cluster_data.pop('parameters')
                if cluster_params is None:
                    db_cluster_params = {}
                else:
                    db_cluster_params = eval(db_cluster[0].get('parameters', '{}'))
                    db_cluster_params = DictUtils.merge_dict(db_cluster_params, cluster_params)
                    db_cluster_params = DictUtils.remove_none_from_dict(db_cluster_params)
                cluster_data['parameters'] = str(db_cluster_params)

            # Store email list as text field
            email = cluster_data.pop("email", None)
            if email is not None:
                cluster_data['email'] = str(email)
            
            provision_role_sequence = cluster_data.pop("provision_role_sequence",
                                                       None)
            if provision_role_sequence is not None:
                cluster_data['provision_role_sequence'] = str(provision_role_sequence)
            self._modify_row(
                cluster_table, cluster_data,
                {'id' : cluster_id}, {})
        except Exception as e:
            raise e
    # End of modify_cluster

    def modify_image(self, image_data):
        try:
            # covert all unicode strings in dict
            image_data = ServerMgrUtil.convert_unicode(image_data)
            image_id = image_data.get('id', None)
            if not image_id:
                raise Exception("No image id specified")
            #Reject if non mutable field changes
            db_image = self.get_image(
                {'id' : image_data['id']},
                detail=True)
            if image_data['path'] != db_image[0]['path']:
                msg = ('Image path cannnot be modified')
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            if image_data['type'] != db_image[0]['type']:
                msg = ('Image type cannnot be modified')
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            # Store image_params dictionary as a text field
            image_parameters = image_data.pop("parameters", None)
            if image_parameters is not None:
                image_data['parameters'] = str(image_parameters)
            self._modify_row(
                image_table, image_data,
                {'id' : image_id}, {})
        except Exception as e:
            raise e
    # End of modify_image

    def modify_server(self, server_data):
        # covert all unicode strings in dict
        server_data = ServerMgrUtil.convert_unicode(server_data)
        db_server = None
        if 'mac_address' in server_data.keys() and \
                 server_data['mac_address'] != None:
            db_server = self.get_server(
                {'mac_address' : server_data['mac_address']},
                detail=True)
        elif 'id' in server_data.keys() and server_data['id'] != None:
            db_server = self.get_server(
                {'id': server_data['id']},
                detail=True)

        if not db_server:
            return db_server
        try:
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                self.check_obj("cluster", {"id" : cluster_id})

            if 'mac_address' in server_data:
                server_data['mac_address'] = str(
                    EUI(server_data['mac_address'])).replace("-", ":")
            server_mac = server_data.get('mac_address', None)
            if not server_mac:
                server_id = server_data.get('id', None)
                if not server_id:
                    msg = ("No server MAC or id specified")
                    self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                else:
                    server_mac = self.get_server_mac(server_id)
            #Check if object exists
            if 'id' in server_data.keys() and \
                    'server_mac' in server_data.keys():
                self.check_obj('server',
                               {'id' : server_data['id']})
                #Reject if primary key values change
                if server_data['mac_address'] != db_server[0]['mac_address']:
                    msg = ('MAC address cannnot be modified', ERR_OPR_ERROR)
                    self.log_and_raise_exception(msg, ERR_OPR_ERROR)

            if 'host_name' in server_data:
                host_name = server_data.pop('host_name', None)
                if host_name is "":
                    ## admin is trying to delete the hostname, this is not
                    ## allowed, we copy the id to host_name
                    server_data['host_name'] = server_data['id'].lower()
                    msg = "MODIFY-SERVER: ID=> %s : %s" %(server_data['id'],server_data['host_name'])
                    self._smgr_log.log(self._smgr_log.ERROR, msg)
                elif host_name != "":
                    server_data['host_name'] = host_name.lower()

            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            if roles is not None:
                server_data['roles'] = str(roles)
            intf_control = server_data.pop("control_data_network", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_bond = server_data.pop("bond_interface", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)

            #Modify network
            if 'network' in server_data:
                network = server_data.pop('network')
                if network is None:
                    db_network = {}
                else:
                    db_network = eval(db_server[0].get('network', '{}'))
                    db_network = DictUtils.merge_dict(db_network, network)
                    db_network = DictUtils.remove_none_from_dict(db_network)
                server_data['network'] = str(db_network)

            #Modify contrail
            if 'contrail' in server_data:
                contrail = server_data.pop('contrail')
                if contrail is None:
                    db_contrail = {}
                else:
                    db_contrail = eval(db_server[0].get('contrail', '{}'))
                    db_contrail = DictUtils.merge_dict(db_contrail, contrail)
                    db_contrail = DictUtils.remove_none_from_dict(db_contrail)
                server_data['contrail'] = str(db_contrail)

            #Add top_of_rack
            if 'top_of_rack' in server_data:
                top_of_rack_data_str = str(server_data.pop("top_of_rack", None))
                server_data['top_of_rack'] = top_of_rack_data_str

            # store tags if any
            server_tags = server_data.pop("tag", None)
            if server_tags is not None:
                tags_dict = self.get_server_tags(detail=True)
                rev_tags_dict = dict((v,k) for k,v in tags_dict.iteritems())
                for k,v in server_tags.iteritems():
                    server_data[rev_tags_dict[k]] = v

            if "ssh_private_key" in server_data and "ssh_public_key" in server_data:
                private_key = str(server_data.pop("ssh_private_key", None))
                public_key = str(server_data.pop("ssh_public_key", None))
                server_data["ssh_private_key"] = private_key
                server_data["ssh_public_key"] = public_key

            # Store server_params dictionary as a text field
            if 'parameters' in server_data:
                server_params = server_data.pop('parameters')
                if server_params is None:
                    db_server_params = {}
                else:
                    db_server_params = eval(db_server[0].get('parameters', '{}'))
                    db_server_params = DictUtils.merge_dict(db_server_params, server_params)
                    db_server_params = DictUtils.remove_none_from_dict(db_server_params)
                server_data['parameters'] = str(db_server_params)

            # Store email list as text field                   
            email = server_data.pop("email", None)
            if email is not None:
                server_data['email'] = str(email)
            self._modify_row(
                server_table, server_data,
                {'mac_address' : server_mac}, {})
            return db_server
        except Exception as e:
            raise e
    # End of modify_server

    # This function for modifying server tag is slightly different
    # compared with modify function for other tables. The tag_data
    # contains tag information for all tags.
    def modify_server_tags(self, tag_data):
        try:
            for key,value in tag_data.iteritems():
                row_data = {
                    'tag_id' : key,
                    'value' : value }
                self._modify_row(
                    server_tags_table, row_data,
                    {'tag_id' : key}, {})
        except Exception as e:
            raise e
    # End of modify_server_tags

    def modify_dhcp_host(self,dhcp_host_config):
        try:
            db_dhcp_host = None
            dhcp_host_config = dict(dhcp_host_config)
            db_dhcp_host = self.get_dhcp_host({'host_fqdn': str(dhcp_host_config['host_fqdn'])})
            #Check if object exists
            if not db_dhcp_host:
                msg = ("No Host matching the modified FQDN specified")
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                return db_dhcp_host

            if 'mac_address' in dhcp_host_config:
                dhcp_host_config['mac_address'] = str(
                    EUI(dhcp_host_config['mac_address'])).replace("-", ":")
            host_mac = dhcp_host_config.get('mac_address', None)
            if host_mac:
                #Reject if primary key values change
                if dhcp_host_config['mac_address'] != db_dhcp_host[0]['mac_address']:
                    msg = ('MAC address cannnot be modified', ERR_OPR_ERROR)
                    self.log_and_raise_exception(msg, ERR_OPR_ERROR)
            for k in db_dhcp_host.keys():
                if k not in dhcp_host_config.keys():
                    dhcp_host_config[k] = db_dhcp_host[k]
 
            self._modify_row(
                dhcp_hosts_table, dhcp_host_config,
                {'mac_address' : db_dhcp_host[0]['mac_address']}, {})
            self._smgr_log.log(self._smgr_log.DEBUG, "MODIFIED DHCP HOST CONFIG FOR HOST FQDN " + dhcp_host_config['host_fqdn'])
        except Exception as e:
            return e.message
        return 0
    # End of modify_dhcp_host

    def modify_dhcp_subnet(self,dhcp_subnet_config):
        try:
            db_dhcp_subnet = None
            dhcp_host_config = dict(dhcp_subnet_config)
            db_dhcp_subnet = self.get_dhcp_subnet({'subnet_address': str(dhcp_subnet_config['subnet_address'])})
            #Check if object exists
            if not db_dhcp_subnet:
                msg = ("No Address matching the Subnet specified. Cannot modify.")
                self.log_and_raise_exception(msg, ERR_OPR_ERROR)
                return db_dhcp_subnet

            for k in db_dhcp_subnet.keys():
                if k not in dhcp_subnet_config.keys():
                    dhcp_subnet_config[k] = db_dhcp_subnet[k]
 
            self._modify_row(
                dhcp_subnet_table, dhcp_subnet_config,
                {'subnet_address' : db_dhcp_subnet[0]['subnet_address']}, {})
            self._smgr_log.log(self._smgr_log.DEBUG, "MODIFIED DHCP SUBNET CONFIG FOR SUBNET ADDRESS " + dhcp_subnet_config['subnet_addres'])
        except Exception as e:
            return e.message
        return 0
    # End of modify_dhcp_subnet

    #hw_data must contain, uuid, dict of basic_hw, detail_hw
    def modify_hw_data(self, hw_data):
        uuid=hw_data['uuid']
        try:
             if (self.check_obj("hw_data", {'uuid': uuid}, raise_exception=False)) :
                 self._smgr_log.log(self._smgr_log.DEBUG, "UUID exists")
                 self._modify_row(hw_data_table, hw_data, {'uuid': uuid}, {})
             else:
                 self._add_row(hw_data_table, hw_data)
                 self._smgr_log.log(self._smgr_log.DEBUG, "UUID doesn't exist")
               

        except Exception as e:
            return e.message

    def get_image(self, match_dict=None, unmatch_dict=None,
                  detail=False, field_list=None):
        try:
            if not field_list:
                field_list = ["id"]
            images = self._get_items(
                image_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return images
    # End of get_image

    def get_server_tags(self, match_dict=None, unmatch_dict=None,
                  detail=True):
        try:
            tag_dict = {}
            tags = self._get_items(
                server_tags_table, match_dict,
                unmatch_dict, True, ["tag_id"])
            for tag in tags:
                tag_dict[tag['tag_id']] = tag['value']
        except Exception as e:
            raise e
        return tag_dict
    # End of get_server_tags

    def get_status(self, match_key=None, match_value=None,
                  detail=False):
        try:
            status = self._get_items(
                server_status_table, {match_key : match_value},
                detail=detail, always_field=["id"])
        except Exception as e:
            raise e
        return status
    # End of get_status

    def put_status(self, server_data):
        try:
            server_id = server_data.get('id', None)
            if not server_id:
                raise Exception("No server id specified")
            # Store vns_params dictionary as a text field
            servers = self._get_items(
                server_status_table, {"id" : server_id},detail=True)
            if servers:
                self._modify_row(
                    server_status_table, server_data,
                    {'id' : server_id}, {})
            else:
                self._add_row(server_status_table, server_data)
        except Exception as e:
            raise e
    # End of put_status


    def get_server(self, match_dict=None, unmatch_dict=None,
                   detail=False, field_list=None):
        try:
            if match_dict and match_dict.get("mac_address", None):
                if match_dict["mac_address"]:
                    match_dict["mac_address"] = str(
                        EUI(match_dict["mac_address"])).replace("-", ":")
            # For server table, when detail is false, return server_id, mac
            # and ip.
            if not field_list:
                field_list = ["id", "mac_address", "ip_address"]
            servers = self._get_items(
                server_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return servers
    # End of get_server

    def get_dhcp_host(self, match_dict=None, unmatch_dict=None):
        try:
            hosts = self._get_items(dhcp_hosts_table, match_dict, unmatch_dict, True, None)
        except Exception as e:
            raise e
        return hosts 
    # End of get_dhcp_host
    
    def get_dhcp_subnet(self, match_dict=None, unmatch_dict=None):
        try:
            subnets = self._get_items(dhcp_subnet_table, match_dict, unmatch_dict, True, None)
        except Exception as e:
            raise e
        return subnets 
    # End of get_dhcp_subnet

    def get_hw_data(self, match_dict=None, unmatch_dict=None):
        try:
            hw_data = self._get_items(hw_data_table, match_dict, unmatch_dict, True, None)
        except Exception as e:
            raise e
        return hw_data
    # End of get_hw_data

    def get_inventory(self, match_dict=None, unmatch_dict=None):
        try:
            frus = self._get_items(inventory_table, match_dict, unmatch_dict, True, None)
        except Exception as e:
            raise e
        return frus
    # End of get_inventory

    def get_cluster(self, match_dict=None,
                unmatch_dict=None, detail=False, field_list=None):
        try:
            if not field_list:
                field_list = ["id"]
            cluster = self._get_items(
                cluster_table, match_dict,
                unmatch_dict, detail, field_list)
        except Exception as e:
            raise e
        return cluster
    # End of get_cluster

    # If any UUIDs are missing from an existing Cluster, we add them during ServerManager DB init
    def update_cluster_uuids(self, cluster):
        try:
            db_cluster_params_str = cluster['parameters']
            db_cluster_params = {}
            if db_cluster_params_str:
                db_cluster_params = eval(db_cluster_params_str)
            if 'uuid' not in db_cluster_params:
                str_uuid = str(uuid.uuid4())
                db_cluster_params.update({"uuid": str_uuid})
            if 'storage_fsid' not in db_cluster_params:
                storage_fsid = str(uuid.uuid4())
                db_cluster_params.update({"storage_fsid": storage_fsid})
            if 'storage_virsh_uuid' not in db_cluster_params:
                storage_virsh_uuid = str(uuid.uuid4())
                db_cluster_params.update({"storage_virsh_uuid": storage_virsh_uuid})
        except Exception as e:
            raise e

        cluster['parameters'] = str(db_cluster_params)
        self._modify_row(
            cluster_table, cluster,
            {'id' : cluster['id']}, {})
    # End of update_cluster_uuids

# End class ServerMgrDb

if __name__ == "__main__":
    pass

