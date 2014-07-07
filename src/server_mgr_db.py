#!/usr/bin/python

import sqlite3 as lite
import sys
import pdb
import uuid
from netaddr import *
from server_mgr_exception import ServerMgrException as ServerMgrException
from server_mgr_logger import ServerMgrlogger as ServerMgrlogger

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
            self._smgr_log = ServerMgrlogger()
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
                                    vns_params TEXT,
                                    email TEXT)""")
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
                         server_params TEXT,
                         roles TEXT, power_user TEXT,
                         power_pass TEXT, power_address TEXT,
                         power_type TEXT, intf_control TEXT,
                         intf_data TEXT, intf_bond TEXT,
                         email TEXT,
                         UNIQUE (server_id))""")
            self._get_table_columns()
            self._smgr_log.log(self._smgr_log.DEBUG, "Created tables")
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
            # Store email list as text field
            email = vns_data.pop("email", None)
            if email is not None:
                vns_data['email'] = str(email)
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
            intf_control = server_data.pop("control", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_data = server_data.pop("data", None)
            if intf_data:
                server_data['intf_data'] = str(intf_data)
            intf_bond = server_data.pop("bond", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)
            # Store email list as text field
            email = server_data.pop("email", None)
            if email:
                server_data['email'] = str(email)


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
            self.check_obj("cluster", "cluster_id", cluster_id)
            servers = self.get_server('cluster_id', cluster_id, True)
            for server in servers:
                server_data = {}
                server_data['cluster_id'] = ''
                self._modify_row(server_table, server_data, "server_id", server['server_id'])
            self._delete_row(cluster_table, "cluster_id", cluster_id)
        except Exception as e:
            raise e
    # End of delete_cluster

    def delete_vns(self, vns_id, force=False):
        try:
            self.check_obj("vns", "vns_id", vns_id)
            servers = self.get_server('vns_id', vns_id, True)
            if servers:
                if force:
                    for server in servers:
                        server_data = {}
                        server_data['vns_id'] = ''
                        self._modify_row(server_table, server_data, \
                                        "server_id", server['server_id'])
                else:
                    msg = ("Servers are present in this vns, "
                            "remove vns association, prior to vns delete.")
                    raise ServerMgrException(msg)
            self._delete_row(vns_table, "vns_id", vns_id)
        except Exception as e:
            raise e
    # End of delete_vns

    def check_obj(self, type, match_key, match_value, raise_exception=True):
        if type == "server":
            cb = self.get_server
            db_obj = cb(match_key, match_value, detail=False)
        elif type == "vns":
            cb = self.get_vns
            db_obj = cb(match_value, detail=False)
        elif type == "cluster":
            cb = self.get_cluster
            db_obj = cb(match_value, detail=False)
        elif type == "image":
            cb = self.get_image
            db_obj = cb(match_key, match_value, detail=False)

        if not db_obj:
            msg = "%s %s not found" % (type, match_value)
            if raise_exception:
                raise ServerMgrException(msg)
            return False
        return True
        #end of check_obj

    def delete_server(self, match_key, match_value):
        try:
            if (match_key.lower() == "mac"):
                if match_value:
                    match_value = str(EUI(match_value)).replace("-", ":")
            self.check_obj("server", match_key, match_value)
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
            self.check_obj("vns", "vns_id", vns_id)
            db_vns = self.get_vns(vns_id, detail=True)
            if not db_vns:
                msg = "%s is not valid" % vns_id
                raise ServerMgrException(msg)
            db_vns_params_str = db_vns[0] ['vns_params']
            db_vns_params = {}
            if db_vns_params_str:
                db_vns_params = eval(db_vns_params_str)
            if 'uuid' not in db_vns_params:
                str_uuid = str(uuid.uuid4())
                vns_data["vns_params"].update({"uuid":str_uuid})

            # Store vns_params dictionary as a text field
            vns_params = vns_data.pop("vns_params", {})
            for k,v in vns_params.iteritems():
                if v == '""':
                    v = ''
                db_vns_params[k] = v
            vns_params = db_vns_params
            if vns_params is not None:
                vns_data['vns_params'] = str(vns_params)

            # Store email list as text field
            email = vns_data.pop("email", None)
            if email is not None:
                vns_data['email'] = str(email)
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
            #Reject if non mutable field changes
            db_image = self.get_image('image_id', image_data['image_id'],
                                                    detail=True)
            #if image_data['image_path'] != db_image[0]['image_path']:
            #    raise ServerMgrException('Image path cannnot be modified')
            #TODO image path can be added in the db
            image_data.pop("image_path", None) 
            if image_data['image_type'] != db_image[0]['image_type']:
                raise ServerMgrException('Image type cannnot be modified')
            self._modify_row(image_table, image_data,
                             'image_id', image_id)
        except Exception as e:
            raise e
    # End of modify_image

    def modify_server(self, server_data):
        db_server = None
        if 'server_id' in server_data.keys():
            db_server = self.get_server('server_id', server_data['server_id'],
                                                    detail=True)
        elif 'mac' in server_data.keys():
            db_server = self.get_server('mac', server_data['mac'],
                                                    detail=True)
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
            #Check if object exists
            if 'server_id' in server_data.keys() and \
                    'server_mac' in server_data.keys():
                self.check_obj('server', 'server_id',
                                        server_data['server_id'])
                #Reject if primary key values change
                if server_data['mac'] != db_server[0]['mac']:
                    raise ServerMgrException('MAC address cannnot be modified')

            # Store roles list as a text field
            roles = server_data.pop("roles", None)
            if roles is not None:
                server_data['roles'] = str(roles)
            intf_control = server_data.pop("control", None)
            if intf_control:
                server_data['intf_control'] = str(intf_control)
            intf_data = server_data.pop("data", None)
            if intf_data:
                server_data['intf_data'] = str(intf_data)
            intf_bond = server_data.pop("bond", None)
            if intf_bond:
                server_data['intf_bond'] = str(intf_bond)

            # Store server_params dictionary as a text field
            server_params = server_data.pop("server_params", None)
            #if server_params is not None:
            #    server_data['server_params'] = str(server_params)
            #check for modify in db server_params
            #Always Update DB server parmas
            db_server_params = {}
            db_server_params_str = db_server[0] ['server_params']
            if db_server_params_str:
                db_server_params = eval(db_server_params_str)
                if server_params:
                    for k,v in server_params.iteritems():
                        if v == '""':
                            v = ''
                        db_server_params[k] = v
            server_data['server_params'] = str(db_server_params)

            # Store email list as text field                   
            email = server_data.pop("email", None)
            if email is not None:
                server_data['email'] = str(email)
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
