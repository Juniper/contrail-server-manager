#comment out parameters from /etc/nova/api-paste.ini
sed -i 's/auth_host = /;auth_host = /' /etc/nova/api-paste.ini
sed -i 's/auth_port = /;auth_port = /' /etc/nova/api-paste.ini
sed -i 's/auth_protocol = /;auth_protocol = /' /etc/nova/api-paste.ini
sed -i 's/admin_tenant_name = /;admin_tenant_name = /' /etc/nova/api-paste.ini
sed -i 's/admin_user = /;admin_user = /' /etc/nova/api-paste.ini
sed -i 's/admin_password = /;admin_password = /' /etc/nova/api-paste.ini

#comment out parameters from /etc/cinder/api-paste.ini
sed -i 's/auth_host = /;auth_host = /' /etc/cinder/api-paste.ini
sed -i 's/auth_port = /;auth_port = /' /etc/cinder/api-paste.ini
sed -i 's/auth_protocol = /;auth_protocol = /' /etc/cinder/api-paste.ini
sed -i 's/admin_tenant_name = /;admin_tenant_name = /' /etc/cinder/api-paste.ini
sed -i 's/admin_user = /;admin_user = /' /etc/cinder/api-paste.ini
sed -i 's/admin_password = /;admin_password = /' /etc/cinder/api-paste.ini
