from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.exceptions import AhTaskError
from accounts_hpc.utils import contains_exception

from sqlalchemy import and_
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

import asyncio
import bonsai
import sys
import json


class LdapUpdate(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.daemon = daemon
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args

        try:
            self.client = bonsai.LDAPClient(self.confopts['ldap']['server'])
            self.client.set_credentials(
                "SIMPLE",
                user=self.confopts['ldap']['user'],
                password=self.confopts['ldap']['password']
            )

        except bonsai.errors.AuthenticationError as exc:
            self.logger.error(exc)
            raise SystemExit(1)

    async def new_organisation_project(self, identifier):
        async with self.client.connect(is_async=True) as conn:
            ldap_org_proj = bonsai.LDAPEntry(f"o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
            ldap_org_proj['objectClass'] = ['top', 'organization']
            ldap_org_proj['o'] = f'PROJECT-{identifier}'
            ldap_org_proj['description'] = f'Project on HRZOO resources {identifier}'
            await conn.add(ldap_org_proj)

            ldap_org_proj_people = bonsai.LDAPEntry(f"ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
            ldap_org_proj_people['objectClass'] = ['organizationalUnit']
            ldap_org_proj_people['ou'] = 'People'
            await conn.add(ldap_org_proj_people)

            ldap_org_proj_group = bonsai.LDAPEntry(f"ou=Group,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
            ldap_org_proj_group['objectClass'] = ['organizationalUnit']
            ldap_org_proj_group['ou'] = 'Group'
            await conn.add(ldap_org_proj_group)

    async def new_user_ldap_add(self, user, conn, identifier=None):
        if identifier:
            ldap_user = bonsai.LDAPEntry(f"cn={user.username_api},ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
        else:
            ldap_user = bonsai.LDAPEntry(f"cn={user.username_api},ou=People,{self.confopts['ldap']['basedn']}")
        ldap_user['objectClass'] = ['top', 'account', 'posixAccount', 'shadowAccount', 'ldapPublicKey']
        ldap_user['cn'] = [user.username_api]
        ldap_user['uid'] = [user.username_api]
        ldap_user['uidNumber'] = [user.ldap_uid]
        ldap_user['gidNumber'] = [user.ldap_gid]
        ldap_user['homeDirectory'] = [f"{self.confopts['usersetup']['homeprefix']}{user.username_api}"]
        ldap_user['loginShell'] = ['/bin/bash']
        ldap_user['gecos'] = [f"{user.first_name} {user.last_name}"]
        ldap_user['userPassword'] = ['']
        # ssh keys relations are set if we synced with --init-set
        keys = [sshkey.public_key for sshkey in await user.awaitable_attrs.sshkey]
        if keys:
            ldap_user['sshPublicKey'] = keys
        else:
            ldap_user['sshPublicKey'] = ''
        await conn.add(ldap_user)
        return ldap_user

    async def update_default_groups(self, users, group, onlyops=False):
        async with self.client.connect(is_async=True) as conn:
            ldap_group = await conn.search(f"cn={group},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)

            try:
                existing_members = ldap_group[0]['memberUid']
            except KeyError:
                existing_members = []
            # TODO: check also is_active
            if onlyops:
                all_usernames = [user.username_api for user in users if user.is_staff]
            else:
                all_usernames = [user.username_api for user in users]
            if set(all_usernames) != set(existing_members):
                ldap_group[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *all_usernames)
                await ldap_group[0].modify()
                diff_res = set(all_usernames).difference(set(existing_members))
                if not diff_res:
                    diff_res = set(existing_members).difference(set(all_usernames))
                self.logger.info(f"Updated default group {group} because of difference: {', '.join(diff_res)}")

    async def update_resource_groups(self, users, group):
        async with self.client.connect(is_async=True) as conn:
            all_usernames = list()
            ldap_group = await conn.search(f"cn={group},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
            if ldap_group:
                try:
                    existing_members = ldap_group[0]['memberUid']
                except KeyError:
                    existing_members = []

                for user in users:
                    resource_match = False
                    for project in user.project:
                        for rt in project.staff_resources_type_api:
                            if rt in group.upper():
                                resource_match = True
                                break
                    if resource_match:
                        all_usernames.append(user.username_api)

                if all_usernames and set(all_usernames) != set(existing_members):
                    ldap_group[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *all_usernames)
                    await ldap_group[0].modify()
                    diff_res = set(all_usernames).difference(set(existing_members))
                    if not diff_res:
                        diff_res = set(existing_members).difference(set(all_usernames))
                    self.logger.info(f"Updated resource group {group} because of difference: {', '.join(diff_res)}")

    async def gid_last_not_workshop(self, user):
        for pr in reversed(user.projects_api):
            stmt = select(Project).where(Project.identifier == pr)
            interested_project = await self.dbsession.execute(stmt)
            interested_project = interested_project.scalars().one()
            if interested_project.type != 'srce-workshop':
                return interested_project.ldap_gid
        return 0

    async def find_target_gid(self, user):
        try:
            all_workshops = all([pr.type == 'srce-workshop' for pr in user.project])
            if (user.project[-1].type == 'srce-workshop' and len(user.projects_api) > 1
                and not user.is_staff and not all_workshops):
                last_gid_project_not_workshop = await self.gid_last_not_workshop(user)
                if not user.skip_defgid:
                    self.logger.info(f"Skip set gidNumber={user.project[-1].ldap_gid} of srce-workshop as user {user.person_uniqueid} is already active on other projects")
                user.skip_defgid = True
                return last_gid_project_not_workshop

            stmt = select(Project).where(Project.identifier == user.projects_api[-1])
            target_project = await self.dbsession.execute(stmt)
            target_project = target_project.scalars().one()
            user.skip_defgid = False
            return target_project.ldap_gid

        except IndexError:
            return 0

    async def update_default_gid(self, proj_add, proj_del, user, ldap_user):
        """
            ensure that user's GID is always correctly set to the GID of last
            assigned project. as order of relations of users to projects might not be
            strictly correct and match what's on HZSI-WEB-API, we exclusively rely
            on projects_api field list of user's project order assignements. additionally
            if user's last assignment was on srce-workshop project, but it has already been
            before assigned to some other type project, don't update his GID to srce-workshop
            GID
        """
        target_gid = await self.find_target_gid(user)

        if target_gid != user.ldap_gid and not user.is_staff:
            ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, target_gid)
            await ldap_user[0].modify()
            self.logger.info(f"User {user.person_uniqueid} gidNumber updated to {target_gid}")
            user.ldap_gid = target_gid

        # explicitly set GID here for reactivated in separate clause
        # as ldap_gid is previously set in usermetadata task so previous
        # does not apply
        if target_gid and user.is_deactivated and not user.is_staff:
            ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, target_gid)
            await ldap_user[0].modify()
            self.logger.info(f"Re-activated user {user.person_uniqueid} gidNumber updated to {target_gid}")
            user.ldap_gid = target_gid

    async def user_sync_api_db(self, user, ldap_user):
        """
            check if there are differencies between user's project just
            synced from API and ones already registered in cache
        """
        projects_diff_add, projects_diff_del = set(), set()
        projects_db = [pr.identifier for pr in await user.awaitable_attrs.project]
        projects_diff_add = set(user.projects_api).difference(set(projects_db))
        # add user to project
        if projects_diff_add:
            for project in projects_diff_add:
                stmt = select(Project).where(Project.identifier == project)
                target_project = await self.dbsession.execute(stmt)
                target_project = target_project.scalars().one()
                target_project_user = await target_project.awaitable_attrs.user
                target_project_user.append(user)
                self.dbsession.add(target_project)
                self.logger.info(f"User {user.person_uniqueid} added to project {project}")
        # remove user from project
        projects_diff_del = set(projects_db).difference(set(user.projects_api))
        if projects_diff_del:
            for project in projects_diff_del:
                stmt = select(Project).where(Project.identifier == project)
                target_project = await self.dbsession.execute(stmt)
                target_project = target_project.scalars().one()
                target_project_user = await target_project.awaitable_attrs.user
                target_project_user.remove(user)
                self.dbsession.add(target_project)
                self.logger.info(f"User {user.person_uniqueid} removed from project {project}")
                if user.skip_defgid:
                    user.skip_defgid = False

        await self.update_default_gid(projects_diff_add, projects_diff_del, user, ldap_user)

    async def user_active_deactive(self, user, ldap_user=None, ldap_conn=None):
        if self.confopts['ldap']['mode'] == 'flat':
            if user.is_active == False and user.is_deactivated == False:
                ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, self.confopts['usersetup']['noshell'])
                await ldap_user[0].modify()
                self.logger.info(f"Deactivating {user.username_api}, setting disabled shell={self.confopts['usersetup']['noshell']}")
                user.is_deactivated = True
                user.mail_is_deactivated = True

            if user.is_active == True and user.is_deactivated == True:
                ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, '/bin/bash')
                await ldap_user[0].modify()

                self.logger.info(f"Activating {user.username_api}, setting default shell=/bin/bash")
                user.is_deactivated = False
                user.mail_is_activated = True
        else:
            if user.is_deactivated_project:
                for proj in user.is_deactivated_project:
                    if not user.is_deactivated_project[proj]:
                        ldap_user = await ldap_conn.search(f"cn={user.username_api},ou=People,o=PROJECT-{proj},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                        ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, self.confopts['usersetup']['noshell'])
                        await ldap_user[0].modify()
                        self.logger.info(f"Deactivating {user.username_api} for {proj}, setting disabled shell={self.confopts['usersetup']['noshell']}")
                        user.is_deactivated_project[proj] = True
                        user.mail_project_is_deactivated[proj] = False
            if user.is_activated_project:
                for proj in user.is_activated_project:
                    if not user.is_activated_project[proj]:
                        ldap_user = await ldap_conn.search(f"cn={user.username_api},ou=People,o=PROJECT-{proj},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                        ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, '/bin/bash')
                        await ldap_user[0].modify()
                        self.logger.info(f"Activating {user.username_api} for {proj}, setting default shell=/bin/bash")
                        user.is_activated_project[proj] = True
                        user.mail_project_is_activated[proj] = False
                        user.is_deactivated = False
            if user.is_active == False and user.is_deactivated == False:
                for proj in await user.awaitable_attrs.project:
                    ldap_user = await ldap_conn.search(f"cn={user.username_api},ou=People,o=PROJECT-{proj.identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                    ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, self.confopts['usersetup']['noshell'])
                    await ldap_user[0].modify()
                    self.logger.info(f"user.is_active=0, deactivating {user.username_api} for {proj.identifier}, setting disabled shell={self.confopts['usersetup']['noshell']}")
                    user.is_deactivated_project[proj.identifier] = True
                    user.mail_project_is_deactivated[proj.identifier] = False
                    user.is_deactivated = True

    async def user_key_update(self, user, ldap_user, identifier=None):
        """
            check if sshkeys are added or removed
        """
        if user.username_api == 'gthakkar':
            import ipdb; ipdb.set_trace()

        keys_diff_add, keys_diff_del = set(), set()
        keys_db = [key.fingerprint for key in await user.awaitable_attrs.sshkey]
        keys_diff_add = set(user.sshkeys_api).difference(set(keys_db))
        if keys_diff_add:
            for key in keys_diff_add:
                try:
                    stmt = select(SshKey).where(
                        and_(
                            SshKey.fingerprint == key,
                            SshKey.uid_api == user.uid_api,
                        )
                    )
                    target_key = await self.dbsession.execute(stmt)
                    target_key = target_key.scalars().one()
                except MultipleResultsFound:
                    try:
                        stmt = select(SshKey).where(
                            and_(
                                SshKey.fingerprint == key,
                                SshKey.user_id == user.id,
                            )
                        )
                        target_key = await self.dbsession.execute(stmt)
                        target_key = target_key.scalars().one()
                    except NoResultFound:
                        stmt = select(SshKey).where(
                            and_(
                                SshKey.fingerprint == key,
                                SshKey.user_id == None
                            )
                        )
                        target_key = await self.dbsession.execute(stmt)
                        target_key = target_key.scalars().one()
                user_sshkey = await user.awaitable_attrs.sshkey
                user_sshkey.append(target_key)
                user.mail_name_sshkey.append(f'ADD:{target_key.name}')
                if self.confopts['ldap']['mode'] == 'project_organisation':
                    mp = user.mail_project_is_sshkeyadded
                    for prj in mp.keys():
                        if mp[prj]:
                            mp[prj] = False
                    user.mail_project_is_sshkeyadded = mp
                else:
                    user.mail_is_sshkeyadded = False
                if self.confopts['ldap']['mode'] == 'project_organisation':
                    self.logger.info(f"Added key {target_key.name} for user {user.person_uniqueid},{identifier}")
                else:
                    self.logger.info(f"Added key {target_key.name} for user {user.person_uniqueid}")

        keys_diff_del = set(keys_db).difference(set(user.sshkeys_api))
        if keys_diff_del:
            for key in keys_diff_del:
                stmt = select(SshKey).where(
                    and_(
                        SshKey.uid_api == user.uid_api,
                        SshKey.fingerprint == key
                    )
                )
                target_key = await self.dbsession.execute(stmt)
                target_key = target_key.scalars().one()
                user_target_key = await user.awaitable_attrs.sshkey
                user_target_key.remove(target_key)
                user.mail_name_sshkey.append(f'DEL:{target_key.name}')
                if self.confopts['ldap']['mode'] == 'project_organisation':
                    mp = user.mail_project_is_sshkeyremoved
                    for prj in mp.keys():
                        if mp[prj]:
                            mp[prj] = False
                    user.mail_project_is_sshkeyremoved = mp
                else:
                    user.mail_is_sshkeyremoved = False
                if self.confopts['ldap']['mode'] == 'project_organisation':
                    self.logger.info(f"Removed key {target_key.name} for user {user.person_uniqueid},{identifier}")
                else:
                    self.logger.info(f"Removed key {target_key.name} for user {user.person_uniqueid}")

        if keys_diff_add or keys_diff_del:
            updated_keys = [sshkey.public_key for sshkey in user.sshkey]
            if len(updated_keys) == 0:
                ldap_user[0].change_attribute('sshPublicKey', bonsai.LDAPModOp.REPLACE, '')
            else:
                ldap_user[0].change_attribute('sshPublicKey', bonsai.LDAPModOp.REPLACE, *updated_keys)
            await ldap_user[0].modify()
            self.dbsession.add(user)
            if self.confopts['ldap']['mode'] == 'project_organisation':
                self.logger.info(f"User {user.person_uniqueid},{identifier} LDAP SSH keys updated")
            else:
                self.logger.info(f"User {user.person_uniqueid} LDAP SSH keys updated")

    async def new_group_ldap_add(self, project):
        async with self.client.connect(is_async=True) as conn:
            if self.confopts['ldap']['mode'] == 'flat':
                ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,{self.confopts['ldap']['basedn']}")
            else:
                ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,o=PROJECT-{project.identifier},{self.confopts['ldap']['basedn']}")
            ldap_project['cn'] = [project.identifier]
            ldap_project['objectClass'] = ['top', 'posixGroup']
            ldap_project['gidNumber'] = [project.ldap_gid]
            ldap_project['memberUid'] = [user.username_api for user in await project.awaitable_attrs.user]
            await conn.add(ldap_project)
            return ldap_project

    async def group_ldap_update(self, project, ldap_project):
        project_members_changed = False
        try:
            users_project_ldap = ldap_project[0]['memberUid']
        except KeyError:
            users_project_ldap = []
        if set(users_project_ldap).difference(set([user.username_api for user in await project.awaitable_attrs.user])):
            project_members_changed = True
        elif set([user.username_api for user in project.user]).difference(set(users_project_ldap)):
            project_members_changed = True
        if project_members_changed:
            project_new_members = [user.username_api for user in project.user]
            if len(project_new_members) == 0:
                del ldap_project[0]['memberUid']
            else:
                ldap_project[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *project_new_members)
            await ldap_project[0].modify()
            if project_new_members:
                self.logger.info(f"Updating memberUid for LDAP cn={project.identifier},ou=Group new members: {', '.join(project_new_members)}")
            else:
                self.logger.info(f"Emptied LDAP cn={project.identifier},ou=Group")

    async def create_default_groups(self):
        async with self.client.connect(is_async=True) as conn:
            numgroup = 1
            for gr in self.confopts['usersetup']['default_groups']:
                group_ldap = await conn.search(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                if not group_ldap:
                    ldap_gid = self.confopts['usersetup']['gid_manual_offset'] + numgroup
                    ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}")
                    ldap_project['cn'] = [gr]
                    ldap_project['objectClass'] = ['top', 'posixGroup']
                    ldap_project['gidNumber'] = [ldap_gid]
                    await conn.add(ldap_project)
                    self.logger.info(f"Created default group {gr} with gid={ldap_gid}")
                    numgroup += 1

    async def create_resource_groups(self):
        async with self.client.connect(is_async=True) as conn:
            numgroup = 1
            num_defgroups = len(self.confopts['usersetup']['default_groups'])
            for gr in self.confopts['usersetup']['resource_groups']:
                group_ldap = await conn.search(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                if not group_ldap:
                    ldap_gid = self.confopts['usersetup']['gid_manual_offset'] + numgroup + num_defgroups
                    ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}")
                    ldap_project['cn'] = [gr]
                    ldap_project['objectClass'] = ['top', 'posixGroup']
                    ldap_project['gidNumber'] = [ldap_gid]
                    await conn.add(ldap_project)
                    self.logger.info(f"Created resource group {gr} with gid={ldap_gid}")
                    numgroup += 1

    async def run(self):
        try:
            stmt = select(User)
            users = await self.dbsession.execute(stmt)
            users = users.scalars().all()

            # default and resource groups are created only for flat hierarchies
            if self.confopts['ldap']['mode'] == 'flat':
                loop = asyncio.get_event_loop()
                tasks = [self.create_resource_groups(), self.create_default_groups()]
                ret_create_groups = await asyncio.gather(*tasks, loop=loop, return_exceptions=True)
                exc_raised, exc = contains_exception(ret_create_groups)
                if exc_raised:
                    self.logger.error(f"Error creating default and resource groups - {repr(exc)}")
                    raise AhTaskError

            for user in users:
                if not user.username_api:
                    continue
                if self.confopts['ldap']['mode'] == 'flat':
                    async with self.client.connect(is_async=True, timeout=None) as conn:
                        ldap_user = await conn.search(f"cn={user.username_api},ou=People,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                        try:
                            if not ldap_user or not user.is_opened:
                                ldap_user = await self.new_user_ldap_add(user, conn)
                                await self.user_sync_api_db(user, [ldap_user])
                                await self.user_active_deactive(user, [ldap_user])
                                await self.user_key_update(user, [ldap_user])
                            else:
                                await self.user_sync_api_db(user, ldap_user)
                                await self.user_active_deactive(user, ldap_user)
                                await self.user_key_update(user, ldap_user)
                            user.is_opened = True
                        except bonsai.errors.AlreadyExists as exc:
                            self.logger.warning(f'LDAP user {user.username_api} - {repr(exc)}')
                            await self.user_sync_api_db(user, ldap_user)
                            await self.user_active_deactive(user, ldap_user)
                            await self.user_key_update(user, ldap_user)
                            user.is_opened = True
                        except bonsai.errors.LDAPError as exc:
                            self.logger.error(f'Error adding/updating LDAP user {user.username_api} - {repr(exc)}')
                else:
                    async with self.client.connect(is_async=True) as conn:
                        for identifier in user.projects_api:
                            ldap_org_proj = await conn.search(f"o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                            if not ldap_org_proj:
                                await self.new_organisation_project(identifier)
                            ldap_user = await conn.search(f"cn={user.username_api},ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                            try:
                                if not ldap_user or not user.is_opened:
                                    ldap_user = await self.new_user_ldap_add(user, conn, identifier)
                                    await self.user_sync_api_db(user, [ldap_user])
                                    await self.user_key_update(user, [ldap_user])
                                else:
                                    await self.user_sync_api_db(user, ldap_user)
                                    await self.user_key_update(user, ldap_user, identifier)
                                user.is_opened = True
                            except bonsai.errors.AlreadyExists as exc:
                                self.logger.warning(f'LDAP user {user.username_api} - {repr(exc)}')
                                await self.user_sync_api_db(user, ldap_user)
                                await self.user_key_update(user, ldap_user)
                                user.is_opened = True
                            except bonsai.errors.LDAPError as exc:
                                self.logger.error(f'Error adding/updating LDAP user {user.username_api} - {repr(exc)}')
                        await self.user_active_deactive(user, ldap_conn=conn)

            stmt = select(Project)
            projects = await self.dbsession.execute(stmt)
            projects = projects.scalars().all()

            async with self.client.connect(is_async=True) as conn:
                for project in projects:
                    if self.confopts['ldap']['mode'] == 'flat':
                        ldap_project = await conn.search(f"cn={project.identifier},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                    else:
                        ldap_project = await conn.search(f"cn={project.identifier},ou=Group,o=PROJECT-{project.identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                    try:
                        if not ldap_project:
                            ldap_project = await self.new_group_ldap_add(project)
                            await self.group_ldap_update(project, [ldap_project])
                        else:
                            await self.group_ldap_update(project, ldap_project)
                    except bonsai.errors.LDAPError as exc:
                        self.logger.error(f'Error adding/updating LDAP group {project.identifier} - {repr(exc)}')

            if self.confopts['ldap']['mode'] == 'flat':
                # handle default groups associations
                task_update_defgroups = asyncio.create_task(self.update_default_groups(users, "hpc-users"))
                # update_default_groups(self.confopts, conn, self.logger, users, "hpc", onlyops=True)

                # handle resource groups associations
                task_update_resgroup1 = asyncio.create_task(self.update_resource_groups(users, "hpc-bigmem"))
                task_update_resgroup2 = asyncio.create_task(self.update_resource_groups(users, "hpc-gpu"))

                await task_update_defgroups
                await task_update_resgroup1
                await task_update_resgroup2

            await self.dbsession.commit()

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling ldapupdate...')
            raise exc

        finally:
            await self.dbsession.close()
