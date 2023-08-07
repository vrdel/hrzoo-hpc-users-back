# hrzoo-hpc-users-back
HRZOO HPC users backend component

## Development

### openldap configuration

```
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/base.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/group.ldif
sudo ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f /home/user/ldap-conf/base/passwd.ldif
```
