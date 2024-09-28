#!/bin/bash

IFS=" "
suffix=""
CHOWN_USER1="dvrcic"
CHOWN_USER2="root"
SYSTEMD_PATH="/usr/lib/systemd/system/"
SYSTEMD_UNIT="hrzoo-accounts-taskd.service"

usage()
{
	printf "Usage: %s [argument]\n" $(basename $0) >&2
	printf "       [-c]            - change permissions of copied over files\n" >&2
	printf "       [-s]            - suffix extension of config files that will be copied over\n" >&2
	exit 2
}

if [[ $# == 0 ]]
then
    usage
fi

while getopts 'chs:' OPTION
do
    case $OPTION in
        s)
            suffix=$OPTARG
             ;;
        c)
            chown=1
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
            if [ ! -z "${chown}" ]
            then
                echo "chowning ${CHOWN_USER1}: ${file%.${suffix}}"
                chown ${CHOWN_USER1} ${file%.${suffix}}
            fi
        done
    fi

		if [[ ! -z "${chown}" && -d ../logrotate.d ]]
		then
				echo -e "\n* chowning ../logrotate.d"
				chown ${CHOWN_USER2} ../logrotate.d/*
		fi

    echo -e "\n* deploying emails..."
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
            if [ ! -z "${chown}" ]
            then
                echo "chowning ${CHOWN_USER1}: ${file%.${suffix}}"
                chown ${CHOWN_USER1} ${file%.${suffix}}
            fi
        done
    fi

		if [ ! -e ${SYSTEMD_PATH}/${SYSTEMD_UNIT} ] && [ ! -L ${SYSTEMD_PATH}/${SYSTEMD_UNIT} ]
		then
			echo -e "\n* deploying systemd unit..."
			echo -e "ln -s ${PWD}/../usr/lib/systemd/system/${SYSTEMD_UNIT} ${SYSTEMD_PATH}"
			ln -s ${PWD}/../../usr/lib/systemd/system/${SYSTEMD_UNIT} ${SYSTEMD_PATH}
			echo -e "systemctl daemon-reload"
			systemctl daemon-reload
		fi
fi
