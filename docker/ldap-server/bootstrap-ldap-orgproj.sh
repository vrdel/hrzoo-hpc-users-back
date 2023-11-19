#!/bin/bash

slapadd -n 0 -F /etc/openldap/slapd.d -l /etc/openldap/slapd.ldif
echo "olcTLSCertificateFile: /etc/openldap/certs/ldap.cert" >> /etc/openldap/slapd.d/cn=config.ldif
echo "olcTLSCertificateKeyFile: /etc/openldap/certs/ldap.key" >> /etc/openldap/slapd.d/cn=config.ldif
chown ldap:ldap -R /etc/openldap/slapd.d
supervisorctl start openldap
ldapadd -h localhost -x -w foobar -D "cn=Manager,dc=hpc,dc=srce,dc=hr" -f ~/ldap-conf/project-as-org/base/base-project-org.ldif
