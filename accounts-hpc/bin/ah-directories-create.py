#!/usr/bin/env python

import argparse
import asyncio
import sys
import json

from accounts_hpc.tasks.createdirectories import DirectoriesCreate
from accounts_hpc.shared import init as init_shared


async def main():
    parser = argparse.ArgumentParser(description="""Create user and project directories""")
    args = parser.parse_args()

    init_shared(sys.argv[0])

    await DirectoriesCreate(args).run()


if __name__ == '__main__':
    asyncio.run(main())
