#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import User # type: ignore
from accounts_hpc.emailsend import EmailSend # type: ignore

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import argparse
import signal


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    parser = argparse.ArgumentParser(description="""Send email for newly opened user and added SSH keys""")
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    users_opened = set()
    users = session.query(User).filter(User.mail_is_opensend == False).all()
    for user in users:
        email = EmailSend(logger, confopts, user.person_mail,
                          username=user.ldap_username)
        if email.send():
            user.mail_is_opensend = True
            users_opened.add(user.ldap_username)
            logger.info(f"Send email for created account {user.ldap_username} @ {user.person_mail}")

    users = session.query(User).filter(User.mail_is_sshkeyadded == False).all()
    for user in users:
        # skip for new users that are just created
        # as they will receive previous email
        if user.ldap_username in users_opened:
            user.mail_is_sshkeyadded = True
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

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
