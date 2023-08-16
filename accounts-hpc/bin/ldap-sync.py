#!/usr/bin/env python

import bonsai
from accounts_hpc.config import parse_config


def main():
    confopts = parse_config()
    client = bonsai.LDAPClient(confopts['ldap']['server'])
    client.set_credentials(
            "SIMPLE",
            user=confopts['ldap']['user'],
            password=confopts['ldap']['password']
        )
    conn = client.connect()
    print(conn.whoami())

    print(conn.search(f"ou=People,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.ONE))



if __name__ == '__main__':
    main()
