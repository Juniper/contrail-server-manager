source /etc/contrail/openstackrc
wget https://launchpad.net/cirros/trunk/0.3.0/+download/cirros-0.3.0-x86_64-disk.img
glance image-create --name 'cirros' --container-format ovf --disk-format qcow2 --file ./cirros-0.3.0-x86_64-disk.img
neutron net-create testvn
neutron subnet-create testvn 30.30.31.0/24 --name test_subnet
nova image-list | grep cirros| grep -oh "[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*"
image_id=$(nova image-list | grep cirros| grep -oh "[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*")
net_id=$(nova net-list | grep testvn_nitishk| grep -oh "[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*-[a-z0-9]*")
nova boot --flavor 1 --nic net-id=$net_id --image $image_id vm100
nova list
nova boot --flavor 1 --nic net-id=$net_id --image $image_id vm101
nova list
sleep 15
nova list

# On the spawned VM100:
# ping 30.30.31.4
# wget http://169.254.169.254/openstack
