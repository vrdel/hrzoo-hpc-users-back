#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.db import Base  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

from sqlalchemy import create_engine


def main():
    parser = argparse.ArgumentParser(description='DB tool that help with initial create and evolution of database')
    parser.add_argument('--init', dest='init', action='store_true',
                        help='Create database with table structure')

    args = parser.parse_args()

    shared = Shared(sys.argv[0])
    confopts = shared.confopts

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']), echo=True)

    if args.init:
        Base.metadata.create_all(engine)


if __name__ == '__main__':
    main()
