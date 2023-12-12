#!/bin/bash

test -z $1 && TAG="latest" || TAG="$1"

podman run \
-e "DISPLAY=unix$DISPLAY" \
--log-driver json-file \
--log-opt max-size=10m \
-v /dev/log:/dev/log \
-v /etc/localtime:/etc/localtime \
-v /tmp/.X11-unix:/tmp/.X11-unix \
-v /sys/fs/cgroup:/sys/fs/cgroup \
-v $HOME:/mnt \
-v $HOME/.ssh/:/home/user/.ssh \
-v $PWD/ldap-conf:/home/user/ldap-conf \
--tmpfs /tmp --tmpfs /run \
-h docker-hrzooldapclientopensuse15 \
--name hrzoo-ldapclient-opensuse15 \
--rm -ti \
-u root \
hrzoo-ldapclient-opensuse15:$TAG /sbin/init
