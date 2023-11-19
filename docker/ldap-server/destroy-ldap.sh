#!/bin/bash

supervisorctl stop openldap
rm -rf /etc/openldap/slapd.d/*
rm -rf /var/lib/ldap/*

