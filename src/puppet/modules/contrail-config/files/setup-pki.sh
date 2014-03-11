
# invoke as setup-pki.sh /etc/contrail/ssl

if [ $# -ne 1 ]; then
    echo "Usage: $0 path/to/cert/store"
    exit 1
fi


PKI_DIR=$1
CERTS_DIR=$PKI_DIR/certs
PRIVATE_DIR=$PKI_DIR/private_keys
KEYSTORE_DIR=$PKI_DIR/keystore
CSR_DIR=$PKI_DIR/csr

red='\e[0;31m'
green='\e[0;32m'
yellow='\e[0;33m'
NC='\e[0m' # No Color

hostname=`hostname --fqdn`

function rm_old {
    rm -rf $CERTS_DIR/*.pem
    rm -rf $PRIVATE_DIR/*.pem
    rm -rf $KEYSTORE_DIR/*.jks
    rm -rf $CSR_DIR/*.csr
}

function cleanup {
    rm -rf *.conf   > /dev/null 2>&1
    rm -rf *.crt    > /dev/null 2>&1
    rm -rf *.pem    > /dev/null 2>&1
    rm -rf index*   > /dev/null 2>&1
    rm -rf serial*  > /dev/null 2>&1
    rm -rf newcerts > /dev/null 2>&1
}

# make copy of CA cert because puppet will change ownership and permission
# rendering it useless for API server and other readers
function generate_puppet_conf {
    if [ ! -f /etc/puppet/puppet.conf ]; then
        echo -e "${red}Puppet server not installed !! Skipping mod${NC}"
        return
    fi
    if [ "`grep cacert /etc/puppet/puppet.conf`" ]; then
        echo -e "${yellow}/etc/puppet/puppet.conf already modified! Skipping mod${NC}"
        return
    fi
    echo -e "
[master]
    # Copy of CA cert for puppet use
    cacert = ${CERTS_DIR}/ca4puppet.pem
    # Location of CA related files
    cadir = ${PKI_DIR}/ca
    # CA private key
    cakey = ${PRIVATE_DIR}/ca_key.pem
    " >> /etc/puppet/puppet.conf
}

function generate_puppet_autosign_conf {
    if [ ! -f /etc/puppet/puppet.conf ]; then
        echo -e "${red}Puppet server not installed !! Skipping autosign${NC}"
        return
    fi
    if [ -f /etc/puppet/autosign.conf ]; then
        echo -e "${yellow}/etc/puppet/autosign.conf already exists! Skipping mod${NC}"
        return
    fi
    echo '*' >> /etc/puppet/autosign.conf
}

function generate_ifmap_conf {
    if [ ! -f /etc/irond/ifmap.properties ]; then
        echo -e "${red}Ifmap server not installed !! Skipping mod${NC}"
        return
    fi
    if [ -f /etc/irond/ifmap.properties.original ]; then
        echo -e "${yellow}/etc/irond/ifmap.properties already modified! Skipping mod${NC}"
        return
    fi
	cp /etc/irond/ifmap.properties /etc/irond/ifmap.properties.original
	sed 's/\(irond.auth.cert.*.file=\).*/\1\/etc\/contrail\/ssl\/keystore\/irond.jks/' \
		< /etc/irond/ifmap.properties > foobar
	mv foobar /etc/irond/ifmap.properties
	diff /etc/irond/ifmap.properties.original /etc/irond/ifmap.properties
}

function setup {
    mkdir -p $PKI_DIR
    cd $PKI_DIR
    touch index.txt
    echo '10' > serial
    mkdir newcerts
    mkdir -p $CSR_DIR $CERTS_DIR $PRIVATE_DIR $KEYSTORE_DIR
    generate_puppet_conf
    generate_puppet_autosign_conf
    generate_ifmap_conf
    generate_ca_conf
    generate_apiserver_cert_conf
    generate_schema_xfer_cert_conf
    generate_hostname_cert_conf
    generate_signing_conf
}

function generate_ca_conf {
    echo '
[ req ]
default_bits            = 2048
default_keyfile         = ca_key.pem
default_md              = sha1
prompt                  = no
distinguished_name      = ca_distinguished_name
x509_extensions         = ca_extensions

[ ca_distinguished_name ]
serialNumber            = 5
countryName             = US
stateOrProvinceName     = CA
localityName            = Sunnyvale
organizationName        = Juniper Networks
organizationalUnitName  = Contrail Systems
commonName              = Contrail CA

[ ca_extensions ]
basicConstraints        = critical,CA:true
' > ca.conf
}

function generate_apiserver_cert_conf {
    echo '
[ req ]
default_bits            = 2048
default_keyfile         = apiserver_key.pem
default_md              = sha1
prompt                  = no
distinguished_name      = apiserver_distinguished_name

[ apiserver_distinguished_name ]
countryName             = US
stateOrProvinceName     = CA
localityName            = Sunnyvale
organizationName        = Juniper Networks
organizationalUnitName  = Contrail Systems
commonName              = API Server
' > apiserver.conf
}

function generate_schema_xfer_cert_conf {
    echo '
[ req ]
default_bits            = 2048
default_keyfile         = schema_xfer_key.pem
default_md              = sha1
prompt                  = no
distinguished_name      = schema_xfer_distinguished_name

[ schema_xfer_distinguished_name ]
countryName             = US
stateOrProvinceName     = CA
localityName            = Sunnyvale
organizationName        = Juniper Networks
organizationalUnitName  = Contrail Systems
commonName              = Schema Transformer
' > schema_xfer.conf
}

function generate_hostname_cert_conf {
    echo -e "
[ req ]
default_bits            = 2048
default_keyfile         = ${hostname}.pem
default_md              = sha1
prompt                  = no
distinguished_name      = hostname_distinguished_name

[ hostname_distinguished_name ]
countryName             = US
stateOrProvinceName     = CA
localityName            = Sunnyvale
organizationName        = Juniper Networks
organizationalUnitName  = Contrail Systems
commonName              = ${hostname}
" > hostname.conf
}

function generate_signing_conf {
    echo '
[ ca ]
default_ca              = signing_ca

[ signing_ca ]
dir                     = .
database                = $dir/index.txt
new_certs_dir           = $dir/newcerts
certificate             = $dir/certs/ca.pem
serial                  = $dir/serial
private_key             = $dir/private_keys/ca_key.pem
default_days            = 730
default_crl_days        = 30
default_md              = sha1
policy                  = policy_any

[ policy_any ]
countryName             = supplied
stateOrProvinceName     = supplied
localityName            = supplied
organizationName        = supplied
organizationalUnitName  = supplied
commonName              = supplied
' > signing.conf
}

function check_error {
    if [ $1 != 0 ] ; then
        echo -e "${red}Failed! rc=${1}${NC}"
        echo -e "${red}Bailing ...${NC}"
        cleanup
        exit $1
    else
        echo -e "${green}Done${NC}"
    fi
}

function generate_ca {
    echo -e "${green}* Generating CA Certificate ...${NC}"
    openssl req -x509 -newkey rsa:2048 -days 3650 -out $CERTS_DIR/ca.pem \
        -keyout $PRIVATE_DIR/ca_key.pem -outform PEM -config ca.conf -nodes
    check_error $?
    # make a copy for puppet because it will override permissions
    cp $CERTS_DIR/ca.pem $CERTS_DIR/ca4puppet.pem
}

function generate_mapserver {
    echo -e "${green}* Generating Map Server keys, keystore ...${NC}"

    # add CA cert to irond keystore as trusted certificate
    keytool -import -trustcacerts -alias contrail-ca -file $CERTS_DIR/ca.pem \
        -keystore $KEYSTORE_DIR/irond.jks -storepass mapserver -noprompt
    check_error $?

    # generate our key-pair
    keytool -genkey -keyalg RSA -alias irond -keysize 2048 \
        -keystore $KEYSTORE_DIR/irond.jks -storepass mapserver -keypass mapserver \
        -dname "CN=Map Server, OU=Contrail, O=Juniper Networks, L=Sunnyvale, S=CA, C=US"
    check_error $?

    # generate CSR
    keytool -certreq -alias irond -file $CSR_DIR/mapserver.csr \
        -keystore $KEYSTORE_DIR/irond.jks -storepass mapserver

    echo -e "${green}* Issuing Map Server Certificate ...${NC}"
    openssl ca -in $CSR_DIR/mapserver.csr -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/10.pem -out $CERTS_DIR/mapserver.pem
    check_error $?

    echo -e "${green}* Importing CA signed mapserver certificate to keystore ...${NC}"
    keytool -import -file $CERTS_DIR/mapserver.pem -alias irond \
        -keystore $KEYSTORE_DIR/irond.jks -storepass mapserver
    check_error $?
}

function generate_irongui {
    echo -e "${green}* Generating Irongui keys, keystore ...${NC}"

    # add CA cert to irongui keystore as trusted certificate
    keytool -import -trustcacerts -alias contrail-ca -file $CERTS_DIR/ca.pem \
        -keystore $KEYSTORE_DIR/irongui.jks -storepass irongui -noprompt
    check_error $?

    # generate key-pair
    keytool -genkey -keyalg RSA -alias irongui -keysize 2048 \
        -keystore $KEYSTORE_DIR/irongui.jks -storepass irongui -keypass irongui \
        -dname "CN=Irongui, OU=Contrail, O=Juniper Networks, L=Sunnyvale, S=CA, C=US"
    check_error $?

    # generate CSR
    keytool -certreq -alias irongui -file $CSR_DIR/irongui.csr \
        -keystore $KEYSTORE_DIR/irongui.jks -storepass irongui

    echo -e "${green}* Issuing Irongui Certificate ...${NC}"
    openssl ca -in $CSR_DIR/irongui.csr -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/12.pem -out $CERTS_DIR/irongui.pem
    check_error $?

    echo -e "${green}* Importing CA signed irongui certificate to keystore ...${NC}"
    keytool -import -file $CERTS_DIR/irongui.pem -alias irongui \
        -keystore $KEYSTORE_DIR/irongui.jks -storepass irongui
    check_error $?
}

function generate_apiserver {
    echo -e "${green}* Generating API Server Certificate request ...${NC}"

    openssl req -newkey rsa:2048 -keyform PEM -out apiserver_req.pem \
        -keyout $PRIVATE_DIR/apiserver_key.pem -outform PEM -config apiserver.conf -nodes
    check_error $?

    echo -e "${green}* Issuing API Server Certificate ...${NC}"
    openssl ca -in apiserver_req.pem -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/11.pem -out $CERTS_DIR/apiserver.pem
    check_error $?
}


function generate_ifmapcli {
    echo -e "${green}* Generating ifmapcli keys, keystore ...${NC}"

    # add CA cert to ifmapcli keystore as trusted certificate
    keytool -import -trustcacerts -alias contrail-ca -file $CERTS_DIR/ca.pem \
        -keystore $KEYSTORE_DIR/ifmapcli.jks -storepass ifmapcli -noprompt
    check_error $?

    # generate key-pair
    keytool -genkey -keyalg RSA -alias ifmapcli -keysize 2048 \
        -keystore $KEYSTORE_DIR/ifmapcli.jks -storepass ifmapcli -keypass ifmapcli \
        -dname "CN=ifmapcli, OU=Contrail, O=Juniper Networks, L=Sunnyvale, S=CA, C=US"
    check_error $?

    # generate CSR
    keytool -certreq -alias ifmapcli -file $CSR_DIR/ifmapcli.csr \
        -keystore $KEYSTORE_DIR/ifmapcli.jks -storepass ifmapcli
    check_error $?

    echo -e "${green}* Issuing ifmapcli Certificate ...${NC}"
    openssl ca -in $CSR_DIR/ifmapcli.csr -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/13.pem -out $CERTS_DIR/ifmapcli.pem
    check_error $?

    echo -e "${green}* Importing CA signed ifmapcli certificate to keystore ...${NC}"
    keytool -import -file $CERTS_DIR/ifmapcli.pem -keystore $KEYSTORE_DIR/ifmapcli.jks \
        -alias ifmapcli -storepass ifmapcli
}

function generate_schema_xfer {
    echo -e "${green}* Generating Schema Transfer Certificate request ...${NC}"

    openssl req -newkey rsa:2048 -keyform PEM -out $CSR_DIR/schema_xfer.csr \
        -keyout $PRIVATE_DIR/schema_xfer_key.pem -outform PEM -config schema_xfer.conf -nodes
    check_error $?

    echo -e "${green}* Issuing Schema transfer Certificate ...${NC}"
    openssl ca -in $CSR_DIR/schema_xfer.csr -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/14.pem -out $CERTS_DIR/schema_xfer.pem
    check_error $?
}

function generate_hostname {
    echo -e "${green}* Generating hostname Certificate request ...${NC}"

    openssl req -newkey rsa:2048 -keyform PEM -out $CSR_DIR/$hostname.csr \
        -keyout $PRIVATE_DIR/$hostname.pem -outform PEM -config hostname.conf -nodes
    check_error $?

    echo -e "${green}* Issuing hostname Certificate ...${NC}"
    openssl ca -in $CSR_DIR/$hostname.csr -config signing.conf -batch
    check_error $?
    openssl x509 -in $PKI_DIR/newcerts/15.pem -out $CERTS_DIR/$hostname.pem
    check_error $?
}

function check_openssl {
    echo -e "${green}* Checking openssl availability ...${NC}"
    which openssl
    check_error $?
    echo -e "${green}* Checking keytool availability ...${NC}"
    which keytool
    check_error $?
}

check_openssl
rm_old
cleanup
setup
generate_ca
generate_mapserver
generate_apiserver
generate_irongui
generate_ifmapcli
generate_schema_xfer
generate_hostname
cleanup
