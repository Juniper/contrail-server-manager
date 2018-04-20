import sys, argparse
import subprocess
import re
import json
import paramiko

'''
         - number of VMs, 
         - VM image(use qcow or reimage?), 
         - params (memory, cpus),
         - physical server to launch
         - bridge to create
         - add vms to server-manager (create server.json)
         - create cluster.json (need vips)
         - issue provision 
'''
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filename', help = 'json file to read from with complete path')
    parser.add_argument('-D', '--delete', action = 'store_true', help = 'delete vm from the host')
    parser.add_argument('-c', '--cpus', type = int, default = 4, help = 'number of CPUs for the VM')
    parser.add_argument('-m', '--memory', type = int, default = 8192, help = 'memory for the VM')
    parser.add_argument('-s', '--physical_host_ip', help = 'ip of server that hosts the VM')
    parser.add_argument('-n', '--mac', help = 'MAC address of the VM')
    parser.add_argument('-nics', '--nics', nargs = '+', help = 'nics mac1,bridge1,uplink1 mac2,b2,upl2 format')
    parser.add_argument('-p', '--qcow', help = 'VM image file path')
    parser.add_argument('-i', '--count', type = int, default = 1, help = 'number of VMs')
    parser.add_argument('-u', '--uplink', default = None, help = 'server uplink interface, for VM network connectivity')
    parser.add_argument('-b', '--bridge', default = 'br1', help = 'bridge for VM network connectivity')
    parser.add_argument('-d', '--disksize', default = '80G', help = 'VM disk size')
    parser.add_argument('-H', '--vmname', help = 'VM name')
    parser.add_argument('-U', '--username', default = 'root', help = 'physical host username')
    parser.add_argument('-P', '--password', default = 'c0ntrail123', help = 'physical host password')
    return parser.parse_args()

def populate_args(jsondata, args):
    args.cpus = jsondata.get('cpus', 4)
    args.memory = jsondata.get('memory', 8192)
    args.disksize = jsondata.get('disksize', '80G')
    args.physical_host_ip = jsondata.get('physical_host_ip')
    args.mac = jsondata.get('mac')
    args.qcow = jsondata.get('qcow', None)
    args.count = jsondata.get('count', 1)
    args.vmname = jsondata.get('vmname')
    args.uplink = jsondata.get('physical_host_uplink', None)
    args.bridge= jsondata.get('physical_host_bridge', 'br1')
    args.username = jsondata.get('physical_host_username', 'root')
    args.password = jsondata.get('physical_host_password', 'c0ntrail123')

def run_command(server, cmd):
    print cmd
    inp, op, err = server.exec_command(cmd)
    #readlines will hang, so just check if process created
    # assume only qemu-system cmd using nohup
    if 'nohup' in cmd:
        f1 = re.search('.*name\s+([.\w-]+)', cmd)
        cmd1 = f1.group(1)
        inp1, op1, err1 = server.exec_command('ps -aux |grep %s| grep -v grep' %cmd1)
        if cmd1 in op1.readlines()[0]:
            return 0, []
        else:
            return 1, err1.readlines()
    x = err.readlines()
    if x:
        return 1, x
    return 0, op.readlines()

def get_tap_intf(server, username = 'root', password = 'c0ntrail123'):
    ''' return last tap interface number plus 1 or 11 if no tap interface'''

    cmd = "ifconfig -a| grep \"^tap\" |grep -v grep"
    e, op = run_command(server, cmd)
    if op:
        for line in op:
            pass
        m = re.search("^tap\d+", line)
        return int(re.search("\d+", m.group()).group()) + 1 
    return 11

def is_vm_exist(server, vmname):
    cmd = "ps -aux| grep %s |grep -v grep" %vmname
    e, op = run_command(server, cmd)
    if op:
        return True
    else:
        return False

def is_br_exist(server, br):
    cmd = "ifconfig %s |grep %s | grep -v grep" %(br, br)
    e, op = run_command(server, cmd)
    if op:
        return True
    else:
        return False

#def set_network(server, tap_name, br = 'br1', uplink = None):
def set_network(server, tap_no, nics):
    i = 0
    for nic in nics:
        nic_elems = nic.split(',')
        br = nic_elems[1]
        uplink = nic_elems[2]
        tap_name = 'tap' + str(tap_no + i)
        if not is_br_exist(server, br):
            run_command(server, "brctl addbr %s" %br)
        run_command(server, "ifconfig %s up" %br)
        run_command(server, "ifconfig %s up" %tap_name)
        e, o = run_command(server, "brctl addif %s %s" %(br, tap_name))
        if e != 0:
            return 1, o
        if uplink and uplink != 'None':
            run_command(server, "brctl addif %s %s" %(br, uplink))
        i += 1
    return 0, []

def delete_vm(server, vmname):
    if is_vm_exist(server, vmname):
        pidcmd = "ps -aux | grep %s| grep -v grep" %vmname
        e, op = run_command(server, pidcmd)
        pid = re.search('\w+\s+(\d+)', op[0]).group(1)
        cmd = "kill -9 %s" %pid
        run_command(server, cmd)

def main():
    args = parse_args()
    if args.filename:
        fh = open(args.filename, 'r')
        jsondata = json.load(fh)
        populate_args(jsondata, args)
    ssh_fd = paramiko.SSHClient()
    ssh_fd.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_fd.connect(args.physical_host_ip, username = args.username, password = args.password)
    if args.delete:
        delete_vm(ssh_fd, args.vmname)
        sys.exit(0)
    tap_int = get_tap_intf(ssh_fd)
    tap_intf = 'tap' + str(tap_int)
    if is_vm_exist(ssh_fd, args.vmname):
        sys.exit(0)
    qemu_cmd = ''
    qemu_img = "%s.qcow2" %args.vmname
    qemu_cmd = "nohup qemu-system-x86_64 --name %s -boot n" %(args.vmname)
    qemu_cmd = qemu_cmd + " -m %d -enable-kvm -smp cpus=%d" %(args.memory, args.cpus)
    i = 0
    for nic in args.nics:
        qemu_cmd = qemu_cmd + " -net nic,macaddr=%s,vlan=%s" %((nic.split(',')[0]), (i+1))
        qemu_cmd = qemu_cmd + " -net tap,ifname=tap%s,script=no,vlan=%s" %((tap_int + i), (i+1))
        i += 1
    qemu_cmd = qemu_cmd + " %s -vnc :%s" %(qemu_img, tap_int)
    run_command(ssh_fd, "rm -rf %s && touch %s" %(qemu_img, qemu_img))
    run_command(ssh_fd, "qemu-img resize %s +%s" %(qemu_img, args.disksize))
    e, o = run_command(ssh_fd, qemu_cmd)
    if e:
        delete_vm(ssh_fd, args.vmname)
        raise Exception("Error creating VM:\n%s\n" %o)
    e, o = set_network(ssh_fd, tap_int, args.nics)
    if e:
        # delete VM
        delete_vm(ssh_fd, args.vmname)
        raise Exception("Error creating VM:\n%s\n" %o)

if __name__ == "__main__":
    main()

