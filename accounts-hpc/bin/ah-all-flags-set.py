#!/usr/bin/env python

import sys

from accounts_hpc.db import Project, User  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

from sqlalchemy import select

import argparse
import asyncio


async def main():
    shared = Shared(sys.argv[0])
    dbsession = shared.dbsession[sys.argv[0]]

    parser = argparse.ArgumentParser(description="""Helper tool to set all flags to true to not send emails""")
    args = parser.parse_args()

    try:
        stmt = select(Project)
        projects = await dbsession.execute(stmt)
        projects = projects.scalars().all()

        stmt = select(User)
        users = await dbsession.execute(stmt)
        users = users.scalars().all()

        for project in projects:
            if not project.is_dir_created:
                project.is_dir_created = True
            if not project.is_pbsfairshare_added:
                project.is_pbsfairshare_added = True

        if shared.confopts['ldap']['mode'] == 'flat':
            for user in users:
                if not user.is_opened:
                    user.is_opened = True
                if not user.is_dir_created:
                    user.is_dir_created = True
                if not user.mail_is_opensend:
                    user.mail_is_opensend = True
                if not user.mail_is_sshkeyadded:
                    user.mail_is_sshkeyadded = True
                    user.mail_name_sshkey = []
                if not user.mail_is_sshkeyremoved:
                    user.mail_is_sshkeyremoved = True
                    user.mail_name_sshkey = []
        else:
            for user in users:
                if not user.is_opened:
                    user.is_opened = True
                if not user.is_dir_created:
                    user.is_dir_created = True
                if user.mail_project_is_opensend:
                    for project in user.mail_project_is_opensend.keys():
                        user.mail_project_is_opensend[project] = True
                if user.mail_project_is_sshkeyadded:
                    for project in user.mail_project_is_sshkeyadded.keys():
                        user.mail_project_is_sshkeyadded[project] = True
                if user.mail_project_is_sshkeyremoved:
                    for project in user.mail_project_is_sshkeyremoved.keys():
                        user.mail_project_is_sshkeyremoved[project] = True
                user.mail_name_sshkey = []

        await dbsession.commit()
        await dbsession.close()

    except Exception as exc:
        print(f"Error setting flags: {repr(exc)}")


if __name__ == '__main__':
    asyncio.run(main())
