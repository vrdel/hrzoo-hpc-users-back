#!/usr/bin/env python

import argparse
import sys

from accounts_hpc.tasks.usermetadata import UserMetadata  # type: ignore


def main():
    parser = argparse.ArgumentParser(description="""Generate username, UID and GID numbers""")
    parser.add_argument('--verbose', dest='verbose', action='store_true', help='Report every step')
    args = parser.parse_args()

    UserMetadata(sys.argv[0], args).run()


if __name__ == '__main__':
    main()
