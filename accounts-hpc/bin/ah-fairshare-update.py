#!/usr/bin/env python

import sys
import asyncio
import argparse

from accounts_hpc.tasks.fairshare import FairshareUpdate
from accounts_hpc.shared import init as init_shared


async def main():
    parser = argparse.ArgumentParser(description="""Update PBS fairshare resource_group""")
    parser.add_argument('--new', dest='new', action='store_true', help='create new resource_group from scratch')
    args = parser.parse_args()

    init_shared(sys.argv[0])

    await FairshareUpdate(args).run()


if __name__ == '__main__':
    asyncio.run(main())
