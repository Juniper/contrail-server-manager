#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_add.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   add server manager configuration objects.
   Objects can be cluster, server, or image.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import json
import readline
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import ConfigParser
import smgr_client_def

# Below array of dictionary's is used by add_payload
# function to add payload when user choses to input
# object parameter values manually instead of providing a
# json file.
object_dict = {
    "cluster" : OrderedDict ([
        ("id", "Specify unique id for this cluster"),
        ("email", "Email id for notifications"),
        ("cluster_parameters", OrderedDict ([
             ("router_asn", "Router asn value"),
             ("subnet_mask", "Subnet mask"),
             ("gateway", "Default gateway for servers in this cluster"),
             ("password", "Default password for servers in this cluster"),
             ("domain", "Default domain for servers in this cluster"),
             ("database_dir", "home directory for cassandra"),
             ("database_token", "initial database token"),
             ("openstack_mgmt_ip", "openstack management ip"),
             ("use_certificates", "whether to use certificates for auth (True/False)"),
             ("multi_tenancy", "Openstack multitenancy (True/False)"),
             ("service_token", "Service token for openstack access"),
             ("keystone_user", "Keystone user name"),
             ("keystone_password", "keystone password"),
             ("keystone_tenant", "keystone tenant name"),
             ("openstack_passwd", "open stack password"),
             ("analytics_data_ttl", "analytics data TTL"),
             ("osd_bootstrap_key", "OSD Bootstrap Key"),
             ("admin_key", "Admin Authentication Key"),
             ("storage_mon_secret", "Storage Monitor Secret Key")]))
    ]),
    "server": OrderedDict ([ 
        ("id", "server id value"),
        ("host_name", "host name of the server"),
        ("ip_address", "server ip address"),
        ("mac_address", "server mac address"),
        ("roles", "comma-separated list of roles for this server"),
        ("server_parameters", OrderedDict([
            ("interface_name", "Ethernet Interface name"),
            ("disks", "Storage OSDs (default none)")])),
        ("cluster_id", "cluster id the server belongs to"),
        ("subnet_mask", "subnet mask (default use value from vns table)"),
        ("gateway", "gateway (default use value from vns table)"),
        ("domain", "domain name (default use value from vns table)"),
        ("password", "root password (default use value from vns table)"),
        ("power_password", "Power password"),
        ("power_username", "Power user"),
        ("power_address", "Power Address"),
        ("email", "email id for notifications (default use value from server's cluster)"),
    ]),
    "image" : OrderedDict ([
        ("id", "Specify unique image id for this image"),
        ("version", "Specify version for this image"),
        ("type",
         "ubuntu/centos/contrail-ubuntu-package/contrail-centos-package/contrail-storage-ubuntu-package"),
        ("path", "complete path where image file is located on server")
    ]),
    "server_keys": "['id','mac_address']",
    "cluster_keys": "['id']",
    "image_keys": "['id']"
}

def parse_arguments(args_str=None):

    # Process the arguments
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(
            description='''Create a Server Manager object'''
        )
    else:
        parser = argparse.ArgumentParser(
            description='''Create a Server Manager object''',
            prog="server-manager add"
        )
    # end else
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--ip_port", "-i",
                        help=("ip addr & port of server manager "
                              "<ip-addr>[:<port>] format, default port "
                              " 9001"))
    group1.add_argument("--config_file", "-c",
                        help=("Server manager client config file "
                              " (default - %s)" %(
                              smgr_client_def._DEF_SMGR_CFG_FILE)))
    subparsers = parser.add_subparsers(title='objects',
                                       description='valid objects',
                                       help='help for objects',
                                       dest='object')

    # Subparser for server add
    parser_server = subparsers.add_parser(
        "server",help='Create server')
    parser_server.add_argument(
        "--file_name", "-f",
        help="json file containing server param values")

    # Subparser for cluster add
    parser_cluster = subparsers.add_parser(
        "cluster", help='Create cluster')
    parser_cluster.add_argument(
        "--file_name", "-f",
        help="json file containing cluster param values")

    # Subparser for image add
    parser_image = subparsers.add_parser(
        "image", help='Create image')
    parser_image.add_argument(
        "--file_name", "-f",
        help="json file containing image param values")

    args = parser.parse_args(args_str)
    return args
# end def parse_arguments

def send_REST_request(ip, port, object, payload, match_key=None,
                        match_value=None, detail=False, method="PUT"):
    try:
        args_str = ""
        response = StringIO()
        headers = ["Content-Type:application/json"]
        if method == "PUT":
            url = "http://%s:%s/%s" %(
                        ip, port, object)
        elif method == "GET":
            url = "http://%s:%s/%s" % (ip, port, object)
            if match_key:
                args_str += match_key + "=" + match_value
            if detail:
                args_str += "&detail"
            if args_str != '':
                url += "?" + args_str
        else:
            return None
        conn = pycurl.Curl()
        conn.setopt(pycurl.URL, url)
        conn.setopt(pycurl.HTTPHEADER, headers)
        if method == "PUT":
            conn.setopt(pycurl.POST, 1)
            conn.setopt(pycurl.POSTFIELDS, '%s'%json.dumps(payload))
            conn.setopt(pycurl.CUSTOMREQUEST, "PUT")
        elif method == "GET":
            conn.setopt(pycurl.HTTPGET, 1)

        conn.setopt(pycurl.WRITEFUNCTION, response.write)
        conn.perform()
        return response.getvalue()
    except:
        return None

def input_default(prompt, default):
    return raw_input("%s [%s]" %(prompt, default)) or default

def rlinput(prompt, prefill=''):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return raw_input(prompt)
    finally:
        readline.set_startup_hook()

def object_exists(object, object_id_key, object_id_value, payload):
    return_val = False
    #post a request for each object
    resp = send_REST_request(smgr_ip, smgr_port,
                             object, payload, object_id_key,
                             object_id_value, True, "GET" )
    if resp:
        json_str = resp.replace("null", "''")
        smgr_object_dict = eval(json_str)
        if len(smgr_object_dict[object]):
            return True

    return False
# end object_exists

def get_object_config_ini_entries(object, config):
    config_object_defaults = None
    try:
        config_object_defaults = config.items(object.upper())
        return config_object_defaults
    except ConfigParser.NoSectionError:
        return config_object_defaults
# end get_object_config_ini_entries

def get_default_object(object, config):
    default_object = {}
    config_object_defaults = get_object_config_ini_entries(object, config)
    if not config_object_defaults:
        return default_object
    default_object[object+"_parameters"] = {}
    for key, value in config_object_defaults:
        if key in object_dict[object]:
            default_object[key] = value
        elif key in object_dict[object][object+"_parameters"]:
            default_object[object+"_parameters"][key] = value
    return default_object
# end get_default_object

def merge_with_defaults(object, payload, config):
    if object not in payload or not payload[object]:
        return
    default_object = get_default_object(object, config)
    for i in range(len(payload[object])):
        obj = payload[object][i]
        obj_id = "id"
        if obj_id not in obj or not obj[obj_id]:
            continue
        if object_exists(object, "id", str(obj[obj_id]), {}):
            continue
        param_object = {}
        if object+"_parameters" in obj and object+"_parameters" in default_object:
            param_object = dict(default_object[object+"_parameters"].items() + obj[object+"_parameters"].items())
        elif object+"_parameters" in default_object:
            param_object = default_object[object+"_parameters"] 
        payload[object][i] = dict(default_object.items() + obj.items())
        if param_object:
            payload[object][i][object+"_parameters"] = param_object

# end merge_with_defaults


# Function to accept parameters from user and then build payload to be
# sent with REST API request for creating the object.
def add_payload(object, default_object):
    payload = {}
    objects = []
    while True:
        temp_dict = {}
        fields_dict = object_dict[object]
        obj_id = "id"
        msg = obj_id + ":"
        user_input = raw_input(msg)

        temp_dict[obj_id] = user_input
        if not user_input:
            print "Empty id is not valid"
            return None
        #post a request for each object
        resp = send_REST_request(smgr_ip, smgr_port,
                                        object, payload, obj_id,
                                        user_input, True, "GET" )
        json_str = resp.replace("null", "''")
        smgr_object_dict = eval(json_str)
        obj_keys = object+"_keys"
        non_mutable_fields = eval(object_dict[obj_keys])

        #If object is present, then we can let the user
        #pick the field to be modified
        #else its a new field and user has to go through each fields
        if len(smgr_object_dict[object]):
            obj = smgr_object_dict[object] [0]

            if obj[obj_id] != user_input:
                print "Server-manager doesn't return the object"
                return None
            
            #print "Display Fields"
            data = ''
            i = 0
            index_dict = {}
            #form the fields to be displayed with index
            for key in fields_dict:
                value = fields_dict[key]
                if (key != (object+"_parameters")):
                    index_dict[i] = key
                    if key in non_mutable_fields :
                        data += str(i)+ ". %s : %s *\n" % (key, obj[key])
                    elif key == "roles":
                        data += str(i)+ ". %s : %s \n" % (key,
                                                    ','.join(eval(obj[key])))
                    else:
                        data += str(i)+ ". %s : %s \n" % (key, obj[key])
                    i+=1
                else:
                    if obj.has_key(object+"_parameters") and obj[object+"_parameters"]:
                        smgr_params = eval(obj[object+"_parameters"])
                    else:
                        smgr_params = {}
                    for param in value:
                        data += str(i)+ ". %s : %s \n" % (param,
                                                smgr_params.get(param, ""))
                        index_dict[i] = param
                        i+=1
            #display them
            print data
            params_dict = {}
            #Prompt if users wants to modify a field in
            # the existing object or continue
            # adding a new object
            while True:
                user_selection = raw_input("Enter Field index to Modify, C to"
                                           " continue with next Object :")
                if user_selection.strip() == 'C':
                    #print 'send output'
                    temp_dict[object+"_parameters"] = params_dict
                    break

                else:
                    try:
                        user_int = int(user_selection.strip())
                        if user_int > len(index_dict):
                            print "Invalid Input"
                            continue
                    except ValueError:
                        print "Invalid Input"
                        continue
     
                    key_selected = index_dict[eval(user_selection)]
                    object_params = object_dict[object] [object+"_parameters"]
                    if key_selected in object_params.keys():
                        msg = key_selected + ":"
                        value = smgr_params.get(key_selected,"")
                        if key_selected != 'disks':
                            user_input = rlinput(msg, default_value)
                        elif key_selected == 'disks' and 'storage' in object_dict["roles"]:
                            disks = raw_input(msg)
                            if disks:
                                disk_list = disks.split(',')
                                user_input = [str(d) for d in disk_list]
                            else:
                                user_input = None
                        params_dict[key_selected] = user_input
                    elif key_selected == "roles":
                        msg = index_dict[eval(user_selection)] + ":"
                        user_input = rlinput(msg,
                                ','.join(eval(obj[index_dict[eval(user_selection)]])))
                        temp_dict[key_selected] = user_input.replace(' ','').split(",")
                    else:
                        msg = index_dict[eval(user_selection)] + ":"
                        user_input = rlinput(msg, obj[index_dict[eval(user_selection)]])
                        temp_dict[key_selected] = user_input
        #Add a new object
        else:
            obj_id = "id"
            for key in fields_dict:
                if key == obj_id:
                    continue
                value = fields_dict[key]
                #non server parameters
                if (key != (object+"_parameters")):
                    msg = key
                    if value:
                        msg += " (%s) " %(value)
                    msg += ": "
                    default_value = default_object.get(key, "")
                    #user_input = raw_input(msg)
                    user_input = rlinput(msg, default_value) 
                    if user_input:
                        # Special case for roles -
                        # store as a list
                        if key == "roles":
                            #add rlinput at user_input for populating with
                            #defaults
                            temp_dict[key] = user_input.replace(' ','').split(",")
                        else:
                            temp_dict[key] = user_input
                #normal fields
                else:
                    param_dict = {}
                    for param in value:
                        pvalue = value[param]
                        msg = param
                        if pvalue:
                            msg += " (%s) " %(pvalue)
                        msg += ": "
                        #user_input = raw_input(msg)
                        if default_object.has_key(object+"_parameters"):
                            default_value = default_object[object+"_parameters"].get(param, "")
                        else:
                            default_value = ""
                        user_input = ""
                        if param == 'disks' and 'storage' in temp_dict["roles"]:
                            disks = raw_input(msg)
                            if disks:
                                disk_list = disks.split(',')
                                user_input = [str(d) for d in disk_list]
                            else:
                                user_input = None
                        else:
                            user_input = raw_input(msg)
                        if user_input:
                            param_dict[param] = user_input
                    temp_dict[key] = param_dict
                # End if (key != (object+"_parameters"))
            # End for key, value in fields_dict 
        objects.append(temp_dict)
        choice = raw_input("More %s(s) to input? (y/N)" %(object))
        if ((not choice) or
            (choice.lower() != "y")):
            break;
    # End while True
    payload[object] = objects
    return payload
# End add_payload
smgr_ip = None
smgr_port = None

def add_config(args_str=None):
    args = parse_arguments(args_str)
    global smgr_ip
    global smgr_port

    if args.ip_port:
        smgr_ip, smgr_port = args.ip_port.split(":")
        if not smgr_port:
            smgr_port = smgr_client_def._DEF_SMGR_PORT
    else:
        if args.config_file:
            config_file = args.config_file
        else:
            config_file = smgr_client_def._DEF_SMGR_CFG_FILE
        # end args.config_file
        try:
            config = ConfigParser.SafeConfigParser()
            config.read([config_file])
            smgr_config = dict(config.items("SERVER-MANAGER"))
            smgr_ip = smgr_config.get("listen_ip_addr", None)
            if not smgr_ip:
                sys.exit(("listen_ip_addr missing in config file"
                          "%s" %config_file))
            smgr_port = smgr_config.get("listen_port", smgr_client_def._DEF_SMGR_PORT)
        except:
            sys.exit("Error reading config file %s" %config_file)
        # end except
    # end else args.ip_port
    object = args.object
    try:
        if args.file_name:
            payload = json.load(open(args.file_name))
            merge_with_defaults(object, payload, config)
        else:
            # Accept parameters and construct json.
            default_object = get_default_object(object, config)
            payload = add_payload(object, default_object)
    except ValueError as e:
        print "Error in JSON Format : %s" % e
        sys.exit(1)
    if payload:
        resp = send_REST_request(smgr_ip, smgr_port,
                                 object, payload)
        smgr_client_def.print_rest_response(resp)

# End of add_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    add_config(sys.argv[1:])
# End if __name__
