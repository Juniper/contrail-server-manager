#!/usr/bin/python
import sys
import argparse
import shutil
import sqlite3 as lite

ERR_OPR_ERROR = 8
ERR_GENERAL_ERROR = 9

class ServerMgrException(Exception):
    def __init__(self, msg, ret_code = 0):
        self.msg = msg
        self.ret_code = ret_code

    def __str__(self):
        return repr(self.msg)


class ServerMgrUtil():
    def convert_unicode():
        def convert_unicode(input):
            if isinstance(input, dict):
                return {convert_unicode(key): convert_unicode(value) for key, value in input.iteritems()}
            elif isinstance(input, list):
                return [convert_unicode(element) for element in input]
            elif isinstance(input, unicode):
                return input.encode('utf-8')
            else:
                return input
        # end convert_unicode(input)
        return convert_unicode
    convert_unicode = staticmethod(convert_unicode())


def_smgr_db_file = './smgr_data.db'
cluster_table = 'cluster_table'

class ServerMgrDb:
    def __init__(self, db_file_name=def_smgr_db_file):
        try:
            self._con = lite.connect(db_file_name)
        except e:
            raise e

    def log_and_raise_exception(self, msg, err_code = ERR_OPR_ERROR):
         raise ServerMgrException(msg, err_code)

    def check_obj(self, type,
                  match_dict=None, unmatch_dict=None, raise_exception=True):
        return True

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
    # End _modify_row

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
                    for k,v in cluster_params.iteritems():
                        if v == '""':
                            v = ''
                        if v is None:
                            db_cluster_params.pop(k, None)
                        else:
                            db_cluster_params[k] = v
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
            #import pdb; pdb.set_trace()
        except Exception as e:
            #import pdb; pdb.set_trace()
            raise e
    # End of modify_cluster


class ConvertParams(object):
    @staticmethod
    def convert_key_value_to_dict_kv(key, value, key_dict):
        if not key:
            return key_dict
        cur_dict = key_dict
        dict_key_list = key.split(".")
        for x in dict_key_list:
            if x in cur_dict:
                previous_dict = cur_dict
                cur_dict = cur_dict[x]
                continue
            new_dict = {}
            cur_dict[x] = new_dict
            previous_dict = cur_dict
            cur_dict = new_dict
        previous_dict[x] = value
        return key_dict

    @staticmethod
    def get_value_from_long_key(key, from_dict, remove=True):
        if not key or not from_dict:
            return False, None
        dict_key_list = key.split(".")
        previous_dict = cur_dict = from_dict
        for x in dict_key_list:
            try:
                previous_dict = cur_dict
                cur_dict = cur_dict[x]
            except KeyError:
                return False, None
        previous_dict[x] =  None
        return True, cur_dict

    @staticmethod
    def convert_value(value, oldformat, newformat):
        if oldformat == newformat:
            return value
        try:
            if newformat == 'boolean' or newformat == 'bool':
                if value.lower() in ['true', '1', 'yes', 'enable']:
                     new_value = True
                elif value.lower() in ['false', '0', 'no', 'disable']:
                     new_value = False
                else:
                     raise ValueError 
            elif newformat == 'integer' or newformat == 'int':
                new_value = int(value)
            return new_value
        except ValueError:
            raise

    @staticmethod
    def convert_params_to_new_params(conversion_dict, old_params, new_params):
        if not old_params:
            return new_params
        for k, v in conversion_dict.items():
            try:
                ret, val = ConvertParams.get_value_from_long_key(k, old_params, remove=True)
            except KeyError:
                continue
            if ret:
                try:
                    val = ConvertParams.convert_value(val, conversion_dict[k]['oldformat'],
                                                      conversion_dict[k]['newformat'])
                    ConvertParams.convert_key_value_to_dict_kv(conversion_dict[k]['name'], 
                                                               val, new_params)
                except ValueError:
                    continue
        return True


class ServerMgrDbClusterParamsUpgrade:
    def __init__(self, conversion_dict, db_file_name=def_smgr_db_file):
        self._db_file_name = def_smgr_db_file
        self._conversion_dict = conversion_dict

    def convert_cluster_params_to_new_format(self):
        smgr_db = ServerMgrDb(self._db_file_name)
        match_dict = {}
        detail = False
        select_clause = ['id', ' parameters']
        clusters = smgr_db.get_cluster(match_dict, 
                                       detail=detail,
                                       field_list=select_clause)
        for cluster in clusters:
            if cluster.get('parameters', None) is not None:
                cluster['parameters'] = eval(cluster['parameters'])
                ConvertParams.convert_params_to_new_params(self._conversion_dict, 
                                                           cluster, cluster)
                smgr_db.modify_cluster(cluster)        
        return


def_smgr_db = './smgr_data.db'
class ParserArgs:
    @staticmethod
    def parser_args(args_str):
        parser = argparse.ArgumentParser(
            description='''ServerManager Cluster DB Upgrade'''
        )
        parser.add_argument("--src_db_file", "-s",
                            help="Source server manager db file",
                            default=def_smgr_db,
                            metavar="FILE")
        parser.add_argument("--dest_db_file", "-d",
                            help="Dest server manager db file",
                            default=def_smgr_db,
                            metavar="FILE")
        args = parser.parse_args(args_str)
        try:
            shutil.copyfile(args.src_db_file, args.dest_db_file)
        except (IOError, shutil.Error) as e:
            print e
        return args

if __name__ == '__main__':
    args = ParserArgs.parser_args(sys.argv[1:])
    conversion_dict = {
        'parameters.analytics_data_ttl': { 
            'name': 'parameters.provision.contrail.analytics.analytics_data_ttl', 
            'oldformat': 'string', 'newformat': 'integer'
        },
        'parameters.database_dir': { 
            'name': 'parameters.provision.contrail.database.database_dir', 
            'oldformat': 'string', 'newformat': 'string' 
        },
        'parameters.database_minimum_diskGB': { 
            'name': 'parameters.provision.contrail.database.database_minimum_diskGB', 
            'oldformat': 'string', 'newformat': 'integer'
        },
        'parameters.database_token': { 
            'name': 'parameters.provision.contrail.database.database_initial_token', 
            'oldformat': 'string', 'newformat': 'integer'
        },
        'parameters.external_bgp': { 
            'name': 'parameters.provision.contrail.control.external_bgp', 
            'oldformat': 'string', 'newformat': 'string'
        },
        'parameters.haproxy': { 
            'name': 'parameters.provision.contrail.ha.haproxy', 
            'oldformat': 'string', 'newformat': 'boolean' 
        },
        'parameters.keystone_password': { 
            'name': 'parameters.provision.openstack.keystone_admin_password', 
            'oldformat': 'string', 'newformat': 'string' 
        },
        'parameters.keystone_tenant': { 
            'name': 'parameters.provision.openstack.keystone_admin_tenant', 
            'oldformat': 'string', 'newformat': 'string' 
        },
        'parameters.keystone_username': { 
            'name': 'parameters.provision.openstack.keystone_admin_user', 
            'oldformat': 'string', 'newformat': 'string' 
        },
        'parameters.multi_tenancy': { 
            'name': 'parameters.provision.openstack.multi_tenancy', 
            'oldformat': 'string', 'newformat': 'boolean' 
        },
        'parameters.router_asn': { 
            'name': 'parameters.provision.contrail.control.router_asn', 
            'oldformat': 'string', 'newformat': 'integer'
        },
        'parameters.use_certificates': { 
            'name': 'parameters.provision.config.use_certs', 
            'oldformat': 'string', 'newformat': 'boolean' 
        }
    }

    upgrade_db = ServerMgrDbClusterParamsUpgrade(conversion_dict, 
                                                 db_file_name=args.dest_db_file)
    upgrade_db.convert_cluster_params_to_new_format()
    
    
