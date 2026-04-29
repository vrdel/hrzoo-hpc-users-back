#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.shared import shared, init as init_shared  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, get_ssh_key_fingerprint, gen_username  # type: ignore

from rich import print
from rich.columns import Columns
from rich.table import Table
from rich.console import Console
from rich.pretty import pprint

from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import NoResultFound, IntegrityError, MultipleResultsFound
from unidecode import unidecode


def flush_users(logger, session):
    users = session.query(User).all()

    for user in users:
        if len(user.sshkey) == 0 and len(user.project) == 0:
            session.delete(user)
            logger.info(f'Flushing {user.username_api}')


def flush_sshkeys(logger, session):
    keys_noowner = session.query(SshKey).filter(SshKey.user_id == None)

    if keys_noowner.count() > 0:
        keys_noowner.delete()
        logger.info('All keys without owner flushed')
    else:
        logger.info('No keys without owner found')


def reset_all_flags(logger, args, session):
    if args.username:
        try:
            users = [session.query(User).filter(User.username_api == args.username).one()]
        except NoResultFound:
            logger.error(f"User {args.username} not found")
            return
    else:
        users = session.query(User).all()

    for user in users:
        if args.null:
            user.mail_is_opensend = False
            user.mail_is_sshkeyadded = False
            user.mail_is_sshkeyremoved = False
            user.mail_is_activated = False
            user.mail_is_deactivated = False
            user.mail_name_sshkey = []
            user.is_deactivated = False
            user.mail_project_is_sshkeyadded = {}
            user.mail_project_is_sshkeyremoved = {}
            user.mail_project_is_activated = {}
            user.mail_project_is_deactivated = {}
            user.mail_project_is_opensend = {}
            user.is_activated_project = {}
            user.is_deactivated_project = {}
            logger.info(f"Nullified all mail related flags for {user.username_api}")
            continue

        if not user.mail_is_opensend:
            user.mail_is_opensend = True
            logger.info(f"Reset mail_is_opensend flag to True for {user.username_api}")

        if not user.mail_is_sshkeyadded:
            user.mail_is_sshkeyadded = True
            logger.info(f"Reset mail_is_sshkeyadded flag to True for {user.username_api}")

        if not user.mail_is_sshkeyremoved:
            user.mail_is_sshkeyremoved = True
            logger.info(f"Reset mail_is_sshkeyremoved flag to True for {user.username_api}")

        if user.mail_is_activated:
            user.mail_is_activated = False
            logger.info(f"Reset mail_is_activated flag to False for {user.username_api}")

        if user.mail_is_deactivated:
            user.mail_is_deactivated = False
            logger.info(f"Reset mail_is_deactivated flag to False for {user.username_api}")

        if user.is_deactivated:
            user.is_deactivated = False
            logger.info(f"Reset is_deactivated flag to False for {user.username_api}")

        sshkeyadded_flag = user.mail_project_is_sshkeyadded
        sshkeyadded_changed = False
        for k, v in sshkeyadded_flag.items():
            if not v:
                sshkeyadded_flag[k] = True
                sshkeyadded_changed = True
        if sshkeyadded_changed:
            user.mail_project_is_sshkeyadded = sshkeyadded_flag
            logger.info(f"Reset mail_project_is_sshkeyadded flags to True for {user.username_api}")

        sshkeyremoved_flag = user.mail_project_is_sshkeyremoved
        sshkeyremoved_changed = False
        for k, v in sshkeyremoved_flag.items():
            if not v:
                sshkeyremoved_flag[k] = True
                sshkeyremoved_changed = True
        if sshkeyremoved_changed:
            user.mail_project_is_sshkeyremoved = sshkeyremoved_flag
            logger.info(f"Reset mail_project_is_sshkeyremoved flags to True for {user.username_api}")

        activated_project_flag = user.is_activated_project
        activated_changed = False
        for k, v in activated_project_flag.items():
            if not v:
                activated_project_flag[k] = True
                activated_changed = True
        if activated_changed:
            user.is_activated_project = activated_project_flag
            logger.info(f"Reset is_activated_project flags to True for {user.username_api}")

        deactivated_project_flag = user.is_deactivated_project
        deactivated_changed = False
        for k, v in deactivated_project_flag.items():
            if not v:
                deactivated_project_flag[k] = True
                deactivated_changed = True
        if deactivated_changed:
            user.is_deactivated_project = deactivated_project_flag
            logger.info(f"Reset is_deactivated_project flags to True for {user.username_api}")

        mail_project_activated_flag = user.mail_project_is_activated
        mail_activated_changed = False
        for k, v in mail_project_activated_flag.items():
            if not v:
                mail_project_activated_flag[k] = True
                mail_activated_changed = True
        if mail_activated_changed:
            user.mail_project_is_activated = mail_project_activated_flag
            logger.info(f"Reset mail_project_is_activated flags to True for {user.username_api}")

        mail_project_deactivated_flag = user.mail_project_is_deactivated
        mail_deactivated_changed = False
        for k, v in mail_project_deactivated_flag.items():
            if not v:
                mail_project_deactivated_flag[k] = True
                mail_deactivated_changed = True
        if mail_deactivated_changed:
            user.mail_project_is_deactivated = mail_project_deactivated_flag
            logger.info(f"Reset mail_project_is_deactivated flags to True for {user.username_api}")

        opensend_project_flag = user.mail_project_is_opensend
        opensend_changed = False
        for k, v in opensend_project_flag.items():
            if not v:
                opensend_project_flag[k] = True
                opensend_changed = True
        if opensend_changed:
            user.mail_project_is_opensend = opensend_project_flag
            logger.info(f"Reset mail_project_is_opensend flags to True for {user.username_api}")

        if len(user.mail_name_sshkey) > 0:
            user.mail_name_sshkey = []
            logger.info(f"Reset mail_name_sshkey to empty for {user.username_api}")


def user_delete(logger, args, session):
    try:
        user = session.query(User).filter(User.username_api == args.username).one()
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
                logger.info(f"Removed {user.username_api} from {project.identifier}")

            if args.force:
                try:
                    project.user.remove(user)
                    session.add(project)
                    logger.info(f"Removed {user.username_api} DB relation from {project.identifier}")

                except ValueError:
                    logger.error(f"{user.username_api} not in {project.identifier}")

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


def user_update(logger, args, session, confopts):
    try:
        user = session.query(User).filter(User.username_api == args.username).one()

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
                key_uid_api = user.uid_api if user.uid_api else 0
                dbkey = SshKey(name=f'{user.first_name}{user.last_name}-additional-key',
                               fingerprint=key_fingerprint,
                               public_key=key_content,
                               uid_api=key_uid_api)

                sshkeys_api = user.sshkeys_api
                if key_fingerprint not in sshkeys_api:
                    sshkeys_api.append(key_fingerprint)
                user.sshkeys_api = sshkeys_api

                if args.force:
                    user.sshkey.append(dbkey)
                    logger.info(f"Key {key_fingerprint} DB relation added for user {args.username}")
                else:
                    logger.info(f"Key {key_fingerprint} added for user {args.username}")

                session.add(dbkey)

        if args.email:
            user.person_mail = args.email
            logger.info(f"Update email with {args.email} for user {args.username}")

        if args.staff is not None:
            user.is_staff = args.staff > 0
            if user.is_staff:
                logger.info(f"Promote user {args.username} to staff")
            else:
                logger.info(f"Demote user {args.username} from staff")

        if args.nullgid:
            user.ldap_gid = 0
            logger.info(f"Setting user {args.username} LDAP GID=0")

        if args.nulluid:
            user.ldap_uid = 0
            logger.info(f"Setting user {args.username} LDAP UID=0")

        if args.uid:
            user.ldap_uid = args.uid
            logger.info(f"Setting user {args.username} LDAP UID={args.uid}")

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
                logger.info(f"User {user.username_api} already assigned to project {args.project}")
            elif args.project not in projects_api:
                projects_api.append(args.project)
                logger.info(f"User {user.username_api} added to project {args.project}")
            user.projects_api = projects_api

            if args.force:
                project.user.append(user)
                logger.info(f"Project {args.project} DB relation added for user {user.username_api}")
                session.add(project)

        if args.flagisdircreated is not None:
            user.is_dir_created = args.flagisdircreated > 0
            logger.info(f"Set is_dir_created={user.is_dir_created} for {user.username_api}")

        if args.flagisdeactivated is not None:
            user.is_deactivated = args.flagisdeactivated > 0
            logger.info(f"Set is_deactivated={user.is_deactivated} for {user.username_api}")

        if args.flagisopensend is not None:
            user.mail_is_opensend = args.flagisopensend > 0
            logger.info(f"Set mail_is_opensend={user.mail_is_opensend} for {user.username_api}")

        if args.flagissshkeyadded is not None:
            user.mail_is_sshkeyadded = args.flagissshkeyadded > 0
            if user.mail_is_sshkeyadded:
                user.mail_name_sshkey = []
            logger.info(f"Set mail_is_sshkeyadded={user.mail_is_sshkeyadded} for {user.username_api}")

        if args.flagmailactivated is not None:
            user.mail_is_activated = args.flagmailactivated > 0
            logger.info(f"Set mail_is_activated={user.mail_is_activated} for {user.username_api}")

        if args.flagmaildeactivated is not None:
            user.mail_is_deactivated = args.flagmaildeactivated > 0
            logger.info(f"Set mail_is_deactivated={user.mail_is_deactivated} for {user.username_api}")

        if args.flagisactive is not None:
            user.is_active = args.flagisactive > 0
            logger.info(f"Set is_active={user.is_active} for {user.username_api}")

        if args.typecreate != None:
            logger.info(f"Set type_create={args.typecreate} for {user.username_api}")
            user.type_create = args.typecreate

        if args.typeperson != None:
            logger.info(f"Set person_type={args.typeperson} for {user.username_api}")
            user.person_type = args.typeperson

        if args.ssouid != None:
            logger.info(f"Set type_create={args.ssouid} for {user.username_api}")
            user.person_uniqueid = args.ssouid

        if args.mailnamesshkeyadd:
            for key in args.mailnamesshkeyadd:
                k = f"ADD:{key}"
                if k not in user.mail_name_sshkey:
                    user.mail_name_sshkey.append(k)
                    logger.info(f"Added {k} to mail_name_sshkey for {user.username_api}")

        if args.mailnamesshkeyremove:
            for key in args.mailnamesshkeyremove:
                k = f"DEL:{key}"
                if k not in user.mail_name_sshkey:
                    user.mail_name_sshkey.append(k)
                    logger.info(f"Added {k} to mail_name_sshkey for {user.username_api}")

        if args.flagactivatedproject:
            identifier, raw_value = args.flagactivatedproject
            if confopts['ldap']['mode'] == 'project_organisation':
                flag = user.is_activated_project
                flag[identifier] = raw_value != '0'
                user.is_activated_project = flag
                logger.info(f"Set is_activated_project[{identifier}]={flag[identifier]} for {user.username_api}")
            else:
                logger.warning("--flag-activated-project requires ldap mode project_organisation")

        if args.flagdeactivatedproject:
            identifier, raw_value = args.flagdeactivatedproject
            if confopts['ldap']['mode'] == 'project_organisation':
                flag = user.is_deactivated_project
                flag[identifier] = raw_value != '0'
                user.is_deactivated_project = flag
                logger.info(f"Set is_deactivated_project[{identifier}]={flag[identifier]} for {user.username_api}")
            else:
                logger.warning("--flag-deactivated-project requires ldap mode project_organisation")

        if args.setactivatedproject:
            identifier = args.setactivatedproject
            if confopts['ldap']['mode'] == 'project_organisation':
                is_activated = user.is_activated_project
                is_activated[identifier] = False
                user.is_activated_project = is_activated
                mail_activated = user.mail_project_is_activated
                mail_activated[identifier] = False
                user.mail_project_is_activated = mail_activated
                logger.info(f"Set is_activated_project[{identifier}]=False and mail_project_is_activated[{identifier}]=False for {user.username_api}")
            else:
                logger.warning("--set-activated-project requires ldap mode project_organisation")

        if args.setdeactivatedproject:
            identifier = args.setdeactivatedproject
            if confopts['ldap']['mode'] == 'project_organisation':
                is_deactivated = user.is_deactivated_project
                is_deactivated[identifier] = False
                user.is_deactivated_project = is_deactivated
                mail_deactivated = user.mail_project_is_deactivated
                mail_deactivated[identifier] = False
                user.mail_project_is_deactivated = mail_deactivated
                logger.info(f"Set is_deactivated_project[{identifier}]=False and mail_project_is_deactivated[{identifier}]=False for {user.username_api}")
            else:
                logger.warning("--set-deactivated-project requires ldap mode project_organisation")

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
        first_name = only_alnum(unidecode(args.first))
        last_name = only_alnum(unidecode(args.last))
        us = User(first_name=first_name,
                  is_active=True,
                  is_opened=False,
                  is_dir_created=False,
                  is_deactivated=False,
                  mail_is_opensend=False,
                  mail_is_sshkeyadded=False,
                  mail_is_sshkeyremoved=False,
                  mail_is_activated=False,
                  mail_is_deactivated=False,
                  is_activated_project=dict(),
                  is_deactivated_project=dict(),
                  mail_project_is_opensend=dict(),
                  mail_project_is_sshkeyadded=dict(),
                  mail_project_is_sshkeyremoved=dict(),
                  mail_project_is_activated=dict(),
                  mail_project_is_deactivated=dict(),
                  mail_name_sshkey=list(),
                  is_staff=args.staff,
                  last_name=last_name,
                  person_mail=args.email,
                  projects_api=[args.project],
                  skip_defgid=False,
                  sshkeys_api=list(),
                  person_uniqueid=f"{args.first}{args.last}@UNIQUEID",
                  person_type=args.typeperson,
                  uid_api=0,
                  ldap_uid=args.uid if args.uid else 0,
                  ldap_gid=0,
                  username_api=gen_username(first_name, last_name, session),
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
                    ['[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("ID = ", str(user.id))
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("Username = ", user.username_api)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("Person type = ", str(user.person_type))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("UID API = ", str(user.uid_api))
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Opened = ", str(user.is_opened))
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Skip DefGID = ", str(user.skip_defgid))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key add = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row("Mail SSH key remove = ", str(user.mail_is_sshkeyremoved))
                table.add_row("Mail activated = ", str(user.mail_is_activated))
                table.add_row("Mail deactivated = ", str(user.mail_is_deactivated))
                table.add_row("Activated project = ", str(user.is_activated_project))
                table.add_row("Deactivated project = ", str(user.is_deactivated_project))
                table.add_row("Mail project open = ", str(user.mail_project_is_opensend))
                table.add_row("Mail project SSH key add = ", str(user.mail_project_is_sshkeyadded))
                table.add_row("Mail project SSH key remove = ", str(user.mail_project_is_sshkeyremoved))
                table.add_row("Mail project activated = ", str(user.mail_project_is_activated))
                table.add_row("Mail project deactivated = ", str(user.mail_project_is_deactivated))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    elif args.first:
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
                    ['[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("ID = ", str(user.id))
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("Username = ", user.username_api)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("Person type = ", str(user.person_type))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("UID API = ", str(user.uid_api))
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Opened = ", str(user.is_opened))
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Skip DefGID = ", str(user.skip_defgid))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key add = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row("Mail SSH key remove = ", str(user.mail_is_sshkeyremoved))
                table.add_row("Mail activated = ", str(user.mail_is_activated))
                table.add_row("Mail deactivated = ", str(user.mail_is_deactivated))
                table.add_row("Activated project = ", str(user.is_activated_project))
                table.add_row("Deactivated project = ", str(user.is_deactivated_project))
                table.add_row("Mail project open = ", str(user.mail_project_is_opensend))
                table.add_row("Mail project SSH key add = ", str(user.mail_project_is_sshkeyadded))
                table.add_row("Mail project SSH key remove = ", str(user.mail_project_is_sshkeyremoved))
                table.add_row("Mail project activated = ", str(user.mail_project_is_activated))
                table.add_row("Mail project deactivated = ", str(user.mail_project_is_deactivated))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    elif args.last:
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
                    ['[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("ID = ", str(user.id))
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("Username = ", user.username_api)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("Person type = ", str(user.person_type))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("UID API = ", str(user.uid_api))
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Opened = ", str(user.is_opened))
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Skip DefGID = ", str(user.skip_defgid))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key add = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row("Mail SSH key remove = ", str(user.mail_is_sshkeyremoved))
                table.add_row("Mail activated = ", str(user.mail_is_activated))
                table.add_row("Mail deactivated = ", str(user.mail_is_deactivated))
                table.add_row("Activated project = ", str(user.is_activated_project))
                table.add_row("Deactivated project = ", str(user.is_deactivated_project))
                table.add_row("Mail project open = ", str(user.mail_project_is_opensend))
                table.add_row("Mail project SSH key add = ", str(user.mail_project_is_sshkeyadded))
                table.add_row("Mail project SSH key remove = ", str(user.mail_project_is_sshkeyremoved))
                table.add_row("Mail project activated = ", str(user.mail_project_is_activated))
                table.add_row("Mail project deactivated = ", str(user.mail_project_is_deactivated))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)

    elif args.username:
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
            if args.username.lower() in user.username_api.lower():
                sshkeys = ', '.join(
                    ['[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
                )
                table.add_row("ID = ", str(user.id))
                table.add_row("First = ", user.first_name)
                table.add_row("Last = ", user.last_name)
                table.add_row("Mail = ", user.person_mail)
                table.add_row("Username = ", user.username_api)
                table.add_row("LDAP UID = ", str(user.ldap_uid))
                table.add_row("LDAP GID = ", str(user.ldap_gid))
                table.add_row("Type create = ", str(user.type_create))
                table.add_row("Person type = ", str(user.person_type))
                table.add_row("SSO UID = ", user.person_uniqueid)
                table.add_row("UID API = ", str(user.uid_api))
                table.add_row("Projects API = ", ', '.join(user.projects_api))
                table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
                table.add_row("SSH keys = ", sshkeys)
                table.add_row("Opened = ", str(user.is_opened))
                table.add_row("Active = ", str(user.is_active))
                table.add_row("Deactivated = ", str(user.is_deactivated))
                table.add_row("Staff = ", str(user.is_staff))
                table.add_row("Directories = ", str(user.is_dir_created))
                table.add_row("Skip DefGID = ", str(user.skip_defgid))
                table.add_row("Mail open = ", str(user.mail_is_opensend))
                table.add_row("Mail SSH key add = ", str(user.mail_is_sshkeyadded))
                table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
                table.add_row("Mail SSH key removed = ", str(user.mail_is_sshkeyremoved))
                table.add_row("Mail activated = ", str(user.mail_is_activated))
                table.add_row("Mail deactivated = ", str(user.mail_is_deactivated))
                table.add_row("Activated project = ", str(user.is_activated_project))
                table.add_row("Deactivated project = ", str(user.is_deactivated_project))
                table.add_row("Mail project open = ", str(user.mail_project_is_opensend))
                table.add_row("Mail project SSH key add = ", str(user.mail_project_is_sshkeyadded))
                table.add_row("Mail project SSH key remove = ", str(user.mail_project_is_sshkeyremoved))
                table.add_row("Mail project activated = ", str(user.mail_project_is_activated))
                table.add_row("Mail project deactivated = ", str(user.mail_project_is_deactivated))
                table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)
    else:
        table = Table(
            title="All users",
            title_justify="left",
            box=None,
            show_lines=True,
            title_style=""
        )
        table.add_column(justify="right")
        table.add_column()
        table.add_column()

        for user in all_users:
            sshkeys = ', '.join(
                ['[{}...{}]'.format(key.public_key[0:32], key.public_key[-32:]) for key in user.sshkey]
            )
            table.add_row("ID = ", str(user.id))
            table.add_row("First = ", user.first_name)
            table.add_row("Last = ", user.last_name)
            table.add_row("Mail = ", user.person_mail)
            table.add_row("Username = ", user.username_api)
            table.add_row("LDAP UID = ", str(user.ldap_uid))
            table.add_row("LDAP GID = ", str(user.ldap_gid))
            table.add_row("Type create = ", str(user.type_create))
            table.add_row("Person type = ", str(user.person_type))
            table.add_row("SSO UID = ", user.person_uniqueid)
            table.add_row("UID API = ", str(user.uid_api))
            table.add_row("Projects API = ", ', '.join(user.projects_api))
            table.add_row("SSH keys API = ", ', '.join(user.sshkeys_api))
            table.add_row("SSH keys = ", sshkeys)
            table.add_row("Opened = ", str(user.is_opened))
            table.add_row("Active = ", str(user.is_active))
            table.add_row("Deactivated = ", str(user.is_deactivated))
            table.add_row("Staff = ", str(user.is_staff))
            table.add_row("Directories = ", str(user.is_dir_created))
            table.add_row("Skip DefGID = ", str(user.skip_defgid))
            table.add_row("Mail open = ", str(user.mail_is_opensend))
            table.add_row("Mail SSH key add = ", str(user.mail_is_sshkeyadded))
            table.add_row("Mail key name = ", ', '.join(user.mail_name_sshkey))
            table.add_row("Mail SSH key remove = ", str(user.mail_is_sshkeyremoved))
            table.add_row("Mail activated = ", str(user.mail_is_activated))
            table.add_row("Mail deactivated = ", str(user.mail_is_deactivated))
            table.add_row("Activated project = ", str(user.is_activated_project))
            table.add_row("Deactivated project = ", str(user.is_deactivated_project))
            table.add_row("Mail project open = ", str(user.mail_project_is_opensend))
            table.add_row("Mail project SSH key add = ", str(user.mail_project_is_sshkeyadded))
            table.add_row("Mail project SSH key remove = ", str(user.mail_project_is_sshkeyremoved))
            table.add_row("Mail project activated = ", str(user.mail_project_is_activated))
            table.add_row("Mail project deactivated = ", str(user.mail_project_is_deactivated))
            table.add_row(" ")

        if table.row_count:
            console = Console()
            console.print(table)


def main():
    parser = argparse.ArgumentParser(description='Manage users create, change and delete manually with needed metadata about them')
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
    parser_create.add_argument('--type-person', dest='typeperson', type=str, metavar='local/foreign',
                               required=False, default='local', help='Set person_type')

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
    parser_update.add_argument('--staff', dest='staff', type=int, metavar='0/1',
                               required=False, help='Promote (1) or demote (0) user to/from staff')
    parser_update.add_argument('--project', dest='project', type=str,
                               required=False, help='Project identifier that user will be associated to')
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
    parser_update.add_argument('--flag-mail-activated', dest='flagmailactivated', type=int, metavar='0/1',
                               required=False, help='Set flag mail_is_activated')
    parser_update.add_argument('--flag-mail-deactivated', dest='flagmaildeactivated', type=int, metavar='0/1',
                               required=False, help='Set flag mail_is_deactivated')
    parser_update.add_argument('--type-create', dest='typecreate', type=str, metavar='api/manual',
                               required=False, help='Set type_create')
    parser_update.add_argument('--type-person', dest='typeperson', type=str, metavar='local/foreign',
                               required=False, help='Set person_type')
    parser_update.add_argument('--sso-uid', dest='ssouid', type=str,
                               required=False, help='Set SSO UID')
    parser_update.add_argument('--null-gid', dest='nullgid', default=False, action='store_true',
                               required=False, help='Set LDAP GID for user to 0')
    parser_update.add_argument('--null-uid', dest='nulluid', default=False, action='store_true',
                               required=False, help='Set LDAP UID for user to 0')
    parser_update.add_argument('--mailname-sshkey-add', dest='mailnamesshkeyadd', type=str, nargs='+',
                               required=False, help='Add one or multiple keys to mail_name_sshkey list indicating a key was added')
    parser_update.add_argument('--mailname-sshkey-remove', dest='mailnamesshkeyremove', type=str, nargs='+',
                               required=False, help='Add one or multiple keys to mail_name_sshkey list indicating a key was removed')
    parser_update.add_argument('--flag-activated-project', dest='flagactivatedproject', type=str, nargs=2,
                               metavar=('IDENTIFIER', '0/1'), required=False,
                               help='Set is_activated_project[IDENTIFIER] flag (project_organisation mode only)')
    parser_update.add_argument('--flag-deactivated-project', dest='flagdeactivatedproject', type=str, nargs=2,
                               metavar=('IDENTIFIER', '0/1'), required=False,
                               help='Set is_deactivated_project[IDENTIFIER] flag (project_organisation mode only)')
    parser_update.add_argument('--set-activated-project', dest='setactivatedproject', type=str,
                               metavar='IDENTIFIER', required=False,
                               help='Trigger LDAP activation and reactivation email for given project by setting is_activated_project and mail_project_is_activated to False (project_organisation mode only)')
    parser_update.add_argument('--set-deactivated-project', dest='setdeactivatedproject', type=str,
                               metavar='IDENTIFIER', required=False,
                               help='Trigger LDAP deactivation and deactivation email for given project by setting is_deactivated_project and mail_project_is_deactivated to False (project_organisation mode only)')

    parser_delete = subparsers.add_parser('delete', help='Delete user metadata')
    parser_delete.add_argument('--username', dest='username', type=str,
                               required=True, help='Username of user')
    parser_delete.add_argument('--pubkey', dest='pubkey',
                               type=str, required=False,
                               help='String to match in public key to delete')
    parser_delete.add_argument('--project', dest='project', type=str,
                               required=False, help='Project identifier that user will be removed from')

    parser_justusername = subparsers.add_parser('just-username', help='Print what username would be generated for given first and last name without creating any DB entries')
    parser_justusername.add_argument('--first', dest='first', type=str,
                                     required=True, help='First name of user')
    parser_justusername.add_argument('--last', dest='last', type=str,
                                     required=True, help='Last name of user')

    parser_resetallflags = subparsers.add_parser('reset-all-flags', help='Reset all mail flags to sent state suppressing pending emails')
    parser_resetallflags.add_argument('--username', dest='username', type=str,
                                      required=False, help='Username of specific user to reset flags for')
    parser_resetallflags.add_argument('--null', dest='null', action='store_true',
                                      required=False, help='Nullify all mail related flags - set to empty values')

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

    init_shared(sys.argv[0])
    confopts = shared.confopts
    logger = shared.logger
    dbsession = shared.dbsession_sync

    if args.command == "create":
        new_user = user_project_add(logger, args, dbsession)
        key_fingerprint = user_key_add(logger, args, dbsession, new_user, args.pubkey)
        logger.info(f"Created user {args.first} {args.last} with key {key_fingerprint} and added to project {args.project}")
    elif args.command == "update":
        user_update(logger, args, dbsession, confopts)
    elif args.command == "delete":
        user_delete(logger, args, dbsession)
    elif args.command == "list":
        user_project_list(logger, args, dbsession)
    elif args.command == "just-username":
        first_name = only_alnum(unidecode(args.first))
        last_name = only_alnum(unidecode(args.last))
        username = gen_username(first_name, last_name, dbsession)
        print(username)
    elif args.command == "reset-all-flags":
        reset_all_flags(logger, args, dbsession)

    if args.flushkeys:
        flush_sshkeys(logger, dbsession)

    if args.flushusers:
        flush_users(logger, dbsession)

    try:
        dbsession.commit()
        dbsession.close()
    except (IntegrityError, StaleDataError) as exc:
        logger.error(f"Error with {args.command}")
        logger.error(exc)


if __name__ == '__main__':
    main()
