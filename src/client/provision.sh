#!/bin/bash

# Server Manager Client Provisioner

set -e

# Setup Logging
datetime_string=$(date +%Y_%m_%d__%H_%M_%S)
PROVISION_DIR=$PWD/sm_provisioning/$datetime_string
mkdir -p $PROVISION_DIR
log_file=$PROVISION_DIR/provision_$datetime_string.log
exec &> >(tee -a "$log_file")

# Prep
eval SCRIPT_PATH=$(dirname $0)
SCRIPT_PATH=$(cd $SCRIPT_PATH; pwd)
space="    "
arrow="---->"
start_time=$(date +"%s")

# Defaults
TESTBED="testbed.py"
DEFAULT_DOMAIN=""
CONTRAIL_PKG=""
CONTRAIL_STORAGE_PKG=""
STORAGE_KEYS_INI=""
CLUSTER_ID="cluster_auto_$RANDOM"
NO_SM_MON=""
NO_SM_WEBUI=""

function usage()
{
    echo "Usage"
    echo ""
    echo "$0"
    echo -e "\t-h --help"
    echo -e "\t-c|--contrail-package <pkg>"
    echo -e "\t-t|--testbed <testbed.py>"
    echo -e "\t-cs|--contrail-storage-package <pkg>"
    echo -e "\t-sk|--storage-keys-ini-file <file>"
    echo -e "\t-cid|--cluster-id <cluster-id>"
    echo ""
}

if [ "$#" -eq 0 ]; then
   usage
   exit 2
fi

# Parse CLI
while [[ $# > 0 ]]; do
    key="$1"
    case $key in
        -c|--contrail-package)
        CONTRAIL_PKG="$2"
        shift # past argument
        ;;
        -t|--testbed)
        TESTBED="$2"
        shift # past argument
        ;;
        -cid|--cluster-id)
        CLUSTER_ID="$2"
        shift # past argument
        ;;
        -cs|--contrail-storage-package)
        CONTRAIL_STORAGE_PKG="$2"
        shift # past argument
        ;;
        -sk|--storage-keys-ini-file)
        STORAGE_KEYS_INI="$2"
        shift # past argument
        ;;
        -h|--help)
        usage
        exit
        ;;
        *)
        # unknown option
        echo "ERROR: unknown parameter $key"
        usage
        exit 1
        ;;
    esac
    shift # past argument or value
done

# Verify Mandatory Arguments exists
if [ "$TESTBED" == "" ] || [ "$CONTRAIL_PKG" == "" ]; then
   exit
fi

function get_real_path ()
{
    eval contrail_package=$1
    if [[ "$contrail_package" = /* ]]; then
        echo $contrail_package
    else
        echo $PWD/$contrail_package
    fi
}

# Update with real path
CONTRAIL_PKG=$(get_real_path $CONTRAIL_PKG)
TESTBED=$(get_real_path $TESTBED)

echo "$space$arrow Convert testbed.py to server manager entities"
# Convert testbed.py to server manager object json files
optional_args=""
if [ ! -z "$CONTRAIL_STORAGE_PKG" ]; then
    optional_args="--contrail-storage-packages ${CONTRAIL_STORAGE_PKG}"
fi
if [ ! -z "$STORAGE_KEYS_INI" ]; then
    STORAGE_KEYS_INI=$(python -c "import os; import sys; print(os.path.abspath(sys.argv[1]))" $STORAGE_KEYS_INI)
    optional_args="--storage-keys-ini-file $STORAGE_KEYS_INI"
fi
if [ ! -z "$CLUSTER_ID" ]; then
    optional_args="$optional_args --cluster-id $CLUSTER_ID"
fi
cd $PROVISION_DIR && $SCRIPT_PATH/testbed_parser.py --testbed ${TESTBED} --contrail-packages ${CONTRAIL_PKG} $optional_args

echo "$arrow Pre provision checks to make sure setup is ready for contrail provisioning"
# Precheck the targets to make sure that, ready for contrail provisioning
SERVER_MGR_IP=$(grep listen_ip_addr /opt/contrail/server_manager/sm-config.ini | grep -Po "listen_ip_addr = \K.*")
cd $PROVISION_DIR && $SCRIPT_PATH/preconfig.py --server-json server.json \
                                               --server-manager-ip ${SERVER_MGR_IP} \
                                               --server-manager-repo-port 80

# Retrieve info from json files
cd $PROVISION_DIR && read IMAGE_ID IMAGE_VERSION IMAGE_TYPE <<< $(python -c "import json;\
                                                                  fid = open('image.json', 'r');\
                                                                  contents = fid.read();\
                                                                  cjson = json.loads(contents);\
                                                                  fid.close();\
                                                                  print cjson['image'][0]['id'],\
                                                                        cjson['image'][0]['version'],\
                                                                        cjson['image'][0]['type']")
cd $PROVISION_DIR && CLUSTER_ID=$(python -c "import json;\
                                  fid = open('cluster.json', 'r');\
                                  data = json.load(fid);\
                                  fid.close();\
                                  print data['cluster'][0]['id']")


# Create package, cluster, server objects
cd $PROVISION_DIR && server-manager upload_image $IMAGE_ID $IMAGE_VERSION $IMAGE_TYPE ${CONTRAIL_PKG}
cd $PROVISION_DIR && server-manager add cluster -f cluster.json
cd $PROVISION_DIR && server-manager add server -f server.json

echo "$arrow Provisioning the cluster"
# Provision the cluster
cd $PROVISION_DIR && server-manager provision -F --cluster_id $CLUSTER_ID ${IMAGE_ID}

end_time=$(date +"%s")
diff=$(($end_time-$start_time))
echo "$arrow Provisioning is issued, and took $(($diff / 60)) minutes and $(($diff % 60)) seconds."
echo "$arrow Populated JSON files and logs are saved at $PROVISION_DIR"
echo "$arrow Check provisioning status using /opt/contrail/contrail_server_manager/provision_status.sh"
