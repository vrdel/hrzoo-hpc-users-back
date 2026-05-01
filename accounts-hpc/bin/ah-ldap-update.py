#!/usr/bin/env python

import asyncio
import argparse
import sys

from accounts_hpc.tasks.ldapupdate import LdapUpdate  # type: ignore
from accounts_hpc.shared import init as init_shared


async def main():
    parser = argparse.ArgumentParser(description="""Create, read and update ou=People and ou=Group entries in LDAP""")
    args = parser.parse_args()

    init_shared(sys.argv[0])

    await LdapUpdate(args).run()

if __name__ == '__main__':
    asyncio.run(main())
