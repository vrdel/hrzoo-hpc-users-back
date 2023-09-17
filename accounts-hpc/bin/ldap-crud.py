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


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    try:
        client = bonsai.LDAPClient(confopts['ldap']['server'])
        client.set_credentials(
            "SIMPLE",
            user=confopts['ldap']['user'],
            password=confopts['ldap']['password']
        )
        conn = client.connect()
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
            ldap_user = bonsai.LDAPEntry(f"cn={user.ldap_username},ou=People,{confopts['ldap']['basedn']}")
            ldap_user['objectClass'] = ['top', 'account', 'posixAccount', 'shadowAccount']
            ldap_user['cn'] = [user.ldap_username]
            ldap_user['uid'] = [user.ldap_username]
            ldap_user['uidNumber'] = [user.ldap_uid]
            ldap_user['gidNumber'] = [user.ldap_gid]
            ldap_user['homeDirectory'] = [f"/lustre/home/{user.ldap_username}"]
            ldap_user['loginShell'] = ['/bin/bash']
            ldap_user['gecos'] = [f"{user.first_name} {user.last_name}"]
            ldap_user['userPassword'] = ['']
            conn.add(ldap_user)

        else:
            # check if there are differencies between user's project just
            # synced from API and ones already registered in cache
            projects_diff = set()
            projects_db = [pr.identifier for pr in user.project]
            projects_diff = set(user.projects_api).difference(set(projects_db))
            # add user to project
            if projects_diff:
                for project in projects_diff:
                    target_project = session.query(Project).filter(Project.identifier == project).one()
                    target_project.user.add(user)
                    session.add(target_project)
                    logger.info(f"User {user.username} added to project {project}")
            # remove user from project
            projects_diff = set(projects_db).difference(set(user.projects_api))
            if projects_diff:
                for project in projects_diff:
                    target_project = session.query(Project).filter(Project.identifier == project).one()
                    target_project.user.remove(user)
                    session.add(target_project)
                    logger.info(f"User {user.person_uniqueid} removed from project {project}")
            if projects_diff:
                ldap_user[0].change_attribute('gidNumber', bonsai.LDAPModOp.REPLACE, confopts['usersetup']['gid_offset'] + user.project[-1].prjid_api)
                ldap_user[0].modify()

    projects = session.query(Project).all()
    for project in projects:
        ldap_project = conn.search(f"cn={project.identifier},ou=Group,{confopts['ldap']['basedn']}", bonsai.LDAPSearchScope.SUBTREE)
        if not ldap_project:
            ldap_project = bonsai.LDAPEntry(f"cn={project.identifier},ou=Group,{confopts['ldap']['basedn']}")
            ldap_project['cn'] = [project.identifier]
            ldap_project['objectClass'] = ['top', 'posixGroup']
            ldap_project['gidNumber'] = [project.ldap_gid]
            ldap_project['memberUid'] = [user.ldap_username for user in project.user]
            conn.add(ldap_project)
        else:
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
                project_new_members = [user.person_uniqueid for user in project.user]
                if len(project_new_members) == 0:
                    del ldap_project[0]['memberUid']
                else:
                    ldap_project[0].change_attribute('memberUid', bonsai.LDAPModOp.REPLACE, project_new_members)
                ldap_project[0].modify()
                logger.info(f"Updating memberUid for LDAP cn={project.identifier},ou=Group")

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
