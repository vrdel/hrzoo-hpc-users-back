from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.emailsend import EmailSend  # type: ignore

from sqlalchemy import select

import asyncio
import sys


class SendEmail(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller)
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args
        self.daemon = daemon

    async def email_project_account(self, users, users_opened):
        for user in users:
            for project in user.mail_project_is_opensend.keys():
                if user.mail_project_is_opensend[project] == False:
                    email = EmailSend(self.logger, self.confopts, user.person_mail,
                                      username=user.ldap_username, project=project)
                    if await email.send():
                        user.mail_project_is_opensend[project] = True
                        users_opened.add(user.ldap_username)
                        self.logger.info(f"Send email for created account {user.ldap_username} - {project} @ {user.person_mail}")

    async def email_project_key(self, users, users_opened):
        for user in users:
            # skip for new users that are just created
            # as they will receive previous email
            if user.ldap_username in users_opened:
                for project in user.mail_project_is_sshkeyadded.keys():
                    user.mail_project_is_sshkeyadded[project] = True
                    user.mail_name_sshkey = list()
                continue
            nmail = 0
            for sshkeyname in user.mail_name_sshkey:
                for project in user.mail_project_is_sshkeyadded.keys():
                    if user.mail_project_is_sshkeyadded[project] == False:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          sshkeyname=sshkeyname, project=project)
                        if await email.send():
                            nmail += 1
                            self.logger.info(f"Send email for added key {sshkeyname} of {user.ldap_username} - {project}")
                            user.mail_project_is_sshkeyadded[project] = True
                if nmail == len(user.mail_name_sshkey) * len(user.mail_project_is_sshkeyadded.keys()):
                    user.mail_name_sshkey = list()

    async def email_account(self, users, users_opened):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.ldap_username)
            if await email.send():
                user.mail_is_opensend = True
                users_opened.add(user.ldap_username)
                self.logger.info(f"Send email for created account {user.ldap_username} @ {user.person_mail}")

    async def email_key(self, users, users_opened):
        for user in users:
            # skip for new users that are just created
            # as they will receive previous email
            if user.ldap_username in users_opened:
                user.mail_is_sshkeyadded = True
                user.mail_name_sshkey = list()
                continue
            nmail = 0
            for sshkeyname in user.mail_name_sshkey:
                email = EmailSend(self.logger, self.confopts, user.person_mail,
                                  sshkeyname=sshkeyname)
                if await email.send():
                    nmail += 1
                    self.logger.info(f"Send email for added key {sshkeyname} of {user.ldap_username}")
            if nmail == len(user.mail_name_sshkey):
                user.mail_is_sshkeyadded = True
                user.mail_name_sshkey = list()

    async def run(self):
        try:
            users_opened = set()
            if self.confopts['email']['project_email']:
                users = await self.dbsession.execute(select(User))
                users = users.scalars().all()
                await self.email_project_account(users, users_opened)
                await self.email_project_key(users, users_opened)

            else:
                stmt = select(User).where(User.mail_is_opensend == False)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()
                await self.email_account(users, users_opened)

                stmt = select(User).where(User.mail_is_sshkeyadded == False)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()
                await self.email_key(users, users_opened)

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling emailsend...')
            raise exc

        finally:
            await self.dbsession.commit()
            await self.dbsession.close()
