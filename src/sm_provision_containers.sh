#!/bin/bash

# Server Manager Provisioner

set -e

# Setup Logging
datetime_string=$(date +%Y_%m_%d__%H_%M_%S)
PROVISION_DIR=/var/log/contrail/sm_provisioning/$datetime_string
mkdir -p $PROVISION_DIR
log_file=$PROVISION_DIR/provision_$datetime_string.log
exec &> >(tee -a "$log_file")

# Prep
eval SCRIPT_PATH=$(dirname $0)
SCRIPT_PATH=$(cd $SCRIPT_PATH; pwd)
start_time=$(date +"%s")
space="    "
arrow="---->"


# Defaults
SOURCES_LIST="sources_list"
DEFAULT_DOMAIN=""
CONTRAIL_PKG=""
CONTRAIL_STORAGE_PKG=""
STORAGE_KEYS_INI=""
HOSTIP=""
NOEXTERNALREPOS=""
INSTALL_SM_LITE="install_sm_lite"
CLEANUP_PUPPET_AGENT=""
NO_LOCAL_REPO=1
LOCAL_REPO_DIR=/opt/contrail/contrail_local_repo
CLUSTER_ID="cluster_auto_$RANDOM"
NO_SM_MON=""
NO_SM_WEBUI=""
SM_WEBUI_PORT=""
CLUSTER_JSON_PATH=""
SERVER_JSON_PATH=""
IMAGE_JSON_PATH=""

function usage()
{
    echo "Usage"
    echo ""
    echo "$0"
    echo -e "\t-h --help"
    echo -e "\t-c|--contrail-package <pkg>"
    echo -e "\t-cs|--contrail-storage-package <pkg>"
    echo -e "\t-sk|--storage-keys-ini-file <file>"
    echo -e "\t-d|--default-domain <domain name>"
    echo -e  "\t-ni|--no-install-sm-lite"
    echo -e "\t-cp|--cleanup-puppet-agent"
    echo -e "\t-cj|--cluster-json"
    echo -e "\t-sj|--server-json"
    echo -e "\t-ij|--image-json"
    echo -e "\t-nr|--no-local-repo"
    echo -e "\t-nm|--no-sm-mon"
    echo -e "\t-nw|--no-sm-webui"
    echo -e "\t-swp|--sm-webui-port"
    echo -e "\t-ip|--hostip"
    echo -e "\t-cid|--cluster-id <cluster-id>"
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
        -cs|--contrail-storage-package)
        CONTRAIL_STORAGE_PKG="$2"
        shift # past argument
        ;;
        -sk|--storage-keys-ini-file)
        STORAGE_KEYS_INI="$2"
        shift # past argument
        ;;
        -d|--default-domain)
        DEFAULT_DOMAIN="$2"
        shift # past argument
        ;;
        -nr|--no-local-repo)
        NO_LOCAL_REPO=0
        ;;
        -ni|--no-install-sm-lite)
        INSTALL_SM_LITE=""
        ;;
        -nm|--no-sm-mon)
        NO_SM_MON="--nosm-mon"
        ;;
        -nw|--no-sm-webui)
        NO_SM_WEBUI="--nowebui"
        ;;
        -swp|--sm-webui-port)
        SM_WEBUI_PORT="$2"
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
        -cj|--cluster-json)
        CLUSTER_JSON_PATH="$2"
        shift # past argument
        ;;
        -sj|--server-json)
        SERVER_JSON_PATH="$2"
        shift # past argument
        ;;
        -ij|--image-json)
        IMAGE_JSON_PATH="$2"
        shift # past argument
        ;;
        --no-external-repos)
        NOEXTERNALREPOS="True"
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
if [ "$CLUSTER_JSON_PATH" == "" ] || [ "$SERVER_JSON_PATH" == "" ] || [ "$IMAGE_JSON_PATH" == "" ]; then
   echo "ONE OF CLUSTER SERVER OR IMAGE JSON PATHS MISSING"
   echo ${CLUSTER_JSON_PATH} ${SERVER_JSON_PATH} ${IMAGE_JSON_PATH}
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
CLUSTER_JSON_PATH=$(get_real_path $CLUSTER_JSON_PATH)
SERVER_JSON_PATH=$(get_real_path $SERVER_JSON_PATH)
IMAGE_JSON_PATH=$(get_real_path $IMAGE_JSON_PATH)

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

read CLUSTER_ID <<< $(python -c "import json;\
                        fid = open('${CLUSTER_JSON_PATH}', 'r');\
                        data = json.load(fid);\
                        fid.close();\
                        print data['cluster'][0]['id']")

# Verify Mandatory Arguments exists
if [ "$CONTRAIL_PKG" == "" ] || [ "$CONTRAIL_IMAGE_TYPE" == "" ] || [ "$CONTRAIL_IMAGE_ID" == "" ]; then
    echo "PGK DETAILS MISSING"
    exit
fi

if [ "$CONTRAIL_IMAGE_TYPE" != "contrail-ubuntu-package" ]; then
    echo "PACKAGE TYPE IS WRONG"
    exit
fi

if [ "$CLUSTER_ID" == "" ]; then
    echo "CLUSTER ID MISSING"
    exit
fi

if [ -f "$CONTRAIL_STORAGE_PKG" ]; then
    CONTRAIL_STORAGE_PKG=$(get_real_path $CONTRAIL_STORAGE_PKG)
fi

function unmount_contrail_local_repo()
{
    echo "$arrow Removing contrail local repo - $LOCAL_REPO_DIR"
    # Remove local repo dir
    if [ -d $LOCAL_REPO_DIR ]; then
        rm -rf $LOCAL_REPO_DIR
    fi

    # Remove preference file
    if [ -f /etc/apt/preferences.d/contrail_local_repo ]; then
        rm -f /etc/apt/preferences.d/contrail_local_repo
    fi

    set +e
    grep "^deb file:$LOCAL_REPO_DIR ./" /etc/apt/sources.list
    exit_status=$?
    set -e
    if [ $exit_status == 0 ]; then
        sed -i "s#deb file:$LOCAL_REPO_DIR ./##g" /etc/apt/sources.list
        apt-get update >> $log_file 2>&1
    fi
}

function mount_contrail_local_repo()
{
    set -e
    # check if package is available
    if [ ! -f "$CONTRAIL_PKG" ]; then
        echo "ERROR: $CONTRAIL_PKG : No Such file..."
        exit 2
    fi

    # mount package and create local repo
    echo "$space$arrow Creating local lepo -- $LOCAL_REPO_DIR"
    set +e
    grep "^deb file:$LOCAL_REPO_DIR ./" /etc/apt/sources.list
    exit_status=$?
    set -e

    if [ $exit_status != 0 ]; then
        mkdir -p $LOCAL_REPO_DIR
        file_type=$(file $CONTRAIL_PKG | cut -f2 -d' ')
        if [ "$file_type" == "Debian" ]; then
           dpkg -x $CONTRAIL_PKG $LOCAL_REPO_DIR >> $log_file 2>&1
           (cd $LOCAL_REPO_DIR && tar xfz opt/contrail/contrail_packages/*.tgz >> $log_file 2>&1)
        elif [ "$file_type" == "gzip" ]; then
           tar xzf $CONTRAIL_PKG -C $LOCAL_REPO_DIR >> $log_file 2>&1
        else
           echo "ERROR: $CONTRAIL_PKG: Invalid package"
           exit 2
        fi
        (cd $LOCAL_REPO_DIR && DEBIAN_FRONTEND=noninteractive dpkg -i binutils_*.deb dpkg-dev_*.deb libdpkg-perl_*.deb make_*.deb patch_*.deb >> $log_file 2>&1)
        (cd $LOCAL_REPO_DIR && dpkg-scanpackages . | gzip -9c > Packages.gz | >> $log_file 2>&1)
        datetime_string=$(date +%Y_%m_%d__%H_%M_%S)
        cp /etc/apt/sources.list /etc/apt/sources.list.contrail.$datetime_string
        echo >> /etc/apt/sources.list
        sed -i "1 i\deb file:$LOCAL_REPO_DIR ./" /etc/apt/sources.list
        cp -v /opt/contrail/contrail_server_manager/contrail_local_preferences /etc/apt/preferences.d/contrail_local_repo >> $log_file 2>&1
        apt-get update >> $log_file 2>&1
    fi
}

function cleanup_puppet_agent()
{
   set +e
   apt-get -y --purge autoremove puppet puppet-common hiera >> $log_file 2>&1
   set -e
}

if [ "$CLEANUP_PUPPET_AGENT" != "" ]; then
   echo "$arrow Remove puppet agent, if it is present"
   cleanup_puppet_agent
fi

# Install sever manager 
if [ "$INSTALL_SM_LITE" != "" ]; then
   # Create a local repo from contrail-install packages
   # so packages from this repo gets preferred
   if [ $NO_LOCAL_REPO != 0 ]; then
       echo "$arrow Provision contrail local repo"
       mount_contrail_local_repo
       LOCAL_REPO_MOUNTED=1
   fi

   echo "$arrow Install server manager without cobbler option"
   pushd /opt/contrail/contrail_server_manager >> $log_file 2>&1
   optional_args=""
   if [ ! -z "$HOSTIP" ]; then
       optional_args="--hostip=$HOSTIP"
   fi
   if [ ! -z "$NOEXTERNALREPOS" ]; then
       optional_args+=" --no-external-repos"
   fi
   ./setup.sh --all --smlite ${NO_SM_MON} ${NO_SM_WEBUI} $optional_args
   popd >> $log_file 2>&1
fi 

if [ -f /etc/contrail/config.global.sm.js ]  && [ "$SM_WEBUI_PORT" != "" ]
then
  echo "$space$arrow Changing SM Webui Port to $SM_WEBUI_PORT"
  sed -i "s|config.https_port =.*|config.https_port = '${SM_WEBUI_PORT}';|g" /etc/contrail/config.global.sm.js
  service supervisor-webui-sm restart >> $log_file 2>&1
fi

if [ ! -z "$CLUSTER_ID" ]; then
    optional_args="$optional_args --cluster-id $CLUSTER_ID"
fi

echo "$arrow Pre provision checks to make sure setup is ready for contrail provisioning"
# Precheck the targets to make sure that, ready for contrail provisioning
SERVER_MGR_IP=$(grep listen_ip_addr /opt/contrail/server_manager/sm-config.ini | grep -Po "listen_ip_addr = \K.*")
cd $PROVISION_DIR && /opt/contrail/server_manager/client/preconfig.py --server-json ${SERVER_JSON_PATH} \
                                                                      --server-manager-ip ${SERVER_MGR_IP} \
                                                                      --server-manager-repo-port 80

# Remove contrail local repo if any
if [[ $LOCAL_REPO_MOUNTED -eq 1 ]]; then
    unmount_contrail_local_repo
fi

echo "$arrow Adding server manager objects to server manager database"
if grep -q domain /etc/contrail/sm-client-config.ini; then
   sed -i "s|domain.*=*|domain = ${DEFAULT_DOMAIN}|g" /etc/contrail/sm-client-config.ini
else
   sed -i "/^\[CLUSTER\]/a domain = ${DEFAULT_DOMAIN}" /etc/contrail/sm-client-config.ini
fi

# Create package, cluster, server objects
cd $PROVISION_DIR && server-manager add image -f ${IMAGE_JSON_PATH}
cd $PROVISION_DIR && server-manager add cluster -f ${CLUSTER_JSON_PATH}
cd $PROVISION_DIR && server-manager add server -f ${SERVER_JSON_PATH}

echo "$arrow Provisioning the cluster"
# Provision the cluster

set +e
server-manager display image --image_id ${CONTRAIL_IMAGE_ID} | grep -w ${CONTRAIL_IMAGE_ID}
exit_status=$?
echo "$arrow Waiting for containers to get loaded"
while [ $exit_status != 0 ]
do
  sleep 15
  server-manager display image --image_id ${CONTRAIL_IMAGE_ID} | grep -w ${CONTRAIL_IMAGE_ID}
  exit_status=$?
done
set -e

cd $PROVISION_DIR && server-manager provision -F --cluster_id $CLUSTER_ID ${CONTRAIL_IMAGE_ID}

end_time=$(date +"%s")
diff=$(($end_time-$start_time))
echo "$arrow Provisioning is issued, and took $(($diff / 60)) minutes and $(($diff % 60)) seconds."
echo "$arrow Populated JSON files and logs are saved at $PROVISION_DIR"
echo "$arrow Check provisioning status using /opt/contrail/contrail_server_manager/provision_status.sh"
