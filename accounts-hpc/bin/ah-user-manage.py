#!/usr/bin/env python

import sys
import argparse


from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, all_none, contains_exception

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound
from unidecode import unidecode


def user_project_add(args, session, project, user, uid, email):
    try:
        pr = session.query(Project).filter(
            Project.identifier == project).one()
    except NoResultFound:
        raise SystemExit(1)

    try:
        us = session.query(User).filter(
            User.ldap_username == user).one()
        projects_api = us.projects_api
        if not projects_api:
            projects_api = list()
        if project not in projects_api:
            projects_api.append(project)
        us.projects_api = projects_api
        # always up to date fields
        us.person_mail = email
        us.person_uniqueid = 'NOT_SET'
        us.is_active = True

    except NoResultFound:
        us = User(first_name='NOT_SET',
                  is_active=True,
                  is_opened=False,
                  is_dir_created=False,
                  is_deactivated=False,
                  mail_is_opensend=False,
                  mail_is_subscribed=False,
                  mail_is_sshkeyadded=False,
                  mail_name_sshkey=list(),
                  is_staff=False,
                  last_name='NOT_SET',
                  person_mail='NOT_SET',
                  projects_api=[project],
                  sshkeys_api=list(),
                  person_uniqueid='NOT_SET',
                  person_oib=0,
                  uid_api=uid,
                  ldap_uid=0,
                  ldap_gid=0,
                  ldap_username='')

    session.add(us)


def main():
    parser = argparse.ArgumentParser(description='Create user manually with needed metadata about him')
    parser.add_argument('--first', dest='first', type=str, required=True, help='First name of user')
    parser.add_argument('--last', dest='last', type=str, required=True, help='Last name of user')
    parser.add_argument('--project', dest='project', type=str, required=True, help='Project identifier that user will be associated to')
    parser.add_argument('--pubkey', dest='pubkey', type=str, required=True, help='File patch od public key component')
    parser.add_argument('--email', dest='email', type=str, required=True, help='Email of the user')
    parser.add_argument('--uid', dest='uid', type=int, required=True, help='UID of the user')

    args = parser.parse_args()

    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    user_project_add(args, session, args.project, args.username, args.uid, args.email)

    session.commit()
    session.close()

if __name__ == '__main__':
    main()
