#!/usr/bin/env python

import asyncio
import argparse
import sys

from accounts_hpc.tasks.ldapupdate import LdapUpdate  # type: ignore


async def main():
    parser = argparse.ArgumentParser(description="""Create, read and update ou=People and ou=Group entries in LDAP""")
    args = parser.parse_args()

    await LdapUpdate(sys.argv[0], args).run()

if __name__ == '__main__':
    asyncio.run(main())
