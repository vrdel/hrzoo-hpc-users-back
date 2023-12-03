#!/usr/bin/env python

from accounts_hpc.tasks.ldapupdate import LdapUpdate  # type: ignore

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="""Create, read and update ou=People and ou=Group entries in LDAP""")
    args = parser.parse_args()

    LdapUpdate(sys.argv[0], args).run()


if __name__ == '__main__':
    main()
