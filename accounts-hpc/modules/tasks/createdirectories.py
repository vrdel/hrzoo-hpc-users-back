from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

import sys
import os
import aiofiles
import aiofiles.os
import asyncio
import aioshutil
import stat

import sqlalchemy

from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound


class DirectoriesCreate(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args
        self.daemon = daemon

    async def run(self):
        try:
            users = await self.dbsession.execute(select(User))
            users = users.scalars().all()

            for user in users:
                if not user.is_dir_created:
                    completed = 0

                    for dir in self.confopts['usersetup']['userdirs_in']:
                        try:
                            await aiofiles.os.mkdir(dir + user.ldap_username, 0o700)

                        except FileExistsError:
                            pass
                        except (PermissionError, FileNotFoundError) as exc:
                            self.logger.error(exc)
                            break

                        try:
                            await aioshutil.chown(dir + user.ldap_username, user.ldap_uid, user.ldap_gid)
                            completed += 1

                        except (PermissionError, OSError, FileNotFoundError) as exc:
                            self.logger.error(exc)

                    if completed == len(self.confopts['usersetup']['userdirs_in']):
                        try:
                            user.is_dir_created = True

                            stmt = select(Project).where(Project.ldap_gid == user.ldap_gid)
                            project_info = await self.dbsession.execute(stmt)
                            project_info = project_info.scalars().one()

                            self.logger.info(f"Created {dir + user.ldap_username} with perm {user.ldap_uid}:{user.ldap_gid} ({user.ldap_username}:{project_info.identifier})")
                        except sqlalchemy.exc.NoResultFound:
                            self.logger.info(f"Created {dir + user.ldap_username} with perm {user.ldap_uid}:{user.ldap_gid}")

            projects = await self.dbsession.execute(select(Project))
            projects = projects.scalars().all()
            for project in projects:
                if not project.is_dir_created:
                    completed = 0

                    for dir in self.confopts['usersetup']['groupdirs_in']:
                        try:
                            await aiofiles.os.mkdir(dir + project.identifier)

                        except FileExistsError:
                            pass
                        except (PermissionError, FileNotFoundError) as exc:
                            self.logger.error(exc)
                            break

                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, os.chmod, dir + project.identifier, 0o2770)

                        try:
                            userown_aw = await project.awaitable_attrs.user
                            userown = userown_aw[0]
                            await aioshutil.chown(dir + project.identifier, userown.ldap_uid, project.ldap_gid)
                            completed += 1

                        except (PermissionError, OSError, FileNotFoundError) as exc:
                            self.logger.error(exc)

                        except IndexError as exc:
                            self.logger.warning(f"Project {project.identifier} without users")
                            self.logger.warning(exc)

                    if completed == len(self.confopts['usersetup']['groupdirs_in']):
                        project.is_dir_created = True
                        for dir in self.confopts['usersetup']['groupdirs_in']:
                            self.logger.info(f"Created {dir + project.identifier} with perm {userown.ldap_uid}:{project.ldap_gid} ({userown.ldap_username}:{project.identifier})")

        except PermissionError as exc:
            self.logger.error(exc)

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling createdirectories...')
            raise exc

        finally:
            await self.dbsession.commit()
            await self.dbsession.close()
