#!/bin/bash

test -z $1 && TAG="latest" || TAG="$1"

docker run \
--privileged \
-e "DISPLAY=unix$DISPLAY" \
--log-driver json-file \
--log-opt max-size=10m \
-v /dev/log:/dev/log \
-v /etc/localtime:/etc/localtime \
-v /tmp/.X11-unix:/tmp/.X11-unix \
-v /sys/fs/cgroup:/sys/fs/cgroup:ro \
-v $HOME:/mnt \
-v $HOME/.ssh/:/home/user/.ssh \
-v $PWD/ldap-conf:/home/user/ldap-conf \
--tmpfs /tmp --tmpfs /run \
-h docker-hrzooldapclientdebian \
--name hrzoo-ldapclient-debian \
--rm -ti \
-u root \
ipanema:5000/hrzoo-ldapclient-debian11:$TAG
