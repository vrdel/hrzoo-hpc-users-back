# hrzoo-hpc-users-back - Centos7 migrationtools 

## container build

```
docker build \
--build-arg MAIL="srce.hr" \
--build-arg BASEDN="dc=hpc,dc=srce,dc=hr" \ 
. \
-t ipanema:5000/migrationtools
```
