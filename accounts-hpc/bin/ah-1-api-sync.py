#!/usr/bin/env python

import asyncio
import sys

from accounts_hpc.tasks.apisync import ApiSync

import argparse


def main():
    parser = argparse.ArgumentParser(description="""Sync projects and users from HRZOO-SIGNUP-API to SQLite cache""")
    parser.add_argument('--init-set', dest='initset', action='store_true', help='initial sync with all associations and flags set so no further tools in the pipeline will be triggered')
    args = parser.parse_args()

    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(ApiSync(sys.argv[0], args).run())

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
