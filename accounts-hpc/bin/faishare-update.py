#!/usr/bin/env python

import sys
import os

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound

import argparse
import json


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Update PBS fairshare resource_group""")
    parser.add_argument('--new', dest='new', action='store_true', help='create new resource_group from scratch')
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    fairshare_path = confopts['usersetup']['pbsfairshare_path']

    if fairshare_path:
        fsobj = None

        try:
            if args.new:
                fsobj = open(fairshare_path, "x")
            else:
                fsobj = open(fairshare_path, "r+")
        except FileNotFoundError as exc:
            logger.error(exc)
            raise SystemExit(1)

        projects = session.query(Project).all()
        all_proj_identifiers = list()
        for project in projects:
            all_proj_identifiers.append(project.identifier)

        if args.new:
            fs_lines_write = list()
            nline = 1
            for ident in all_proj_identifiers:
                line_to_write = '{0:<32} {1:03} root 100\n'.format(ident, nline)
                nline += 1
                fs_lines_write.append(line_to_write)
            fsobj.writelines(fs_lines_write)
        else:
            fs_lines = fsobj.readlines()

        fsobj.close()


    session.commit()
    session.close()


if __name__ == '__main__':
    main()
