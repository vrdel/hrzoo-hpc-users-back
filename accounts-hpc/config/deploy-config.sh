#!/bin/bash

IFS=" "

for file in $(echo "*.$1")
do
	echo cp -f $file ${file%.$1}
	cp -f $file ${file%.$1}
    sudo chown root:root ../logrotate.d/*
done
