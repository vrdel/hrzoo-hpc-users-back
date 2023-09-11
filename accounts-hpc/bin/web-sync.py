#!/usr/bin/env python

import asyncio
import json
import sys
import timeit

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User  # type: ignore
from accounts_hpc.http import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound


def contains_exception(list):
    for a in list:
        if isinstance(a, Exception):
            return (True, a)

    return (False, None)


def all_none(list):
    if all(list):
        return False
    else:
        return True


def update_projects_api(user, proj_id):
    projects_api = user.projects_api
    if not projects_api:
        projects_api = list()
    if proj_id not in projects_api:
        projects_api.append(proj_id)
    user.projects_api = projects_api


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


async def run(logger, confopts):
    try:
        sshkeys, userproject = await fetch_data(logger, confopts)

    except SyncHttpError:
        logger.error('Data fetch did not succeed')
        raise SystemExit(1)

    projects_users = list()
    visited_users = set()
    for key in sshkeys:
        for up in userproject:
            if up['user']['id'] in visited_users:
                continue
            if up['user']['id'] == key['user']['id']:
                projects_users.append(up)
        visited_users.update([key['user']['id']])

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    for uspr in projects_users:
        try:
            pr = session.query(Project).filter(
                Project.identifier == uspr['project']['identifier']).one()
            # update staff_resources_type with latest value
            pr.staff_resources_type = uspr['project']['staff_resources_type']
        except NoResultFound:

            pr = Project(name=uspr['project']['name'],
                         identifier=uspr['project']['identifier'],
                         resources_type=uspr['project']['staff_resources_type'])

        try:
            us = session.query(User).filter(
                User.person_uniqueid == uspr['user']['username']).one()
            update_projects_api(us, uspr['project']['identifier'])

        except NoResultFound:
            us = User(person_uniqueid=uspr['user']['username'],
                      first_name=uspr['user']['first_name'],
                      last_name=uspr['user']['last_name'],
                      person_mail=uspr['user']['person_mail'],
                      is_staff=uspr['user']['is_staff'],
                      is_opened=True,
                      projects_api=[uspr['project']['identifier']],
                      is_active=uspr['user']['is_active'])

        if us not in pr.user:
            pr.user.append(us)
        session.add(pr)

    session.commit()
    session.close()


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(run(logger, confopts))

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
