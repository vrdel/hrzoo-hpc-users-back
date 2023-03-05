# hrzoo-hpc-users-back - LDAP server

## container build

```
docker build \
--build-arg RHUSER=user \
--build-arg RHPASS=pass \
. \
-t ipanema:5000/hrzoo-ldapserv
```
