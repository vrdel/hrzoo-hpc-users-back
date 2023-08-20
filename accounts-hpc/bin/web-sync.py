#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config
from accounts_hpc.log import Logger

from sqlalchemy import create_engine


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite://{}".format(confopts['db']['path']), echo=True)


if __name__ == '__main__':
    main()
