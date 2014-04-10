#!/usr/bin/python
import sys
import ConfigParser
import time
import commands
import argparse
import ast

from vnc_api.vnc_api import *
from vnc_api.gen.resource_xsd import RouteType
from vnc_api.gen.resource_xsd import RouteTableType
from vnc_api.gen.resource_client import InterfaceRouteTable

from novaclient import client as mynovaclient
from neutronclient.neutron import client
from neutronclient.client import HTTPClient

import sys

class WinTSetup(object) :
    # Makes client connections to nova, neutron and vnc-api
    def __init__(self,
                 ostack_ip, ostack_user, ostack_password, ostack_project,
                 neutron_port, api_server_ip, api_server_port) :

        print 'Initializing connection to to Nova, Neutron and API'
        try :
            auth_url='http://'+ ostack_ip+':5000/v2.0'
            self.nova_client=mynovaclient.Client('2', username = ostack_user,
                                                 project_id = ostack_project,
                                                 api_key = ostack_password,
                                                 auth_url = auth_url)
        except Exception,e :
            print 'Error making client connection to Nova... Exiting '
            print e
            sys.exit(1)

        try :
            httpclient = HTTPClient(username = ostack_user,
                                    tenant_name = ostack_project,
                                    password = ostack_password,
                                    auth_url = auth_url)
            httpclient.authenticate()

            OS_URL = 'http://%s:%s/' %(api_server_ip, neutron_port)
            OS_TOKEN = httpclient.auth_token
            self.neutron_client = client.Client('2.0', endpoint_url=OS_URL,
                                                token = OS_TOKEN)
        except Exception,e :
            print 'Error making client connection to Neutron... Exiting '
            print e
            sys.exit(1)

        try :
            self.vnc_client = VncApi(ostack_user, ostack_password,
                                     ostack_project, api_server_ip,
                                     api_server_port, '/')

            s = 'default-domain:'+ ostack_project
            fq_name = s.split(':')
            self.project_obj = self.vnc_client.project_read(fq_name = fq_name)
        except Exception,e :
            print 'Error making client connection to Neutron... Exiting '
            print e
            sys.exit(1)

        print 'Nova, Neutron and API server connection established successfully'
    # def __init__

    # Find virtual-network for a project and vn-name
    def FindVn(self, ostack_project, vn_name) :
        try :
            net_list = self.neutron_client.list_networks()
        except Exception,e :
            print 'Error querying neutron net-list.... Exiting'
            print e
            sys.exit(2)

        for (x,y,z) in [(network['name'], network['id'],
            network['contrail:fq_name'])
            for network in net_list['networks']]:
                if ostack_project in z and vn_name == x :
                    return self.neutron_client.show_network(network=y)
        return None
    # def FindVn

    # Create a VN
    def EnsureVn(self, ostack_project, vn_name, subnet) :
        print 'Creating virtual-network ', vn_name
        net = self.FindVn(ostack_project, vn_name)
        if net == None :
            net_req = {'name': vn_name}
            try:
                net = self.neutron_client.create_network({'network': net_req})
            except Exception,e:
                print 'Error creating network ', vn_name
                print e
                sys.exit(2)
            print 'Network ' + vn_name + ' created successfully'
        else :
            s = 'Network ' + vn_name + ' already present'
            print s

        return net
    # def EnsureVn

    def EnsureIpam(self, project, name) :
        print 'Creating IPAM ', project, ':', name
        try : 
            ipam_rsp = self.neutron_client.list_ipams()
        except Exception,e :
            print 'Error quering ipam list '
            print e
            sys.exit(2)

        ipam_obj = None
        for ipam in ipam_rsp['ipams'] :
            if name in ipam['fq_name'] and project in ipam['fq_name'] :
                ipam_obj = ipam
                break
        if ipam_obj != None :
            print 'IPAM ', project, ':', name, ' already present'
            return ipam_obj

        try :
            ipam_req = {'name': name}
            ipam_rsp = self.neutron_client.create_ipam({'ipam' : ipam_req})
            print 'IPAM ', project, ':', name, ' created successfully'
            return ipam_rsp['ipam']
        except Exception,e :
            print 'Error creating ipam ', name
            print e
            sys.exit(2)
        return None
    # def EnsureIpam

    def EnsureSubnet(self, net, net_uuid, subnet, ipam) :
        print 'Creating subnet ', subnet
        if len(net['network']['subnets']) == 0 :
            subnet_req = {'network_id': net_uuid,
                          'cidr': subnet,
                          'ip_version': 4,
                          'contrail:ipam_fq_name': ipam['fq_name']}
            try :
                self.neutron_client.create_subnet({'subnet': subnet_req})
            except Exception,e :
                print 'Error creating subnet ', subnet
                print e
                sys.exit(2)
            print 'Subnet ', subnet, ' created successfully'
        else :
            print 'Subnet ', subnet, ' already present'
    # def EnsureSubnet
    
    # Get the image UUID
    def GetImage(self, image_name, openstack_ip, image_file) :
        try:
            image = self.nova_client.images.find(name=image_name)
        except Exception,e:
            cmd = '/bin/bash -c \"export OS_IMAGE_URL=http://' 
            cmd += openstack_ip + ':9292/;'
            cmd += 'source /etc/contrail/openstackrc; glance add name='
            cmd += image_name
            cmd += ' is_public=true container_format=ovf disk_format=qcow2 < ' 
            cmd += image_file 
            cmd += '\"' 
            (s,o) = commands.getstatusoutput(cmd)
            if (s != 0) :
                print 'Glance of VSRX image failed: ', s, ' error ', o 
                sys.exit(2)
            image = self.nova_client.images.find(name=image_name)
        print 'Found Image ', image_name, ' with UUID ', image.id
        return image.id
    # def GetImage

    def EnsureVm(self, vm_name, image_uuid, compute, fabric_uuid, vn_uuid) :
        print 'Looking for VM ', vm_name
        vm = None
        try :
            vm_list = self.nova_client.servers.list()
        except Exception,e :
            print 'Error quering server list'
            print e
            sys.exit(2)

        for vm_obj in vm_list:
            if vm_obj.name == vm_name:
                vm = vm_obj
                break

        nics_list=[]
        if vm == None:
            flavor = self.nova_client.flavors.find(name='m1.medium')
            nics_list.append({'net-id': vn_uuid})
            nics_list.append({'net-id': fabric_uuid})
            zone = 'nova:'+compute
            try :
                print 'Spawning VM ', vm_name
                vm = self.nova_client.servers.create(name = vm_name,
                                                     image = image_uuid,
                                                    flavor = flavor,
                                                    availability_zone = zone,
                                                    nics = nics_list)
            except Exception,e :
                print 'Error creating server'
                print e
                sys.exit(2)
        else :
            print 'VM ', vm_name, ' already present'

        # Wait till VM is in ACTIVE status
        for i in range(1,120):
            vm = self.nova_client.servers.find(id=vm.id)
            if vm.status == u'ACTIVE':
                break
            if vm.status == u'ERROR':
                break
            time.sleep(1)

        if vm.status != 'ACTIVE':
            print 'VM did not move to ACTIVE status in 120 secs... Exiting'
            print 'VM state : ', vm.status
            return None

        print 'Found VM in state ', vm.status
        return vm
    # def EnsureVm

    def GetPort(self, vm, vn_uuid) :
        try : 
            port_rsp = self.neutron_client.list_ports(device_id = [vm.id])
        except Exception,e :
            print 'Error querying port-list'
            print e
            sys.exit(2)

        if port_rsp['ports'][0]['network_id'] == vn_uuid:
            return port_rsp['ports'][0]['id']

        if port_rsp['ports'][1]['network_id'] == vn_uuid:
           return port_rsp['ports'][1]['id']

        return None
    #def GetPort


    def AddInterfaceRoute(self, project, port_uuid, table_name, prefix) :
        print 'Adding interface-route entries for port ', port_uuid
        # Create InterfaceRoutTable if already not present
        route_table = RouteTableType(table_name)
        route_table.set_route([])
        interface_route_table = InterfaceRouteTable(
                                    interface_route_table_routes = route_table,
                                    parent_obj = self.project_obj,
                                    name=table_name)
        try:
            route_table_obj = self.vnc_client.interface_route_table_read(
                                fq_name=interface_route_table.get_fq_name())
            interface_route_table_id = route_table_obj.uuid
        except NoIdError:
            interface_route_table_id = self.vnc_client.interface_route_table_create(
                                        interface_route_table)

        interface_route_table_obj = self.vnc_client.interface_route_table_read(
                                        id = interface_route_table_id)

        # Check if prefix to add is already present
        rt_routes = interface_route_table_obj.get_interface_route_table_routes()
        routes = rt_routes.get_route()
        found = False
        for route in routes:
            if route.prefix == prefix:
                found = True

        if not found:
            rt1 = RouteType(prefix = prefix)
            routes.append(rt1)

        # Update interface route-table with new route
        self.vnc_client.interface_route_table_update(interface_route_table_obj)

        # Update the VMI Object to link with interface route-table
        vmi_obj = self.vnc_client.virtual_machine_interface_read(id = port_uuid)
        vmi_obj.set_interface_route_table(interface_route_table_obj)
        self.vnc_client.virtual_machine_interface_update(vmi_obj)
        print 'Interface route table for ', port_uuid, ' added successfully'
    # def AddInterfaceRoute

    def GetVsrxImage(self, image_file) :
        url = 'wget http://puppet/contrail/' + image_file + ' -O /root/vsrx_nat.img'
        (s,o) = commands.getstatusoutput(url)
        if (s != 0) :
            print 'Copying the VSRX image failed: ', s, ' error ', o 
            sys.exit(2)
        print 'Fetched the image ', image_file, ' successfully'

#end class WinTSetup(object) :

def main(args_str=None):


    if not args_str:
        args_str = ' '.join(sys.argv[1:])

    parser = argparse.ArgumentParser(add_help = False)
    parser.add_argument("--openstack_ip", help = "Name of Openstack node")
    parser.add_argument("--openstack_user", help = "Openstack node user name")
    parser.add_argument("--openstack_passwd", help = "Openstack node password ")
    parser.add_argument("--api_server_ip", help = "Name of API server node")
    parser.add_argument("--compute", help = "Name of compute node")
    parser.add_argument("--image_name", help = "Vsrx Image Name in Glance")
    parser.add_argument("--image_file", help = "Vsrx Image file")
    parser.add_argument("--vsrx_vm_name", help = "Vsrx VM name on Compute")
    vsrx_data = parser.parse_args()


    vn_project = "admin"
    vn_name = "vn1" 
    fabric_subnet = '10.1.1.0/24'
    vn_subnet = '10.1.1.0/24'
    intf_route_prefix = '0.0.0.0/0'
    intf_route_table_name = 'VsrxRouteTable'

    setup = WinTSetup(vsrx_data.openstack_ip, vsrx_data.openstack_user,
                      vsrx_data.openstack_passwd, vn_project, 9696,
                      vsrx_data.api_server_ip, 8082)
    
    setup.GetVsrxImage(vsrx_data.image_file)

    # Create default ipam
    fabric_ipam = setup.EnsureIpam('default-project', 'default-network-ipam')
    vn_ipam = setup.EnsureIpam(vn_project, 'default-network-ipam')

    fabric_net = setup.FindVn('default-project', 'ip-fabric')
    if fabric_net == None:
        print 'Error finding fabric-vn... Exiting'
        sys.exit(1)

    # Ensure dummy subnet added for fabric network
    setup.EnsureSubnet(fabric_net, fabric_net['network']['id'], fabric_subnet,
                       fabric_ipam)

    vn_net = setup.EnsureVn(vn_project, vn_name, vn_subnet)
    if vn_net == None:
        print 'Error creating user-vn... Exiting'
        sys.exit(1)
    setup.EnsureSubnet(vn_net, vn_net['network']['id'], vn_subnet, vn_ipam)

    image_uuid = setup.GetImage(vsrx_data.image_name, vsrx_data.openstack_ip, "/root/vsrx_nat.img")

    vsrx_vm = setup.EnsureVm(vsrx_data.vsrx_vm_name, image_uuid,
                             vsrx_data.compute,
                             fabric_net['network']['id'],
                             vn_net['network']['id'])

    vn_port_uuid = setup.GetPort(vsrx_vm, vn_net['network']['id'])
    setup.AddInterfaceRoute(vn_project, vn_port_uuid,
                            intf_route_table_name, intf_route_prefix)
if __name__ == "__main__":
    main()
