#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import User  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from urllib.parse import urlencode

import argparse
import signal
import requests
import json


def subscribe_maillist(confopts, logger, email, username):
    try:
        headers = dict()

        headers = requests.utils.default_headers()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        auth = tuple(confopts['mailinglist']['credentials'].split(':'))
        response = requests.get('{}/lists/{}'.format(
            confopts['mailinglist']['server'], confopts['mailinglist']['name']),
            auth=auth,
            headers=headers
        )
        list_id = json.loads(response.content)['list_id']
        subscribe_payload = dict(list_id=list_id, subscriber=email,
                                 pre_verified=True, pre_confirmed=True)
        data = urlencode(subscribe_payload, doseq=True)

        response = requests.post('{}/members'.format(confopts['mailinglist']['server']),
                                 headers=headers, auth=auth, data=data,
                                 timeout=confopts['mailinglist']['timeout'])
        response.raise_for_status()

        return True

    except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
        excp_msg = getattr(e.response, 'content', False)
        if excp_msg:
            errormsg = ('{} {}').format(str(e), excp_msg)
        else:
            errormsg = ('{}').format(str(e))

        logger.error('Failed subscribing user %s on %s: %s' % (username,
                                                               confopts['mailinglist']['name'],
                                                               errormsg))
        return False


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Subscribe new users to mailing list""")
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users = session.query(User).filter(User.mail_is_subscribed == False).all()
    for user in users:
        if subscribe_maillist(
            confopts,
            logger,
            user.person_mail,
            user.ldap_username,
        ):
            user.mail_is_subscribed = True
            logger.info(f"User {user.ldap_username} subscribed to {confopts['mailinglist']['name']}")

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
