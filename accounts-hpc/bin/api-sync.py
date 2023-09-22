#!/usr/bin/env python

import asyncio
import json
import sys
import timeit

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.httpconn import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError
from accounts_hpc.utils import only_alnum, all_none, contains_exception


from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound

from unidecode import unidecode

import argparse


def replace_projects_fields(session, fields):
    projects = session.query(Project).all()
    users = session.query(User).all()

    for project in projects:
        for field in fields:
            which = field.get('field').split('.')[1]
            value = getattr(project, which)
            if field['from'] in value:
                value = value.replace(field['from'], field['to'])
                setattr(project, which, value)
                # specifically for project identifier replace also
                # user.projects_api
                if which == 'identifier':
                    for user in users:
                        newp = list()
                        change = False
                        for pr in user.projects_api:
                            if field['from'] in pr:
                                newp.append(pr.replace(field['from'], field['to']))
                                change = True
                            else:
                                newp.append(pr)
                        if change:
                            user.projects_api = newp


def sshkeys_del(args, session, projects_users, sshkeys):
    interested_users = [up['user']['id'] for up in projects_users]
    hzsi_api_user_keys = dict()

    for key in sshkeys:
        if key['user']['id'] not in interested_users:
            continue

        if key['user']['username'] not in hzsi_api_user_keys:
            hzsi_api_user_keys[key['user']['username']] = list()

        hzsi_api_user_keys[key['user']['username']].append(key['fingerprint'])

    users = session.query(User).all()

    for us in users:
        if us.person_uniqueid not in hzsi_api_user_keys.keys():
            hzsi_api_user_keys[us.person_uniqueid] = list()

        if len(us.sshkey) > len(hzsi_api_user_keys[us.person_uniqueid]):
            rem_keys = list(
                set(us.sshkeys_api)
                .difference(hzsi_api_user_keys[us.person_uniqueid]))
            us.sshkeys_api = hzsi_api_user_keys[us.person_uniqueid]
            if args.initset:
                rem_keys_db = session.query(SshKey).filter(
                    and_(
                        SshKey.fingerprint.in_(rem_keys),
                        SshKey.user_id == us.id
                    ))
                for key in rem_keys_db:
                    us.sshkey.remove(key)
                    session.delete(key)


def sshkeys_add(args, session, projects_users, sshkeys):
    interested_users = set([up['user']['id'] for up in projects_users])

    for key in sshkeys:
        if key['user']['id'] not in interested_users:
            continue

        us = session.query(User).filter(User.person_uniqueid == key['user']['username']).one()

        if key['fingerprint'] not in us.sshkeys_api:
            us.sshkeys_api.append(key['fingerprint'])

        # same key unfortunately can be added from two
        # different users, that's why we require uid_api as well
        try:
            dbkey = session.query(SshKey).filter(
                and_(
                    SshKey.fingerprint == key['fingerprint'],
                    SshKey.uid_api == key['user']['id']
                )).one()
        except NoResultFound:
            dbkey = SshKey(name=key['name'],
                           fingerprint=key['fingerprint'],
                           public_key=key['public_key'],
                           uid_api=key['user']['id'])

        if dbkey not in us.sshkey and args.initset:
            us.sshkey.append(dbkey)
            session.add(us)
        else:
            session.add(dbkey)
            session.add(us)


def users_projects_del(args, session, projects_users):
    hzsi_api_user_projects = dict()

    for uspr in projects_users:
        if uspr['user']['username'] not in hzsi_api_user_projects:
            hzsi_api_user_projects.update({
                uspr['user']['username']: list()
            })
        if uspr['project']['identifier'] not in hzsi_api_user_projects[uspr['user']['username']]:
            hzsi_api_user_projects[uspr['user']['username']].\
                append(uspr['project']['identifier'])

    visited_users = set()
    for uspr in projects_users:
        if uspr['user']['id'] in visited_users:
            continue

        us = session.query(User).filter(User.person_uniqueid == uspr['user']['username']).one()

        if len(us.projects_api) > len(hzsi_api_user_projects[uspr['user']['username']]):
            us.projects_api = hzsi_api_user_projects[uspr['user']['username']]
            if args.initset:
                prjs_diff = list(
                    set(us.projects_api)
                    .difference(
                        set(hzsi_api_user_projects[uspr['user']['username']])
                    ))
                prjs_diff_db = session.query(Project).filter(Project.identifier.in_(prjs_diff)).all()
                for pr in prjs_diff_db:
                    us.project.remove(pr)

        visited_users.update([uspr['user']['id']])


def users_projects_add(args, session, projects_users):
    for uspr in projects_users:
        try:
            pr = session.query(Project).filter(
                Project.identifier == uspr['project']['identifier']).one()
            # update staff_resources_type with latest value
            pr.staff_resources_type_api = uspr['project']['staff_resources_type']
        except NoResultFound:
            pr = Project(name=uspr['project']['name'],
                         identifier=uspr['project']['identifier'],
                         prjid_api=uspr['project']['id'],
                         is_dir_created=True if args.initset else False,
                         staff_resources_type_api=uspr['project']['staff_resources_type'],
                         ldap_gid=0)

        try:
            # TODO: OIB
            # and update first_name, last_name, unique_person_id
            us = session.query(User).filter(
                User.person_uniqueid == uspr['user']['username']).one()
            projects_api = us.projects_api
            # always up-to-date projects_api field with project associations
            if not projects_api:
                projects_api = list()
            if uspr['project']['identifier'] not in projects_api:
                projects_api.append(uspr['project']['identifier'])
            us.projects_api = projects_api

        except NoResultFound:
            us = User(first_name=only_alnum(unidecode(uspr['user']['first_name'])),
                      is_active=uspr['user']['is_active'],
                      is_opened=False if args.initset else True,
                      is_dir_created=True if args.initset else False,
                      is_staff=uspr['user']['is_staff'],
                      last_name=only_alnum(unidecode(uspr['user']['last_name'])),
                      person_mail=uspr['user']['person_mail'],
                      projects_api=[uspr['project']['identifier']],
                      sshkeys_api=list(),
                      person_uniqueid=uspr['user']['username'],
                      uid_api=uspr['user']['id'],
                      ldap_uid=0,
                      ldap_gid=0,
                      ldap_username='')

        # sync (user, project) relations to cache
        # only if --init-set
        if us not in pr.user and args.initset:
            pr.user.append(us)
            session.add(pr)
        elif not args.initset:
            session.add(pr)
            session.add(us)


async def fetch_data(logger, confopts):
    session = SessionWithRetry(logger, confopts, handle_session_close=True)

    coros = [
        session.http_get(
            confopts['hzsiapi']['sshkeys'],
        ),
        session.http_get(
            confopts['hzsiapi']['userproject'],
        )
    ]

    start = timeit.default_timer()
    fetched_data = await asyncio.gather(*coros, return_exceptions=True)
    end = timeit.default_timer()

    await session.close()

    if all_none(fetched_data):
        logger.error("Error while trying to fetch data, exiting")
        raise SystemExit(1)

    exc_raised, exc = contains_exception(fetched_data)
    if exc_raised:
        raise exc

    else:
        logger.info(f"Fetched data in {format(end - start, '.2f')} seconds")
        sshkeys, userproject = fetched_data

        sshkeys = json.loads(sshkeys)
        userproject = json.loads(userproject)
        return sshkeys, userproject


async def run(logger, args, confopts):
    try:
        sshkeys, userproject = await fetch_data(logger, confopts)

    except SyncHttpError:
        logger.error('Data fetch did not succeed')
        raise SystemExit(1)

    projects_users = list()
    visited_users = set()
    # build of projects_users association list
    # user has at least one key added - enough at this point
    # filter project according to interested state and approved
    # resources
    for key in sshkeys:
        for up in userproject:
            if (up['project']['state']
                    not in confopts['hzsiapi']['project_state']):
                continue
            rt_found = False
            for rt in up['project']['staff_resources_type']:
                if rt in confopts['hzsiapi']['project_resources']:
                    rt_found = True
            if not rt_found:
                continue
            if up['user']['id'] == key['user']['id']:
                projects_users.append(up)
        visited_users.update([key['user']['id']])

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users_projects_add(args, session, projects_users)
    users_projects_del(args, session, projects_users)
    sshkeys_add(args, session, projects_users, sshkeys)
    sshkeys_del(args, session, projects_users, sshkeys)

    if confopts['hzsiapi']['replacestring_map']:
        with open(confopts['hzsiapi']['replacestring_map'], mode='r') as fp:
            fieldsreplace = json.loads(fp.read())
    projectsfields = [field for field in fieldsreplace if field.get('field').startswith('project.')]
    if projectsfields:
        replace_projects_fields(session, projectsfields)

    session.commit()
    session.close()


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Sync projects and users from HRZOO-SIGNUP-API to SQLite cache""")
    parser.add_argument('--init-set', dest='initset', action='store_true', help='initial sync with all associations and flags set so no further tools in the pipeline will be triggered')
    args = parser.parse_args()

    confopts = parse_config()

    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(run(logger, args, confopts))

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
