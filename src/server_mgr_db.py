#!/usr/bin/python

import sqlite3 as lite
import sys
import pdb
from netaddr import *

def_server_db_file = 'smgr_data.db'
pod_table = 'pod_table'
rack_table = 'rack_table'
cluster_table = 'cluster_table'
vns_table = 'vns_table'
cloud_table = 'cloud_table'
server_table = 'server_table'
image_table = 'image_table'
server_status_table = 'status_table'
_DUMMY_STR = "DUMMY_STR"


class ServerMgrDb:

    _pod_table_cols = []
    _rack_table_cols = []
    _cluster_table_cols = []
    _vns_table_cols = []
    _cloud_table_cols = []
    _server_table_cols = []
    _image_table_cols = []
    _status_table_cols = []

    # Keep list of table columns
    def _get_table_columns(self):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT * FROM " +
                               pod_table + " WHERE pod_id=?", (_DUMMY_STR,))
                self._pod_table_cols = [x[0] for x in cursor.description]
                cursor.execute("SELECT * FROM " +
                               rack_table + " WHERE rack_id=?", (_DUMMY_STR,))
                self._rack_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    cluster_table + " WHERE cluster_id=?", (_DUMMY_STR,))
                self._cluster_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    server_table + " WHERE server_id=?", (_DUMMY_STR,))
                self._server_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    image_table + " WHERE image_id=?", (_DUMMY_STR,))
                self._image_table_cols = [x[0] for x in cursor.description]
                cursor.execute("SELECT * FROM " +
                               vns_table + " WHERE vns_id=?", (_DUMMY_STR,))
                self._vns_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    cloud_table + " WHERE cloud_id=?", (_DUMMY_STR,))
                self._cloud_table_cols = [x[0] for x in cursor.description]
                cursor.execute(
                    "SELECT * FROM " +
                    server_status_table + " WHERE server_id=?", (_DUMMY_STR,))
                self._status_table_cols = [x[0] for x in cursor.description]
        except Exception as e:
            raise e
    # end _get_table_columns

    def __init__(self, db_file_name=def_server_db_file):
        try:
            self._con = lite.connect(db_file_name)
            with self._con:
                cursor = self._con.cursor()
                # Create pod table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + pod_table +
                               """ (pod_id TEXT PRIMARY KEY, rack_id TEXT)""")
                # Create rack table.
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + rack_table +
                    """ (rack_id TEXT PRIMARY KEY, cluster_id TEXT)""")
                # Create cluster table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + cluster_table +
                               """ (cluster_id TEXT PRIMARY KEY)""")
                # Create vns table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + vns_table +
                               """ (vns_id TEXT PRIMARY KEY,
                                    vns_params TEXT)""")
                # Create cloud table.
                cursor.execute("CREATE TABLE IF NOT EXISTS " + cloud_table +
                               """ (cloud_id TEXT PRIMARY KEY)""")
                # Create image table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               image_table + """ (image_id TEXT PRIMARY KEY,
                    image_version TEXT, image_type TEXT)""")
                # Create status table
                cursor.execute("CREATE TABLE IF NOT EXISTS " +
                               server_status_table + """ (server_id TEXT PRIMARY KEY,
			server_status TEXT)""")
                # Create server table
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS " + server_table +
                    """ (mac TEXT PRIMARY KEY NOT NULL,
                         server_id TEXT, static_ip varchar default 'N',
                         ip TEXT, mask TEXT, gway TEXT, domain TEXT,
                         pod_id TEXT, rack_id TEXT, cluster_id TEXT,
                         vns_id TEXT, cloud_id TEXT, base_image_id TEXT,
                         package_image_id TEXT, passwd TEXT,
                         update_time TEXT, disc_flag varchar default 'N',
                         server_params TEXT, roles TEXT, power_user TEXT,
                         power_pass TEXT, power_address TEXT,
                         power_type TEXT, UNIQUE (server_id))""")
            self._get_table_columns()
        except e:
            raise e
    # End of __init__

    def delete_tables(self):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.executescript("""
                .DELETE FROM """ + pod_table + """;
                .DELETE FROM """ + rack_table + """;
                .DELETE FROM """ + cluster_table + """;
                .DELETE FROM """ + vns_table + """;
                .DELETE FROM """ + cloud_table + """;
                .DELETE FROM """ + server_table + """;
		.DELETE FROM """ + server_status_table + """;
                .DELETE FROM """ + image_table + ";")
        except:
            raise e
    # End of delete_tables

    def get_server_id(self, server_mac):
        try:
            if server_mac:
                server_mac = str(EUI(server_mac)).replace("-", ":")
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT server_id FROM " +
                               server_table + " WHERE mac=?",
                              (server_mac,))
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    return None
        except:
            return None
    # end get_server_id

    def get_server_mac(self, server_id):
        try:
            with self._con:
                cursor = self._con.cursor()
                cursor.execute("SELECT mac FROM " +
                               server_table + " WHERE server_id=?",
                              (server_id,))
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

    def _delete_row(self, table_name, match_key, match_value):
        try:
            delete_str = "DELETE FROM %s WHERE %s='%s'" \
                % (table_name, match_key, match_value)
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(delete_str)
        except Exception as e:
            raise e
    # End _delete_row

    def _modify_row(self, table_name, dict, match_key, match_value):
        try:
            keys, values = zip(*dict.items())
            modify_str = "UPDATE %s SET " % (table_name)
            update_list = ",".join(key + "=?" for key in keys)
            modify_str += update_list
            modify_str += " WHERE %s=?" % (match_key)
            values = values + (match_value,)
            with self._con:
                cursor = self._con.cursor()
                cursor.execute(modify_str, values)
        except Exception as e:
            raise e

    def _get_items(self, table_name, match_key=None,
                   match_value=None, detail=False, primary_key=None):
        try:
            with self._con:
                cursor = self._con.cursor()
                if detail:
                    sel_cols = "*"
                else:
                    sel_cols = primary_key
                if ((not match_key) or (not match_value)):
                    select_str = "SELECT %s FROM %s" % (sel_cols, table_name)
                else:
                    select_str = "SELECT %s FROM %s WHERE %s=\'%s\'" \
                        % (sel_cols, table_name, match_key, match_value)
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
            self._add_row(cluster_table, cluster_data)
        except Exception as e:
            raise e
    # End of add_cluster

    def add_vns(self, vns_data):
        try:
            # Store vns_params dictionary as a text field
            vns_params = vns_data.pop("vns_params", None)
            if vns_params is not None:
                vns_data['vns_params'] = str(vns_params)
            self._add_row(vns_table, vns_data)
        except Exception as e:
            raise e
    # End of add_vns

    def add_server(self, server_data):
        try:
            if 'mac' in server_data:
                server_data['mac'] = str(
                    EUI(server_data['mac'])).replace("-", ":")
            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            if roles is not None:
                server_data['roles'] = str(roles)
            # Store server_params dictionary as a text field
            server_params = server_data.pop("server_params", None)
            if server_params is not None:
                server_data['server_params'] = str(server_params)
            self._add_row(server_table, server_data)
            # Create an entry for cluster, pod, rack etc if needed.
            pod_id = server_data.get('pod_id', None)
            if pod_id:
                pod_data = {"pod_id": pod_id}
                self._add_row(pod_table, pod_data)
            rack_id = server_data.get('rack_id', None)
            if rack_id:
                rack_data = {"rack_id": rack_id}
                self._add_row(rack_table, rack_data)
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                cluster_data = {"cluster_id": cluster_id}
                self._add_row(cluster_table, cluster_data)
            vns_id = server_data.get('vns_id', None)
            if vns_id:
                vns_data = {"vns_id": vns_id}
                self._add_row(vns_table, vns_data)
            cloud_id = server_data.get('cloud_id', None)
            if cloud_id:
                cloud_data = {"cloud_id": cloud_id}
                self._add_row(cloud_table, cloud_data)
        except Exception as e:
            raise e
        return 0
    # End of add_server

    def server_discovery(self, action, entity):
        try:
            if 'mac' in entity:
                entity['mac'] = str(EUI(entity['mac'])).replace("-", ":")
            mac = entity.get("mac", None)
            if action.lower() == "add":
                # If this server is already present in our table,
                # update IP address if DHCP was not static.
                servers = self._get_items(server_table, "mac", mac, True)
                if servers:
                    server = servers[0]
                    self._modify_row(server_table, entity, "mac", mac)
                    return
                entity['disc_flag'] = "Y"
                self._add_row(server_table, entity)
            elif action.lower() == "delete":
                servers = self.get_server("mac", mac, True)
                if ((servers) and (servers[0]['disc_flag'] == "Y")):
                    self._delete_row(server_table, "mac", mac)
            else:
                return
        except:
            return
    # End of server_discovery

    def add_image(self, image_data):
        try:
            self._add_row(image_table, image_data)
        except Exception as e:
            raise e
    # End of add_image

    def delete_cluster(self, cluster_id):
        try:
            self._delete_row(server_table, "cluster_id", cluster_id)
            self._delete_row(cluster_table, "cluster_id", cluster_id)
        except Exception as e:
            raise e
    # End of delete_cluster

    def delete_vns(self, vns_id):
        try:
            self._delete_row(server_table, "vns_id", vns_id)
            self._delete_row(vns_table, "vns_id", vns_id)
        except Exception as e:
            raise e
    # End of delete_vns

    def delete_server(self, match_key, match_value):
        try:
            if (match_key.lower() == "mac"):
                if match_value:
                    match_value = str(EUI(match_value)).replace("-", ":")
            self._delete_row(server_table, match_key, match_value)
        except Exception as e:
            raise e
    # End of delete_server

    def delete_image(self, image_id):
        try:
            self._delete_row(image_table, "image_id", image_id)
        except Exception as e:
            raise e
    # End of delete_image

    def modify_vns(self, vns_data):
        try:
            vns_id = vns_data.get('vns_id', None)
            if not vns_id:
                raise Exception("No vns id specified")
            # Store vns_params dictionary as a text field
            vns_params = vns_data.pop("vns_params", None)
            if vns_params is not None:
                vns_data['vns_params'] = str(vns_params)
            self._modify_row(vns_table, vns_data,
                             'vns_id', vns_id)
        except Exception as e:
            raise e
    # End of modify_vns

    def modify_image(self, image_data):
        try:
            image_id = image_data.get('image_id', None)
            if not image_id:
                raise Exception("No image id specified")
            # Store vns_params dictionary as a text field
            self._modify_row(image_table, image_data,
                             'image_id', image_id)
        except Exception as e:
            raise e
    # End of modify_image

    def modify_server(self, server_data):
        try:
            if 'mac' in server_data:
                server_data['mac'] = str(
                    EUI(server_data['mac'])).replace("-", ":")
            server_mac = server_data.get('mac', None)
            if not server_mac:
                server_id = server_data.get('server_id', None)
                if not server_id:
                    raise Exception("No server MAC or id specified")
                else:
                    server_mac = self.get_server_mac(server_id)
            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            if roles is not None:
                server_data['roles'] = str(roles)
            # Store server_params dictionary as a text field
            server_params = server_data.pop("server_params", None)
            if server_params is not None:
                server_data['server_params'] = str(server_params)
            self._modify_row(server_table, server_data,
                             'mac', server_mac)
            # Create an entry for cluster, pod, rack etc if needed.
            pod_id = server_data.get('pod_id', None)
            if pod_id:
                pod_data = {"pod_id": pod_id}
                self._add_row(pod_table, pod_data)
            rack_id = server_data.get('rack_id', None)
            if rack_id:
                rack_data = {"rack_id": rack_id}
                self._add_row(rack_table, rack_data)
            cluster_id = server_data.get('cluster_id', None)
            if cluster_id:
                cluster_data = {"cluster_id": cluster_id}
                self._add_row(cluster_table, cluster_data)
            vns_id = server_data.get('vns_id', None)
            if vns_id:
                vns_data = {"vns_id": vns_id}
                self._add_row(vns_table, vns_data)
            cloud_id = server_data.get('cloud_id', None)
            if cloud_id:
                cloud_data = {"cloud_id": cloud_id}
                self._add_row(cloud_table, cloud_data)
        except Exception as e:
            raise e
    # End of modify_server

    def get_image(self, match_key=None, match_value=None,
                  detail=False):
        try:
            images = self._get_items(image_table, match_key,
                                     match_value, detail, "image_id")
        except Exception as e:
            raise e
        return images
    # End of get_image



    def get_status(self, match_key=None, match_value=None,
                  detail=False):
        try:
            status = self._get_items(server_status_table, match_key,
                                     match_value, detail, "server_id")
        except Exception as e:
            raise e
        return status
    # End of get_status

    def put_status(self, server_data):
        try:
            server_id = server_data.get('server_id', None)
            if not server_id:
                raise Exception("No server id specified")
            # Store vns_params dictionary as a text field
            servers = self._get_items(server_status_table, "server_id", server_id, True)
            if servers:
                self._modify_row(server_status_table, server_data,
                             'server_id', server_id)
	    else:
		self._add_row(server_status_table, server_data)
        except Exception as e:
            raise e
    # End of put_status


    def get_server(self, match_key=None, match_value=None,
                   detail=False):
        try:
            if ((match_key) and (match_key.lower() == "mac")):
                if match_value:
                    match_value = str(EUI(match_value)).replace("-", ":")
            servers = self._get_items(server_table, match_key,
                                      match_value, detail, "server_id")
        except Exception as e:
            raise e
        return servers
    # End of get_server

    def get_cluster(self, cluster_id=None,
                    detail=False):
        try:
            clusters = self._get_items(cluster_table, "cluster_id",
                                       cluster_id, detail, "cluster_id")
        except Exception as e:
            raise e
        return clusters
    # End of get_cluster

    def get_vns(self, vns_id=None,
                    detail=False):
        try:
            vns = self._get_items(vns_table, "vns_id",
                                       vns_id, detail, "vns_id")
        except Exception as e:
            raise e
        return vns
    # End of get_vns

# End class ServerMgrDb

if __name__ == "__main__":
    pass
