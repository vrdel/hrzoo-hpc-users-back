from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.emailsend import EmailSend  # type: ignore
from accounts_hpc.exceptions import AhTaskError
from accounts_hpc.utils import contains_exception, chunk_list

from sqlalchemy import select
from sqlalchemy import or_

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
                                      username=user.username_api, project=project)
                    if await email.send():
                        user.mail_project_is_opensend[project] = True
                        if not self.users_project_opened.get(project, False):
                            self.users_project_opened[project] = list()
                        self.users_project_opened[project].append(user.username_api)
                        self.logger.info(f"Send email for created account {user.username_api} - {project} @ {user.person_mail}")

    async def _email_project_key(self, users):
        for user in users:
            already_opened = 0
            for project in user.mail_project_is_sshkeyadded.keys():
                if user.username_api in self.users_project_opened.get(project, []):
                    user.mail_project_is_sshkeyadded[project] = True
                    user.mail_project_is_sshkeyremoved[project] = True
                    already_opened += 1
            user_project = await user.awaitable_attrs.project
            if already_opened == len(user_project):
                user.mail_name_sshkey = list()

            added_keys = [key for key in user.mail_name_sshkey if key.startswith('ADD:')]
            removed_keys = [key for key in user.mail_name_sshkey if key.startswith('DEL:')]

            nmail = 0
            for sshkeyname in added_keys:
                key_name = sshkeyname.split('ADD:', 1)[1]
                for project in user.mail_project_is_sshkeyadded.keys():
                    if user.mail_project_is_sshkeyadded[project] == False:
                        email = EmailSend(self.logger, self.confopts,
                                          user.person_mail,
                                          sshkeyname=key_name,
                                          project=project, keyop='add')
                        if await email.send():
                            nmail += 1
                            self.logger.info(f"Send email for added key {key_name} of {user.username_api} - {project}")
                            user.mail_project_is_sshkeyadded[project] = True
                if nmail == len(added_keys) * len(user.mail_project_is_sshkeyadded.keys()):
                    user.mail_name_sshkey = [key for key in user.mail_name_sshkey if not key.startswith('ADD:')]

            for sshkeyname in removed_keys:
                key_name = sshkeyname.split('DEL:', 1)[1]
                for project in user.mail_project_is_sshkeyremoved.keys():
                    if user.mail_project_is_sshkeyremoved[project] == False:
                        email = EmailSend(self.logger, self.confopts,
                                          user.person_mail,
                                          sshkeyname=key_name,
                                          project=project, keyop='del')
                        if await email.send():
                            nmail += 1
                            self.logger.info(f"Send email for removed key {key_name} of {user.username_api} - {project}")
                            user.mail_project_is_sshkeyremoved[project] = True
                if nmail == len(removed_keys) * len(user.mail_project_is_sshkeyremoved.keys()):
                    user.mail_name_sshkey = [key for key in user.mail_name_sshkey if not key.startswith('DEL:')]

    async def _email_account(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.username_api)
            if await email.send():
                user.mail_is_opensend = True
                self.users_opened.add(user.username_api)
                self.logger.info(f"Send email for created account {user.username_api} @ {user.person_mail}")

    async def _email_project_deactivate(self, users):
        for user in users:
            if user.mail_project_is_deactivated:
                for proj in user.mail_project_is_deactivated:
                    if not user.mail_project_is_deactivated[proj]:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          username=user.username_api, project=proj, deactivated=True)
                        if await email.send():
                            user.mail_project_is_deactivated[proj] = True
                            self.logger.info(f"Send email for deactivated account {user.username_api} - {proj} @ {user.person_mail}")

    async def _email_project_activate(self, users):
        for user in users:
            if user.mail_project_is_activated:
                for proj in user.mail_project_is_activated:
                    if not user.mail_project_is_activated[proj]:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          username=user.username_api, project=proj, activated=True)
                        if await email.send():
                            user.mail_project_is_activated[proj] = True
                            user.mail_project_is_opensend[proj] = True
                            user.mail_project_is_sshkeyadded[proj] = True
                            self.logger.info(f"Send email for reactivated account {user.username_api} - {proj} @ {user.person_mail}")

    async def _email_activate(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.username_api, activated=True)
            if await email.send():
                user.mail_is_activated = False
                user.mail_is_sshkeyadded = True
                # all SSH keys are readded once user is back so we null it here
                # so that user does not get an email for his SSH keys
                user.mail_name_sshkey = list()
                self.logger.info(f"Send email for reactivated account {user.username_api} @ {user.person_mail}")

    async def _email_deactivate(self, users):
        for user in users:
            email = EmailSend(self.logger, self.confopts, user.person_mail,
                              username=user.username_api, deactivated=True)
            if await email.send():
                user.mail_is_deactivated = False
                self.logger.info(f"Send email for deactivated account {user.username_api} @ {user.person_mail}")

    async def _email_key(self, users):
        for user in users:
            # skip for new users that are just created
            # as they will receive previous email
            if user.username_api in self.users_opened:
                user.mail_is_sshkeyadded = True
                user.mail_is_sshkeyremoved = True
                user.mail_name_sshkey = list()
                continue
            nmail = 0

            added_keys = [key for key in user.mail_name_sshkey if key.startswith('ADD:')]
            removed_keys = [key for key in user.mail_name_sshkey if key.startswith('DEL:')]

            for sshkeyname in added_keys:
                key_name = sshkeyname.split('ADD:', 1)[1]
                email = EmailSend(self.logger, self.confopts, user.person_mail,
                                  sshkeyname=key_name, keyop='add')
                if await email.send():
                    nmail += 1
                    self.logger.info(f"Send email for added key {key_name} of {user.username_api}")
            if nmail == len(added_keys):
                user.mail_is_sshkeyadded = True
                user.mail_name_sshkey = [key for key in user.mail_name_sshkey if not key.startswith('ADD:')]

            nmail = 0
            for sshkeyname in removed_keys:
                key_name = sshkeyname.split('DEL:', 1)[1]
                email = EmailSend(self.logger, self.confopts, user.person_mail,
                                  sshkeyname=key_name, keyop='del')
                if await email.send():
                    nmail += 1
                    self.logger.info(f"Send email for removed key {key_name} of {user.username_api}")
            if nmail == len(removed_keys):
                user.mail_is_sshkeyremoved = True
                user.mail_name_sshkey = [key for key in user.mail_name_sshkey if not key.startswith('DEL:')]

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

                await self._email_project_key(users)

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

                stmt = select(User).where(or_(
                    User.mail_is_sshkeyadded == False,
                    User.mail_is_sshkeyremoved == False
                ))
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
