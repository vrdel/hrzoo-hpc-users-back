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
    pattern="*.${suffix}"
    files=()
    while read line
    do
        files+=("$line")
    done < <(find . -maxdepth 1 -type f -name "$pattern")

    if [ ${#files[@]} -eq 0 ] || [ "${files[0]}" = "$pattern" ]
    then
        echo "No files matching pattern ${pattern} found."
    else
        for file in "${files[@]}"
        do
            echo "cp -f ${file} ${file%.${suffix}}"
            cp -f ${file} ${file%.${suffix}}
        done
    fi

    if [ -d ../logrotate.d ]
    then
        echo "* chowning ../logrotate.d"
        sudo chown root:root ../logrotate.d/*
    fi

    echo "* deploying emails..."
    pattern="*.${suffix}"
    files=()
    while read line
    do
        files+=("$line")
    done < <(find ./emails/ -maxdepth 1 -type f -name "$pattern")

    if [ ${#files[@]} -eq 0 ] || [ "${files[0]}" = "$pattern" ]
    then
        echo "No files matching pattern ${pattern} found."
    else
        for file in "${files[@]}"
        do
            echo "cp -f ${file} ${file%.${suffix}}"
            cp -f ${file} ${file%.${suffix}}
        done
    fi
fi
