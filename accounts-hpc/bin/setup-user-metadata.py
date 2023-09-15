#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound

import argparse


def gen_username(first, last, existusers):
    # ASCII convert
    name = first.lower()
    surname = last.lower()
    # take first char of name and first seven from surname
    username = name[0] + surname[:7]

    if username not in existusers:
        return username

    elif username in existusers:
        match = list()
        if len(username) < 8:
            match = list(filter(lambda u: u.startswith(username), existusers))
        else:
            match = list(filter(lambda u: u.startswith(username[:-1]), existusers))

        return username + str(len(match))


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Generate username, UID and GID numbers""")
    parser.add_argument('--verbose', dest='verbose', action='store_true', help='Report every step')
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users = session.query(User).all()
    all_usernames = [user.ldap_username for user in users]
    for user in users:
        if not user.ldap_username:
            user.ldap_username = gen_username(user.first_name, user.last_name, all_usernames)
            all_usernames.append(user.ldap_username)

    session.commit()
    session.close()


if __name__ == '__main__':
    main()