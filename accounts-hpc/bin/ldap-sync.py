#!/usr/bin/env python

import bonsai
import sys

from accounts_hpc.config import parse_config
from accounts_hpc.log import Logger


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    try:
        client = bonsai.LDAPClient(confopts['ldap']['server'])
        client.set_credentials(
                "SIMPLE",
                user=confopts['ldap']['user'],
                password=confopts['ldap']['password']
            )
        conn = client.connect()
    except bonsai.errors.AuthenticationError as exc:
        logger.error(exc)
        raise SystemExit(1)

    print(conn.whoami())

    print(conn.search(f"ou=People,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.ONE))



if __name__ == '__main__':
    main()
