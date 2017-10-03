#!/bin/bash
set -e

start_time=$(date +"%s")
datetime_string=`date +%Y_%m_%d__%H_%M_%S`
mkdir -p /var/log/contrail/install_logs/
log_file=/var/log/contrail/install_logs/install_$datetime_string.log
exec &> >(tee -a "$log_file")

space="    "
arrow="---->"
install_str=" Installing package "

echo "$arrow This install is being logged at: $log_file"

ALL=""
SM=""
SMCLIENT=""
SMCLIFFCLIENT=""
HOSTIP=""
WEBUI=""
WEBCORE=""
CERT_NAME=""
SMLITE=""
NOEXTERNALREPOS=""
HOST_IP_LIST=`ifconfig | sed -n -e 's/:127\.0\.0\.1 //g' -e 's/:172\.17\.0\.1//g' -e 's/ *inet addr:\([0-9.]\+\).*/\1/gp'`
HOSTIP=`echo $HOST_IP_LIST | cut -d' ' -f1`
default_docker_changed=0
rel=`lsb_release -r`
rel=( $rel )

function ansible_and_docker_configs()
{
    # Ansible stuff
    echo "Configuring Ansible"
    if [ ${rel[1]} == "16.04"  ]; then
        DOCKER_RUN_OPTS=' --security-opt apparmor:unconfined -d -e REGISTRY_HTTP_ADDR=0.0.0.0:5100 --restart=always --net=host '
    else
        DOCKER_RUN_OPTS=' -d -e REGISTRY_HTTP_ADDR=0.0.0.0:5100 --restart=always --net=host '
    fi
    sed -i "/callback_plugin/c\callback_plugins = \/opt\/contrail\/server_manager\/ansible\/plugins" /etc/ansible/ansible.cfg
    sed -i "/host_key_checking/c\host_key_checking = False" /etc/ansible/ansible.cfg
    sed -i "/record_host_keys/c\record_host_keys = False" /etc/ansible/ansible.cfg
    sed -i "/ssh_args/c\ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o UserKnownHostsFile=/dev/null" /etc/ansible/ansible.cfg
    sed -i "s/#remote_tmp.*/remote_tmp = \$HOME\/.ansible\/tmp/" /etc/ansible/ansible.cfg
    sed -i "s/#local_tmp.*/local_tmp = \$HOME\/.ansible\/tmp/" /etc/ansible/ansible.cfg

    echo "Starting docker if required"
    # Docker behaves differently on Ubuntu 16.04 because of systemd
    if [ ${rel[1]} == "16.04"  ]; then
        # systemd stuff ...
        if grep -q "DOCKER_OPTS=\"--insecure-registry $HOSTIP:5100\"" /etc/default/docker; then
            if systemctl status docker | grep Active | grep running; then
                echo "Docker insecure-registry option already set"
            else
                echo "Starting docker with options"
                default_docker_changed=1
            fi
        else
            echo "DOCKER_OPTS=\"--insecure-registry $HOSTIP:5100\"" >> /etc/default/docker
            default_docker_changed=1
        fi
        if grep -q "DOCKER_OPTS" /lib/systemd/system/docker.service; then
            echo "DOCKER_OPTS alredy set in systemd option"
        else
            echo "Setting DOCKER_OPTS in systemd service file"
            sed -i "/ExecStart/c\EnvironmentFile=\/etc\/default\/docker\nExecStart=\/usr\/bin\/dockerd -H fd:\/\/ \$DOCKER_OPTS" /lib/systemd/system/docker.service
            default_docker_changed=1
        fi
        if [ "$default_docker_changed" == 1 ]; then
            echo "Restarting Docker"
            systemctl daemon-reload >> 1 2>&1
            systemctl restart docker >> 1 2>&1
        fi
    else
        # good old sysv init service
        if grep -q "DOCKER_OPTS=\"--insecure-registry $HOSTIP:5100\"" /etc/default/docker; then
            if service docker status | grep running; then
                echo "option already set"
            else
                echo "starting docker with options"
                service docker restart >> 1 2>&1
            fi
        else
            echo "restarting docker with options"
            echo "DOCKER_OPTS=\"--insecure-registry $HOSTIP:5100\"" >> /etc/default/docker
            service docker restart >> 1 2>&1
        fi

    fi

    cur_name=`docker ps | grep -w "registry$" | awk '{print $NF}'`
    stopped_name=`docker ps -a | grep -w "registry$" | awk '{print $NF}'`
    if [ "$cur_name" == "registry" ]; then
        echo "Docker registry already running"
    else
        if [ "$stopped_name" == "registry" ]; then
            echo "Restarting docker regitry"
            docker start registry
        else
            echo "Starting docker registry with ${DOCKER_RUN_OPTS}"
            docker load < /opt/contrail/contrail_server_manager/registry.tar.gz
            docker run ${DOCKER_RUN_OPTS} --name registry registry:2
        fi
    fi
}

function usage()
{
    echo "Usage:"
    echo ""
    echo "-h --help"
    echo "--smlite"
    echo "--nowebui"
    echo "--sm"
    echo "--sm-client"
    echo "--sm-cliff-client"
    echo "--webui"
    echo "--hostip=<HOSTIP>"
    echo "--cert-name=<PUPPET CERTIFICATE NAME>"
    echo "--all"
    echo ""
}

function cleanup_smgr_repos()
{

  echo "$space$arrow Cleaning up existing sources.list and Server Manager sources file"
  local_repo="deb file:/opt/contrail/contrail_server_manager/packages ./"
  sed -i "s|$local_repo||g" /etc/apt/sources.list
  if [ -f /etc/apt/sources.list.d/smgr_sources.list ]; then
    rm /etc/apt/sources.list.d/smgr_sources.list
  fi

}

function setup_apt_conf()
{
  echo "$space$arrow Allow Install of Unauthenticated APT packages"
  # Allow unauthenticated pacakges to get installed.
  # Do not over-write apt.conf. Instead just append what is necessary
  # retaining other useful configurations such as http::proxy info.
  apt_auth="APT::Get::AllowUnauthenticated \"true\";"
  set +e
  grep --quiet "$apt_auth" /etc/apt/apt.conf
  exit_status=$?
  set -e
  if [ $exit_status != "0" ]; then
    echo "$apt_auth" >> /etc/apt/apt.conf
  fi

  set +e
  apt-get update >> $log_file 2>&1
  set -e
}


function setup_smgr_repos()
{

  echo "$space$arrow Installing dependent packages for Setting up Smgr repos"
  #scan pkgs in local repo and create Packages.gz
  if [ ${rel[1]} == "16.04"  ]; then
    PKG_16_04='xz-utils_*.deb perl*.deb libperl*.deb libopts*.deb ntp*.deb'
  fi

  pushd /opt/contrail/contrail_server_manager/packages >> $log_file 2>&1
  (DEBIAN_FRONTEND=noninteractive dpkg -i binutils_*.deb dpkg-dev_*.deb libdpkg-perl_*.deb make_*.deb patch_*.deb ${PKG_16_04} >> $log_file 2>&1)
  dpkg-scanpackages . | gzip -9c > Packages.gz | >> $log_file 2>&1
  popd >> $log_file 2>&1

  echo "deb file:/opt/contrail/contrail_server_manager/packages ./" > /tmp/local_repo
  cat /tmp/local_repo /etc/apt/sources.list.d/smgr_sources.list > /tmp/new_smgr_sources.list
  mv /tmp/new_smgr_sources.list /etc/apt/sources.list.d/smgr_sources.list

  set +e
  apt-get update >> $log_file 2>&1
  set -e

}

function cleanup_passenger()
{
  echo "$space$arrow Cleaning up passenger for Server Manager Ugrade"
  if [ -f /etc/apache2/mods-enabled/passenger.conf ]; then
    a2dismod passenger >> $log_file 2>&1
  fi
  service apache2 restart >> $log_file 2>&1
}

if [ "$#" -eq 0 ]; then
   usage
   exit
fi

while [ "$1" != "" ]; do
    PARAM=`echo $1 | awk -F= '{print $1}'`
    VALUE=`echo $1 | awk -F= '{print $2}'`
    case $PARAM in
        -h | --help)
            usage
            exit 1
            ;;
        --all)
            ALL="all"
	    SM="contrail-server-manager"
	    WEBUI="contrail-web-server-manager"
	    WEBCORE="contrail-web-core"
	    SMCLIFFCLIENT="contrail-server-manager-cliff-client"
            ;;
	--smlite)
	    SMLITE="smlite"
	    ;;
        --sm)
	    SM="contrail-server-manager"
            ;;
        --webui)
	    WEBUI="contrail-web-server-manager"
	    WEBCORE="contrail-web-core"
            ;;
        --sm-client)
	    SMCLIENT="contrail-server-manager-client"
            ;;
        --sm-cliff-client)
	    SMCLIFFCLIENT="contrail-server-manager-cliff-client"
            ;;
        --hostip)
            HOSTIP=$VALUE
            rm -rf /opt/contrail/contrail_server_manager/IP.txt
            echo $HOSTIP >> /opt/contrail/contrail_server_manager/IP.txt
            ;;
        --cert-name)
            CERT_NAME=$VALUE
            ;;
        *)
            echo "ERROR: unknown parameter \"$PARAM\""
            usage
            exit 1
            ;;
    esac
    shift
done

cleanup_smgr_repos
setup_apt_conf
touch /etc/apt/sources.list.d/smgr_sources.list
setup_smgr_repos

RESTART_SERVER_MANAGER=""
if [ "$SM" != "" ]; then
  echo "$arrow Server Manager"

  # Removing the existing puppet agent certs, so that puppet master certs can take its place
  # Check if below logic will work in pre-install of contrail-smgr
  puppetmaster_installed=`dpkg -l | grep "puppetmaster-passenger" || true`

  if [[ -d /var/lib/puppet/ssl && $puppetmaster_installed == "" ]]; then
      datetime_string=`date +%Y_%m_%d__%H_%M_%S`
      echo "$space$arrow Puppet agent certificates have been moved to /var/lib/puppet/ssl_$datetime_string"
      mv /var/lib/puppet/ssl /var/lib/puppet/ssl_$datetime_string
  fi
  # Check if this is an upgrade
  if [ "$SMLITE" != "" ]; then
      installed_version=`dpkg -l | grep "contrail-server-manager-lite " | awk '{print $3}'`
  else
      installed_version=`dpkg -l | grep "contrail-server-manager " | awk '{print $3}'`
  fi
  check_upgrade=1
  if [ "$installed_version" != ""  ]; then
      version_to_install=`ls /opt/contrail/contrail_server_manager/packages/contrail-server-manager_* | cut -d'_' -f 4`
      set +e
      comparison=`dpkg --compare-versions $installed_version lt $version_to_install`
      check_upgrade=`echo $?`
      set -e
      if [[ $check_upgrade == 0 || "$installed_version" == "$version_to_install" ]]; then
          echo "$space$arrow Upgrading Server Manager to version $version_to_install"
      else
          echo "$space$arrow Cannot upgrade Server Manager to version $version_to_install"
          exit
      fi
  fi

  if [ $check_upgrade == 0 ]; then
    #  Cleanup old Passenger Manual Install so that it doesn't collide with new package
    passenger_upgrade_version="2.22"
    contrail_server_manager_version=`dpkg -l | grep "contrail-server-manager " | awk '{print $3}' | cut -d'-' -f 1`
    awk -v n1=$passenger_upgrade_version -v n2=$contrail_server_manager_version 'BEGIN{ if (n1>n2) cleanup_passenger}'
  fi

  PUPPET_VERSION="3.7.3-1puppetlabs1"
  #TODO: To be Removed after local repo additions
  if [ ${rel[1]} == "16.04"  ]; then
    apt-get --no-install-recommends -y install libpython2.7 >> $log_file 2>&1
    PUPPET_VERSION="3.8.5-2"
    ANSIBLE_VERSION="2.3.1.0-1ppa~xenial"
  fi
  if [ ${rel[1]} == "14.04"  ]; then
    apt-get --no-install-recommends -y install libpython2.7 >> $log_file 2>&1
    PUPPET_VERSION="3.7.3-1puppetlabs1"
    ANSIBLE_VERSION="2.3.1.0-1ppa~trusty"
  fi

  # explicit install ansible (with 4.0 onwards ansible2.3 is packaged) to take care of upgrade SM case
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install ansible=${ANSIBLE_VERSION} >> $log_file 2>&1
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install python-pyvmomi >> $log_file 2>&1
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install puppet-common=${PUPPET_VERSION} puppetmaster-common=${PUPPET_VERSION} >> $log_file 2>&1
  cp /opt/contrail/contrail_server_manager/puppet.conf /etc/puppet/
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install nodejs=0.10.35-1contrail1 >> $log_file 2>&1

  if [ "$CERT_NAME" != "" ]; then
    host=$CERT_NAME
    echo "$space$arrow Creating puppet certificate with name $host"
  else
    host=$(hostname -f)
    echo "$space$arrow Using default puppet certificate name $host"
  fi
  set +e
  puppet cert list --all 2>&1 | grep -v $(hostname -f) && puppet cert generate $host >> $log_file 2>&1
  set -e
  #To be Removed after local repo additions
  echo "$space$arrow$install_str Puppetmaster Passenger"
  apt-get --no-install-recommends -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install puppetmaster-passenger=${PUPPET_VERSION} >> $log_file 2>&1
  service apache2 restart >> $log_file 2>&1

  if [ -e /etc/init.d/apparmor ]; then
    /etc/init.d/apparmor stop >> $log_file 2>&1
    update-rc.d -f apparmor remove >> $log_file 2>&1
  fi

  if [ $check_upgrade == 0 ]; then
    # Take a backup of the existing dhcp.template
    # Upgrade
    echo "$space$arrow Upgrading Server Manager"
    RESTART_SERVER_MANAGER="1"
    if [ "$SMLITE" != "" ]; then
       echo "$space$arrow$install_str Server Manager Lite"
       dpkg -P --force-all contrail-server-manager-monitoring >> $log_file 2>&1
       apt-get -y install contrail-server-manager-lite >> $log_file 2>&1
       apt-get -y install -f >> $log_file 2>&1
    else
       cp /etc/cobbler/dhcp.template /var/tmp/dhcp.template
       cv=`cobbler --version`
       cv=( $cv  )
       if [ "${cv[1]}" != "2.6.11" ]; then
          dpkg -P --force-all python-cobbler >> $log_file 2>&1
          dpkg -P --force-all cobbler-common >> $log_file 2>&1
          dpkg -P --force-all cobbler-web >> $log_file 2>&1
          dpkg -P --force-all cobbler >> $log_file 2>&1
          dpkg -P --force-all contrail-server-manager >> $log_file 2>&1
       fi
       echo "$space$arrow$install_str Server Manager"
       apt-get -y install cobbler="2.6.11-1" >> $log_file 2>&1 # TODO : Remove after local repo pinning
       dpkg -P --force-all contrail-server-manager-monitoring >> $log_file 2>&1
       apt-get -y install contrail-server-manager >> $log_file 2>&1
       apt-get -y install -f >> $log_file 2>&1
       # Stopping webui service that uses old name
       if [ -f /etc/init.d/supervisor-webui ]; then
         old_webui_status=`service supervisor-webui status | awk '{print $2}' | cut -d'/' -f 1`
         if [ $old_webui_status != "stop"  ]; then
            service supervisor-webui stop >> $log_file 2>&1 # TODO : Remove for 3.0 release
         fi
       fi
    fi
  else
    if [ "$SMLITE" != "" ]; then
       echo "$space$arrow$install_str Server Manager Lite"
       apt-get -y install contrail-server-manager-lite >> $log_file 2>&1
       RESTART_SERVER_MANAGER="1"
    else
      echo "$space$arrow$install_str Server Manager"
      apt-get -y install cobbler="2.6.11-1" >> $log_file 2>&1 # TODO : Remove after local repo pinning
      apt-get -y install contrail-server-manager >> $log_file 2>&1
      cp /etc/contrail_smgr/cobbler/bootup_dhcp.template.u /etc/cobbler/dhcp.template
    fi
    apt-get -y install -f >> $log_file 2>&1
  fi

  ansible_and_docker_configs
  echo "$arrow Completed Installing Server Manager"
fi

if [ "$SMCLIENT" != "" ]; then
  echo "$arrow Server Manager Client"
  echo "$space$arrow$install_str Server Manager Client"
  apt-get -y install contrail-server-manager-client >> $log_file 2>&1
  apt-get -y install -f >> $log_file 2>&1
  echo "$arrow Completed Installing Server Manager Client"
fi

if [ "$SMCLIFFCLIENT" != "" ]; then
  echo "$arrow Server Manager Cliff Client"
  echo "$space$arrow$install_str Server Manager Cliff Client"
  dpkg -P --force-all contrail-server-manager-client >> $log_file 2>&1
  apt-get -y install contrail-server-manager-cliff-client >> $log_file 2>&1
  apt-get -y install -f >> $log_file 2>&1
  echo "$arrow Completed Installing Server Manager Cliff Client"
fi

if [ "$WEBUI" != "" ]; then
  echo "$arrow Web Server Manager"
  # install webui
  echo "$space$arrow$install_str Contrail Web Core"
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install contrail-web-core >> $log_file 2>&1
  echo "$space$arrow$install_str Contrail Web Server Manager"
  apt-get -y --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" install contrail-web-server-manager >> $log_file 2>&1
  apt-get -y install -f >> $log_file 2>&1
  echo "$arrow Completed Installing Web Server Manager"
fi

if [ "x$RESTART_SERVER_MANAGER" == "x1" ]; then
  if [ "$SMLITE" != "" ]; then
    echo "$space$space$arrow Starting Server Manager Lite Service"
  else
    echo "$space$space$arrow Starting Server Manager Service"
  fi
  service contrail-server-manager restart >> $log_file 2>&1
  sleep 5
fi

# Should we remove Puppet/Passenger sources.list.d files also?
echo "$arrow Reverting Repos to old state"
rm -f /etc/apt/sources.list.d/puppet.list >> $log_file 2>&1
rm -f /etc/apt/sources.list.d/passenger.list >> $log_file 2>&1
rm -f /etc/apt/sources.list.d/smgr_sources.list >> $log_file 2>&1
set +e
apt-get update >> $log_file 2>&1
set -e

# In case of upgrade restore the saved dhcp.template back
if [ $check_upgrade == 0 ]; then
    if [ "$SMLITE" != "" ]; then
      echo "SMLite case, no dhcp.template" >> $log_file 2>&1
    else
      mv /var/tmp/dhcp.template /etc/cobbler/dhcp.template
    fi
fi

sm_installed=`dpkg -l | grep "contrail-server-manager " || true`
if [ "$sm_installed" != "" ]; then
  echo "IMPORTANT: CONFIGURE /ETC/COBBLER/DHCP.TEMPLATE, NAMED.TEMPLATE, SETTINGS TO BRING UP SERVER MANAGER."
  echo "If your install has failed, please make sure the /etc/apt/sources.list file reflects the default sources.list for your version of Ubuntu."
  echo "Sample sources.list files are available at /opt/contrail/contrail_server_manager/."
  echo "Install log is at /var/log/contrail/install_logs/"
fi

end_time=$(date +"%s")
diff=$(($end_time-$start_time))
echo "SM installation took $(($diff / 60)) minutes and $(($diff % 60)) seconds."
