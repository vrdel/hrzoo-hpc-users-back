from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore

from sqlalchemy import and_
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

import bonsai
import sys
import json


class LdapUpdate(object):
    def __init__(self, caller, args):
        shared = Shared(caller)
        self.confopts = shared.confopts
        self.logger = shared.log.get()
        self.dbsession = shared.dbsession
        self.args = args

        try:
            client = bonsai.LDAPClient(self.confopts['ldap']['server'])
            client.set_credentials(
                "SIMPLE",
                user=self.confopts['ldap']['user'],
                password=self.confopts['ldap']['password']
            )
            self.conn = client.connect()

        except bonsai.errors.AuthenticationError as exc:
            self.logger.error(exc)
            raise SystemExit(1)

    def new_organisation_project(self, identifier):
        ldap_org_proj = bonsai.LDAPEntry(f"o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
        ldap_org_proj['objectClass'] = ['top', 'organization']
        ldap_org_proj['o'] = f'PROJECT-{identifier}'
        ldap_org_proj['description'] = f'Project on HRZOO resources {identifier}'
        self.conn.add(ldap_org_proj)

        ldap_org_proj_people = bonsai.LDAPEntry(f"ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
        ldap_org_proj_people['objectClass'] = ['organizationalUnit']
        ldap_org_proj_people['ou'] = 'People'
        self.conn.add(ldap_org_proj_people)

        ldap_org_proj_group = bonsai.LDAPEntry(f"ou=Group,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
        ldap_org_proj_group['objectClass'] = ['organizationalUnit']
        ldap_org_proj_group['ou'] = 'Group'
        self.conn.add(ldap_org_proj_group)

    def new_user_ldap_add(self, user, identifier=None):
        if identifier:
            ldap_user = bonsai.LDAPEntry(f"cn={user.ldap_username},ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}")
        else:
            ldap_user = bonsai.LDAPEntry(f"cn={user.ldap_username},ou=People,{self.confopts['ldap']['basedn']}")
        ldap_user['objectClass'] = ['top', 'account', 'posixAccount', 'shadowAccount', 'ldapPublicKey']
        ldap_user['cn'] = [user.ldap_username]
        ldap_user['uid'] = [user.ldap_username]
        ldap_user['uidNumber'] = [user.ldap_uid]
        ldap_user['gidNumber'] = [user.ldap_gid]
        ldap_user['homeDirectory'] = [f"{self.confopts['usersetup']['homeprefix']}{user.ldap_username}"]
        ldap_user['loginShell'] = ['/bin/bash']
        ldap_user['gecos'] = [f"{user.first_name} {user.last_name}"]
        ldap_user['userPassword'] = ['']
        # ssh keys relations are set if we synced with --init-set
        keys = [sshkey.public_key for sshkey in user.sshkey]
        if keys:
            ldap_user['sshPublicKey'] = keys
        else:
            ldap_user['sshPublicKey'] = ''
        self.conn.add(ldap_user)
        return ldap_user

    def update_default_groups(self, users, group, onlyops=False):
        ldap_group = self.conn.search(f"cn={group},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)

        try:
            existing_members = ldap_group[0]['memberUid']
        except KeyError:
            existing_members = []
        # TODO: check also is_active
        if onlyops:
            all_usernames = [user.ldap_username for user in users if user.is_staff]
        else:
            all_usernames = [user.ldap_username for user in users]
        if set(all_usernames) != set(existing_members):
            ldap_group[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *all_usernames)
            ldap_group[0].modify()
            diff_res = set(all_usernames).difference(set(existing_members))
            if not diff_res:
                diff_res = set(existing_members).difference(set(all_usernames))
            self.logger.info(f"Updated default group {group} because of difference: {', '.join(diff_res)}")

    def update_resource_groups(self, users, group):
        all_usernames = list()
        ldap_group = self.conn.search(f"cn={group},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
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
                    all_usernames.append(user.ldap_username)

            if all_usernames and set(all_usernames) != set(existing_members):
                ldap_group[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *all_usernames)
                ldap_group[0].modify()
                diff_res = set(all_usernames).difference(set(existing_members))
                if not diff_res:
                    diff_res = set(existing_members).difference(set(all_usernames))
                self.logger.info(f"Updated resource group {group} because of difference: {', '.join(diff_res)}")

    def user_ldap_update(self, user, ldap_user):
        """
            check if there are differencies between user's project just
            synced from API and ones already registered in cache
        """

        projects_diff_add, projects_diff_del = set(), set()
        projects_db = [pr.identifier for pr in user.project]
        projects_diff_add = set(user.projects_api).difference(set(projects_db))
        # add user to project
        if projects_diff_add:
            for project in projects_diff_add:
                target_project = self.dbsession.query(Project).filter(Project.identifier == project).one()
                target_project.user.append(user)
                self.dbsession.add(target_project)
                self.logger.info(f"User {user.person_uniqueid} added to project {project}")
        # remove user from project
        projects_diff_del = set(projects_db).difference(set(user.projects_api))
        if projects_diff_del:
            for project in projects_diff_del:
                target_project = self.dbsession.query(Project).filter(Project.identifier == project).one()
                target_project.user.remove(user)
                self.dbsession.add(target_project)
                self.logger.info(f"User {user.person_uniqueid} removed from project {project}")
        try:
            target_gid = self.confopts['usersetup']['gid_offset'] + user.project[-1].prjid_api
        except IndexError:
            target_gid = 0
        if projects_diff_add or projects_diff_del:
            if not user.is_staff:
                ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, target_gid)
                ldap_user[0].modify()
                self.logger.info(f"User {user.person_uniqueid} gidNumber updated to {target_gid}")
        # trigger default gid update when associated projects remain same
        if not user.is_staff and user.ldap_gid != target_gid:
            ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, target_gid)
            ldap_user[0].modify()
            self.logger.info(f"Enforce user {user.person_uniqueid} gidNumber update to {target_gid}")
        if not user.is_staff:
            user.ldap_gid = target_gid

        if user.is_active == 0 and user.is_deactivated == 0:
            ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, self.confopts['usersetup']['noshell'])
            ldap_user[0].modify()
            self.logger.info(f"Deactivating {user.ldap_username}, setting disabled shell={self.confopts['usersetup']['noshell']}")
            user.is_deactivated = 1

        if user.is_active == 1 and user.is_deactivated == 1:
            ldap_user[0].change_attribute('loginShell', bonsai.LDAPModOp.REPLACE, '/bin/bash')
            ldap_user[0].modify()
            self.logger.info(f"Activating {user.ldap_username}, setting default shell=/bin/bash")
            user.is_deactivated = 0

    def user_key_update(self, user, ldap_user):
        """
            check if sshkeys are added or removed
        """
        keys_diff_add, keys_diff_del = set(), set()
        keys_db = [key.fingerprint for key in user.sshkey]
        keys_diff_add = set(user.sshkeys_api).difference(set(keys_db))
        if keys_diff_add:
            for key in keys_diff_add:
                try:
                    target_key = self.dbsession.query(SshKey).filter(and_(
                        SshKey.fingerprint == key,
                        SshKey.uid_api == user.uid_api,
                    )).one()
                except MultipleResultsFound:
                    try:
                        target_key = self.dbsession.query(SshKey).filter(and_(
                            SshKey.fingerprint == key,
                            SshKey.user_id == user.id,
                        )).one()
                    except NoResultFound:
                        target_key = self.dbsession.query(SshKey).filter(and_(
                            SshKey.fingerprint == key,
                            SshKey.user_id == None
                        )).one()
                user.sshkey.append(target_key)
                user.mail_name_sshkey.append(target_key.name)
                if self.confopts['email']['project_email']:
                    mp = user.mail_project_is_sshkeyadded
                    for prj in mp.keys():
                        if mp[prj]:
                            mp[prj] = False
                    user.mail_project_is_sshkeyadded = mp
                else:
                    user.mail_is_sshkeyadded = False
                self.logger.info(f"Added key {target_key.name} for user {user.person_uniqueid}")

        keys_diff_del = set(keys_db).difference(set(user.sshkeys_api))
        if keys_diff_del:
            for key in keys_diff_del:
                target_key = self.dbsession.query(SshKey).filter(SshKey.fingerprint == key).one()
                user.sshkey.remove(target_key)
                self.logger.info(f"Removed key {target_key.name} for user {user.person_uniqueid}")
        if keys_diff_add or keys_diff_del:
            updated_keys = [sshkey.public_key for sshkey in user.sshkey]
            if len(updated_keys) == 0:
                ldap_user[0].change_attribute('sshPublicKey', bonsai.LDAPModOp.REPLACE, '')
            else:
                ldap_user[0].change_attribute('sshPublicKey', bonsai.LDAPModOp.REPLACE, *updated_keys)
            ldap_user[0].modify()
            self.dbsession.add(user)
            self.logger.info(f"User {user.person_uniqueid} LDAP SSH keys updated")

    def new_group_ldap_add(self, project):
        if not self.confopts['ldap']['project_organisation']:
            ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,{self.confopts['ldap']['basedn']}")
        else:
            ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,o=PROJECT-{project.identifier},{self.confopts['ldap']['basedn']}")
        ldap_project['cn'] = [project.identifier]
        ldap_project['objectClass'] = ['top', 'posixGroup']
        ldap_project['gidNumber'] = [project.ldap_gid]
        ldap_project['memberUid'] = [user.ldap_username for user in project.user]
        self.conn.add(ldap_project)
        return ldap_project

    def group_ldap_update(self, project, ldap_project):
        project_members_changed = False
        try:
            users_project_ldap = ldap_project[0]['memberUid']
        except KeyError:
            users_project_ldap = []
        if set(users_project_ldap).difference(set([user.ldap_username for user in project.user])):
            project_members_changed = True
        elif set([user.ldap_username for user in project.user]).difference(set(users_project_ldap)):
            project_members_changed = True
        if project_members_changed:
            project_new_members = [user.ldap_username for user in project.user]
            if len(project_new_members) == 0:
                del ldap_project[0]['memberUid']
            else:
                ldap_project[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *project_new_members)
            ldap_project[0].modify()
            self.logger.info(f"Updating memberUid for LDAP cn={project.identifier},ou=Group new members: {', '.join(project_new_members)}")

    def create_default_groups(self):
        numgroup = 1
        for gr in self.confopts['usersetup']['default_groups']:
            group_ldap = self.conn.search(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
            if not group_ldap:
                ldap_gid = self.confopts['usersetup']['gid_manual_offset'] + numgroup
                ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}")
                ldap_project['cn'] = [gr]
                ldap_project['objectClass'] = ['top', 'posixGroup']
                ldap_project['gidNumber'] = [ldap_gid]
                self.conn.add(ldap_project)
                self.logger.info(f"Created default group {gr} with gid={ldap_gid}")
                numgroup += 1

    def create_resource_groups(self):
        numgroup = 1
        num_defgroups = len(self.confopts['usersetup']['default_groups'])
        for gr in self.confopts['usersetup']['resource_groups']:
            group_ldap = self.conn.search(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
            if not group_ldap:
                ldap_gid = self.confopts['usersetup']['gid_manual_offset'] + numgroup + num_defgroups
                ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{self.confopts['ldap']['basedn']}")
                ldap_project['cn'] = [gr]
                ldap_project['objectClass'] = ['top', 'posixGroup']
                ldap_project['gidNumber'] = [ldap_gid]
                self.conn.add(ldap_project)
                self.logger.info(f"Created resource group {gr} with gid={ldap_gid}")
                numgroup += 1

    def run(self):
        users = self.dbsession.query(User).all()

        # default and resource groups are created only for flat hierarchies
        if not self.confopts['ldap']['project_organisation']:
            self.create_default_groups()
            self.create_resource_groups()

        for user in users:
            if not user.ldap_username:
                continue
            if not self.confopts['ldap']['project_organisation']:
                ldap_user = self.conn.search(f"cn={user.ldap_username},ou=People,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                try:
                    if not ldap_user or not user.is_opened:
                        ldap_user = self.new_user_ldap_add(user)
                        self.user_ldap_update(user, [ldap_user])
                        self.user_key_update(user, [ldap_user])
                    else:
                        self.user_ldap_update(user, ldap_user)
                        self.user_key_update(user, ldap_user)
                    user.is_opened = True
                except bonsai.errors.AlreadyExists as exc:
                    self.logger.warning(f'LDAP user {user.ldap_username} - {repr(exc)}')
                    self.user_ldap_update(user, ldap_user)
                    self.user_key_update(user, ldap_user)
                    user.is_opened = True
                except bonsai.errors.LDAPError as exc:
                    self.logger.error(f'Error adding/updating LDAP user {user.ldap_username} - {repr(exc)}')
            else:
                for identifier in user.projects_api:
                    ldap_org_proj = self.conn.search(f"o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                    if not ldap_org_proj:
                        self.new_organisation_project(identifier)
                    ldap_user = self.conn.search(f"cn={user.ldap_username},ou=People,o=PROJECT-{identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
                    try:
                        if not ldap_user or not user.is_opened:
                            ldap_user = self.new_user_ldap_add(user, identifier)
                            self.user_ldap_update(user, [ldap_user])
                            self.user_key_update(user, [ldap_user])
                        else:
                            self.user_ldap_update(user, ldap_user)
                            self.user_key_update(user, ldap_user)
                        user.is_opened = True
                    except bonsai.errors.AlreadyExists as exc:
                        self.logger.warning(f'LDAP user {user.ldap_username} - {repr(exc)}')
                        self.user_ldap_update(user, ldap_user)
                        self.user_key_update(user, ldap_user)
                        user.is_opened = True
                    except bonsai.errors.LDAPError as exc:
                        self.logger.error(f'Error adding/updating LDAP user {user.ldap_username} - {repr(exc)}')

        projects = self.dbsession.query(Project).all()
        for project in projects:
            if not self.confopts['ldap']['project_organisation']:
                ldap_project = self.conn.search(f"cn={project.identifier},ou=Group,{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
            else:
                ldap_project = self.conn.search(f"cn={project.identifier},ou=Group,o=PROJECT-{project.identifier},{self.confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
            try:
                if not ldap_project:
                    ldap_project = self.new_group_ldap_add(project)
                    self.group_ldap_update(project, [ldap_project])
                else:
                    self.group_ldap_update(project, ldap_project)
            except bonsai.errors.LDAPError as exc:
                self.logger.error(f'Error adding/updating LDAP group {project.identifier} - {repr(exc)}')

        if not self.confopts['ldap']['project_organisation']:
            # handle default groups associations
            self.update_default_groups(users, "hpc-users")
            # update_default_groups(self.confopts, conn, self.logger, users, "hpc", onlyops=True)

            # handle resource groups associations
            self.update_resource_groups(users, "hpc-bigmem")
            self.update_resource_groups(users, "hpc-gpu")

        self.dbsession.commit()
        self.dbsession.close()
