#!/usr/bin/env python

import sys

from accounts_hpc.db import Project, User  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import argparse


def main():
    shared = Shared(sys.argv[0])
    confopts = shared.confopts

    parser = argparse.ArgumentParser(description="""Helper tool to set all flags to true""")
    args = parser.parse_args()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    projects = session.query(Project).all()
    for project in projects:
        if not project.is_dir_created:
            project.is_dir_created = True
        if not project.is_pbsfairshare_added:
            project.is_pbsfairshare_added = True

    users = session.query(User).all()
    for user in users:
        if not user.is_opened:
            user.is_opened = True
        if not user.is_dir_created:
            user.is_dir_created = True
        if not user.mail_is_opensend:
            user.mail_is_opensend = True
        if not user.mail_is_subscribed:
            user.mail_is_subscribed = True
        if not user.mail_is_sshkeyadded:
            user.mail_is_sshkeyadded = True
            user.mail_name_sshkey = []

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
