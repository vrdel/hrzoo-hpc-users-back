#!/bin/bash

declare -a paths

paths=("$HOME/my_work/srce/git.hrzoo-hpc-users-back/hrzoo-hpc-users-back/docker/ldap-client/pysitepkg/sitepkg32" \
	"$HOME/my_work/srce/git.hrzoo-hpc-users-back/hrzoo-hpc-users-back/docker/ldap-client/pysitepkg/sitepkg64")

# additional manual append
paths[${#paths[@]}+1]="/home/dvrcic/my_work/srce/git.hrzoo-hpc-users-back/hrzoo-hpc-users-back/docker/ldap-client/pysitepkg/sitepkg64/accounts_hpc/"

for f in ${paths[@]}
do
	PYTHONPATH="$PYTHONPATH:$f"
done

export PYTHONPATH
