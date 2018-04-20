#!/usr/bin/env python
'''
    This program reads a json file containing mapping of node name to
    environment to be used for the given node. It is used as an External
    node classifier by puppet master. To specify a particular environment
    to be used for a node, add an entry for the node name to environment
    name in the json file.
    The default json file used is /etc/contrail_smgr/puppet/node_mapping.json.
    If there is error in reading the node configuration file, or if
    given node is not found in the file, program returns null output.
    If node is found, "environment : env_name", where env_name is the
    environment corresponding to the node is output.
'''
import sys
import json
import argparse

_NODE_ENV_DICT_FILE = "/etc/contrail_smgr/puppet/node_mapping.json"

def main(args_str=None):
    # import pdb; pdb.set_trace()
    # Accept parameters
    parser = argparse.ArgumentParser(
        description = '''Program to classify a puppet node 
                         to fetch environment, given node name''')
    # Optional config file, to be used to run the program directly
    # for testing the logic, will not be used when puppet invokes this
    # code.
    parser.add_argument(
        "--node_env_map_file", "-c", default = _NODE_ENV_DICT_FILE,
        help = ("file containing node to environment mapping, default %s",
                _NODE_ENV_DICT_FILE))
    # Mandatoty paramater, node name for which environment is desired./
    parser.add_argument(
        "node_name",
        help = "Node name of server for which environment is to be fetched." )
    args = parser.parse_args(args_str)

    # Read the file and get mapping for node specified
    environement = None
    try:
        with open(args.node_env_map_file, "r") as env_file:
            node_env_dict = json.loads(env_file.read())
        environment = node_env_dict.get(args.node_name, None)
        if environment:
            print ("environment : %s" %environment)
    except:
        pass
# End of main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')

    main(sys.argv[1:])
# End if __name__
