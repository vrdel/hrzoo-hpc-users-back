#!/usr/bin/env python

import sys
import asyncio
import argparse

from accounts_hpc.tasks.fairshare import FairshareUpdate


async def main():
    parser = argparse.ArgumentParser(description="""Update PBS fairshare resource_group""")
    parser.add_argument('--new', dest='new', action='store_true', help='create new resource_group from scratch')
    args = parser.parse_args()

    await FairshareUpdate(sys.argv[0], args).run()


if __name__ == '__main__':
    asyncio.run(main())
