#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.config import parse_config
from accounts_hpc.log import Logger
from accounts_hpc.db import Base

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

    import ipdb; ipdb.set_trace()

    if args.init:
        Base.metadata.create_all(engine)

if __name__ == '__main__':
    main()
