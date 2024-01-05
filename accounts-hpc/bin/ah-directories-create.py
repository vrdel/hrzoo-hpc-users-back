#!/usr/bin/env python

import argparse
import sys
import json

from accounts_hpc.tasks.createdirectories import DirectoriesCreate


def main():
    parser = argparse.ArgumentParser(description="""Create user and project directories""")
    args = parser.parse_args()

    DirectoriesCreate(sys.argv[0], args).run()


if __name__ == '__main__':
    main()
