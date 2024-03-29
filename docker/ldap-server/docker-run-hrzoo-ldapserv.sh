#!/bin/bash

test -z $1 && TAG="latest" || TAG="$1"

docker run \
-e "DISPLAY=unix$DISPLAY" \
--log-driver json-file \
--log-opt max-size=10m \
-v /dev/log:/dev/log \
-v /etc/localtime:/etc/localtime \
-v /tmp/.X11-unix:/tmp/.X11-unix \
-v /sys/fs/cgroup:/sys/fs/cgroup:ro \
-v $HOME:/mnt/ \
-v $HOME/.ssh:/home/user/.ssh/ \
-v $PWD/ldap-conf:/home/user/ldap-conf \
-h docker-hrzooldapserv \
--name hrzoo-ldapserv \
--rm -ti \
ipanema:5000/hrzoo-ldapserv:$TAG
