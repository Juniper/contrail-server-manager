import pprint
import logging
import json
import subprocess

ALLOCATE_IP_ADDRESS=False
HTTP_SERVER='/'
_DEF_HTML_ROOT_DIR = '/var/www/html/'
DEFAULT_PATH_LSTOPO_XML='/var/www/html/contrail/lstopo/'
DEFAULT_IP_ADDR_POOL1="data_network"
DEFAULT_IP_ADDR_POOL2= {
  "mgmt_network": {
    "subnet"   : "192.168.99.0/24",
    "dgateway" : "192.168.99.1",
    "dhcp"     : True
  },
  "data_network": {
    "subnet"   : "10.10.10.0/24",
    "dgateway" : "10.10.10.1",
    "dhcp"     : False
  }
}

log = logging.getLogger('smgr_discovery')
log.setLevel(logging.DEBUG)

def generate_server_data(hw_json):
    mgmt_ifname = hw_json['mgmt_ifname']
    if_data = hw_json['if_data']
    #pprint.pprint(if_data)
    ipmi_address = hw_json['ipmi']['ip']
    server_data = {}
    log.debug( "MGMT")
    log.debug( mgmt_ifname)
    mgmt_mac = ""
    network_data = []
    for ifname in if_data:
       if_detail = {}
       lldp_data=if_data[ifname]['lldp']
       if lldp_data != "":
         #pprint.pprint(lldp_data)
         lldp_data = lldp_data.split('\n')
         lldp_dict = {}
         for value in lldp_data:
           if "=" in value.decode("utf-8"):
             k,v = value.split("=")
             lldp_dict[k] = v
         port_id = lldp_dict["lldp."+ifname+".port.descr"]
         sname   = lldp_dict["lldp."+ifname+".chassis.name"]
         rid     = lldp_dict["lldp."+ifname+".rid"]
         #pprint.pprint (lldp_dict)
       else:
         port_id = ""
         sname   = ""
         rid     = ""
         
       log.debug(ifname)
       if_mac = if_data[ifname]['mac']
       if mgmt_ifname == ifname:
         mgmt_mac = if_data[ifname]['mac']

       if_detail['name'] = ifname
       if_detail['sw_name'] = sname
       if_detail['sw_rid'] = rid
       if_detail['sw_port'] = port_id
       if_detail['mac_address']  = if_mac.rstrip()
       if ALLOCATE_IP_ADDRESS == True:
         ip_address = get_ip_from_pool()
         print ip_address
         if_detail['ip_address'] = ip_address['ip']+'/'+str(ip_address['plen'])
         if_detail['dhcp'] = ip_address['dhcp']
         if_detail['default_gateway'] = ip_address['dgateway']
         allocate_ip_from_pool(ip_address)

       network_data.append(if_detail)

    disk_data = hw_json["disks"]
    all_disks = {}
    if disk_data != "":
      disk_data = disk_data.split("\n")
      disk_data = [x for x in disk_data if x]
      pprint.pprint(disk_data)
      for disk_line in disk_data:
        if "TYPE=\"disk\"" in disk_line:
          disk_info = disk_line.split(" ")
          print disk_info
          disk_dict = {}
          for value in disk_info:
            print value
            k,v = value.split("=")
            disk_dict[k] = v
          #print disk_dict
          disk_name = "/dev/" + disk_dict["NAME"][1:-1]
          all_disks[disk_name] = {}
          all_disks[disk_name]['name'] = disk_name
          all_disks[disk_name]['size'] = disk_dict["SIZE"][1:-1]
          #all_disks[disk_name]['model'] = disk_dict["MODEL"]
          if disk_dict["ROTA"][1:-1] == "0":
            all_disks[disk_name]['ssd'] = True
          else:
            all_disks[disk_name]['ssd'] = False


    pprint.pprint( all_disks)
    server_id = "cc-" + mgmt_mac.replace(":", "").rstrip()
    server_data['id']      = server_id
    server_data['password'] = "c0ntrail123"
    server_data['domain'] = "contrail.juniper.net"
    server_data['ipmi_address'] = ipmi_address.rstrip()
    server_data['parameters']  = {}
    server_data['parameters']['all_disks'] = all_disks
    server_data['network']  = {}
    server_data['network']['management_interface'] = mgmt_ifname
    server_data['network']['interfaces'] = network_data
    server_array = []
    server_array.append(server_data)
    add_server = {}
    add_server['server']=server_array
    sm_json_filename=DEFAULT_PATH_LSTOPO_XML+server_id+'.json'
    outfile = open(sm_json_filename , 'w') 
    outfile.write(json.dumps(add_server, sort_keys=True, indent=4 ))
    outfile.close

    #if ALLOCATE_IP_ADDRESS == True:
        #put_server(internal_json = add_server)
    
    log.debug(server_id)
    return server_array, server_id


def parse_hw_data(hw_json):
    sm_json, sid = generate_server_data(hw_json)
    system_details  = get_system_details(hw_json)
    cpu_details     = calculate_cpu(hw_json)
    memory_details  = calculate_memory(hw_json)
    disk_details    = calculate_disks(hw_json)
    #network_details = calculate_networks(hw_json)
    lstopo_file     = generate_lstopo(hw_json)
    lstopo_url      = HTTP_SERVER+ lstopo_file.replace(_DEF_HTML_ROOT_DIR, '')
    basic_hw_data={}
    basic_hw_data['system'] = system_details
    basic_hw_data['cpu'] = str(cpu_details)
    basic_hw_data['memory'] = str(memory_details)
    basic_hw_data['mem_GB'] = str(memory_details/(1024*1024*1024))
    basic_hw_data['disk'] = disk_details
    basic_hw_data['network'] = ""
    basic_hw_data['topology'] = lstopo_file
    basic_hw_data['topo_url'] = lstopo_url
    return basic_hw_data, sm_json, sid

def get_system_details(hw_json):
    system_details = {}
    system_details['vendor'] = hw_json['hw_specs']['vendor']
    system_details['product'] = "UNKOWN"

    return system_details

def generate_lstopo(hw_json):
    uuid=hw_json['server_uuid']
    lstopo_xml_data=hw_json['lstopo']
    xml_filename=DEFAULT_PATH_LSTOPO_XML+uuid+'.xml'
    svg_filename=DEFAULT_PATH_LSTOPO_XML+uuid+'.svg'
    print xml_filename
    outfile=open(xml_filename, 'w')
    outfile.write(lstopo_xml_data)
    outfile.close()

    svg_data=subprocess.Popen(['/usr/bin/lstopo', '--output-format', 'svg' , '--input', xml_filename], stdout=subprocess.PIPE).communicate()[0]
    outfile=open(svg_filename, 'w')
    outfile.write(svg_data)
    outfile.close()

    return svg_filename

def calculate_networks(hw_json):
    uuid=hw_json['server_uuid']
    #print uuid
    hw_details=hw_json['hw_specs']['children']
    total_cores = 0
    network_details = {}
    #pprint.pprint(hw_details)
    return network_details
    for i,hw_data in enumerate(hw_details):
      if hw_data['class'] == 'bus':
        for j,data in enumerate(hw_data['children']):
          if data['class'] == 'bridge' and 'children' in data:
            for k,ndata in enumerate(data['children']):
              if 'children' in ndata:
    	        for m,mdata in enumerate(ndata['children']):
    	          if mdata['class'] == 'network':
    	            #print mdata['id'], mdata.get('logicalname', "UNK NAME"),mdata['class'], mdata.get('serial', ""), mdata.get('size',"UNK SPEED")
    	            #print mdata
    	            ifname = mdata['logicalname']
    	            network_details[ifname]={}
    	            network_details[ifname]['name']=ifname
    	            network_details[ifname]['serial']=mdata.get('serial', "")
    	            network_details[ifname]['speed']=mdata.get('size', "UNKNOWN SPEED")
    	            network_details[ifname]['capacity']=mdata.get('capacity', "UNKNOWN CAPACITY")
    	            network_details[ifname]['driver']=mdata['configuration'].get("driver", "UNKNOWN DRIVER")
    	            network_details[ifname]['link']=mdata['configuration'].get("link", "UNKNOWN LINK")
                  if ndata['class'] == 'network':
    	            #print ndata['id'], ndata.get('logicalname', "UNK NAME"),ndata['class'], ndata.get('serial', ""), ndata.get('size',"UNK SPEED")
    	            #print ndata
    	            ifname = ndata['logicalname']
    	            network_details[ifname]={}
    	            network_details[ifname]['name']=ifname
    	            network_details[ifname]['serial']=ndata.get('serial', "")
    	            network_details[ifname]['speed']=ndata.get('size', "UNKNOWN SPEED")
    	            network_details[ifname]['capacity']=ndata.get('capacity', "UNKNOWN CAPACITY")
    	            network_details[ifname]['driver']=ndata['configuration'].get("driver", "UNKNOWN DRIVER")
    	            network_details[ifname]['link']=ndata['configuration'].get("link", "UNKNOWN LINK")
                  #elif 'children' in data:
                    #for k,ndata in enumerate(data['children']):
                      #if ndata['class'] == 'bridge' and 'children' in ndata:
    	            #for m,mdata in enumerate(ndata['children']):
    	              #print "HLL"
    	              #if mdata['class'] == 'network':
    	                ##print mdata['id'], mdata.get('logicalname', "UNK NAME"),mdata['class'], mdata.get('serial', ""), mdata.get('size',"UNK SPEED")
    	                #print mdata['id'], mdata
    
    #pprint.pprint( network_details)
    return network_details

def calculate_disks(hw_json):
    uuid=hw_json['server_uuid']
    #print uuid
    disk_details={}
    hw_details=hw_json['hw_specs']['children']
    total_cores = 0
    for i,hw_data in enumerate(hw_details):
      #print i, hw_data['class'], hw_data['id']
      if hw_data['class'] == 'bus':
        for j,data in enumerate(hw_data['children']):
          #print i,j,  data['id'], data['class'], type(data)
          #if data['class'] == 'disk':
            #print data['id'], data['logicalname']
          if 'children' in data:
            for k,ndata in enumerate(data['children']):
              #print i,j,k,  ndata['id'], ndata['class'], type(ndata)
              if ndata['class'] == 'disk':
    	        #print ndata['id'],ndata['logicalname']
    	        disk_name=str(ndata['logicalname'])
    	        if 'size' in ndata:
    	          disk_details[disk_name]={}
    	          disk_details[disk_name]['name']=disk_name
    	          #print ndata['id'],ndata['logicalname'], int(ndata['size'])/(1024*1024*1024)
    	          disk_details[disk_name]['size']=str(int(ndata['size'])/(1024*1024*1024))
    	  

    #print "CPU => " + str(total_cores)
    #pprint.pprint( disk_details)
    return disk_details

def calculate_cpu(hw_json):
    uuid=hw_json['server_uuid']
    #print uuid
    hw_details=hw_json['hw_specs']['children']
    total_cores = 0
    for i,hw_data in enumerate(hw_details):
      #print i, hw_data['class'], hw_data['id']
      if hw_data['class'] == 'bus':
        for j,data in enumerate(hw_data['children']):
          #print i,j,  data['id'], data['class'], type(data)
          if data['class'] == 'processor' and data['id'].startswith('cpu'):
            #print data['id']
            if 'configuration' in data:
              threads=int(data['configuration'].get('threads', 1))
            else:
              threads=1
            total_cores = total_cores + threads 

    #print "CPU => " + str(total_cores)
    return total_cores


def calculate_memory(hw_json):
    uuid=hw_json['server_uuid']
    #print uuid
    hw_details=hw_json['hw_specs']['children']
    total_memory = 0
    for i,hw_data in enumerate(hw_details):
      #print i, hw_data['class'], hw_data['id']
      if hw_data['class'] == 'bus':
        for j,data in enumerate(hw_data['children']):
          #print i,j,  data['id'], data['class'], type(data)
          if data['class'] == 'memory' and data['id'].startswith('memory'):
            #print data['id']
            if 'children' in data:
              for key,value in enumerate(data['children']):
    	        if 'size' in value:
    	          #print key, value['size']
    	          total_memory = total_memory + value['size']

    #print 'MEMORY => ' + str(total_memory)  + ' ' +str(total_memory/(1024*1024*1024))+ 'GB'
    return total_memory

_ip_pool = {}

def startup_ip_pools(self):
  ip_pool = {}
  for pool_name in DEFAULT_IP_ADDR_POOL2:
    print pool_name
    pool_data = DEFAULT_IP_ADDR_POOL2[pool_name]
    ip_pool[pool_name] = {}
    ip_pool[pool_name]['details'] = {}
    ip_pool[pool_name]['details']['dhcp'] = pool_data['dhcp']
    ip_pool[pool_name]['details']['plen'] = IPNetwork(pool_data['subnet']).prefixlen
    ip_pool[pool_name]['details']['dgateway'] = pool_data['dgateway']
    ip_pool[pool_name]['pool'] = {}
    for ipaddr in IPNetwork(pool_data['subnet']):
        ip_pool[pool_name]['pool'][str(ipaddr)] = {}
        ip_pool[pool_name]['pool'][str(ipaddr)]['ip'] = str(ipaddr )
        ip_pool[pool_name]['pool'][str(ipaddr)]['used'] = False

    self._ip_pool = ip_pool
  pprint.pprint(self._ip_pool)
    
def allocate_ip_from_pool(self,consumed_ip, pool_name=None):
    if pool_name is None:
      pool_name = DEFAULT_IP_ADDR_POOL1

    ip_pool = self._ip_pool[pool_name]
    ip_pool['pool'][consumed_ip['ip']]['used'] = True

def get_ip_from_pool(self,pool_name=None):
    if pool_name is None:
      pool_name = DEFAULT_IP_ADDR_POOL1

    ip_pool = self._ip_pool[pool_name]
    allocated_ip = {}
    #pprint.pprint(ip_pool)
    for ip in ip_pool['pool']:
      #print ip
      if ip_pool['pool'][ip]['used'] == False:
        allocated_ip['ip'] = ip
        allocated_ip['plen'] = ip_pool['details']['plen']
        allocated_ip['dhcp'] = ip_pool['details']['dhcp']
        allocated_ip['dgateway'] = ip_pool['details']['dgateway']
        print "AVAIL"
        return allocated_ip
    print "NO ADDR AVAIL"
    
    return ""
    
