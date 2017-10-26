#!/bin/bash

# Server Manager Provisioner

set -e

# Setup Logging
datetime_string=$(date +%Y_%m_%d__%H_%M_%S)
PROVISION_DIR=/var/log/contrail/sm_provisioning/$datetime_string
mkdir -p $PROVISION_DIR
log_file=$PROVISION_DIR/provision_$datetime_string.log
exec &> >(tee -a "$log_file")

IMAGEO_PATH=/var/log/contrail/sm_provisioning/image_output.json
CLUSTERO_PATH=/var/log/contrail/sm_provisioning/cluster_output.json
SERVERO_PATH=/var/log/contrail/sm_provisioning/server_output.json

# Prep
eval SCRIPT_PATH=$(dirname $0)
SCRIPT_PATH=$(cd $SCRIPT_PATH; pwd)
start_time=$(date +"%s")
space="    "
arrow="---->"


# Defaults
SOURCES_LIST="sources_list"
TESTBED=""
DEFAULT_DOMAIN=""
CONTRAIL_PKG=""
HOSTIP=""
INSTALL_SM_LITE="install_sm_lite"
CLEANUP_PUPPET_AGENT=""
NO_LOCAL_REPO=1
LOCAL_REPO_DIR=/opt/contrail/contrail_local_repo
CLUSTER_ID="cluster_auto_$RANDOM"
SM_WEBUI_PORT=""
JSON_PATH=""
SM_OS_SKU=""
TRANSLATION_DICT_PATH="/opt/contrail/server_manager/client/container-parameter-translation-dict.json"

function usage()
{
    echo "Usage"
    echo ""
    echo "$0"
    echo -e "\t-h --help"
    echo -e "\t-c|--contrail-package <pkg>"
    echo -e "\t-d|--default-domain <domain name>"
    echo -e  "\t-ni|--no-install-sm-lite"
    echo -e "\t-cp|--cleanup-puppet-agent"
    echo -e "\t-j|--json"
    echo -e "\t-swp|--sm-webui-port"
    echo -e "\t-ip|--hostip"
    echo -e "\t-cid|--cluster-id <cluster-id>"
    echo -e "\t-sku|--sku <openstack-sku>"
    echo ""
}

if [ "$#" -eq 0 ]; then
   usage
   exit 
fi

while [[ $# > 0 ]]
    do
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
        -d|--default-domain)
        DEFAULT_DOMAIN="$2"
        shift # past argument
        ;;
        -ni|--no-install-sm-lite)
        INSTALL_SM_LITE=""
        ;;
        -swp|--sm-webui-port)
        SM_WEBUI_PORT="$2"
        ;;
        -sku|--sku)
        SM_OS_SKU="$2"
        shift
        ;;
        -cp|--no-cleanup-puppet-agent)
        CLEANUP_PUPPET_AGENT="cleanup_puppet_agent"
        ;;
        -cid|--cluster-id)
        CLUSTER_ID="$2"
        shift # past argument
        ;;
        -ip|--hostip)
        HOSTIP="$2"
        shift # past argument
        ;;
        -j|--json)
        JSON_PATH="$2"
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

if [ ! -z "$TESTBED" ]
then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "$arrow The use of testbed.py as an input to Server Manager has been deprecated!"
    echo "$arrow Please convert the testbed.py you have provided as input to a JSON using the testbed_parser utility"
    echo "$arrow You can invoke the utility as below:"
    echo "python /opt/contrail/contrail_server_manager/testbed_parser.py -t <path to testbed.py> -c <path to contrail-package>"
    echo "$arrow This script will create a file - combined.json - Which you can use as an input to the provision script as below:"
    echo "/opt/contrail/server_manager/client/provision_containers.sh -j <Path to combined.json>"
    echo "$arrow This script will now exit"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    exit
fi

function get_real_path ()
{
    eval script_path=$1
    if [[ "$script_path" = /* ]]; then
        echo $script_path
    else
        echo $PWD/$script_path
    fi
}

function install_sm_lite ()
{
  ./setup.sh --all --smlite $optional_args
}

if [ "$CLEANUP_PUPPET_AGENT" != "" ]; then
   echo "$arrow Remove puppet agent, if it is present"
   cleanup_puppet_agent
fi

# Install sever manager 
if [ "$INSTALL_SM_LITE" != "" ]; then

   echo "$arrow Installing server manager without cobbler option"
   pushd /opt/contrail/contrail_server_manager >> $log_file 2>&1
   optional_args=""
   if [ ! -z "$HOSTIP" ]; then
       optional_args="--hostip=$HOSTIP"
   fi

   # Check if SM is already installed
   installed_version=`dpkg -l | grep "contrail-server-manager-lite " | awk '{print $3}'`
   check_upgrade=1
   skipping_install=0
   if [ "$installed_version" != ""  ]; then
      version_to_install=`ls /opt/contrail/contrail_server_manager/packages/contrail-server-manager-lite_* | cut -d'_' -f 4`
      set +e
      comparison=`dpkg --compare-versions $installed_version lt $version_to_install`
      check_upgrade=`echo $?`
      set -e
      if [[ $check_upgrade == 0 ]]; then
          install_sm_lite
      elif [[ "$installed_version" == "$version_to_install" ]]; then
          echo "$space$arrow Same version of SM already installed, skipping install"
          skipping_install=1
      else
          echo "$space$arrow Higher version of SM already installed, skipping install"
          skipping_install=1
      fi
   else
     install_sm_lite
   fi
fi 

if [ -f /etc/contrail/config.global.sm.js ]  && [ "$SM_WEBUI_PORT" != "" ]
then
  echo "$space$arrow Changing SM Webui Port to $SM_WEBUI_PORT"
  sed -i "s|config.https_port =.*|config.https_port = '${SM_WEBUI_PORT}';|g" /etc/contrail/config.global.sm.js
  service supervisor-webui-sm restart >> $log_file 2>&1
fi


# Verify Mandatory Arguments exists
if [ "$JSON_PATH" == "" ]; then
   echo "JSON FILE CONTAINING CLUSTER, SERVER AND IMAGE OBJECTS IS MISSING"
   exit
fi
JSON_PATH=$(get_real_path $JSON_PATH)
# set cluster, server and image json file paths.
CLUSTER_JSON_PATH="$PROVISION_DIR/cluster.json"
SERVER_JSON_PATH="$PROVISION_DIR/server.json"
IMAGE_JSON_PATH="$PROVISION_DIR/image.json"
$(python -c "import json;\
             fid = open('$JSON_PATH', 'r');\
             data = json.load(fid);\
             fid.close();\
             fid = open('$CLUSTER_JSON_PATH', 'w');\
             json.dump({'cluster': data['cluster']}, fid, indent=4);\
             fid.close();\
             fid = open('$SERVER_JSON_PATH', 'w');\
             json.dump({'server': data['server']}, fid, indent=4);\
             fid.close();\
             fid = open('$IMAGE_JSON_PATH', 'w');\
             json.dump({'image': data['image']}, fid, indent=4);\
             fid.close();\
             ")

read CLUSTER_ID AUTH_PATH <<< $(python -c "import json;\
                        fid = open('${CLUSTER_JSON_PATH}', 'r');\
                        data = json.load(fid);\
                        fid.close();\
                        print data['cluster'][0]['id'], \
                              data['cluster'][0]['parameters'].get('auth')")

if [ "$AUTH_PATH" != "None" ]; then
      read KEY_PATH <<< $(python -c "import json;\
                            fid = open('${CLUSTER_JSON_PATH}', 'r');\
                            data = json.load(fid);\
                            fid.close();\
                            print data['cluster'][0]['parameters']['auth'].get('ssh_private_key_path')")
fi

if [ "$CLUSTER_ID" == "" ]; then
    echo "CLUSTER ID MISSING"
    exit
fi

# Retrieve info from json files
read CONTRAIL_IMAGE_ID CONTRAIL_IMAGE_VERSION CONTRAIL_IMAGE_TYPE CONTRAIL_PKG <<< $(python -c "import json;\
                                                          fid = open('${IMAGE_JSON_PATH}', 'r');\
                                                          contents = fid.read();\
                                                          cjson = json.loads(contents);\
                                                              fid.close();\
                                                              print cjson['image'][0]['id'],\
                                                                    cjson['image'][0]['version'],\
                                                                    cjson['image'][0]['type'],\
                                                                    cjson['image'][0]['path']")

# Verify Mandatory Image Arguments exists
if [ "$CONTRAIL_PKG" == "" ] || [ "$CONTRAIL_IMAGE_TYPE" == "" ] || [ "$CONTRAIL_IMAGE_ID" == "" ]; then
    echo "CONTRAIL PACKAGE DETAILS MISSING"
    exit
fi

optional_args=""

if [ ! -z "$CLUSTER_ID" ]; then
    optional_args="$optional_args --cluster-id $CLUSTER_ID"
fi

optional_preconfig_args=""

if [ ! -z "$SM_OS_SKU" ]; then
    optional_preconfig_args="$optional_preconfig_args --sku $SM_OS_SKU"
fi

if [ ! -z "$KEY_PATH" ]; then
    optional_preconfig_args="$optional_preconfig_args --key-path $KEY_PATH"
fi

echo "$arrow Pre provision checks to make sure setup is ready for contrail provisioning"
# Precheck the targets to make sure that, ready for contrail provisioning
SERVER_MGR_IP=$(grep listen_ip_addr /opt/contrail/server_manager/sm-config.ini | grep -Po "listen_ip_addr = \K.*")
cd $PROVISION_DIR && /opt/contrail/server_manager/client/preconfig.py --server-json ${SERVER_JSON_PATH} \
                                                                      --server-manager-ip ${SERVER_MGR_IP} \
                                                                      --server-manager-repo-port 80 \
                                                                      $optional_preconfig_args

echo "$arrow Adding server manager objects to server manager database"
if grep -q domain /etc/contrail/sm-client-config.ini; then
   sed -i "s|domain.*=*|domain = ${DEFAULT_DOMAIN}|g" /etc/contrail/sm-client-config.ini
else
   sed -i "/^\[CLUSTER\]/a domain = ${DEFAULT_DOMAIN}" /etc/contrail/sm-client-config.ini
fi

# Create package, cluster, server objects
cd $PROVISION_DIR && server-manager add image -f ${IMAGE_JSON_PATH} > ${IMAGEO_PATH}
cd $PROVISION_DIR && server-manager add cluster -f ${CLUSTER_JSON_PATH} > ${CLUSTERO_PATH}
cd $PROVISION_DIR && server-manager add server -f ${SERVER_JSON_PATH} > ${SERVERO_PATH}


read I_ERROR_CODE I_ERROR_MSG <<< $(python -c "import json;\
                                               fid = open('${IMAGEO_PATH}', 'r');\
                                               contentsimage = fid.read();\
                                               ijson = json.loads(contentsimage);\
                                               fid.close();\
                                               print str(ijson['return_code']),str(ijson['return_msg'])")

if [ "$I_ERROR_CODE" != "0" ]; then
    echo "${I_ERROR_MSG}"
    exit
fi

read C_ERROR_CODE C_ERROR_MSG <<< $(python -c "import json;\
                                               fid = open('${CLUSTERO_PATH}', 'r');\
                                               contentscluster = fid.read();\
                                               ccjson = json.loads(contentscluster);\
                                               fid.close();\
                                               print str(ccjson['return_code']),str(ccjson['return_msg'])")

if [ "$C_ERROR_CODE" != "0" ]; then
    echo "${C_ERROR_MSG}"
    exit
fi

read S_ERROR_CODE S_ERROR_MSG <<< $(python -c "import json;\
                                               fid = open('${SERVERO_PATH}', 'r');\
                                               contentsserver = fid.read();\
                                               sjson = json.loads(contentsserver);\
                                               fid.close();\
                                               print str(sjson['return_code']),str(sjson['return_msg'])")

if [ "$S_ERROR_CODE" != "0" ]; then
    echo "${S_ERROR_MSG}"
    exit
fi

echo "$arrow Provisioning the cluster"
# Provision the cluster

set +e
COUNTER=1
COUNTER_LIMIT=120
if [ ! -z "$SM_OS_SKU" ]; then
    if [ $SM_OS_SKU == 'ocata' ]; then
        COUNTER_LIMIT=400
    fi
fi
server-manager display image --image_id ${CONTRAIL_IMAGE_ID} | grep -w ${CONTRAIL_IMAGE_ID}
exit_status=$?
optional_message=""
if [ ! -z "$SM_OS_SKU" ]; then
    if [ $SM_OS_SKU == 'ocata' ]; then
        optional_message="Check /var/log/contrail-server-manager/debug.log for more details"
    fi
fi
echo "$arrow Waiting for containers to get loaded. $optional_message"
while [ $exit_status != 0 ] && [ $COUNTER -lt $COUNTER_LIMIT ]
do
  sleep 15
  server-manager display image --image_id ${CONTRAIL_IMAGE_ID} | grep -w ${CONTRAIL_IMAGE_ID}
  exit_status=$?
  COUNTER=$[$COUNTER +1]
done
set -e
if [ $exit_status != 0 ]; then
  echo "$arrow Containers did not get loaded correctly. Please check the debug log for more details"
  exit
fi
cd $PROVISION_DIR && server-manager provision -F --cluster_id $CLUSTER_ID ${CONTRAIL_IMAGE_ID}

end_time=$(date +"%s")
diff=$(($end_time-$start_time))
echo "$arrow Provisioning is issued, and took $(($diff / 60)) minutes and $(($diff % 60)) seconds."
echo "$arrow Populated JSON files and logs are saved at $PROVISION_DIR"
echo "$arrow Provisioning logs are available at /var/log/contrail-server-manager/debug.log"
echo "$arrow Openstack Provisioning logs are available at /var/log/syslog on the Openstack nodes"
echo "$arrow Check provisioning status using /opt/contrail/contrail_server_manager/provision_status.sh"
