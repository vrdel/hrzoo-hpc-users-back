from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

import sys
import os
import stat

import sqlalchemy
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound


class DirectoriesCreate(object):
    def __init__(self, caller, args):
        shared = Shared(caller)
        self.confopts = shared.confopts
        self.logger = shared.log.get()
        self.dbsession = shared.dbsession[caller]
        self.args = args

    def run(self):
        users = self.dbsession.query(User).all()
        for user in users:
            if not user.is_dir_created:
                completed = 0

                for dir in self.confopts['usersetup']['userdirs_in']:
                    try:
                        os.mkdir(dir + user.ldap_username, 0o700)

                    except FileExistsError:
                        pass
                    except (PermissionError, FileNotFoundError) as exc:
                        self.logger.error(exc)
                        break

                    try:
                        os.chown(dir + user.ldap_username, user.ldap_uid, user.ldap_gid)
                        completed += 1

                    except (PermissionError, OSError, FileNotFoundError) as exc:
                        self.logger.error(exc)

                if completed == len(self.confopts['usersetup']['userdirs_in']):
                    try:
                        user.is_dir_created = True
                        project_info = self.dbsession.query(Project).filter(Project.ldap_gid == user.ldap_gid).one()
                        self.logger.info(f"Created {dir + user.ldap_username} with perm {user.ldap_uid}:{user.ldap_gid} ({user.ldap_username}:{project_info.identifier})")
                    except sqlalchemy.exc.NoResultFound:
                        self.logger.info(f"Created {dir + user.ldap_username} with perm {user.ldap_uid}:{user.ldap_gid}")

        projects = self.dbsession.query(Project).all()
        for project in projects:
            if not project.is_dir_created:
                completed = 0

                for dir in self.confopts['usersetup']['groupdirs_in']:
                    try:
                        os.mkdir(dir + project.identifier)

                    except FileExistsError:
                        pass
                    except (PermissionError, FileNotFoundError) as exc:
                        self.logger.error(exc)
                        break

                    os.chmod(dir + project.identifier, 0o2770)

                    try:
                        userown = project.user[0]
                        os.chown(dir + project.identifier, userown.ldap_uid, project.ldap_gid)
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

        self.dbsession.commit()
        self.dbsession.close()
