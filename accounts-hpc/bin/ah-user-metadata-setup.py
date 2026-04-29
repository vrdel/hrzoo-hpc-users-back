#!/usr/bin/env python

import asyncio
import argparse
import sys

from accounts_hpc.tasks.usermetadata import UserMetadata  # type: ignore
from accounts_hpc.shared import init as init_shared


async def main():
    parser = argparse.ArgumentParser(description="""Generate username, UID and GID numbers""")
    parser.add_argument('--verbose', dest='verbose', action='store_true', help='Report every step')
    args = parser.parse_args()

    init_shared(sys.argv[0])

    await UserMetadata(args).run()


if __name__ == '__main__':
    asyncio.run(main())
