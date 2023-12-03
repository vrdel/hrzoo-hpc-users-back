#!/usr/bin/env python

import sys

from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.emailsend import EmailSend  # type: ignore

import argparse
import signal


def main():
    parser = argparse.ArgumentParser(description="""Send email for newly opened user and added SSH keys""")
    args = parser.parse_args()

    shared = Shared(sys.argv[0])
    confopts = shared.confopts
    logger = shared.log.get()
    dbsession = shared.dbsession

    users_opened = set()
    users = dbsession.query(User).filter(User.mail_is_opensend == False).all()
    for user in users:
        email = EmailSend(logger, confopts, user.person_mail,
                          username=user.ldap_username)
        if email.send():
            user.mail_is_opensend = True
            users_opened.add(user.ldap_username)
            logger.info(f"Send email for created account {user.ldap_username} @ {user.person_mail}")

    users = dbsession.query(User).filter(User.mail_is_sshkeyadded == False).all()
    for user in users:
        # skip for new users that are just created
        # as they will receive previous email
        if user.ldap_username in users_opened:
            user.mail_is_sshkeyadded = True
            user.mail_name_sshkey = list()
            continue
        nmail = 0
        for sshkeyname in user.mail_name_sshkey:
            email = EmailSend(logger, confopts, user.person_mail,
                              sshkeyname=sshkeyname)
            if email.send():
                nmail += 1
                logger.info(f"Send email for added key {sshkeyname} of {user.ldap_username}")
        if nmail == len(user.mail_name_sshkey):
            user.mail_is_sshkeyadded = True
            user.mail_name_sshkey = list()

    dbsession.commit()
    dbsession.close()


if __name__ == '__main__':
    main()
