# -*- coding: utf-8 -*-

from email.message import EmailMessage
from email.header import Header
from email.headerregistry import Address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from accounts_hpc.utils import latest_project

import datetime
import re
import aiosmtplib
import aiofiles
import socket
import ssl


class EmailSend(object):
    def __init__(self, logger, confopts, emailto, username=None, sshkeyname=None, project=None):
        self.username = username
        self.sshkeyname = sshkeyname
        self.project = project
        if username:
            if confopts['email']['project_email']:
                self.template = confopts['email']['template_newuser']
                self.template = self.template.replace('.', f'_{self.project}.')
            else:
                self.template = confopts['email']['template_newuser']
        else:
            if confopts['email']['project_email']:
                self.template = confopts['email']['template_newkey']
                self.template = self.template.replace('.', f'_{self.project}.')
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

    async def _construct_email(self):
        text = None

        try:
            async with aiofiles.open(self.template, encoding='utf-8') as fp:
                text = await fp.readlines()
                self.subject = text[0].strip()
        except FileNotFoundError as exc:
            self.logger.error(f'{exc.filename} - {repr(exc)}')
            raise SystemExit(1)

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

    async def send(self):
        email_text = await self._construct_email()

        for part in [self.emailfrom, self.emailto, self.subject]:
            if not part:
                self.logger.error('To, From or Subject missing')
                return False

        if not email_text:
            self.logger.error('Could not construct an email')

        else:
            try:
                if self.port == 25:
                    s = aiosmtplib.SMTP(hostname=self.smtpserver, port=self.port, timeout=self.timeout)
                else:
                    s = aiosmtplib.SMTP(hostname=self.smtpserver, port=self.port, timeout=self.timeout)
                    context = ssl.create_default_context()
                    await s.starttls(tls_context=context)
                    await s.login(self.user, self.password)
                await s.connect()
                await s.sendmail(self.emailfrom, [self.emailbcc, self.emailto], email_text)
                await s.quit()

                return True

            except (socket.error, aiosmtplib.SMTPException) as e:
                self.logger.error(repr(e))
