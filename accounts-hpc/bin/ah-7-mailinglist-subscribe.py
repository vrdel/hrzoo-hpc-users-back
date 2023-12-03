#!/usr/bin/env python

import asyncio
import argparse
import sys

from accounts_hpc.tasks.listsubscribe import ListSubscribe
from accounts_hpc.exceptions import SyncHttpError


def main():
    parser = argparse.ArgumentParser(description="""Subscribe new users to mailing list""")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()

    try:
        list_subscribe = ListSubscribe(sys.argv[0], args)
        loop.run_until_complete(list_subscribe.run())

    except (SyncHttpError, KeyboardInterrupt):
        pass


if __name__ == '__main__':
    main()
