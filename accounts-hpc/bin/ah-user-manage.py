#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, all_none, contains_exception, get_ssh_key_fingerprint

from rich import print
from rich.columns import Columns
from rich.table import Table
from rich.console import Console
from rich.pretty import pprint

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import NoResultFound, IntegrityError, MultipleResultsFound
from unidecode import unidecode


def flush_users(logger, session):
    users = session.query(User).all()

    for user in users:
        if len(user.sshkey) == 0 and len(user.project) == 0:
            session.delete(user)
            logger.info(f'Flushing {user.ldap_username}')


def flush_sshkeys(logger, session):
    keys_noowner = session.query(SshKey).filter(SshKey.user_id == None)

    if keys_noowner.count() > 0:
        keys_noowner.delete()
        logger.info('All keys without owner flushed')
    else:
        logger.info('No keys without owner found')


def user_delete(logger, args, session):
    try:
        user = session.query(User).filter(User.ldap_username == args.username).one()
        user_keys = user.sshkey

        if args.pubkey:
            found = False

            for key in user_keys:
                if args.pubkey in key.public_key:
                    if args.force:
                        user.sshkeys_api.remove(key.fingerprint)
                        session.delete(key)
                        logger.info(f"Key {key.fingerprint} DB relation deleted for {args.username}")
                    else:
                        user.sshkeys_api.remove(key.fingerprint)
                        logger.info(f"Key {key.fingerprint} deleted for {args.username}")
                    found = True

            if not found:
                logger.info(f"Key not found for {args.username}")

        elif args.project:
            try:
                project = session.query(Project).filter(Project.identifier == args.project).one()
            except NoResultFound as exc:
                logger.error(f"No project with identifier {args.project} found - {repr(exc)}")

            if args.project in user.projects_api:
                user.projects_api.remove(project.identifier)
                logger.info(f"Removed {user.ldap_username} from {project.identifier}")

            if args.force:
                try:
                    project.user.remove(user)
                    session.add(project)
                    logger.info(f"Removed {user.ldap_username} DB relation from {project.identifier}")

                except ValueError:
                    logger.error(f"{user.ldap_username} not in {project.identifier}")

        else:
            if args.force:
                for key in user_keys:
                    session.delete(key)
                session.delete(user)
                logger.info(f"Deleted {args.username} and keys and all DB relations")
            else:
                user.projects_api = []
                user.sshkeys_api = []
                user.is_active = 0
                logger.info(f"Deleted {args.username} and keys")

    except NoResultFound:
        logger.error(f"User {args.username} not found")
        raise SystemExit(1)


def user_update(logger, args, session):
    try:
        user = session.query(User).filter(User.ldap_username == args.username).one()

        if args.pubkey:
            try:
                key_content = args.pubkey.read().strip()
                key_fingerprint = get_ssh_key_fingerprint(key_content)
                dbkey = session.query(SshKey).filter(and_(
                    SshKey.fingerprint == key_fingerprint,
                    SshKey.user_id == user.id
                )).one()
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

                if args.force:
                    user.sshkey.append(dbkey)
                    logger.info(f"Key {key_fingerprint} DB relation added for user {args.username}")
                else:
                    logger.info(f"Key {key_fingerprint} added for user {args.username}")

                session.add(dbkey)

        if args.email:
            user.person_mail = args.email
            logger.info(f"Update email with {args.email} for user {args.username}")

        if args.oib:
            user.person_oib = int(args.oib)
            logger.info(f"Update OIB with {args.oib} for user {args.username}")

        if args.staff:
            user.is_staff = True
            logger.info(f"Promote user {args.username} to staff")

        if args.uid:
            user.uid = args.uid
            logger.info(f"Setting user {args.username} UID={args.uid}")

        if args.project:
            try:
                project = session.query(Project).filter(Project.identifier == args.project).one()
            except NoResultFound as exc:
                logger.error(f"No project with identifier {args.project} found - {repr(exc)}")
                raise SystemExit(1)

            projects_api = user.projects_api
            if not projects_api:
                projects_api = list()
            if args.project in projects_api:
                logger.info(f"User {user.ldap_username} already assigned to project {args.project}")
            elif args.project not in projects_api:
                projects_api.append(args.project)
                logger.info(f"User {user.ldap_username} added to project {args.project}")
            user.projects_api = projects_api

            if args.force:
                project.user.append(user)
                logger.info(f"Project {args.project} DB relation added for user {user.ldap_username}")
                session.add(project)

        if args.flagissubscribed and args.flagissubscribed > 0:
            user.mail_is_subscribed = True
        elif args.flagissubscribed == 0:
            user.mail_is_subscribed = False
        if args.flagissubscribed != None:
            logger.info(f"Set mail_is_subscribed={args.flagissubscribed} for {user.ldap_username}")

        if args.flagisdircreated and args.flagisdircreated > 0:
            user.is_dir_created = True
        elif args.flagisdircreated == 0:
            user.is_dir_created = False
        if args.flagisdircreated != None:
            logger.info(f"Set is_dir_created={args.flagisdircreated} for {user.ldap_username}")

        if args.flagisdeactivated and args.flagisdeactivated > 0:
            user.is_deactivated = True
        elif args.flagisdeactivated == 0:
            user.is_deactivated = False
        if args.flagisdeactivated != None:
            logger.info(f"Set is_deactivated={args.flagisdeactivated} for {user.ldap_username}")

        if args.flagisopensend and args.flagisopensend > 0:
            user.mail_is_opensend = True
        elif args.flagisopensend == 0:
            user.mail_is_opensend = False
        if args.flagisopensend != None:
            logger.info(f"Set mail_is_opensend={args.flagisopensend} for {user.ldap_username}")

        if args.flagissshkeyadded and args.flagissshkeyadded > 0:
            user.mail_is_sshkeyadded = True
            user.mail_name_sshkey = []
        elif args.flagissshkeyadded == 0:
            user.mail_is_sshkeyadded = False
        if args.flagissshkeyadded != None:
            logger.info(f"Set mail_is_sshkeyadded={args.flagissshkeyadded} for {user.ldap_username}")

        if args.flagisactive and args.flagisactive > 0:
            user.is_active = True
        elif args.flagisactive == 0:
            user.is_active = False
        if args.flagisactive != None:
            logger.info(f"Set is_active={args.flagisactive} for {user.ldap_username}")

        if args.typecreate != None:
            logger.info(f"Set type_create={args.typecreate} for {user.ldap_username}")
            user.type_create = args.typecreate

    except NoResultFound:
        logger.error(f"User {args.username} not found")
        raise SystemExit(1)


def user_key_add(logger, args, session, new_user, pubkey):
    key_content = pubkey.read().strip()
    key_fingerprint = get_ssh_key_fingerprint(key_content)

    try:
        dbkey = session.query(SshKey).filter(
            and_(
                SshKey.fingerprint == key_fingerprint,
                SshKey.user_id == new_user.id
            )).one()
        logger.info(f'Key already found in DB for {new_user}')

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

        if args.force:
            new_user.sshkey.append(dbkey)
        else:
            session.add(dbkey)

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
                  is_staff=args.staff,
                  last_name=args.last,
                  person_mail=args.email,
                  projects_api=[args.project],
                  sshkeys_api=list(),
                  person_uniqueid=f"{args.first}{args.last}@UNIQUEID",
                  person_oib=0,
                  uid_api=0,
                  ldap_uid=args.uid if args.uid else 0,
                  ldap_gid=0,
                  ldap_username='',
                  type_create='manual')

    if args.force and not already_exists:
        pr.user.append(us)
        session.add(pr)
    elif not already_exists:
        session.add(us)

    return us


def user_project_list(logger, args, session):
    all_users = session.query(User).all()

    if args.project:
        table = Table(
            title=f"Found users for projects {args.project}",
            title_justify="left",
            box=None,
            show_lines=True,
            title_style=""
        )
        table.add_column(justify="right")
        table.add_column()
        table.add_column()

        projects = session.query(Project).filter(Project.identifier == args.project)
        for project in projects:
            for user in project.user:
                sshkeys = ', '.join(
                    ['\[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("OIB = ", user.person_oib)
                table.add_row("Username = ", user.ldap_username)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Subscribed = ", str(user.mail_is_subscribed))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    if args.first:
        table = Table(
            title=f"Found users with first name {args.first}",
            title_justify="left",
            box=None,
            show_lines=True,
            title_style=""
        )
        table.add_column(justify="right")
        table.add_column()
        table.add_column()

        for user in all_users:
            if args.first.lower() in user.first_name.lower():
                sshkeys = ', '.join(
                    ['\[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("OIB = ", user.person_oib)
                table.add_row("Username = ", user.ldap_username)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Subscribed = ", str(user.mail_is_subscribed))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    if args.last:
        table = Table(
            title=f"Found users with last name {args.last}",
            title_justify="left",
            box=None,
            show_lines=True,
            title_style=""
        )
        table.add_column(justify="right")
        table.add_column()
        table.add_column()

        for user in all_users:
            if args.last.lower() in user.last_name.lower():
                sshkeys = ', '.join(
                    ['\[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("OIB = ", user.person_oib)
                table.add_row("Username = ", user.ldap_username)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Subscribed = ", str(user.mail_is_subscribed))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    if args.username:
        table = Table(
            title=f"Found users with username {args.username}",
            title_justify="left",
            box=None,
            show_lines=True,
            title_style=""
        )
        table.add_column(justify="right")
        table.add_column()
        table.add_column()

        for user in all_users:
            if args.username.lower() in user.ldap_username.lower():
                sshkeys = ', '.join(
                    ['\[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("OIB = ", user.person_oib)
                table.add_row("Username = ", user.ldap_username)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Subscribed = ", str(user.mail_is_subscribed))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)


def main():
    parser = argparse.ArgumentParser(description='Manage user create, change and delete manually with needed metadata about him')
    parser.add_argument('--force', dest='force', action='store_true', required=False,
                        help='Make changes in DB relations')
    parser.add_argument('--flush-keys', dest='flushkeys', action='store_true', required=False,
                        help='Flush all keys not associated to any user')
    parser.add_argument('--flush-users', dest='flushusers', action='store_true', required=False,
                        help='Flush all users without any keys and projects associated')
    subparsers = parser.add_subparsers(help="User subcommands", dest="command")

    parser_create = subparsers.add_parser('create', help='Create user based on passed metadata')
    parser_create.add_argument('--first', dest='first', type=str,
                               required=True, help='First name of user')
    parser_create.add_argument('--last', dest='last', type=str, required=True,
                               help='Last name of user')
    parser_create.add_argument('--project', dest='project', type=str,
                               required=True, help='Project identifier that user will be associated to')
    parser_create.add_argument('--pubkey', dest='pubkey',
                               type=argparse.FileType(), required=True,
                               help='File path od public key component')
    parser_create.add_argument('--email', dest='email', type=str,
                               required=True, help='Email of the user')
    parser_create.add_argument('--uid', dest='uid', type=int,
                               required=False, help='Set UID in advance - be careful')
    parser_create.add_argument('--staff', dest='staff', action='store_true',
                               default=False,
                               required=False, help='Flag user as staff')

    parser_update = subparsers.add_parser('update', help='Update user metadata')
    parser_update.add_argument('--username', dest='username', type=str,
                               required=True, help='Username of user')
    parser_update.add_argument('--pubkey', dest='pubkey',
                               type=argparse.FileType(), required=False,
                               help='File path od public key component')
    parser_update.add_argument('--email', dest='email', type=str,
                               required=False, help='Email of the user')
    parser_update.add_argument('--oib', dest='oib', type=str, required=False,
                               help='OIB of the user')
    parser_update.add_argument('--uid', dest='uid', type=int, required=False,
                               help='Update UID of the user - be careful')
    parser_update.add_argument('--staff', dest='staff', action='store_true',
                               required=False, help='Flag user as staff')
    parser_update.add_argument('--project', dest='project', type=str,
                               required=False, help='Project identifier that user will be associated to')
    parser_update.add_argument('--flag-subscribed', dest='flagissubscribed', type=int, metavar='0/1',
                               required=False, help='Set flag mail_is_subscribed')
    parser_update.add_argument('--flag-dircreated', dest='flagisdircreated', type=int, metavar='0/1',
                               required=False, help='Set flag is_dir_created')
    parser_update.add_argument('--flag-deactivated', dest='flagisdeactivated', type=int, metavar='0/1',
                               required=False, help='Set flag is_deactivated')
    parser_update.add_argument('--flag-active', dest='flagisactive', type=int, metavar='0/1',
                               required=False, help='Set flag is_active')
    parser_update.add_argument('--flag-sshkeyadded', dest='flagissshkeyadded', type=int, metavar='0/1',
                               required=False, help='Set flag mail_is_sshkeyadded')
    parser_update.add_argument('--flag-opensend', dest='flagisopensend', type=int, metavar='0/1',
                               required=False, help='Set flag mail_is_opensend')
    parser_update.add_argument('--type-create', dest='typecreate', type=str, metavar='api/manual',
                               required=False, help='Set type_create')

    parser_delete = subparsers.add_parser('delete', help='Delete user metadata')
    parser_delete.add_argument('--username', dest='username', type=str,
                               required=True, help='Username of user')
    parser_delete.add_argument('--pubkey', dest='pubkey',
                               type=str, required=False,
                               help='String to match in public key to delete')
    parser_delete.add_argument('--project', dest='project', type=str,
                               required=False, help='Project identifier that user will be removed from')

    parser_list = subparsers.add_parser('list', help='List users and their metadata')
    parser_list.add_argument('--username', dest='username', type=str,
                             required=False, help='Username of user')
    parser_list.add_argument('--first', dest='first', type=str, required=False,
                             help='First name')
    parser_list.add_argument('--last', dest='last', type=str, required=False,
                             help='Last name')
    parser_list.add_argument('--project', dest='project', type=str,
                             required=False, help='List users assigned to project with idenitifer')

    args = parser.parse_args()

    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    if args.command == "create":
        new_user = user_project_add(logger, args, session)
        key_fingerprint = user_key_add(logger, args, session, new_user, args.pubkey)
        logger.info(f"Created user {args.first} {args.last} with key {key_fingerprint} and added to project {args.project}")
    elif args.command == "update":
        user_update(logger, args, session)
    elif args.command == "delete":
        user_delete(logger, args, session)
    elif args.command == "list":
        user_project_list(logger, args, session)

    if args.flushkeys:
        flush_sshkeys(logger, session)

    if args.flushusers:
        flush_users(logger, session)

    try:
        session.commit()
        session.close()
    except (IntegrityError, StaleDataError) as exc:
        logger.error(f"Error with {args.command}")
        logger.error(exc)


if __name__ == '__main__':
    main()
