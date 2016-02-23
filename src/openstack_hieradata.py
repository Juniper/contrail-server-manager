import string

template = string.Template("""
openstack::region: 'RegionOne'

######## Networks
openstack::network::api: '$__openstack_ip__/$__subnet_mask__'
openstack::network::external: '$__openstack_ip__/$__subnet_mask__'
openstack::network::management: '$__openstack_ip__/$__subnet_mask__'
openstack::network::data: '$__openstack_ip__/$__subnet_mask__'

openstack::network::external::ippool::start: ''
openstack::network::external::ippool::end: ''
openstack::network::external::gateway: ''
openstack::network::external::dns: ''

######## Private Neutron Network
openstack::network::neutron::private: '192.168.0.0/24'

######## Fixed IPs (controllers)
openstack::controller::address::api: '$__openstack_ip__'
openstack::controller::address::management: '$__openstack_ip__'
openstack::storage::address::api: '$__openstack_ip__'
openstack::storage::address::management: '$__openstack_ip__'

######## Database
openstack::mysql::root_password: '$__mysql_root_password__'
openstack::mysql::service_password: '$__mysql_service_password__'
##### TBD has hard-coded vaue. need to plug in local interface network.
openstack::mysql::allowed_hosts: ['localhost', '127.0.0.1', $__mysql_allowed_hosts__]

######## RabbitMQ
openstack::rabbitmq::user: 'guest'
openstack::rabbitmq::password: 'guest'

######## Keystone
openstack::keystone::admin_token: '$__keystone_admin_token__'
openstack::keystone::admin_email: 'test@orgname.com'
openstack::keystone::admin_password: '$__keystone_admin_password__'

openstack::keystone::tenants:
    "test":
        description: "Test tenant"

openstack::keystone::users:
    "test":
        password: "test123"
        tenant: "test"
        email: "test@orgname.com"
        admin: true
    "demo":
        password: "demo123"
        tenant: "test"
        email: "test@orgname.com"
        admin: false

######## Glance
openstack::glance::password: '$__openstack_password__'

######## Cinder
openstack::cinder::password: '$__openstack_password__'
openstack::cinder::volume_size: '8G'

######## Swift
openstack::swift::password: '$__openstack_password__'
openstack::swift::hash_suffix: ''

######## Nova
openstack::nova::libvirt_type: 'kvm'
openstack::nova::password: '$__openstack_password__'

######## Neutron
openstack::neutron::password: '$__openstack_password__'
openstack::neutron::shared_secret : 'XLbZ3ZzRsMoqwRJcFlmrpoc'
neutron::bind_port: '9697'

######## Ceilometer
openstack::ceilometer::mongo::password: '$__openstack_password__'
openstack::ceilometer::password: '$__openstack_password__'
openstack::ceilometer::meteringsecret: ''

######## Heat
openstack::heat::password: '$__openstack_password__'
openstack::heat::encryption_key: '$__heat_encryption_key__'

######## Horizon
openstack::horizon::secret_key: '$__openstack_password__'

######## Tempest
openstack::tempest::configure_images    : true
openstack::tempest::image_name          : 'Cirros'
openstack::tempest::image_name_alt      : 'Cirros'
openstack::tempest::username            : 'demo'
openstack::tempest::username_alt        : 'demo2'
openstack::tempest::username_admin      : 'test'
openstack::tempest::configure_network   : true
openstack::tempest::public_network_name : 'public'
openstack::tempest::cinder_available    : true
openstack::tempest::glance_available    : true
openstack::tempest::horizon_available   : true
openstack::tempest::nova_available      : true
openstack::tempest::neutron_available   : true
openstack::tempest::heat_available      : false
openstack::tempest::swift_available     : false

######## Log levels
openstack::verbose: 'True'
openstack::debug: 'True'
""")
