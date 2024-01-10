#!/usr/bin/env python

import argparse
import asyncio
import sys
import json

from accounts_hpc.tasks.createdirectories import DirectoriesCreate


async def main():
    parser = argparse.ArgumentParser(description="""Create user and project directories""")
    args = parser.parse_args()

    await DirectoriesCreate(sys.argv[0], args).run()


if __name__ == '__main__':
    asyncio.run(main())
