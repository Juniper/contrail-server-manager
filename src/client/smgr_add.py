#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_add.py
   Author : Abhay Joshi
   Description : This program is a simple cli interface to
   add server manager configuration objects.
   Objects can be vns, cluster, server, or image.
"""
import argparse
import pdb
import sys
import pycurl
from StringIO import StringIO
import json
import readline
from collections import OrderedDict
import ConfigParser
import smgr_client_def

# Below array of dictionary's is used by add_payload
# function to add payload when user choses to input
# object parameter values manually instead of providing a
# json file.
object_dict = {
    "vns" : OrderedDict ([
        ("vns_id", "Specify unique vns_id for this vns cluster"),
        ("email", "Email id for notifications"),
        ("vns_params", OrderedDict ([
             ("router_asn", "Router asn value"),
             ("mask", "Subnet mask"),
             ("gway", "Default gateway for servers in this cluster"),
             ("passwd", "Default password for servers in this cluster"),
             ("domain", "Default domain for servers in this cluster"),
             ("database_dir", "home directory for cassandra"),
             ("db_initial_token", "initial database token"),
             ("openstack_mgmt_ip", "openstack management ip"),
             ("use_certs", "whether to use certificates for auth (True/False)"),
             ("multi_tenancy", "Openstack multitenancy (True/False)"),
             ("service_token", "Service token for openstack access"),
             ("ks_user", "Keystone user name"),
             ("ks_passwd", "keystone password"),
             ("ks_tenant", "keystone tenant name"),
             ("openstack_passwd", "open stack password"),
             ("analytics_data_ttl", "analytics data TTL")]))
    ]),
    "server": OrderedDict ([ 
        ("server_id", "server id value"),
        ("ip", "server ip address"),
        ("mac", "server mac address"),
        ("roles", "comma-separated list of roles for this server"),
        ("server_params", OrderedDict([
            ("ifname", "Ethernet Interface name"),
            ("compute_non_mgmt_ip", "compute node non mgmt ip (default none)"),
            ("compute_non_mgmt_gway", "compute node non mgmt gway (default none)")])),
        ("vns_id", "vns id the server belongs to"),
        ("cluster_id", "Physical cluster id the server belongs to"),
        ("pod_id", "pod id the server belongs to"),
        ("rack_id", "rack id the server belongs to"),
        ("cloud_id", "cloud id the server belongs to"),
        ("mask", "subnet mask (default use value from vns table)"),
        ("gway", "gateway (default use value from vns table)"),
        ("domain", "domain name (default use value from vns table)"),
        ("passwd", "root password (default use value from vns table)"),
        ("power_pass", "IPMI password"),
        ("power_user", "IPMI user"),
        ("power_address", "IPMI Address"),
        ("email", "email id for notifications (default use value from vns table)"),
    ]),
    "image" : OrderedDict ([
        ("image_id", "Specify unique image id for this image"),
        ("image_version", "Specify version for this image"),
        ("image_type",
         "ubuntu/centos/contrail-ubuntu-package/contrail-centos-package"),
        ("image_path", "complete path where image file is located on server")
    ]),
    "cluster" : OrderedDict ([
        ("cluster_id", "Specify unique cluster_id for this cluster"),
    ]),
    "server_keys": "['server_id','mac']",
    "vns_keys": "['vns_id']",
    "cluster_keys": "['cluster_id']",
    "image_keys": "['image_id']"
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

    # Subparser for vns add
    parser_vns = subparsers.add_parser(
        "vns", help='Create vns')
    parser_vns.add_argument(
        "--file_name", "-f",
        help="json file containing vns param values")

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

# Function to accept parameters from user and then build payload to be
# sent with REST API request for creating the object.
def add_payload(object):
    payload = {}
    objects = []
    while True:
        temp_dict = {}
        fields_dict = object_dict[object]
        obj_id = object+"_id"
        msg = obj_id + ":"
        user_input = raw_input(msg)

        temp_dict[obj_id] = user_input 
        #post a request for each object
        resp = send_REST_request(smgr_ip, smgr_port,
                                        object, payload, obj_id,
                                        user_input, True, "GET" )
#        pdb.set_trace()
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
                if (key != (object+"_params")):
                    index_dict[i] = key
                    if key in non_mutable_fields :
                        data += str(i)+ ". %s : %s *\n" % (key, obj[key])
                    else: 
                        data += str(i)+ ". %s : %s \n" % (key, obj[key])
                    i+=1
                else:
#                    pdb.set_trace()
                    smgr_params = eval(obj[object+"_params"])
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
                    temp_dict[object+"_params"] = params_dict
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
     
#                    pdb.set_trace()
                    key_selected = index_dict[eval(user_selection)]
                    object_params = object_dict[object] [object+"_params"]
                    if key_selected in object_params.keys():
                        msg = key_selected + ":"
                        value = smgr_params.get(key_selected,"")
                        user_input = rlinput(msg, value)
                        params_dict[key_selected] = user_input

                    else:
                        msg = index_dict[eval(user_selection)] + ":"
                        user_input = rlinput(msg, obj[index_dict[eval(user_selection)]])
                        temp_dict[key_selected] = user_input
       #Add a new object                     
        else:
            obj_id = object+"_id"
            for key in fields_dict:
                if key == obj_id:
                    continue
                value = fields_dict[key]
                #non server params
                if (key != (object+"_params")):
                    msg = key
                    if value:
                        msg += " (%s) " %(value)
                    msg += ": "
                    user_input = raw_input(msg)
                    if user_input:
                        # Special case for roles -
                        # store as a list
                        if key == "roles":
                            #add rlinput at user_input for populating with
                            #defaults
                            temp_dict[key] = user_input.strip().split(",")
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
                        user_input = raw_input(msg)
                        if user_input:
                            param_dict[param] = user_input
                    temp_dict[key] = param_dict
                # End if (key != (object+"_params"))
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
        else:
            # Accept parameters and construct json.
            payload = add_payload(object)
    except ValueError as e:
        print "Error in JSON Format : %s" % e
        sys.exit(1)
    resp = send_REST_request(smgr_ip, smgr_port,
                      object, payload)
    print resp
# End of add_config

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    add_config(sys.argv[1:])
# End if __name__
