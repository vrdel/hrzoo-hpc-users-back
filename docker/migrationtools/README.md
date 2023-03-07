# hrzoo-hpc-users-back - Centos7 migrationtools

## container build

```
docker build \
--build-arg MAIL="srce.hr" \
--build-arg BASEDN="dc=hpc,dc=srce,dc=hr" \
. \
-t ipanema:5000/migrationtools
```

## sample ldif

Example LDAP ldifs will be generated from `/etc/passwd` and `/etc/groups` and placed in `/home/user`.
