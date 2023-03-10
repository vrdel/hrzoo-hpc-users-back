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
--tmpfs /tmp --tmpfs /run \
-v $HOME/.zsh_history:/home/user/.zsh_history \
-v $HOME:/mnt/ \
-v $HOME/.ssh:/home/user/.ssh/ \
-h docker-rh7 \
--net host \
--name hrzoo-migrationtools \
-u user \
--rm -ti \
ipanema:5000/migrationtools:$TAG
