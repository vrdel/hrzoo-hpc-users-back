#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.exceptions import SyncHttpError
from accounts_hpc.httpconn import SessionWithRetry
from accounts_hpc.utils import contains_exception

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib.parse import urlencode

import asyncio
import argparse
import signal
import requests
import json


async def maillist_id(confopts, session, headers):
    headers = dict()

    response = await session.http_get('{}/lists/{}'.format(
        confopts['mailinglist']['server'], confopts['mailinglist']['name']),
        headers=headers
    )

    if response:
        list_id = json.loads(response)['list_id']

        return list_id
    else:
        return False


async def subscribe_maillist(confopts, session, logger, email, username, list_id):
    try:
        headers = dict()
        subscribe_payload = dict(list_id=list_id, subscriber=email,
                                 pre_verified=True, pre_confirmed=True)
        response = await session.http_post(
            '{}/members'.format(confopts['mailinglist']['server']),
            headers=headers, data=subscribe_payload
        )

        if response.status >= 200 and response.status < 300:
            return (True, response)
        else:
            return (False, response)

    except SyncHttpError as exc:
        errormsg = ('{}').format(str(exc))

        logger.error('Failed subscribing user %s on %s: %s' % (username,
                                                               confopts['mailinglist']['name'],
                                                               errormsg))
        return (False, exc)


async def run(logger, session, confopts):
    headers = requests.utils.default_headers()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    auth = confopts['mailinglist']['credentials'].split(':')

    sessionhttp = SessionWithRetry(logger, confopts, auth=auth, handle_session_close=True)

    try:
        list_id = await maillist_id(confopts, sessionhttp, headers)
    except SyncHttpError as exc:
        logger.error(f"Error fetch mailing list id {repr(exc)}")
        raise SystemExit(1)

    users = session.query(User).filter(User.mail_is_subscribed == False).all()
    coros = []
    for user in users:
        coros.append(subscribe_maillist(confopts, sessionhttp, logger, user.person_mail, user.ldap_username, list_id))

    response = await asyncio.gather(*coros, return_exceptions=True)

    exc_raised, exc = contains_exception(response)

    if exc_raised:
        raise exc
    else:
        nu = 0
        for res in response:
            if res[0]:
                user.mail_is_subscribed = True
                logger.info(f"User {users[nu].ldap_username} subscribed to {confopts['mailinglist']['name']}")
            else:
                if res[1].status == 409:
                    logger.info(f"User {users[nu].ldap_username} already subscribed to {confopts['mailinglist']['name']}, setting flag to True")
                    user.mail_is_subscribed = True
                else:
                    logger.error(f"Error subscribing user {users[nu].ldap_username} to {confopts['mailinglist']['name']}")
            nu += 1

    await sessionhttp.close()


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Subscribe new users to mailing list""")
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(run(logger, session, confopts))

    except (SyncHttpError, KeyboardInterrupt):
        pass

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
