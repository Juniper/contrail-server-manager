#!/usr/bin/python

# vim: tabstop=4 shiftwidth=4 softtabstop=4
"""
   Name : smgr_client.py
   Author : Abhay Joshi
   Description : Wrapper smgr client program that calls other functions, based
                 on user input.
"""
import os
import subprocess
import argparse
import pdb
import tempfile
import json
import sys
import ConfigParser
import get_config
import add_config
import delete_config
import upload_image
import modify_server
import upgrade_server
import provision_server
import restart_server

_DEF_SMGR_CFG_FILE = './smgr.ini'
_DEF_SMGR_IP_ADDR = '127.0.0.1'
_DEF_SMGR_PORT = 9001

call_table = {
    "1": get_config.get_config,
    "2": delete_config.delete_config,
    "3": add_config.add_config,
    "4": modify_server.modify_server,
    "5": upload_image.upload_image,
    "6": upgrade_server.upgrade_server,
    "7": provision_server.provision_server,
    "8": restart_server.restart_server,
}


def parse_arguments(args_str=None):
    if not args_str:
        args_str = sys.argv[1:]
    conf_parser = argparse.ArgumentParser(add_help=False)
    conf_parser.add_argument("-c", "--config_file",
                             help=("Specify config file "
                                   " with the parameter values."),
                             metavar="FILE")
    cargs, remaining_args = conf_parser.parse_known_args(args_str)
    serverMgrCfg = {
        'smgr_ip_addr': _DEF_SMGR_IP_ADDR,
        'smgr_port': _DEF_SMGR_PORT
    }

    if cargs.config_file:
        config_file = cargs.config_file
    else:
        config_file = _DEF_SMGR_CFG_FILE

    config = ConfigParser.SafeConfigParser()
    config.read([config_file])
    for key in serverMgrCfg.keys():
        serverMgrCfg[key] = dict(config.items("SERVER-MANAGER"))[key]
    # Now Process rest of the arguments
    parser = argparse.ArgumentParser(
        description=''' Add a cluster to server manager DB. ''',
    )
    parser.set_defaults(**serverMgrCfg)
    parser.add_argument("--smgr_ip_addr",
                        help="IP address of the server manager.")
    parser.add_argument("--smgr_port",
                        help=("Port number on which the server"
                              " manager is serving REST requests."))
    args = parser.parse_args(remaining_args)
    return args


def get_user_input():
    while True:
        prompt = \
            """
************* Please select one of the options below : ***************
1 : Get config         2. Delete config         3. Add config
4 : Modify server      5. Upload image          6. Upgrade server (reimage)
7 : Provision Server   8 : Restart server
q : Exit the program \n"""
        os.system("clear")
        choice = raw_input(prompt)
        args_list = []
        args_list.append(choice)
        if choice == "1":
            element = raw_input(
                ("config element"
                 " (all/cluster/server/image/role) : "))
            if (element.lower() not in
               ("all", "cluster", "server", "image", "role")):
                raw_input("Invalid config element")
                continue
            args_list.append(element)
            match_key = raw_input(
                "match key name for element (<Enter> for all) : ")
            if match_key:
                match_value = raw_input("match key value : ")
                args_list.append("--match_key")
                args_list.append(match_key)
                args_list.append("--match_value")
                args_list.append(match_value)
            detail = raw_input(" details? (y/n) : ")
            if detail.lower() == "y":
                args_list.append("--detail")
        elif choice == "2":
            element = raw_input(
                ("config element"
                 " (cluster/server/image/role) : "))
            if (element.lower() not in
               ("cluster", "server", "image", "role")):
                raw_input("Invalid config element")
                continue
            args_list.append(element)
            match_key = raw_input("match key name for element : ")
            if not match_key:
                raw_input("no match key specified")
                continue
            args_list.append(match_key)
            match_value = raw_input("match key value : ")
            if not match_value:
                raw_input("no match value specified")
                continue
            args_list.append(match_value)
        elif choice == "3":
            element = raw_input(
                ("config element"
                 " (cluster/server/image/role) : "))
            if (element.lower() not in
               ("cluster", "server", "image", "role")):
                raw_input("Invalid config element")
                continue
            args_list.append(element)
            file_name = raw_input("JSON file (<Enter> to input manually) : ")
            if file_name:
                args_list.append("-f")
                args_list.append(file_name)
        elif choice == "4":
            file_name = raw_input("JSON file (<Enter> to input manually) : ")
            if file_name:
                args_list.append("-f")
                args_list.append(file_name)
        elif choice == "5":
            image_id = raw_input("Image id : ")
            args_list.append(image_id)
            image_version = raw_input("Image version : ")
            args_list.append(image_version)
            image_type = raw_input((
                "Image type "
                "(fedora/centos/ubuntu/contrail-ubuntu-repo) : "))
            args_list.append(image_type)
            file_name = raw_input("complete file path : ")
            args_list.append(file_name)
        elif choice == "6":
            match_key = raw_input("match key name for element : ")
            if not match_key:
                raw_input("no match key specified")
                continue
            args_list.append(match_key)
            match_value = raw_input("match key value : ")
            if not match_value:
                raw_input("no match value specified")
                continue
            args_list.append(match_value)
            base_image_id = raw_input("Base Image id : ")
            if not base_image_id:
                raw_input("no base image id specified")
                continue
            args_list.append(base_image_id)
            repo_image_id = raw_input("Repo Image id : ")
            if not repo_image_id:
                repo_image_id = ''
            args_list.append(repo_image_id)
        elif choice == "7":
            match_key = raw_input("match key name for element : ")
            if not match_key:
                raw_input("no match key specified")
                continue
            args_list.append(match_key)
            match_value = raw_input("match key value : ")
            if not match_value:
                raw_input("no match value specified")
                continue
            args_list.append(match_value)
        elif choice == "8":
            match_key = raw_input("match key name for element : ")
            if not match_key:
                raw_input("no match key specified")
                continue
            args_list.append(match_key)
            match_value = raw_input("match key value : ")
            if not match_value:
                raw_input("no match value specified")
                continue
            args_list.append(match_value)
            net_boot = raw_input(
                "enable net boot for servers being restarted? (y/N)")
            if (net_boot):
                args_list.append("--net_boot")
                args_list.append(net_boot)
        elif choice == "q":
            pass
        else:
            raw_input("Invalid choice !!! Press <Enter> to continue.")
            continue
        return args_list
    # End of get_user_input


def smgr_client(args_str=None):
    args = parse_arguments(args_str)
    while True:
        new_args = get_user_input()
        choice = new_args[0]
        if choice.lower() == "q":
            exit()
        args_list = sys.argv[1:]
        args_list.extend(new_args[1:])
        call_table[choice](args_list)
        x = raw_input("======= Enter to Continue =======")
# End of smgr_client

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    smgr_client(sys.argv[1:])
# End if __name__
