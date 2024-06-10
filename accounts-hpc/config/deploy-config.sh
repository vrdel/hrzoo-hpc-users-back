#!/bin/bash

IFS=" "
suffix=""

usage()
{
	printf "Usage: %s [argument]\n" $(basename $0) >&2
	printf "       [-s]            - suffix extension of config files that will be copied over\n" >&2
	exit 2
}

if [[ $# == 0 ]]
then
    usage
fi

while getopts 'hs:' OPTION
do
    case $OPTION in
        s)
            suffix=$OPTARG
             ;;

        h)
            usage
            ;;
        ?)
            usage
            ;;
    esac
done

let ok=0
if [ ! -z "$suffix" ]
then
    echo "* deploying configs..."
    for file in $(echo "*.${suffix}")
    do
        echo cp -f $file ${file%.${suffix}}
        cp -f $file ${file%.${suffix}}
        ok=1
    done

    if [ -d ../logrotate.d ]
    then
        echo "* chowning ../logrotate.d"
        sudo chown root:root ../logrotate.d/*
    fi

    echo "* deploying emails..."
    for file in $(echo "emails/*.${suffix}")
    do
        echo cp -f $file ${file%.${suffix}}
        cp -f $file ${file%.${suffix}}
        ok=1
    done
fi
