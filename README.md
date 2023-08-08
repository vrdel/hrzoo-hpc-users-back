# hrzoo-hpc-users-back
HRZOO HPC users backend component

## Development

### certificate

* root CA
```
openssl ecparam -out root.key -name prime256v1 -genkey
openssl req -new -sha256 -key root.key -out root.csr
openssl x509 -req -sha256 -days 3650 -in root.csr -signkey root.key -out root.cert
```
* root CA signed certificate
```
openssl ecparam -out ldap.key -name prime256v1 -genkey
openssl req -new -sha256 -key ldap.key -out ldap.csr
openssl x509 -req -in ldap.csr -CA root.cert -CAkey root.key -CAcreateserial -out ldap.cert -days 3650 -sha256
```

### openldap configuration

```
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/base.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/group.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/passwd.ldif
```
