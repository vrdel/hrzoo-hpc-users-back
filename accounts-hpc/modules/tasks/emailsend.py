from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore
from accounts_hpc.emailsend import EmailSend  # type: ignore

import sys


class SendEmail(object):
    def __init__(self, caller, args):
        shared = Shared(caller)
        self.confopts = shared.confopts
        self.logger = shared.log.get()
        self.dbsession = shared.dbsession
        self.args = args

    def run(self):
        users_opened = set()
        if self.confopts['email']['project_email']:
            users = self.dbsession.query(User).all()
            for user in users:
                for project in user.mail_project_is_opensend.keys():
                    if user.mail_project_is_opensend[project] == False:
                        email = EmailSend(self.logger, self.confopts, user.person_mail,
                                          username=user.ldap_username, project=project)
                        if email.send():
                            user.mail_project_is_opensend[project] = True
                            users_opened.add(user.ldap_username)
                            self.logger.info(f"Send email for created account {user.ldap_username} - {project} @ {user.person_mail}")

            for user in users:
                # skip for new users that are just created
                # as they will receive previous email
                if user.ldap_username in users_opened:
                    for project in user.mail_project_is_sshkeyadded.keys():
                        user.mail_project_is_sshkeyadded[project] = True
                        user.mail_name_sshkey = list()
                    continue
                nmail = 0
                for sshkeyname in user.mail_name_sshkey:
                    email = EmailSend(self.logger, self.confopts, user.person_mail,
                                      sshkeyname=sshkeyname)
                    if email.send():
                        nmail += 1
                        self.logger.info(f"Send email for added key {sshkeyname} of {user.ldap_username}")
                if nmail == len(user.mail_name_sshkey):
                    user.mail_is_sshkeyadded = True
                    user.mail_name_sshkey = list()
        else:
            users = self.dbsession.query(User).filter(User.mail_is_opensend == False).all()
            for user in users:
                email = EmailSend(self.logger, self.confopts, user.person_mail,
                                  username=user.ldap_username)
                if email.send():
                    user.mail_is_opensend = True
                    users_opened.add(user.ldap_username)
                    self.logger.info(f"Send email for created account {user.ldap_username} @ {user.person_mail}")

            users = self.dbsession.query(User).filter(User.mail_is_sshkeyadded == False).all()
            for user in users:
                # skip for new users that are just created
                # as they will receive previous email
                if user.ldap_username in users_opened:
                    user.mail_is_sshkeyadded = True
                    user.mail_name_sshkey = list()
                    continue
                nmail = 0
                for sshkeyname in user.mail_name_sshkey:
                    email = EmailSend(self.logger, self.confopts, user.person_mail,
                                      sshkeyname=sshkeyname)
                    if email.send():
                        nmail += 1
                        self.logger.info(f"Send email for added key {sshkeyname} of {user.ldap_username}")
                if nmail == len(user.mail_name_sshkey):
                    user.mail_is_sshkeyadded = True
                    user.mail_name_sshkey = list()

        self.dbsession.commit()
        self.dbsession.close()
