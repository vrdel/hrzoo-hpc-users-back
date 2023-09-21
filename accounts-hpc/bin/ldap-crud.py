#!/usr/bin/env python

import bonsai
import sys

from accounts_hpc.config import parse_config
from accounts_hpc.log import Logger
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import NoResultFound

import argparse


def new_user_ldap_add(confopts, conn, user):

    ldap_user = bonsai.LDAPEntry(f"cn={user.ldap_username},ou=People,{confopts['ldap']['basedn']}")
    ldap_user['objectClass'] = ['top', 'account', 'posixAccount', 'shadowAccount', 'ldapPublicKey']
    ldap_user['cn'] = [user.ldap_username]
    ldap_user['uid'] = [user.ldap_username]
    ldap_user['uidNumber'] = [user.ldap_uid]
    ldap_user['gidNumber'] = [user.ldap_gid]
    ldap_user['homeDirectory'] = [f"/lustre/home/{user.ldap_username}"]
    ldap_user['loginShell'] = ['/bin/bash']
    ldap_user['gecos'] = [f"{user.first_name} {user.last_name}"]
    ldap_user['userPassword'] = ['']
    # ssh keys relations are set if we synced with --init-set
    keys = [sshkey.public_key for sshkey in user.sshkey]
    if keys:
        ldap_user['sshPublicKey'] = keys
    else:
        ldap_user['sshPublicKey'] = ''
    conn.add(ldap_user)


def update_default_groups(confopts, conn, logger, users, group, onlyops=False):
    ldap_group = conn.search(f"cn={group},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
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
        logger.info(f"Updated default group {group} because of difference: {diff_res}")


def update_resource_groups(confopts, conn, logger, users, group):
    all_usernames = list()
    ldap_group = conn.search(f"cn={group},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
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

    if set(all_usernames) != set(existing_members):
        ldap_group[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, *all_usernames)
        ldap_group[0].modify()
        diff_res = set(all_usernames).difference(set(existing_members))
        if not diff_res:
            diff_res = set(existing_members).difference(set(all_usernames))
        logger.info(f"Updated resource group {group} because of difference: {diff_res}")


def user_ldap_update(confopts, session, logger, user, ldap_user):
    # check if there are differencies between user's project just
    # synced from API and ones already registered in cache
    projects_diff_add, projects_diff_del = set(), set()
    projects_db = [pr.identifier for pr in user.project]
    projects_diff_add = set(user.projects_api).difference(set(projects_db))
    # add user to project
    if projects_diff_add:
        for project in projects_diff_add:
            target_project = session.query(Project).filter(Project.identifier == project).one()
            target_project.user.append(user)
            session.add(target_project)
            logger.info(f"User {user.person_uniqueid} added to project {project}")
    # remove user from project
    projects_diff_del = set(projects_db).difference(set(user.projects_api))
    if projects_diff_del:
        for project in projects_diff_del:
            target_project = session.query(Project).filter(Project.identifier == project).one()
            target_project.user.remove(user)
            session.add(target_project)
            logger.info(f"User {user.person_uniqueid} removed from project {project}")
    if projects_diff_add or projects_diff_del:
        target_gid = confopts['usersetup']['gid_offset'] + user.project[-1].prjid_api
        ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, target_gid)
        ldap_user[0].modify()
        logger.info(f"User {user.person_uniqueid} gidNumber updated to {target_gid}")

    # check if sshkeys are added or removed
    keys_diff_add, keys_diff_del = set(), set()
    keys_db = [key.fingerprint for key in user.sshkey]
    keys_diff_add = set(user.sshkeys_api).difference(set(keys_db))
    if keys_diff_add:
        for key in keys_diff_add:
            target_key = session.query(SshKey).filter(and_(
                SshKey.fingerprint == key,
                SshKey.uid_api == user.uid_api,
            )).one()
            user.sshkey.append(target_key)
            logger.info(f"Added key {target_key.name} for user {user.person_uniqueid}")
    keys_diff_del = set(keys_db).difference(set(user.sshkeys_api))
    if keys_diff_del:
        for key in keys_diff_del:
            target_key = session.query(SshKey).filter(SshKey.fingerprint == key).one()
            user.sshkey.remove(target_key)
            logger.info(f"Removed key {target_key.name} for user {user.person_uniqueid}")
    if keys_diff_add or keys_diff_del:
        updated_keys = [sshkey.public_key for sshkey in user.sshkey]
        ldap_user[0].change_attribute('sshPublicKey', bonsai.LDAPModOp.REPLACE, *updated_keys)
        ldap_user[0].modify()
        session.add(user)
        logger.info(f"User {user.person_uniqueid} LDAP SSH keys updated")


def new_group_ldap_add(confopts, conn, project):
    ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,{confopts['ldap']['basedn']}")
    ldap_project['cn'] = [project.identifier]
    ldap_project['objectClass'] = ['top', 'posixGroup']
    ldap_project['gidNumber'] = [project.ldap_gid]
    ldap_project['memberUid'] = [user.ldap_username for user in project.user]
    conn.add(ldap_project)


def group_ldap_update(confopts, session, logger, project, ldap_project):
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
        logger.info(f"Updating memberUid for LDAP cn={project.identifier},ou=Group")


def create_default_groups(confopts, conn, logger):
    numgroup = 1
    for gr in confopts['usersetup']['default_groups']:
        group_ldap = conn.search(f"cn={gr},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
        if not group_ldap:
            ldap_gid = confopts['usersetup']['gid_ops_offset'] + numgroup
            ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{confopts['ldap']['basedn']}")
            ldap_project['cn'] = [gr]
            ldap_project['objectClass'] = ['top', 'posixGroup']
            ldap_project['gidNumber'] = [ldap_gid]
            conn.add(ldap_project)
            logger.info(f"Created default group {gr} with gid={ldap_gid}")
            numgroup += 1


def create_resource_groups(confopts, conn, logger):
    numgroup = 1
    num_defgroups = len(confopts['usersetup']['default_groups'])
    for gr in confopts['usersetup']['resource_groups']:
        group_ldap = conn.search(f"cn={gr},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
        if not group_ldap:
            ldap_gid = confopts['usersetup']['gid_ops_offset'] + numgroup + num_defgroups
            ldap_project = bonsai.LDAPEntry(f"cn={gr},ou=Group,{confopts['ldap']['basedn']}")
            ldap_project['cn'] = [gr]
            ldap_project['objectClass'] = ['top', 'posixGroup']
            ldap_project['gidNumber'] = [ldap_gid]
            conn.add(ldap_project)
            logger.info(f"Created resource group {gr} with gid={ldap_gid}")
            numgroup += 1


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Create, read and update ou=People and ou=Group entries in LDAP""")
    args = parser.parse_args()

    confopts = parse_config()

    try:
        client = bonsai.LDAPClient(confopts['ldap']['server'])
        client.set_credentials(
            "SIMPLE",
            user=confopts['ldap']['user'],
            password=confopts['ldap']['password']
        )
        conn = client.connect()

        create_default_groups(confopts, conn, logger)
        create_resource_groups(confopts, conn, logger)

    except bonsai.errors.AuthenticationError as exc:
        logger.error(exc)
        raise SystemExit(1)

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users = session.query(User).all()

    for user in users:
        if not user.ldap_username:
            continue
        ldap_user = conn.search(f"cn={user.ldap_username},ou=People,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
        if not ldap_user:
            new_user_ldap_add(confopts, conn, user)
        else:
            user_ldap_update(confopts, session, logger, user, ldap_user)

    projects = session.query(Project).all()
    for project in projects:
        ldap_project = conn.search(f"cn={project.identifier},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
        if not ldap_project:
            new_group_ldap_add(confopts, conn, project)
        else:
            group_ldap_update(confopts, session, logger, project, ldap_project)

    # handle default groups associations
    update_default_groups(confopts, conn, logger, users, "hpc-users")
    update_default_groups(confopts, conn, logger, users, "hpc", onlyops=True)

    # handle resource groups associations
    update_resource_groups(confopts, conn, logger, users, "hpc-bigmem")
    update_resource_groups(confopts, conn, logger, users, "hpc-gpu")

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
