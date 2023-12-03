from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.httpconn import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError
from accounts_hpc.utils import contains_exception

import asyncio
import signal
import json
import sys

from urllib.parse import urlencode


class ListSubscribe(object):
    def __init__(self, caller, args):
        shared = Shared(caller)
        self.confopts = shared.confopts
        self.logger = shared.log.get()
        self.dbsession = shared.dbsession
        self.args = args

    async def maillist_id(self, headers):
        headers = dict()

        response = await self.httpsession.http_get('{}/lists/{}'.format(
            self.confopts['mailinglist']['server'], self.confopts['mailinglist']['name']),
            headers=headers
        )

        if response:
            list_id = json.loads(response)['list_id']

            return list_id
        else:
            return False

    async def subscribe_maillist(self, email, username, list_id):
        try:
            headers = dict()
            subscribe_payload = dict(list_id=list_id, subscriber=email,
                                     pre_verified=True, pre_confirmed=True)
            response = await self.httpsession.http_post(
                '{}/members'.format(self.confopts['mailinglist']['server']),
                headers=headers, data=subscribe_payload
            )

            if response.status >= 200 and response.status < 300:
                return (True, response)
            else:
                return (False, response)

        except SyncHttpError as exc:
            errormsg = ('{}').format(str(exc))

            self.logger.error('Failed subscribing user %s on %s: %s' % (username,
                                                                        self.confopts['mailinglist']['name'],
                                                                        errormsg))
            return (False, exc)

    async def run(self):
        headers = dict()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        auth = self.confopts['mailinglist']['credentials'].split(':')

        self.httpsession = SessionWithRetry(self.logger, self.confopts, auth=auth, handle_session_close=True)

        try:
            list_id = await self.maillist_id(headers)
        except SyncHttpError as exc:
            self.logger.error(f"Error fetch mailing list id {repr(exc)}")
            raise SystemExit(1)

        users = self.dbsession.query(User).filter(User.mail_is_subscribed == False).all()
        coros = []
        for user in users:
            coros.append(self.subscribe_maillist(user.person_mail, user.ldap_username, list_id))

        response = await asyncio.gather(*coros, return_exceptions=True)

        exc_raised, exc = contains_exception(response)

        if exc_raised:
            raise exc
        else:
            nu = 0
            for res in response:
                if res[0]:
                    user.mail_is_subscribed = True
                    self.logger.info(f"User {users[nu].ldap_username} subscribed to {self.confopts['mailinglist']['name']}")
                else:
                    if res[1].status == 409:
                        self.logger.info(f"User {users[nu].ldap_username} already subscribed to {self.confopts['mailinglist']['name']}, setting flag to True")
                        user.mail_is_subscribed = True
                    else:
                        self.logger.error(f"Error subscribing user {users[nu].ldap_username} to {self.confopts['mailinglist']['name']}")
                nu += 1

        await self.httpsession.close()

        self.dbsession.commit()
        self.dbsession.close()
