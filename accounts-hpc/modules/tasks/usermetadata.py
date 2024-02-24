from sqlalchemy import and_
from sqlalchemy.exc import NoResultFound
from sqlalchemy import select

from accounts_hpc.db import Project, User  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

import json
import aiofiles
import asyncio


class UserMetadata(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args

    async def run(self):
        try:
            mapuser = list()

            if self.confopts['usersetup']['usermap']:
                async with aiofiles.open(self.confopts['usersetup']['usermap'], mode='r') as fp:
                    mapuser = json.loads(await fp.read())

            projects = await self.dbsession.execute(select(Project))
            projects = projects.scalars().all()
            for project in projects:
                if not project.ldap_gid:
                    project.ldap_gid = self.confopts['usersetup']['gid_offset'] + project.prjid_api

            users = await self.dbsession.execute(select(User))
            users = users.scalars().all()

            for user in users:
                set_metadata = False

                if user.is_active == 0:
                    continue

                if not user.ldap_uid and not user.is_staff:
                    if user.type_create == 'manual':
                        target_user = [tu for tu in mapuser if tu['username'] == user.username_api]
                        if target_user:
                            user.ldap_uid = target_user[0]['uid']
                        else:
                            self.logger.warning(f"UID for manually created user {user.username_api} must be defined in mapping file")
                            self.logger.warning("Skipping UID set")
                    else:
                        user.ldap_uid = self.confopts['usersetup']['uid_offset'] + user.uid_api
                    set_metadata = True
                if not user.ldap_gid and not user.is_staff and await user.awaitable_attrs.project:
                    # user GID is always set to GID of last assigned project
                    # we assume here that --init-set is run and relation between user,project is set
                    user_project = await user.awaitable_attrs.project
                    user.ldap_gid = self.confopts['usersetup']['gid_offset'] + user_project[-1].prjid_api
                    set_metadata = True
                if not user.ldap_gid and not user.is_staff and not await user.awaitable_attrs.project:
                    # set ldap_gid based on user.projects_api last project
                    try:
                        target_project = [pr for pr in projects if pr.identifier == user.projects_api[-1]]
                        user.ldap_gid = self.confopts['usersetup']['gid_offset'] + target_project[0].prjid_api
                        set_metadata = True
                    except IndexError:
                        self.logger.warning(f"User {user.username_api} type={user.type_create} with empty projects_api")
                if user.is_staff and not user.ldap_uid:
                    target_user = [tu for tu in mapuser if tu['username'] == user.username_api]
                    if target_user:
                        user.ldap_uid = target_user[0]['uid']
                    else:
                        user.ldap_uid = self.confopts['usersetup']['uid_manual_offset'] + user.uid_api
                    set_metadata = True
                if user.is_staff and not user.ldap_gid:
                    target_user = [tu for tu in mapuser if tu['username'] == user.username_api]
                    if target_user:
                        user.ldap_gid = target_user[0]['gid']
                        set_metadata = True

                if set_metadata:
                    self.logger.info(f"{user.first_name} {user.last_name} set username={user.username_api} UID={user.ldap_uid} GID={user.ldap_gid}")

            await self.dbsession.commit()

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling usermetadata...')
            raise exc

        finally:
            await self.dbsession.close()
