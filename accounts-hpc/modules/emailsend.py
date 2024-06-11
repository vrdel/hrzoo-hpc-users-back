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
    def __init__(self, logger, confopts, emailto, username=None,
                 sshkeyname=None, project=None, activated=None,
                 deactivated=None, keyop=None, foreign=None):
        self.confopts = confopts
        self.username = username
        self.sshkeyname = sshkeyname
        self.activated = activated
        self.deactivated = deactivated
        self.project = project
        if activated:
            self.template = self._load_template('template_activateuser')
        elif deactivated:
            self.template = self._load_template('template_deactivateuser')
        elif username:
            self.template = self._load_template('template_newuser')
        else:
            if keyop == 'add':
                self.template = self._load_template('template_newkey')
            elif keyop == 'del':
                self.template = self._load_template('template_delkey')
        if foreign:
            self.template = self._load_en()
        self.smtpserver = confopts['email']['smtp']
        self.port = confopts['email']['port']
        self.tls = confopts['email']['tls']
        self.ssl = confopts['email']['ssl']
        self.user = confopts['email']['user']
        self.password = confopts['email']['password']
        self.timeout = confopts['email']['timeout']
        if foreign:
            self.emailfrom = confopts['email']['fromen']
        else:
            self.emailfrom = confopts['email']['from']
        self.emailbcc = confopts['email']['bcc']
        self.emailto = emailto
        self.logger = logger

    def _load_en(self):
        return self.template.replace('.txt', '-en.txt')

    def _load_template(self, template):
        template_file = None
        if self.confopts['ldap']['mode'] == 'project_organisation':
            template_file = self.confopts['email'][template]
            template_file = template_file.replace('.txt', f'_{self.project}.txt')
        else:
            template_file = self.confopts['email'][template]
        return template_file

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
                s = aiosmtplib.SMTP(hostname=self.smtpserver, port=self.port, timeout=self.timeout)

                if self.port != 25:
                    context = ssl.create_default_context()
                    await s.starttls(tls_context=context)
                if self.user and self.password:
                    await s.login(self.user, self.password)

                await s.connect()

                if ',' in self.emailbcc:
                    self.emailbcc = self.emailbcc.split(',')
                    self.emailbcc = [email.strip() for email in self.emailbcc]
                    await s.sendmail(self.emailfrom, self.emailbcc + [self.emailto], email_text)
                else:
                    await s.sendmail(self.emailfrom, [self.emailbcc, self.emailto], email_text)

                await s.quit()

                return True

            except (socket.error, aiosmtplib.SMTPException) as e:
                self.logger.error(repr(e))
