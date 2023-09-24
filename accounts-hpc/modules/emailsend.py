# -*- coding: utf-8 -*-

from email.message import EmailMessage
from email.header import Header
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import datetime
import re
import smtplib
import socket
import ssl


class EmailSend(object):
    def __init__(self, logger, confopts, emailto, username=None, sshkeyname=None):
        self.username = username
        self.sshkeyname = sshkeyname
        if username:
            self.template = confopts['email']['template_newuser']
        else:
            self.template = confopts['email']['template_newkey']
        self.smtpserver = confopts['email']['smtp']
        self.port = confopts['email']['port']
        self.tls = confopts['email']['tls']
        self.ssl = confopts['email']['ssl']
        self.user = confopts['email']['user']
        self.password = confopts['email']['password']
        self.timeout = confopts['email']['timeout']
        self.emailfrom = confopts['email']['from']
        # TODO: uncomment
        # self.emailbcc = "daniel.vrcic@gmail.com"
        self.emailbcc = confopts['email']['bcc']
        # TODO: uncomment
        # self.emailto = "daniel.vrcic@srce.hr"
        self.emailto = emailto
        self.logger = logger

    def _construct_email(self):
        text = None

        with open(self.template, encoding='utf-8') as fp:
            text = fp.readlines()
            self.subject = text[0].strip()

        # first line - subject
        # second line - separator
        # skip these
        del text[0:2]
        text = ''.join(text)

        if self.username:
            text = text.replace('__USERNAME__', str(self.username))
        if self.sshkeyname:
            text = text.replace('__KEYNAME__', str(self.sshkeyname))

        if text:
            email = EmailMessage()
            displayname = f"{self.emailfrom.split(' ')[0]} {self.emailfrom.split(' ')[1]}"
            addr_spec = self.emailfrom.split(' ')[-1].replace('>', '').replace('<', '')
            email['From'] = Address(display_name=displayname, addr_spec=addr_spec)
            email['To'] = self.emailto
            email['Subject'] = self.subject
            email['Bcc'] = self.emailbcc
            email.set_content(text)
            # multipart_email.attach(mailplain)
            return email.as_string()

        else:
            return None

    def send(self):
        email_text = self._construct_email()

        for part in [self.emailfrom, self.emailto, self.subject]:
            if not part:
                self.logger.error('To, From or Subject missing')
                return False

        if not email_text:
            self.logger.error('Could not construct an email')

        else:
            try:
                if self.port == 25:
                    s = smtplib.SMTP(self.smtpserver, self.port, timeout=self.timeout)
                else:
                    s = smtplib.SMTP(self.smtpserver, self.port, timeout=self.timeout)
                    context = ssl.create_default_context()
                    s.starttls(context=context)
                    s.login(self.user, self.password)
                s.ehlo()
                s.sendmail(self.emailfrom, [self.emailbcc, self.emailto], email_text)
                s.quit()

                return True

            except (socket.error, smtplib.SMTPException) as e:
                self.logger.error(repr(e))
