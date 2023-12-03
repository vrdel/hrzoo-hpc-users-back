#!/usr/bin/env python

import sys

from accounts_hpc.db import Project, User  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound

import argparse
import json


def gen_username(first: str, last: str, existusers: list[str]) -> str:
    # ASCII convert
    name = first.lower()
    surname = last.lower()
    # take first char of name and first seven from surname
    username = name[0] + surname[:7]

    if username in existusers:
        match = list()
        if len(username) < 8:
            match = list(filter(lambda u: u.startswith(username), existusers))
        else:
            match = list(filter(lambda u: u.startswith(username[:-1]), existusers))

        return username + str(len(match))

    else:
        return username


def main():
    parser = argparse.ArgumentParser(description="""Generate username, UID and GID numbers""")
    parser.add_argument('--verbose', dest='verbose', action='store_true', help='Report every step')
    args = parser.parse_args()

    shared = Shared(sys.argv[0])
    confopts = shared.confopts
    logger = shared.log.get()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    mapuser = list()

    if confopts['usersetup']['usermap']:
        with open(confopts['usersetup']['usermap'], mode='r') as fp:
            mapuser = json.loads(fp.read())

    projects = session.query(Project).all()
    for project in projects:
        if not project.ldap_gid:
            project.ldap_gid = confopts['usersetup']['gid_offset'] + project.prjid_api

    users = session.query(User).all()

    all_usernames = [user.ldap_username for user in users if user.ldap_username]
    for user in users:
        set_metadata = False

        if user.is_active == 0:
            continue

        if not user.ldap_username:
            user.ldap_username = gen_username(user.first_name, user.last_name, all_usernames)
            all_usernames.append(user.ldap_username)
            set_metadata = True
        if not user.ldap_uid and not user.is_staff:
            if user.type_create == 'manual':
                target_user = [tu for tu in mapuser if tu['username'] == user.ldap_username]
                if target_user:
                    user.ldap_uid = target_user[0]['uid']
                else:
                    logger.warning(f"UID for manually created user {user.ldap_username} must be defined in mapping file")
                    logger.warning("Skipping UID set")
            else:
                user.ldap_uid = confopts['usersetup']['uid_offset'] + user.uid_api
            set_metadata = True
        if not user.ldap_gid and not user.is_staff and user.project:
            # user GID is always set to GID of last assigned project
            # we assume here that --init-set is run and relation between user,project is set
            user.ldap_gid = confopts['usersetup']['gid_offset'] + user.project[-1].prjid_api
            set_metadata = True
        if not user.ldap_gid and not user.is_staff and not user.project:
            # set ldap_gid based on user.projects_api last project
            try:
                target_project = [pr for pr in projects if pr.identifier == user.projects_api[-1]]
                user.ldap_gid = confopts['usersetup']['gid_offset'] + target_project[0].prjid_api
                set_metadata = True
            except IndexError:
                logger.warning(f"User {user.ldap_username} type={user.type_create} with empty projects_api")
        if user.is_staff and not user.ldap_uid:
            target_user = [tu for tu in mapuser if tu['username'] == user.ldap_username]
            if target_user:
                user.ldap_uid = target_user[0]['uid']
            else:
                user.ldap_uid = confopts['usersetup']['uid_manual_offset'] + user.uid_api
            set_metadata = True
        if user.is_staff and not user.ldap_gid:
            target_user = [tu for tu in mapuser if tu['username'] == user.ldap_username]
            if target_user:
                user.ldap_gid = target_user[0]['gid']
                set_metadata = True

        if set_metadata:
            logger.info(f"{user.first_name} {user.last_name} set username={user.ldap_username} UID={user.ldap_uid} GID={user.ldap_gid}")

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
