import argparse
import platform
import os
import socket
import netifaces
import netaddr
import subprocess
import struct
import tempfile
import xml.etree.ElementTree as ET
import commands

def find_gateway(dev):
    gateway = ''
    cmd = "netstat -rn | grep ^\"0.0.0.0\" | grep %s | awk '{ print $2 }'" % \
        dev
    gateway = subprocess.check_output(cmd, shell=True).strip()
    return gateway
# end find_gateway


def get_dns_servers(dev):
    cmd = "grep \"^nameserver\\>\" /etc/resolv.conf | awk  '{print $2}'"
    dns_list = subprocess.check_output(cmd, shell=True)
    return dns_list.split()
# end get_dns_servers


def get_domain_search_list():
    domain_list = ''
    cmd = "grep ^\"search\" /etc/resolv.conf | awk '{$1=\"\";print $0}'"
    domain_list = subprocess.check_output(cmd, shell=True).strip()
    if not domain_list:
        cmd = "grep ^\"domain\" /etc/resolv.conf | awk '{$1=\"\"; print $0}'"
        domain_list = subprocess.check_output(cmd, shell=True).strip()
    return domain_list


def get_if_mtu(dev):
    cmd = "ifconfig %s | grep mtu | awk '{ print $NF }'" % dev
    mtu = subprocess.check_output(cmd, shell=True).strip()
    if not mtu:
        # for debian
        cmd = "ifconfig %s | grep MTU | sed 's/.*MTU.\([0-9]\+\).*/\1/g'" % dev
        mtu = subprocess.check_output(cmd, shell=True).strip()
    if mtu and mtu != '1500':
        return mtu
    return ''
# end if_mtu


def get_secondary_device(primary):
    for i in netifaces.interfaces ():
        try:
            if i == 'pkt1':
                continue
            if i == primary:
                continue
            if i == 'vhost0':
                continue
            if not netifaces.ifaddresses (i).has_key (netifaces.AF_INET):
                return i
        except ValueError,e:
                print "Skipping interface %s" % i
    raise RuntimeError, '%s not configured, rerun w/ --physical_interface' % ip


def get_device_by_ip(ip):
    for i in netifaces.interfaces():
        try:
            if i == 'pkt1':
                continue
            if netifaces.AF_INET in netifaces.ifaddresses(i):
                if ip == netifaces.ifaddresses(i)[netifaces.AF_INET][0][
                        'addr']:
                    if i == 'vhost0':
                        print "vhost0 is already present!"
                    return i
        except ValueError, e:
            print "Skipping interface %s" % i
    raise RuntimeError('%s not configured, rerun w/ --physical_interface' % ip)
# end get_device_by_ip


def rewrite_ifcfg_file(temp_dir_name, filename, dev, prsv_cfg):
    bond = False
    mac = ''

    if os.path.isdir('/sys/class/net/%s/bonding' % dev):
        bond = True
    # end if os.path.isdir...

    mac = netifaces.ifaddresses(dev)[netifaces.AF_LINK][0]['addr']
    ifcfg_file = '/etc/sysconfig/network-scripts/ifcfg-%s' % (dev)
    if not os.path.isfile(ifcfg_file):
        ifcfg_file = temp_dir_name + '/ifcfg-' + dev
        with open(ifcfg_file, 'w') as f:
            f.write('''#Contrail %s
TYPE=Ethernet
ONBOOT=yes
DEVICE="%s"
USERCTL=yes
NM_CONTROLLED=no
HWADDR=%s
''' % (dev, dev, mac))
            for dcfg in prsv_cfg:
                f.write(dcfg + '\n')
            f.flush()
    fd = open(ifcfg_file)
    f_lines = fd.readlines()
    fd.close()
    new_f_lines = []
    remove_items = ['IPADDR', 'NETMASK', 'PREFIX', 'GATEWAY', 'HWADDR',
                    'DNS1', 'DNS2', 'BOOTPROTO', 'NM_CONTROLLED', '#Contrail']

    remove_items.append('DEVICE')
    new_f_lines.append('#Contrail %s\n' % dev)
    new_f_lines.append('DEVICE=%s\n' % dev)

    for line in f_lines:
        found = False
        for text in remove_items:
            if text in line:
                found = True
        if not found:
            new_f_lines.append(line)

    new_f_lines.append('NM_CONTROLLED=no\n')
    if bond:
        new_f_lines.append('SUBCHANNELS=1,2,3\n')
    else:
        new_f_lines.append('HWADDR=%s\n' % mac)

    fdw = open(filename, 'w')
    fdw.writelines(new_f_lines)
    fdw.close()
# end rewrite_ifcfg_file


def migrate_routes(device):
    '''
    Sample output of /proc/net/route :
    Iface   Destination     Gateway         Flags   RefCnt  Use     Metric \
    Mask            MTU     Window  IRTT
    p4p1    00000000        FED8CC0A        0003    0       0       0      \
    00000000        0       0       0
    '''
    with open('/etc/sysconfig/network-scripts/route-vhost0',
              'w') as route_cfg_file:
        for route in open('/proc/net/route', 'r').readlines():
            if route.startswith(device):
                route_fields = route.split()
                destination = int(route_fields[1], 16)
                gateway = int(route_fields[2], 16)
                flags = int(route_fields[3], 16)
                mask = int(route_fields[7], 16)
                if flags & 0x2:
                    if destination != 0:
                        route_cfg_file.write(
                            socket.inet_ntoa(struct.pack('I', destination)))
                        route_cfg_file.write(
                            '/' + str(bin(mask).count('1')) + ' ')
                        route_cfg_file.write('via ')
                        route_cfg_file.write(
                            socket.inet_ntoa(struct.pack('I', gateway)) + ' ')
                        route_cfg_file.write('dev vhost0')
                    # end if detination...
                # end if flags &...
            # end if route.startswith...
        # end for route...
    # end with open...
# end def migrate_routes



def _rewrite_net_interfaces_file(temp_dir_name, dev, mac, vhost_ip, netmask, gateway_ip,
							non_mgmt_ip):

    result,status = commands.getstatusoutput('grep \"iface vhost0\" /etc/network/interfaces')
    if status == 0 :
        print "Interface vhost0 is already present in /etc/network/interfaces"
        print "Skipping rewrite of this file"
        return
    #endif

    vlan = False
    if os.path.isfile ('/proc/net/vlan/%s' % dev):
        vlan_info = open('/proc/net/vlan/config').readlines()
        match  = re.search('^%s.*\|\s+(\S+)$'%dev, "\n".join(vlan_info), flags=re.M|re.I)
        if not match:
            raise RuntimeError, 'Configured vlan %s is not found in /proc/net/vlan/config'%dev
        phydev = match.group(1)
        vlan = True

    # Replace strings matching dev to vhost0 in ifup and ifdown parts file
    # Any changes to the file/logic with static routes has to be
    # reflected in setup-vnc-static-routes.py too
    ifup_parts_file = os.path.join(os.path.sep, 'etc', 'network', 'if-up.d', 'routes')
    ifdown_parts_file = os.path.join(os.path.sep, 'etc', 'network', 'if-down.d', 'routes')

    if os.path.isfile(ifup_parts_file) and os.path.isfile(ifdown_parts_file):
        commands.getstatusoutput("sudo sed -i 's/%s/vhost0/g' %s" %(dev, ifup_parts_file))
        commands.getstatusoutput("sudo sed -i 's/%s/vhost0/g' %s" %(dev, ifdown_parts_file))

    temp_intf_file = '%s/interfaces' %(temp_dir_name)
    commands.getstatusoutput("cp /etc/network/interfaces %s" %(temp_intf_file))
    with open('/etc/network/interfaces', 'r') as fd:
        cfg_file = fd.read()

    if not non_mgmt_ip:
        # remove entry from auto <dev> to auto excluding these pattern
        # then delete specifically auto <dev> 
        commands.getstatusoutput("sed -i '/auto %s/,/auto/{/auto/!d}' %s" %(dev, temp_intf_file))
        commands.getstatusoutput("sed -i '/auto %s/d' %s" %(dev, temp_intf_file))
        # add manual entry for dev
        commands.getstatusoutput("echo 'auto %s' >> %s" %(dev, temp_intf_file))
        commands.getstatusoutput("echo 'iface %s inet manual' >> %s" %(dev, temp_intf_file))
        commands.getstatusoutput("echo '    pre-up ifconfig %s up' >> %s" %(dev, temp_intf_file))
        commands.getstatusoutput("echo '    post-down ifconfig %s down' >> %s" %(dev, temp_intf_file))
        if vlan:
            commands.getstatusoutput("echo '    vlan-raw-device %s' >> %s" %(phydev, temp_intf_file))
        if 'bond' in dev.lower():
            iters = re.finditer('^\s*auto\s', cfg_file, re.M)
            indices = [match.start() for match in iters]
            matches = map(cfg_file.__getslice__, indices, indices[1:] + [len(cfg_file)])
            for each in matches:
                each = each.strip()
                if re.match('^auto\s+%s'%dev, each):
                    string = ''
                    for lines in each.splitlines():
                        if 'bond-' in lines:
                            string += lines+os.linesep
                    commands.getstatusoutput("echo '%s' >> %s" %(string, temp_intf_file))
                else:
                    continue
        commands.getstatusoutput("echo '' >> %s" %(temp_intf_file))
    else:
        #remove ip address and gateway
        commands.getstatusoutput("sed -i '/iface %s inet static/, +2d' %s" % (dev, temp_intf_file))
        commands.getstatusoutput("sed -i '/auto %s/ a\iface %s inet manual\\n    pre-up ifconfig %s up\\n    post-down ifconfig %s down\' %s"% (dev, dev, dev, dev, temp_intf_file))

    # populte vhost0 as static
    commands.getstatusoutput("echo '' >> %s" %(temp_intf_file))
    commands.getstatusoutput("echo 'auto vhost0' >> %s" %(temp_intf_file))
    commands.getstatusoutput("echo 'iface vhost0 inet static' >> %s" %(temp_intf_file))
    commands.getstatusoutput("echo '    pre-up %s/if-vhost0' >> %s" %('/opt/contrail/bin', temp_intf_file))
    commands.getstatusoutput("echo '    netmask %s' >> %s" %(netmask, temp_intf_file))
    commands.getstatusoutput("echo '    network_name application' >> %s" %(temp_intf_file))
    if vhost_ip:
        commands.getstatusoutput("echo '    address %s' >> %s" %(vhost_ip, temp_intf_file))
    if (not non_mgmt_ip) and gateway_ip:
        commands.getstatusoutput("echo '    gateway %s' >> %s" %(gateway_ip, temp_intf_file))

    domain = get_domain_search_list()
    if domain:
        commands.getstatusoutput("echo '    dns-search %s' >> %s" %(domain, temp_intf_file))
    dns_list = get_dns_servers(dev)
    if dns_list:
        commands.getstatusoutput("echo -n '    dns-nameservers' >> %s" %(temp_intf_file))
        for dns in dns_list:
            commands.getstatusoutput("echo -n ' %s' >> %s" %(dns, temp_intf_file))
    commands.getstatusoutput("echo '\n' >> %s" %(temp_intf_file))

    # move it to right place
    commands.getstatusoutput("sudo mv -f %s /etc/network/interfaces" %(temp_intf_file))

    #end _rewrite_net_interfaces_file




def rewrite_net_interfaces_file(temp_dir_name, dev, mac, vhost_ip, netmask, gateway_ip, non_mgmt_ip):
    temp_intf_file = '%s/interfaces' %(temp_dir_name)

    # Save original network interfaces file
    if (os.path.isfile("/etc/network/interfaces")):
        subprocess.call("mv -f /etc/network/interfaces /etc/network/interfaces-orig", shell=True)
	output = subprocess.Popen(['sed', '/'+dev+'/d' ,'/etc/network/interfaces-orig'], stdout=subprocess.PIPE).communicate()[0]
        

    # replace with dev as manual and vhost0 as static
    with open(temp_intf_file, 'w') as f:
	f.write("\n")
        f.write("auto vhost0\n")
        f.write("iface vhost0 inet static\n")
        f.write("    pre-up /opt/contrail/bin/if-vhost0\n")
        f.write("    netmask %s\n" %(netmask))
        f.write("    network_name application\n")
        if vhost_ip:
            f.write("    address %s\n" %(vhost_ip))
        if gateway_ip:
            f.write("    gateway %s\n" %(gateway_ip))
        domain = get_domain_search_list()
        if domain: 
            f.write("    dns-search %s\n" %(domain))
        dns_list = get_dns_servers(dev)
        if dns_list:
            f.write("    dns-nameservers")
            for dns in dns_list:
                f.write(" %s" %(dns))
            f.write("\n")

	if not non_mgmt_ip:
	    # remove entry from auto <dev> to auto excluding these pattern
	    # then delete specifically auto <dev>
	    #local("sed -i '/auto %s/,/auto/{/auto/!d}' %s" %(dev, temp_intf_file))
	    #local("sed -i '/auto %s/d' %s" %(dev, temp_intf_file))
	    # add manual entry for dev
	    f.write("auto %s\n" %(dev))
	    f.write("iface %s inet manual\n" %(dev))
	    f.write("    pre-up ifconfig %s up\n" %(dev))
	    f.write("    post-down ifconfig %s down\n" %(dev))
	    f.write("\n")
            f.write(output)
    # move it to right place
    cmd = "mv -f %s /etc/network/interfaces" %(temp_intf_file)
    subprocess.call(cmd, shell=True)

#end rewrite_net_interfaces_file


def replace_discovery_server(agent_elem, discovery_ip, ncontrols):
    for srv in agent_elem.findall('discovery-server'):
        agent_elem.remove(srv)

    pri_dss_elem = ET.Element('discovery-server')
    pri_dss_ip = ET.SubElement(pri_dss_elem, 'ip-address')
    pri_dss_ip.text = '%s' % (discovery_ip)

    xs_instances = ET.SubElement(pri_dss_elem, 'control-instances')
    xs_instances.text = '%s' % (ncontrols)
    agent_elem.append(pri_dss_elem)

# end _replace_discovery_server


def update_dev_net_config_files(compute_ip, physical_interface,
                                non_mgmt_ip, non_mgmt_gw,
                                collector_ip, discovery_ip, ncontrols,
                                macaddr):
    dist = platform.dist()[0]
    # add /dev/net/tun in cgroup_device_acl needed for type=ethernet interfaces
    return_code = subprocess.call(
        "grep -q '^cgroup_device_acl' /etc/libvirt/qemu.conf", shell=True)
    if return_code == 1:
        if ((dist.lower() == 'centos') or
            (dist.lower() == 'fedora')):
            subprocess.call(
                'echo "clear_emulator_capabilities = 1" >> '
                '/etc/libvirt/qemu.conf', shell=True)
            subprocess.call(
                'echo \'user = "root"\' >> /etc/libvirt/qemu.conf', shell=True)
            subprocess.call(
                'echo \'group = "root"\' >> /etc/libvirt/qemu.conf',
                shell=True)
        subprocess.call(
            'echo \'cgroup_device_acl = [\' >> /etc/libvirt/qemu.conf',
            shell=True)
        subprocess.call(
            'echo \'    "/dev/null", "/dev/full", "/dev/zero",\' >> '
            '/etc/libvirt/qemu.conf', shell=True)
        subprocess.call(
            'echo \'    "/dev/random", "/dev/urandom",\' >> '
            '/etc/libvirt/qemu.conf', shell=True)
        subprocess.call(
            'echo \'    "/dev/ptmx", "/dev/kvm", "/dev/kqemu",\' >> '
            '/etc/libvirt/qemu.conf', shell=True)
        subprocess.call(
            'echo \'    "/dev/rtc", "/dev/hpet","/dev/net/tun",\' >> '
            '/etc/libvirt/qemu.conf', shell=True)
        subprocess.call('echo \']\' >> /etc/libvirt/qemu.conf', shell=True)

    multi_net = False
    vhost_ip = compute_ip
    if non_mgmt_ip:
        if non_mgmt_ip != compute_ip:
            multi_net = True
            vhost_ip = non_mgmt_ip
        else:
            non_mgmt_ip = None
    dev = None
    compute_dev = None
    if physical_interface:
        if physical_interface in netifaces.interfaces():
            dev = physical_interface
        else:
            raise KeyError('Interface %s in present' % (
                physical_interface))
    else:
        # deduce the phy interface from ip, if configured
        dev = get_device_by_ip(vhost_ip)
        if multi_net:
            compute_dev = get_device_by_ip(compute_ip)

    if dev and dev != 'vhost0':
        netmask = netifaces.ifaddresses(dev)[netifaces.AF_INET][0][
            'netmask']
        if multi_net:
            gateway = non_mgmt_gw
        else:
            gateway = find_gateway(dev)
        cidr = str(netaddr.IPNetwork('%s/%s' % (vhost_ip, netmask)))

        cmd = "sed 's/COLLECTOR=.*/COLLECTOR=%s/g;s/dev=.*/dev=%s/g'" \
            " /etc/contrail/agent_param.tmpl >" \
            " /etc/contrail/agent_param" % (
                collector_ip, dev)
        subprocess.call(cmd, shell=True)

        # set agent conf with control node IPs, first remove old ones
        agent_tree = ET.parse('/etc/contrail/rpm_agent.conf')
        agent_root = agent_tree.getroot()
        agent_elem = agent_root.find('agent')
        vhost_elem = agent_elem.find('vhost')
        for vip in vhost_elem.findall('ip-address'):
            vhost_elem.remove(vip)
        vip = ET.Element('ip-address')
        vip.text = cidr
        vhost_elem.append(vip)
        for gw in vhost_elem.findall('gateway'):
            vhost_elem.remove(gw)
        if gateway:
            gw = ET.Element('gateway')
            gw.text = gateway
            vhost_elem.append(gw)

        ethpt_elem = agent_elem.find('eth-port')
        for pn in ethpt_elem.findall('name'):
            ethpt_elem.remove(pn)
        pn = ET.Element('name')
        pn.text = dev
        ethpt_elem.append(pn)

        replace_discovery_server(agent_elem, discovery_ip, ncontrols)

        control_elem = ET.Element('control')
        control_ip_elem = ET.Element('ip-address')
        control_ip_elem.text = compute_ip
        control_elem.append(control_ip_elem)
        agent_elem.append(control_elem)

        agent_tree = agent_tree.write('/etc/contrail/agent.conf')

        temp_dir_name = tempfile.mkdtemp()
        # make ifcfg-vhost0
        if dist.lower() == 'centos' or dist.lower() == 'fedora':
            with open('%s/ifcfg-vhost0' % temp_dir_name, 'w') as f:
                f.write('''#Contrail vhost0
DEVICE=vhost0
ONBOOT=yes
BOOTPROTO=none
IPV6INIT=no
USERCTL=yes
IPADDR=%s
NETMASK=%s
NM_CONTROLLED=no
#NETWORK MANAGER BUG WORKAROUND
SUBCHANNELS=1,2,3
''' % (vhost_ip, netmask))
                # Don't set gateway and DNS on vhost0 if on non-mgmt network
                if not multi_net:
                    if gateway:
                        f.write('GATEWAY=%s\n' % (gateway))
                    dns_list = get_dns_servers(dev)
                    for i, dns in enumerate(dns_list):
                        f.write('DNS%d=%s\n' % (i + 1, dns))
                    domain_list = get_domain_search_list()
                    if domain_list:
                        f.write('DOMAIN="%s"\n' % domain_list)

                prsv_cfg = []
                mtu = get_if_mtu(dev)
                if mtu:
                    dcfg = 'MTU=%s' % str(mtu)
                    f.write(dcfg + '\n')
                    prsv_cfg.append(dcfg)
                f.flush()
            cmd = "mv %s/ifcfg-vhost0 /etc/sysconfig/" \
                "network-scripts/ifcfg-vhost0" % (
                    temp_dir_name)
            subprocess.call(cmd, shell=True)
            # make ifcfg-$dev
            if not os.path.isfile(
                    '/etc/sysconfig/network-scripts/ifcfg-%s.rpmsave' % dev):
                cmd = "cp /etc/sysconfig/network-scripts/ifcfg-%s \
                   /etc/sysconfig/network-scripts/ifcfg-%s.rpmsave" % (dev, dev)
                subprocess.call(cmd, shell=True)
            rewrite_ifcfg_file(temp_dir_name, '%s/ifcfg-%s' %
                               (temp_dir_name, dev), dev, prsv_cfg)

            if multi_net:
                migrate_routes(dev)
            cmd = "mv -f %s/ifcfg-%s /etc/contrail/" % (temp_dir_name, dev)
            subprocess.call(cmd, shell=True)
            # cmd = "cp -f /etc/contrail/ifcfg-%s" \
            #	" /etc/sysconfig/network-scripts" % (dev)
            #subprocess.call(cmd, shell=True)
        # end if "centos" or "fedora"
        if ((dist.lower() == "ubuntu") or
            (dist.lower() == "debian")):
	    _rewrite_net_interfaces_file(temp_dir_name, dev, macaddr,
                                        vhost_ip, netmask, gateway, non_mgmt_ip)
    else:
        # allow for updating anything except self-ip/gw and eth-port
        cmd = "sed -i 's/COLLECTOR=.*/COLLECTOR=%s/g'" \
            " /etc/contrail/agent_param" % (
                collector_ip)
        subprocess.call(cmd, shell=True)

        agent_tree = ET.parse('/etc/contrail/agent.conf')
        agent_root = agent_tree.getroot()
        agent_elem = agent_root.find('agent')
        replace_discovery_server(agent_elem, discovery_ip, ncontrols)

        agent_tree = agent_tree.write('/etc/contrail/agent.conf')
    # end if-else vhost0
# end update_dev_net_config_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compute_ip", help="IP address of compute node")
    parser.add_argument("--collector_ip", help="IP address of collector node")
    parser.add_argument("--discovery_ip", help="IP address of config node")
    parser.add_argument("--ncontrols", help="number of control nodes")
    parser.add_argument("--physical_interface",
                        help="name of the physical interface on the compute"
                        " node",
                        default="")
    parser.add_argument("--non_mgmt_ip",
                        help="non mgmt ip address of the compute node",
                        default="")
    parser.add_argument("--non_mgmt_gw",
                        help="non mgmt gw of the compute node",
                        default="")
    parser.add_argument("--mac",
                        help="mac address of the interface",
                        default="")
    args = parser.parse_args()
    update_dev_net_config_files(args.compute_ip, args.physical_interface,
                                args.non_mgmt_ip, args.non_mgmt_gw,
                                args.collector_ip, args.discovery_ip,
                                args.ncontrols, args.mac)
# end main

if __name__ == "__main__":
    import cgitb
    cgitb.enable(format='text')
    main()
# end if __name__
