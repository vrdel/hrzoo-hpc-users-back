from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.emailsend import EmailSend  # type: ignore
from accounts_hpc.exceptions import AhTaskError
from accounts_hpc.utils import contains_exception, chunk_list

from sqlalchemy import select

import asyncio
import sys


class SendEmail(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args
        self.daemon = daemon
        self.users_opened = set()
        self.users_project_opened = dict()

    async def _email_project_account(self, users):
        for user in users:
            for project in user.mail_project_is_opensend.keys():
                if user.mail_project_is_opensend[project] == False:
                    email = EmailSend(self.logger, self.confopts, user.person_mail,
                                      username=user.ldap_username, project=project)
                    if await email.send():
                        user.mail_project_is_opensend[project] = True
                        if not self.users_project_opened.get(project, False):
                            self.users_project_opened[project] = list()
                        self.users_project_opened[project].append(user.ldap_username)
                        self.logger.info(f"Send email for created account {user.ldap_username} - {project} @ {user.person_mail}")

    async def _email_project_key(self, users):
        for user in users:
            already_opened = 0
            for project in user.mail_project_is_sshkeyadded.keys():
                if user.ldap_username in self.users_project_opened.get(project, []):
                    user.mail_project_is_sshkeyadded[project] = True
                    already_opened += 1
            user_project = await user.awaitable_attrs.project
            if already_opened == len(user_project):
                user.mail_name_sshkey = list()
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

    async def _email_account(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.ldap_username)
            if await email.send():
                user.mail_is_opensend = True
                self.users_opened.add(user.ldap_username)
                self.logger.info(f"Send email for created account {user.ldap_username} @ {user.person_mail}")

    async def _email_project_deactivate(self, users):
        for user in users:
            if user.mail_project_is_deactivated:
                for proj in user.mail_project_is_deactivated:
                    if not user.mail_project_is_deactivated[proj]:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          username=user.ldap_username, project=proj, deactivated=True)
                        if await email.send():
                            user.mail_project_is_deactivated[proj] = True
                            self.logger.info(f"Send email for deactivated account {user.ldap_username} - {proj} @ {user.person_mail}")

    async def _email_project_activate(self, users):
        for user in users:
            if user.mail_project_is_activated:
                for proj in user.mail_project_is_activated:
                    if not user.mail_project_is_activated[proj]:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          username=user.ldap_username, project=proj, activated=True)
                        if await email.send():
                            user.mail_project_is_activated[proj] = True
                            user.mail_project_is_opensend[proj] = True
                            user.mail_project_is_sshkeyadded[proj] = True
                            self.logger.info(f"Send email for reactivated account {user.ldap_username} - {proj} @ {user.person_mail}")

    async def _email_activate(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.ldap_username, activated=True)
            if await email.send():
                user.mail_is_activated = False
                user.mail_is_sshkeyadded = True
                # all SSH keys are readded once user is back so we null it here
                # so that user does not get an email for his SSH keys
                user.mail_name_sshkey = list()
                self.logger.info(f"Send email for reactivated account {user.ldap_username} @ {user.person_mail}")

    async def _email_deactivate(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.ldap_username, deactivated=True)
            if await email.send():
                user.mail_is_deactivated = False
                self.logger.info(f"Send email for deactivated account {user.ldap_username} @ {user.person_mail}")

    async def _email_key(self, users):
        for user in users:
            # skip for new users that are just created
            # as they will receive previous email
            if user.ldap_username in self.users_opened:
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
            if self.confopts['ldap']['mode'] == 'project_organisation':
                users = await self.dbsession.execute(select(User))
                users = users.scalars().all()

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_project_activate(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_project_deactivate(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_project_account(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                # await self.email_project_account(users, users_opened)
                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_project_key(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

            else:
                stmt = select(User).where(User.mail_is_activated == True)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_activate(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                stmt = select(User).where(User.mail_is_deactivated == True)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_deactivate(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                stmt = select(User).where(User.mail_is_opensend == False)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_account(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

                stmt = select(User).where(User.mail_is_sshkeyadded == False)
                users = await self.dbsession.execute(stmt)
                users = users.scalars().all()

                coros = []
                for chunk in chunk_list(users):
                    coros.append(self._email_key(chunk))
                calrets = await asyncio.gather(*coros, return_exceptions=True)
                exc_raised, exc = contains_exception(calrets)
                if exc_raised:
                    raise exc

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling emailsend...')
            raise exc

        finally:
            await self.dbsession.commit()
            await self.dbsession.close()
