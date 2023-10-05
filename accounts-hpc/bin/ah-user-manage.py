#!/usr/bin/env python

import sys
import argparse


from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, all_none, contains_exception, get_ssh_key_fingerprint

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound, IntegrityError, MultipleResultsFound
from unidecode import unidecode


def user_delete():
    pass


def user_update(logger, args, session):
    try:
        user = session.query(User).filter(User.ldap_username == args.username).one()

        if args.pubkey:
            try:
                key_content = args.pubkey.read().strip()
                key_fingerprint = get_ssh_key_fingerprint(key_content)
                dbkey = session.query(SshKey).filter(SshKey.fingerprint == key_fingerprint).one()
                if dbkey:
                    logger.error(f"Key {key_fingerprint} already found in DB for the user {args.username}")
                    raise SystemExit(1)

            except MultipleResultsFound:
                logger.error(f"Key {key_fingerprint} already found in DB")
                raise SystemExit(1)

            except NoResultFound:
                dbkey = SshKey(name=f'{user.first_name}{user.last_name}-additional-key',
                               fingerprint=key_fingerprint,
                               public_key=key_content,
                               uid_api=0)

                sshkeys_api = user.sshkeys_api
                if key_fingerprint not in sshkeys_api:
                    sshkeys_api.append(key_fingerprint)
                user.sshkeys_api = sshkeys_api
                if key_fingerprint not in user.mail_name_sshkey:
                    user.mail_name_sshkey.append(key_fingerprint)
                user.mail_is_sshkeyadded = False
                # purposley for that it gets triggered in ldap-update
                # user.sshkey.append(dbkey)
                session.add(dbkey)
                logger.info(f"Key {key_fingerprint} added for user {args.username}")

        if args.email:
            user.person_mail = args.email
            logger.info(f"Update email with {args.email} for user {args.username}")

        if args.oib:
            user.person_oib = int(args.oib)
            logger.info(f"Update OIB with {args.oib} for user {args.username}")

    except NoResultFound:
        logger.error('User {args.username} not found')
        raise SystemExit(1)


def user_key_add(logger, session, new_user, pubkey):
    key_content = pubkey.read().strip()
    key_fingerprint = get_ssh_key_fingerprint(key_content)

    try:
        dbkey = session.query(SshKey).filter(
            and_(
                SshKey.fingerprint == key_fingerprint,
                SshKey.user_id == new_user.id
            )).one()
        logger.info('Key already found in DB')

        sshkeys_api = new_user.sshkeys_api
        if not sshkeys_api:
            sshkeys_api = list()
        if key_fingerprint not in sshkeys_api:
            sshkeys_api.append(key_fingerprint)
        new_user.sshkeys_api = sshkeys_api

    except NoResultFound:
        dbkey = SshKey(name=f'{new_user.first_name}{new_user.last_name}-initial-key',
                       fingerprint=key_fingerprint,
                       public_key=key_content,
                       uid_api=0)

        sshkeys_api = new_user.sshkeys_api
        if not sshkeys_api:
            sshkeys_api = list()
        if key_fingerprint not in sshkeys_api:
            sshkeys_api.append(key_fingerprint)
        new_user.sshkeys_api = sshkeys_api
        new_user.sshkey.append(dbkey)
        session.add(new_user)

    except IntegrityError as exc:
        logger.error(f"Error while adding key - {repr(exc)}")

    return key_fingerprint


def user_project_add(logger, args, session):

    already_exists = False

    try:
        pr = session.query(Project).filter(Project.identifier == args.project).one()
    except NoResultFound as exc:
        logger.error(f"No project with identifier {args.project} found - {repr(exc)}")
        raise SystemExit(1)

    try:
        us = session.query(User).filter(and_(
            User.first_name == args.first,
            User.last_name == args.last,
        )).one()
        projects_api = us.projects_api
        if not projects_api:
            projects_api = list()
        if args.project not in projects_api:
            projects_api.append(args.project)
        us.projects_api = projects_api
        # always up to date fields
        us.person_mail = args.email
        us.is_active = True
        logger.info('User already found in cache DB')
        already_exists = True
        # exit for now
        raise SystemExit(1)

    except NoResultFound:
        us = User(first_name=args.first,
                  is_active=True,
                  is_opened=False,
                  is_dir_created=False,
                  is_deactivated=False,
                  mail_is_opensend=False,
                  mail_is_subscribed=False,
                  mail_is_sshkeyadded=False,
                  mail_name_sshkey=list(),
                  is_staff=False,
                  last_name=args.last,
                  person_mail=args.email,
                  projects_api=[args.project],
                  sshkeys_api=list(),
                  person_uniqueid=f"{args.first}{args.last}@UNIQUEID",
                  person_oib=0,
                  uid_api=0,
                  ldap_uid=0,
                  ldap_gid=0,
                  ldap_username='',
                  type_create='manual')

    if not already_exists:
        pr.user.append(us)
        session.add(pr)

    return us


def main():
    parser = argparse.ArgumentParser(description='Manage user create, change and delete manually with needed metadata about him')
    subparsers = parser.add_subparsers(help="User subcommands", dest="command")

    parser_create = subparsers.add_parser('create', help='Create user based on passed metadata')
    parser_create.add_argument('--first', dest='first', type=str, required=True, help='First name of user')
    parser_create.add_argument('--last', dest='last', type=str, required=True, help='Last name of user')
    parser_create.add_argument('--project', dest='project', type=str, required=True, help='Project identifier that user will be associated to')
    parser_create.add_argument('--pubkey', dest='pubkey', type=argparse.FileType(), required=True, help='File path od public key component')
    parser_create.add_argument('--email', dest='email', type=str, required=True, help='Email of the user')

    parser_update = subparsers.add_parser('update', help='Update user settings')
    parser_update.add_argument('--username', dest='username', type=str, required=True, help='Username of user')
    parser_update.add_argument('--pubkey', dest='pubkey', type=argparse.FileType(), required=False, help='File path od public key component')
    parser_update.add_argument('--email', dest='email', type=str, required=False, help='Email of the user')
    parser_update.add_argument('--oib', dest='oib', type=str, required=False, help='OIB of the user')

    parser_delete = subparsers.add_parser('delete', help='Delete user settings')

    args = parser.parse_args()

    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    if args.command == "create":
        new_user = user_project_add(logger, args, session)
        key_fingerprint = user_key_add(logger, session, new_user, args.pubkey)
        logger.info(f"Created user {args.first} {args.last} with key {key_fingerprint} and added to project {args.project}")
    elif args.command == "update":
        user_update(logger, args, session)
    elif args.command == "delete":
        user_delete(logger, args, session)

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
