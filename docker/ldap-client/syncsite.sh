#!/bin/bash

SITEPACK=$(python3 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

printf "**** sync sitepkg64\n"
rsync -avz $(echo $SITEPACK/ | sed "s/lib\//lib64\//" ) /home/user/pysitepkg/sitepkg64

# printf "**** sync sitepkg32\n"
# rsync -avz --exclude='*node_modules*' $SITEPACK/ /root/pysitepkg/sitepkg32
