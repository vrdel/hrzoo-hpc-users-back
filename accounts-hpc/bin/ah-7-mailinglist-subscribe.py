#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.exceptions import SyncHttpError
from accounts_hpc.httpconn import SessionWithRetry

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
    import ipdb; ipdb.set_trace()

    if response:
        list_id = json.loads(response)['list_id']

        return list_id


async def subscribe_maillist(confopts, logger, email, username, list_id):
    try:
        headers = dict()
        subscribe_payload = dict(list_id=list_id, subscriber=email,
                                 pre_verified=True, pre_confirmed=True)
        data = urlencode(subscribe_payload, doseq=True)

        response = requests.post('{}/members'.format(confopts['mailinglist']['server']),
                                 headers=headers, auth=auth, data=data,
                                 timeout=confopts['mailinglist']['timeout'])
        response.raise_for_status()

        return (True, True)

    except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
        excp_msg = getattr(e.response, 'content', False)
        if excp_msg:
            errormsg = ('{} {}').format(str(e), excp_msg)
        else:
            errormsg = ('{}').format(str(e))

        logger.error('Failed subscribing user %s on %s: %s' % (username,
                                                               confopts['mailinglist']['name'],
                                                               errormsg))
        return (False, e)


async def run(logger, session, confopts):
    headers = requests.utils.default_headers()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    auth = confopts['mailinglist']['credentials'].split(':')

    session = SessionWithRetry(logger, confopts, auth, handle_session_close=True)

    try:
        list_id = await maillist_id(confopts, session, headers)
        print(list_id)
    except SyncHttpError as exc:
        logger.error(f"Error fetch mailing list id {repr(exc)}")
        raise SystemExit(1)

    # users = session.query(User).filter(User.mail_is_subscribed == False).all()
    # for user in users:
        # subscribed = await subscribe_maillist(confopts, logger, user.person_mail, user.ldap_username, list_id)
        # if subscribed[0]:
            # user.mail_is_subscribed = True
            # logger.info(f"User {user.ldap_username} subscribed to {confopts['mailinglist']['name']}")
        # else:
            # if subscribed[1].response.status_code == 409:
                # logger.info(f"User {user.ldap_username} already subscribed to {confopts['mailinglist']['name']}, setting flag to True")
                # user.mail_is_subscribed = True

    await session.close()


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
        loop.run_until_complete(run(logger, args, confopts))

    except (SyncHttpError, KeyboardInterrupt):
        pass

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
