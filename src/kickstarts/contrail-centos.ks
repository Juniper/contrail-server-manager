# Kickstart template for the NewNode (includes openstack)

## Basic keys for installation
text
firewall --disabled
firstboot --disable
keyboard us
lang en_US
selinux --disabled
timezone --utc America/Los_Angeles
install
clearpart --all --initlabel
zerombr
reboot
bootloader --location=mbr --timeout=5 --driveorder=sda --append="rhgb quiet"
## Default users and passwords
## Hash created using openssl passwd -1 <pass>
## 
auth  --useshadow  --enablemd5
rootpw --iscrypted $passwd
url --url=$tree
$yum_repo_stanza
## If we put repo stuff in ksmeta, create repo url
#set $reponame = $getVar("reponame","")
#set $repourl = $getVar("repourl","")
#if $reponame != "" and $repourl != ""
  ## echo "reponame=$reponame"
  ## echo "repourl=$repourl"
  #set $repcmd = "repo --name="+$reponame+" --baseurl=\""+$repourl+"\""
  $repcmd
#end if
autopart

%pre
set -x -v
exec 1>/tmp/ks-pre.log 2>&1

# Once root's homedir is there, copy over the log.
while : ; do
    sleep 10
    if [ -d /mnt/sysimage/root ]; then
        cp /tmp/ks-pre.log /mnt/sysimage/root/
        logger "Copied %pre section log to system"
        break
    fi
done &
#set system_name = $getVar('system_name','')
#set profile_name = $getVar('profile_name','')
#set breed = $getVar('breed','')
#set srv = $getVar('http_server','')
#set run_install_triggers = $str($getVar('run_install_triggers',''))
#set runpre = ""

#if $system_name != ''

    ## RUN PRE TRIGGER
    #if $run_install_triggers in [ "1", "true", "yes", "y" ]
        #if $breed == 'redhat'
            #set runpre = "\nwget \"http://%s/cblr/svc/op/trig/mode/pre/%s/%s\" -O /dev/null" % (srv, "system", system_name)
        #else if $breed == 'vmware'
            #set runpre = "\nwget \"http://%s/cblr/svc/op/trig/mode/pre/%s/%s\" -O /dev/null" % (srv, "system", system_name)
        #end if
    #end if

#else if $profile_name != ''

    ## RUN PRE TRIGGER
    #if $run_install_triggers in [ "1", "true", "yes", "y" ]
        #if $breed == 'redhat'
            #set runpre = "\nwget \"http://%s/cblr/svc/op/trig/mode/pre/%s/%s\" -O /dev/null" % (srv, "profile", profile_name)
        #else if $breed == 'vmware'
            #set runpre = "\nwget \"http://%s/cblr/svc/op/trig/mode/pre/%s/%s\" -O /dev/null" % (srv, "profile", profile_name)
        #end if
    #end if

#end if

#echo $runpre
#if $getVar("system_name","") != ""
# Start pre_install_network_config generated code
    #set ikeys = $interfaces.keys()
    #import re
    #set $vlanpattern = $re.compile("[a-zA-Z0-9]+[\.:][0-9]+")
    #set $routepattern = $re.compile("[0-9/.]+:[0-9.]+")
    ##
    ## Determine if we should use the MAC address to configure the interfaces first
    ## Only physical interfaces are required to have a MAC address
    #set $configbymac = True
    #for $iname in $ikeys
        #set $idata = $interfaces[$iname]
        #if $idata["mac_address"] == "" and not $vlanpattern.match($iname) and not $idata["interface_type"].lower() in ("master","bond","bridge")
            #set $configbymac = False
        #end if
    #end for
    #set $i = 0

    #if $configbymac
        ## Output diagnostic message
# Start of code to match cobbler system interfaces to physical interfaces by their mac addresses
    #end if
    #for $iname in $ikeys
#  Start $iname
        #set $idata         = $interfaces[$iname]
        #set $mac           = $idata["mac_address"]
        #set $static        = $idata["static"]
        #set $ip            = $idata["ip_address"]
        #set $netmask       = $idata["netmask"]
        #set $iface_type    = $idata["interface_type"]
        #set $iface_master  = $idata["interface_master"]
        #set $static_routes = $idata["static_routes"]
        #set $devfile       = "/etc/sysconfig/network-scripts/ifcfg-" + $iname
        #if $vlanpattern.match($iname)
            ## If this is a VLAN interface, skip it, anaconda doesn't know
            ## about VLANs.
            #set $is_vlan = "true"
        #else
            #set $is_vlan = "false"
        #end if
        #if ($configbymac and $is_vlan == "false" and $iface_type.lower() not in ("slave","bond_slave","bridge_slave")) or $iface_type.lower() in ("master","bond","bridge")
            ## This is a physical interface, hand it to anaconda. Do not
            ## process slave interface here.
            #if $iface_type.lower() in ("master","bond","bridge")
                ## Find a slave for this interface
                #for $tiname in $ikeys
                    #set $tidata = $interfaces[$tiname]
                    #if $tidata["interface_type"].lower() in ("slave","bond_slave","bridge_slave") and $tidata["interface_master"].lower() == $iname
                        #set $mac = $tidata["mac_address"]
#  Found a slave for this interface: $tiname ($mac)
                        #break
                    #end if
                #end for
            #end if
            #if $static and $ip != ""
                #if $netmask == ""
                    ## Netmask not provided, default to /24.
                    #set $netmask = "255.255.255.0"
                #end if
                #set $netinfo = "--bootproto=static --ip=%s --netmask=%s" % ($ip, $netmask)
                #if $gateway != ""
	            #set $netinfo = "%s --gateway=%s" % ($netinfo, $gateway)
    	        #end if
    	        #if $len($name_servers) > 0
    	            #set $netinfo = "%s --nameserver=%s" % ($netinfo, $name_servers[0])
                #end if
            #else if not $static
                #set $netinfo = "--bootproto=dhcp"
            #else
                ## Skip this interface, it's set as static, but without
                ## networking info.
#  Skipping (no configuration)...
                #continue
            #end if
            #if $hostname != ""
                #set $netinfo = "%s --hostname=%s" % ($netinfo, $hostname)
            #end if
# Configuring $iname ($mac)
if ifconfig -a | grep -i $mac
then
  IFNAME=\$(ifconfig -a | grep -i '$mac' | cut -d " " -f 1)
  echo "network --device=\$IFNAME $netinfo" >> /tmp/pre_install_network_config
            #for $route in $static_routes
                #if $routepattern.match($route)
                    #set $routebits = $route.split(":")
                    #set [$network, $router] = $route.split(":")
  ip route add $network via $router dev \$IFNAME
                #else
  # Warning: invalid route "$route"
                #end if
            #end for
fi
        #else
            #if $iface_type.lower() in ("slave","bond_slave","bridge_slave")
#  Skipping (slave-interface)
            #else
#  Skipping (not a physical interface)...
            #end if
        #end if
    #end for
# End pre_install_network_config generated code
#end if
#if $str($getVar('anamon_enabled','')) == "1"
wget -O /tmp/anamon "http://$server:$http_port/cobbler/aux/anamon"
python /tmp/anamon --name "$name" --server "$server" --port "$http_port"
#end if
%end

services --enabled=sshd

%packages --nobase
*
%end

%post
set -x -v
exec 1>/root/ks-post.log 2>&1
## For now, assume the cobbler server as the ntp server
## Set date from server before enabling ntpd so it syncs soon
/sbin/ntpdate $http_server
/bin/mv /etc/ntp.conf /etc/ntp.conf.orig
/bin/touch /var/lib/ntp/drift
cat << __EOT__ > /etc/ntp.conf
driftfile /var/lib/ntp/drift
server 10.84.5.100
server 172.17.28.5
server 66.129.255.62
server 172.28.16.17
restrict 127.0.0.1
restrict -6 ::1
includefile /etc/ntp/crypto/pw
keys /etc/ntp/keys
__EOT__
/sbin/chkconfig ntpd on
/opt/contrail/contrail_packages/setup.sh
/bin/echo "$server puppet" >> /etc/hosts
# TBD Abhay hardcoded IP address to be replaced with parameter later.
/bin/echo "$ip_address $system_name.$system_domain $system_name" >> /etc/hosts
$yum_config_stanza
#if $getVar('kernel_options_post','') != ''
# Start post install kernel options update
/sbin/grubby --update-kernel=`/sbin/grubby --default-kernel` --args="$kernel_options_post"
# End post install kernel options update
#end if

# Start post_install_network_config generated code
#if $getVar("system_name","") != ""
    ## this is being provisioned by system records, not profile records
    ## so we can do the more complex stuff
    ## get the list of interface names
    #set ikeys = $interfaces.keys()
    #set osversion = $getVar("os_version","")
    #import re
    #set $vlanpattern = $re.compile("[a-zA-Z0-9]+[\.:][0-9]+")
    ## Determine if we should use the MAC address to configure the interfaces first
    ## Only physical interfaces are required to have a MAC address
    ## Also determine the number of bonding devices we have, so we can set the
    ## max-bonds option in modprobe.conf accordingly. -- jcapel
    #set $configbymac = True
    #set $numbondingdevs = 0
    #set $enableipv6 = False
    ## =============================================================================
    #for $iname in $ikeys
        ## look at the interface hash data for the specific interface
        #set $idata = $interfaces[$iname]
        ## do not configure by mac address if we don't have one AND it's not for bonding/vlans
        ## as opposed to a "real" physical interface
        #if $idata.get("mac_address", "") == "" and not $vlanpattern.match($iname) and not $idata.get("interface_type", "").lower() in ("master","bond","bridge"):
                ## we have to globally turn off the config by mac feature as we can't
                ## use it now
                #set $configbymac = False
        #end if
        ## count the number of bonding devices we have.
        #if $idata.get("interface_type", "").lower() in ("master","bond")
            #set $numbondingdevs += 1
        #end if
        ## enable IPv6 networking if we set an ipv6 address or turn on autoconfiguration
        #if $idata.get("ipv6_address", "") != "" or $ipv6_autoconfiguration == True
            #set $enableipv6 = True
        #end if
    #end for
    ## end looping through the interfaces to see which ones we need to configure.
    ## =============================================================================
    #set $i = 0
    ## setup bonding if we have to
    #if $numbondingdevs > 0

# we have bonded interfaces, so set max_bonds
if [ -f "/etc/modprobe.conf" ]; then
    echo "options bonding max_bonds=$numbondingdevs" >> /etc/modprobe.conf
fi
    #end if
    ## =============================================================================
    ## create a staging directory to build out our network scripts into
    ## make sure we preserve the loopback device

# create a working directory for interface scripts
mkdir /etc/sysconfig/network-scripts/cobbler
cp /etc/sysconfig/network-scripts/ifcfg-lo /etc/sysconfig/network-scripts/cobbler/
    ## =============================================================================
    ## configure the gateway if set up (this is global, not a per-interface setting)
    #if $gateway != ""

# set the gateway in the network configuration file
grep -v GATEWAY /etc/sysconfig/network > /etc/sysconfig/network.cobbler
echo "GATEWAY=$gateway" >> /etc/sysconfig/network.cobbler
rm -f /etc/sysconfig/network
mv /etc/sysconfig/network.cobbler /etc/sysconfig/network
    #end if
    ## =============================================================================
    ## Configure the system's primary hostname. This is also passed to anaconda, but
    ## anaconda doesn't seem to honour it in DHCP-setups.
    #if $hostname != ""

# set the hostname in the network configuration file
grep -v HOSTNAME /etc/sysconfig/network > /etc/sysconfig/network.cobbler
echo "HOSTNAME=$hostname" >> /etc/sysconfig/network.cobbler
rm -f /etc/sysconfig/network
mv /etc/sysconfig/network.cobbler /etc/sysconfig/network

# Also set the hostname now, some applications require it
# (e.g.: if we're connecting to Puppet before a reboot).
/bin/hostname $hostname
    #end if
    #if $enableipv6 == True
grep -v NETWORKING_IPV6 /etc/sysconfig/network > /etc/sysconfig/network.cobbler
echo "NETWORKING_IPV6=yes" >> /etc/sysconfig/network.cobbler
rm -f /etc/sysconfig/network
mv /etc/sysconfig/network.cobbler /etc/sysconfig/network
        #if $ipv6_autoconfiguration != ""
grep -v IPV6_AUTOCONF /etc/sysconfig/network > /etc/sysconfig/network.cobbler
            #if $ipv6_autoconfiguration == True
echo "IPV6_AUTOCONF=yes" >> /etc/sysconfig/network.cobbler
            #else
echo "IPV6_AUTOCONF=no" >> /etc/sysconfig/network.cobbler
            #end if
rm -f /etc/sysconfig/network
mv /etc/sysconfig/network.cobbler /etc/sysconfig/network
        #end if
        #if $ipv6_default_device != ""
grep -v IPV6_DEFAULTDEV /etc/sysconfig/network > /etc/sysconfig/network.cobbler
echo "IPV6_DEFAULTDEV=$ipv6_default_device" >> /etc/sysconfig/network.cobbler
rm -f /etc/sysconfig/network
mv /etc/sysconfig/network.cobbler /etc/sysconfig/network
        #end if
    #end if
    ## =============================================================================
    ## now create the config file for each interface
    #for $iname in $ikeys

# Start configuration for $iname
        ## create lots of variables to use later
        #set $idata                = $interfaces[$iname]
        #set $mac                  = $idata.get("mac_address", "").upper()
        #set $mtu                  = $idata.get("mtu", "")
        #set $static               = $idata.get("static", "")
        #set $ip                   = $idata.get("ip_address", "")
        #set $netmask              = $idata.get("netmask", "")
        #set $static_routes        = $idata.get("static_routes", "")
        #set $iface_type           = $idata.get("interface_type", "").lower()
        #set $iface_master         = $idata.get("interface_master", "")
        #set $bonding_opts         = $idata.get("bonding_opts", "")
        #set $bridge_opts          = $idata.get("bridge_opts", "").split(" ")
        #set $ipv6_address         = $idata.get("ipv6_address", "")
        #set $ipv6_secondaries     = $idata.get("ipv6_secondaries", "")
        #set $ipv6_mtu             = $idata.get("ipv6_mtu", "")
        #set $ipv6_default_gateway = $idata.get("ipv6_default_gateway", "")
        #set $ipv6_static_routes   = $idata.get("ipv6_static_routes", "")
        #set $devfile              = "/etc/sysconfig/network-scripts/cobbler/ifcfg-" + $iname
        #set $routesfile           = "/etc/sysconfig/network-scripts/cobbler/route-" + $iname
        #set $ipv6_routesfile      = "/etc/sysconfig/network-scripts/cobbler/route6-" + $iname
        ## determine if this interface is for a VLAN
        #if $vlanpattern.match($iname)
            #set $is_vlan = "true"
        #else
            #set $is_vlan = "false"
        #end if
        ## ===================================================================
        ## Things every interface get, no matter what
        ## ===================================================================
echo "DEVICE=$iname" > $devfile
echo "ONBOOT=yes" >> $devfile
            #if $mac != "" and $iface_type not in ("master","bond","bridge")
            ## virtual interfaces don't get MACs
echo "HWADDR=$mac" >> $devfile
IFNAME=\$(ifconfig -a | grep -i '$mac' | cut -d ' ' -f 1)
            ## Rename this interface in modprobe.conf
            ## FIXME: if both interfaces startwith eth this is wrong
if [ -f "/etc/modprobe.conf" ] && [ \$IFNAME ]; then
    grep \$IFNAME /etc/modprobe.conf | sed "s/\$IFNAME/$iname/" >> /etc/modprobe.conf.cobbler
    grep -v \$IFNAME /etc/modprobe.conf >> /etc/modprobe.conf.new
    rm -f /etc/modprobe.conf
    mv /etc/modprobe.conf.new /etc/modprobe.conf
fi
            #end if
        ## ===================================================================
        ## Actions based on interface_type
        ## ===================================================================
        #if $iface_type in ("master","bond")
            ## if this is a bonded interface, configure it in modprobe.conf
            #if $osversion == "rhel4"
if [ -f "/etc/modprobe.conf" ]; then
    echo "install $iname /sbin/modprobe bonding -o $iname $bonding_opts" >> /etc/modprobe.conf.cobbler
fi
            #else
            ## Add required entry to modprobe.conf
if [ -f "/etc/modprobe.conf" ]; then
    echo "alias $iname bonding" >> /etc/modprobe.conf.cobbler
fi
            #end if
            #if $bonding_opts != ""
cat >> $devfile << EOF
BONDING_OPTS="$bonding_opts"
EOF
            #end if
        #elif $iface_type in ("slave","bond_slave") and $iface_master != ""
echo "TYPE=Ethernet" >> $devfile
echo "SLAVE=yes" >> $devfile
echo "MASTER=$iface_master" >> $devfile
echo "HOTPLUG=no" >> $devfile
        #elif $iface_type == "bridge"
echo "TYPE=Bridge" >> $devfile
        #for $bridge_opt in $bridge_opts
            #if $bridge_opt.strip() != ""
echo "$bridge_opt" >> $devfile
            #end if
        #end for
        #elif $iface_type == "bridge_slave" and $iface_master != ""
echo "TYPE=Ethernet" >> $devfile
echo "BRIDGE=$iface_master" >> $devfile
echo "HOTPLUG=no" >> $devfile
        #else
echo "TYPE=Ethernet" >> $devfile
        #end if
        ## ===================================================================
        ## Actions based on static/dynamic configuration
        ## ===================================================================
        #if $static
            #if $mac == "" and $iface_type == ""
# WARNING! Configuring interfaces by their names only
#          is error-prone, and can cause issues if and when
#          the kernel gives an interface a different name
#          following a reboot/hardware changes.
            #end if
            #if $ip != "" and $iface_type not in ("slave","bond_slave","bridge_slave")
                ## Only configure static networking if an IP-address is configured
                ## and if the interface isn't slaved to another interface (bridging or bonding)
echo "BOOTPROTO=static" >> $devfile
echo "IPADDR=$ip" >> $devfile
                #if $netmask == ""
                    ## Default to 255.255.255.0?
                    #set $netmask = "255.255.255.0"
                #end if
echo "NETMASK=$netmask" >> $devfile
            #else
                ## Leave the interface unconfigured
                ## we don't have enough info for static configuration
echo "BOOTPROTO=none" >> $devfile
            #end if
            #if $enableipv6 == True and $ipv6_autoconfiguration == False
                #if $ipv6_address != ""
echo "IPV6INIT=yes" >> $devfile
echo "IPV6ADDR=$ipv6_address" >> $devfile
                #end if
                #if $ipv6_secondaries != ""
                    #set ipv6_secondaries = ' '.join(ipv6_secondaries)
                    ## The quotes around the ipv6 ip's need to be here
echo "IPV6ADDR_SECONDARIES=\"$ipv6_secondaries\"" >> $devfile
                #end if
                #if $ipv6_mtu != ""
echo "IPV6MTU=$ipv6_mtu" >> $devfile
                #end if
                #if $ipv6_default_gateway != ""
echo "IPV6_DEFAULTGW=$ipv6_default_gateway" >> $devfile
                #end if
            #end if
        #else
            ## this is a DHCP interface, much less work to do
echo "BOOTPROTO=dhcp" >> $devfile
        #end if
        ## ===================================================================
        ## VLAN configuration
        ## ===================================================================
        #if $is_vlan == "true"
echo "VLAN=yes" >> $devfile
echo "ONPARENT=yes" >> $devfile
        #end if
        ## ===================================================================
        ## Optional configuration stuff
        ## ===================================================================
        #if $mtu != ""
echo "MTU=$mtu" >> $devfile
        #end if
        ## ===================================================================
        ## Non-slave DNS configuration, when applicable
        ## ===================================================================
        ## If the interface is anything but a slave then add DNSn entry
        #if $iface_type.lower() not in ("slave","bond_slave","bridge_slave")
            #set $nct = 0
            #for $nameserver in $name_servers
                #set $nct = $nct + 1
echo "DNS$nct=$nameserver" >> $devfile
            #end for
        #end if
        ## ===================================================================
        ## Interface route configuration
        ## ===================================================================
        #for $route in $static_routes
            #set routepattern = $re.compile("[0-9/.]+:[0-9.]+")
            #if $routepattern.match($route)
                #set $routebits = $route.split(":")
                #set [$network, $router] = $route.split(":")
echo "$network via $router" >> $routesfile
            #else
# Warning: invalid route "$route"
            #end if
        #end for
        #if $enableipv6 == True
            #for $route in $ipv6_static_routes
                #set routepattern = $re.compile("[0-9a-fA-F:/]+,[0-9a-fA-F:]+")
                #if $routepattern.match($route)
                    #set $routebits = $route.split(",")
                    #set [$network, $router] = $route.split(",")
echo "$network via $router dev $iname" >> $ipv6_routesfile
                #else
# Warning: invalid ipv6 route "$route"
                #end if
            #end for
        #end if
        ## ===================================================================
        ## Done with this interface
        ## ===================================================================
        #set $i = $i + 1
# End configuration for $iname
    #end for
    ## =============================================================================
    ## Configure name server search path in /etc/resolv.conf
    #set $num_ns = $len($name_servers)
    #set $num_ns_search = $len($name_servers_search)
    #if $num_ns_search > 0

sed -i -e "/^search /d" /etc/resolv.conf
echo -n "search " >>/etc/resolv.conf
        #for $nameserversearch in $name_servers_search
echo -n "$nameserversearch " >>/etc/resolv.conf
        #end for
echo "" >>/etc/resolv.conf
    #end if
    ## =============================================================================
    ## Configure name servers in /etc/resolv.conf
    #if $num_ns > 0

sed -i -e "/^nameserver /d" /etc/resolv.conf
        #for $nameserver in $name_servers
echo "nameserver $nameserver" >>/etc/resolv.conf
        #end for
    #end if

## Disable all eth interfaces by default before overwriting
## the old files with the new ones in the working directory
## This stops unneccesary (and time consuming) DHCP queries
## during the network initialization
sed -i 's/ONBOOT=yes/ONBOOT=no/g' /etc/sysconfig/network-scripts/ifcfg-eth*

## Move all staged files to their final location
rm -f /etc/sysconfig/network-scripts/ifcfg-*
mv /etc/sysconfig/network-scripts/cobbler/* /etc/sysconfig/network-scripts/
rm -r /etc/sysconfig/network-scripts/cobbler
if [ -f "/etc/modprobe.conf" ]; then
cat /etc/modprobe.conf.cobbler >> /etc/modprobe.conf
rm -f /etc/modprobe.conf.cobbler
fi
#end if
# End post_install_network_config generated code

#if $str($getVar('func_auto_setup','')) == "1"
# Start func registration section

/sbin/chkconfig --level 345 funcd on

cat <<EOFM > /etc/func/minion.conf
[main]
log_level = INFO
acl_dir = /etc/func/minion-acl.d

listen_addr =
listen_port = 51234
EOFM

cat <<EOCM > /etc/certmaster/minion.conf
[main]
certmaster = $func_master
certmaster_port = 51235
log_level = DEBUG
cert_dir = /etc/pki/certmaster
EOCM

# End func registration section
#end if
#if $str($getVar('puppet_auto_setup','')) == "1"
# Abhay Tmp fix, copy the init.d script for puppet agent. This should be included in puppet package install.
wget -O /etc/init.d/puppet "http://$server:$http_port/cobbler/aux/puppet"
chmod 755 /etc/init.d/puppet
echo "[agent]" >> /etc/puppet/puppet.conf
echo "    pluginsync = true" >> /etc/puppet/puppet.conf
# generate puppet certificates and trigger a signing request, but
# don't wait for signing to complete
/usr/sbin/puppetd --test --waitforcert 0

# turn puppet service on for reboot
/sbin/chkconfig puppet on

#end if
# Start download cobbler managed config files (if applicable)
#for $tkey, $tpath in $template_files.items()
    #set $orig = $tpath
    #set $tpath = $tpath.replace("_","__").replace("/","_")
    #if $getVar("system_name","") != ""
        #set $ttype = "system"
        #set $tname = $system_name
    #else
        #set $ttype = "profile"
        #set $tname = $profile_name
    #end if
    #set $turl = "http://"+$http_server+"/cblr/svc/op/template/"+$ttype+"/"+$tname+"/path/"+$tpath
#if $orig.startswith("/")
mkdir -p `dirname $orig`
wget "$turl" --output-document="$orig"
#end if
#end for
# End download cobbler managed config files (if applicable)
# Start koan environment setup
echo "export COBBLER_SERVER=$server" > /etc/profile.d/cobbler.sh
echo "setenv COBBLER_SERVER $server" > /etc/profile.d/cobbler.csh
# End koan environment setup
# begin Red Hat management server registration
#if $redhat_management_type != "off" and $redhat_management_key != ""
mkdir -p /usr/share/rhn/
   #if $redhat_management_type == "site"
      #set $mycert_file = "RHN-ORG-TRUSTED-SSL-CERT"
      #set $mycert = "/usr/share/rhn/" + $mycert_file
wget http://$redhat_management_server/pub/RHN-ORG-TRUSTED-SSL-CERT -O $mycert   
perl -npe 's/RHNS-CA-CERT/$mycert_file/g' -i /etc/sysconfig/rhn/*  
   #end if
   #if $redhat_management_type == "hosted"
      #set $mycert = "/usr/share/rhn/RHNS-CA-CERT"
   #end if 
   #set $endpoint = "https://%s/XMLRPC" % $redhat_management_server
rhnreg_ks --serverUrl=$endpoint --sslCACert=$mycert --activationkey=$redhat_management_key
#else
# not configured to register to any Red Hat management server (ok)
#end if
# end Red Hat management server registration
# Begin cobbler registration
#if $getVar('system_name','') == ''
#if $str($getVar('register_new_installs','')) in [ "1", "true", "yes", "y" ]
if [ -f "/usr/bin/cobbler-register" ]; then
    cobbler-register --server=$server --fqdn '*AUTO*' --profile=$profile_name --batch
fi
#else
# cobbler registration is disabled in /etc/cobbler/settings
#end if
#else
# skipping for system-based installation
#end if
# End cobbler registration
#if $str($getVar('anamon_enabled','')) == "1"

## install anamon script
wget -O /usr/local/sbin/anamon "http://$server:$http_port/cobbler/aux/anamon"
## install anamon system service
wget -O /etc/rc.d/init.d/anamon "http://$server:$http_port/cobbler/aux/anamon.init"

## adjust permissions
chmod 755 /etc/rc.d/init.d/anamon /usr/local/sbin/anamon
test -d /selinux && restorecon /etc/rc.d/init.d/anamon /usr/local/sbin/anamon

## enable the script
chkconfig --add anamon

## configure anamon service
cat << __EOT__ > /etc/sysconfig/anamon
COBBLER_SERVER="$server"
COBBLER_PORT="$http_port"
COBBLER_NAME="$name"
LOGFILES="/var/log/boot.log /var/log/messages /var/log/dmesg"
__EOT__

#end if
## Temporary workarounds for getting thru for now
#if $getVar('contrailTempWorkarounds','') == "YES"
mkdir /cs-shared
echo "10.84.5.100:/cs-shared   /cs-shared      nfs     rw,intr,bg,soft     0 0" >> /etc/fstab
mkdir /var/crashes
chmod 777 /var/crashes
echo "kernel.core_pattern = /var/crashes/core.%e.%p.%h.%t" >> /etc/sysctl.conf
echo "root             -" >> /etc/security/limits.conf
echo "stack            -" >> /etc/security/limits.conf
mkdir -p /etc/yum.repos.d/old
mv /etc/yum.repos.d/f* /etc/yum.repos.d/old/

mv /etc/mail/sendmail.cf /etc/mail/sendmail.cf.orig
wget -O /etc/mail/sendmail.cf "http://$server/contrail_target_files/sendmail.cf"

## Debug stuff
cat /etc/contrail/agent.conf

cat /etc/contrail/agent_param

cat /etc/sysconfig/network-scripts/ifcfg-vhost0


cat /etc/sysconfig/network-scripts/ifcfg-$(cat /etc/contrail/default_if)

#end if
## yum -y install contrail-agent
$SNIPPET('kickstart_done')
%end
