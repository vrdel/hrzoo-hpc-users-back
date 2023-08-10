# hrzoo-hpc-users-back
HRZOO HPC users backend component

## Development environment

### Containers

Build:
```
docker/ldap-server/$ docker build . -t ipanema:5000/hrzoo-ldapserv
docker/ldap-client/$ docker build . -t ipanema:5000/hrzoo-ldapclient
```

Further customization with shell settings etc.
```
docker/$ docker compose up
docker exec -t -u user -i hrzoo-client /bin/zsh
docker exec -t -u user -i hrzoo-ldapserv /bin/zsh
./chezmoi-config-apply.sh
```

#### Predefined settings

These settings are implied in the configuration files of server and client:
* hostnames: `docker-hrzooldapserv`, `docker-hrzooldapclient`
* base LDAP DN: `dc=hpc,dc=srce,dc=hr`
* LDAP password: `foobar`

### CA and LDAP certificate

* CA certificate
```
openssl ecparam -out root.key -name prime256v1 -genkey
openssl req -new -sha256 -key root.key -out root.csr
openssl x509 -req -sha256 -days 3650 -in root.csr -signkey root.key -out root.cert
```
* CA signed LDAP certificate
```
openssl ecparam -out ldap.key -name prime256v1 -genkey
openssl req -new -sha256 -key ldap.key -out ldap.csr
openssl x509 -req -in ldap.csr -CA root.cert -CAkey root.key -CAcreateserial -out ldap.cert -days 3650 -sha256
```

### OpenLDAP configuration

Container context:
```
docker exec -t -u user -i hrzoo-ldapserv /bin/zsh
```

Initial configuration:
```
sudo su -c 'VIFM=/home/user/.config/vifm /home/user/.bin/vifm/bin/vifm'
sudo slapadd -n 0 -F /etc/openldap/slapd.d -l /etc/openldap/slapd.ldif
sudo chown -R ldap:ldap /etc/openldap/slapd.d/
```

Append to `/etc/openldap/slapd.d/cn=config.ldif`:
```
olcTLSCertificateFile: /etc/openldap/certs/ldap.cert
olcTLSCertificateKeyFile: /etc/openldap/certs/ldap.key
```

Restart service:
```
sudo supervisorctl restart openldap
```

#### Base ldifs

Preset password=`foobar`
```
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/base.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/group.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/passwd.ldif
```

#### sudoers ldif

```
sudo -s
export SUDOERS_BASE="ou=SUDOers,dc=hpc,dc=srce,dc=hr"
cvtsudoers -f ldif -o /tmp/sudoers.ldif /etc/sudoers
```

Edit `/tmp/sudoers.ldif` and prepend:
```
dn: ou=SUDOers,dc=hpc,dc=srce,dc=hr
objectClass: top
objectClass: organizationalUnit
ou: SUDOers
description: SUDOers container

dn: cn=defaults,ou=SUDOers,dc=hpc,dc=srce,dc=hr
...
```

```
ldapadd -x -W -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /tmp/sudoers.ldif
```

#### Test query

Initiate test query and watch logs:
```
sudo ldapsearch -x -h localhost
tail -f /home/user/ldap-logs
```

#### Save changes

Commit changes:
```
docker commit hrzoo-ldapserv ipanema:5000/hrzoo-ldapserv
```
