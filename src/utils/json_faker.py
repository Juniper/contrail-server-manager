#! /usr/bin/python
import sys
import json
import argparse
import optparse

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

#TODO: handle ref by calling generate_data with appropriate dict loaded from
# section of the $ref file
def handle_ref(defs, schema, final_json, last_key):
    ref_str = schema["$ref"].split("/")[-1]
    generate_data(defs, defs["definitions"][ref_str], final_json, last_key)

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


def main():
    final_json = {}
    defs = {}
    final_json['contrail_4'] = {}

    OptionParser = optparse.OptionParser()
    OptionParser.add_option('-i', '--input',action="append", dest="inputfiles",help="inputfile string", default=[])
    OptionParser.add_option('-o', '--output',action="store", dest="output",help="outputfile string", default=[])
    options, args = OptionParser.parse_args()

    samplefile = options.output

    if len(sys.argv) == 1:
        print "USAGE: %s [-h][-i] <path-to-schema-jsons> [-o] <path-to-generated-json>" % sys.argv[0]


    for inputOP in options.inputfiles:
        if "definitions.json" in inputOP:
            defs = load_schema(inputOP)

    for inputOP in options.inputfiles:
        if "definitions.json" not in inputOP:
            data = load_schema(inputOP)
            if 'properties' in data.keys():
                generate_data(defs, data['properties'], final_json['contrail_4'])

    with open(samplefile, 'w') as outfile:
        json.dump(final_json, outfile, indent = 2)

if __name__ == "__main__":
    main()
