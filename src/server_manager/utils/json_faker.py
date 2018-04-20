#! /usr/bin/python
import sys
import json
import optparse
import os
from jsonschema import validate, RefResolver,FormatChecker, exceptions

key_translations = {
   "agent_config" : "AGENT",
   "schema_config" : "SCHEMA",
   "alarm_gen_config" : "ALARM_GEN",
   "device_manager_config" : "DEVICE_MANAGER",
   "analytics_api_config" : "ANALYTICS_API",
   "topology_config" : "TOPOLOGY",
   "snmp_collector_config" : "SNMP_COLLECTOR",
   "query_engine_config" : "QUERY_ENGINE",
   "cassandra_config" : "CASSANDRA",
   "keystone_config" : "KEYSTONE",
   "global_config" : "GLOBAL",
   "svc_monitor_config" : "SVC_MONITOR",
   "hypervisor_config" : "HYPERVISOR",
   "control_config" : "CONTROL",
   "analytics_collector_config" : "ANALYTICS_COLLECTOR",
   "rabbitmq_config" : "RABBITMQ",
   "webui_config" : "WEBUI",
   "dns_config" : "DNS",
   "controller_config" : "CONTROLLER",
   "api_config" : "API"
}

def load_schema(schema_file):
    data = None
    with open(schema_file) as dat_file:
        data = json.load(dat_file)
    return data

def handle_type(schema, final_json, last_key):
    if 'default' in schema.keys():
        final_json[last_key] = schema['default']
    elif schema['type'] == 'string':
        if 'enum' in schema.keys():
            final_json[last_key] = schema['enum'][0]
        else:
            final_json[last_key] = ""
    elif schema['type'] == 'object':
        final_json[last_key] = {}
    elif schema['type'] == 'boolean':
        final_json[last_key] = False
    elif schema['type'] == 'array':
        final_json[last_key] = []

# handle ref by calling generate_data with appropriate dict loaded from
# section of the $ref file
def handle_ref(defs, schema, final_json, last_key):
    ref_str = schema["$ref"].split("/")[-1]
    generate_data(defs, defs["definitions"][ref_str], final_json, last_key)

#generate the JSON data from JSON-schema files
def generate_data(defs, schema, final_json, last_key=None):
    if "properties" not in schema.keys():
        if 'type' in schema.keys() and not isinstance(schema['type'], dict):
            handle_type(schema, final_json, last_key)
        elif "$ref" in schema.keys():
            handle_ref(defs, schema, final_json, last_key)
        else:
            if last_key==None:
                for k,v in schema.iteritems():
                    if k.isupper():
                        k = k.lower() + "_config"
                    final_json[k] = dict()
                    generate_data(defs, v, final_json[k], k)
            else:
                for k,v in schema.iteritems():
                    generate_data(defs, v, final_json, k)
    elif last_key:
        for k,v in schema.iteritems():
            generate_data(defs, schema['properties'], final_json, k)
    elif last_key == None:
        for k,v in schema.iteritems():
            if k.isupper():
                k = k.lower() + "_config"
            final_json[k] = dict()
            generate_data(defs, schema['properties'], final_json[k], k)

#JSON file gets created from JSON-schema files
def created_JSON(options,final_json):
    for inputOP in options.schemafiles:
        if "definitions.json" in inputOP:
            defs = load_schema(inputOP)

    for inputOP in options.schemafiles:
        if "definitions.json" not in inputOP:
            data = load_schema(inputOP)
            if 'properties' in data.keys():
                generate_data(defs, data['properties'], final_json['contrail_4'])

    with open(options.output, 'w') as outfile:
        json.dump(final_json, outfile, indent = 2)

#Combining various Schema-files into one if there are more than one JSON-schema file to be be validated
def combine_dictionaries(dict1, dict2):
    final_output = {}
    for item, value in dict1.iteritems():
        if dict2.has_key(item):
            if isinstance(dict2[item], dict):
                final_output[item] = combine_dictionaries(value, dict2.pop(item))
        else:
            final_output[item] = value
    for item, value in dict2.iteritems():
         final_output[item] = value
    return final_output

#Validate JSON against JSON-schema
def validate_JSON(data,combined_schema):
    for keys in combined_schema['properties']:
        if "$ref" in (combined_schema['properties'])[keys]:
            refUrl= ((combined_schema['properties'])[keys])['$ref']
            references_file, section = refUrl.split('#')

    if not os.path.isfile(references_file):
        print "References file does not exists"
        sys.exit()

    schema_dir = os.path.dirname(os.path.realpath(references_file))
    resolver = RefResolver("file://{}/".format(schema_dir), None)

    try:
        validate(data,combined_schema,format_checker=FormatChecker(), resolver=resolver)
        print "JSON is valid with the schema"
        return True
    except exceptions.ValidationError as error:
        print(error.message)
        return False

#Merging schemas and putting key translations
def pre_validation(options, fschema_json):
    for inputOP in options.schemafiles:
        if "definitions.json" not in inputOP:
            with open(inputOP, "r") as infile:
                fschema_json = combine_dictionaries(fschema_json, json.load(infile))

    merged_schema = json.dumps(fschema_json, indent = 2)
    s = open(options.dataJSON,'r').read()

    for key in key_translations:
        s = s.replace(key, key_translations[key])
    dict_to_validate = json.loads(s)

    if 'contrail_4' in dict_to_validate.keys():
        dict_to_validate = dict_to_validate['contrail_4']

    schema_dict =(json.loads(merged_schema))
    validate_JSON(dict_to_validate, schema_dict)

def main():
    final_json = {}
    fschema_json = {}
    defs = {}
    final_json['contrail_4'] = {}

    OptionParser = optparse.OptionParser()
    OptionParser.add_option('-s', '--input',action="append", dest="schemafiles",help="schema files ", default=[])
    OptionParser.add_option('-o', '--output',action="store", dest="output",help="output file generated", default=[])
    OptionParser.add_option('-v', '--validate',action="store", dest="dataJSON",help="JSON file to be validated", default=[])
    options, args = OptionParser.parse_args()

    if options.output and options.dataJSON:
        OptionParser.error("options -o and -v are mutually exclusive")

    if len(sys.argv) == 1:
        print "USAGE: %s [-h] -s <path-to-schema-jsons> (-o <path-to-generated-json> | -v <path-to-json-to-be-validated>)" % sys.argv[0]

    elif options.output:
        created_JSON(options,final_json)

    elif options.dataJSON:
        pre_validation(options,fschema_json)

    else:
        sys.exit()

if __name__ == "__main__":
    main()
