#!/usr/bin/env python

import bonsai
from accounts_hpc.config import parse_config


def main():
    confopts = parse_config()
    client = bonsai.LDAPClient(confopts['ldap']['server'])
    conn = client.connect()


if __name__ == '__main__':
    main()
