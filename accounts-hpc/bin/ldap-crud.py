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

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
