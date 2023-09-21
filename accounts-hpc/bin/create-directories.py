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

    parser = argparse.ArgumentParser(description="""Create user and project directories""")
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users = session.query(User).all()
    for user in users:
        if not user.is_dir_created:
            completed = 0

            for dir in confopts['usersetup']['userdirs_in']:
                try:
                    os.mkdir(dir + user.ldap_username, 0o700)

                except FileExistsError:
                    pass
                except (PermissionError, FileNotFoundError) as exc:
                    logger.error(exc)
                    break

                try:
                    os.chown(dir + user.ldap_username, user.ldap_uid, user.ldap_gid)
                    completed += 1

                except (PermissionError, OSError, FileNotFoundError) as exc:
                    logger.error(exc)

            if completed == len(confopts['usersetup']['userdirs_in']):
                user.is_dir_created = True
                logger.info(f"Created {dir + user.ldap_username} with perm {user.ldap_uid}:{user.ldap_gid}")

    projects = session.query(Project).all()
    for project in projects:
        pass

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
