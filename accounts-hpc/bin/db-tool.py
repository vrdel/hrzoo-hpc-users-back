#!/usr/bin/env python

import sys
import argparse


from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base  # type: ignore

from sqlalchemy import create_engine


def main():
    parser = argparse.ArgumentParser(description='DB tool that help with initial create and evolution of database')
    parser.add_argument('--init', dest='init', action='store_true',
                        help='Create database with table structure')

    args = parser.parse_args()

    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']), echo=True)

    if args.init:
        Base.metadata.create_all(engine)


if __name__ == '__main__':
    main()
