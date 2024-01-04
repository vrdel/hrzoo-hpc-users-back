import asyncio
import json
import sys
import timeit

from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.httpconn import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError
from accounts_hpc.utils import only_alnum, all_none, contains_exception
from accounts_hpc.shared import Shared  # type: ignore

from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from unidecode import unidecode

import argparse


def replace_projectsapi_fields(projectsfields, userproject):
    for field in projectsfields:
        which = field.get('field').split('.')[1]
        if field['from'] in userproject['project'][which]:
            userproject['project'][which] = userproject['project'][which].replace(field['from'], field['to'])


class ApiSync(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args

    def sshkeys_del(self, projects_users, sshkeys):
        interested_users = [up['user']['id'] for up in projects_users]
        hzsi_api_user_keys = dict()

        for key in sshkeys:
            if key['user']['id'] not in interested_users:
                continue

            if key['user']['username'] not in hzsi_api_user_keys:
                hzsi_api_user_keys[key['user']['username']] = list()

            hzsi_api_user_keys[key['user']['username']].append(key['fingerprint'])

        users = self.dbsession.query(User).filter(User.type_create == 'api').all()

        for us in users:
            if us.person_uniqueid not in hzsi_api_user_keys.keys():
                hzsi_api_user_keys[us.person_uniqueid] = list()

            if len(us.sshkey) > len(hzsi_api_user_keys[us.person_uniqueid]):
                rem_keys = list(
                    set(us.sshkeys_api)
                    .difference(hzsi_api_user_keys[us.person_uniqueid]))
                us.sshkeys_api = hzsi_api_user_keys[us.person_uniqueid]
                if self.args.initset:
                    rem_keys_db = self.dbsession.query(SshKey).filter(
                        and_(
                            SshKey.fingerprint.in_(rem_keys),
                            SshKey.user_id == us.id
                        ))
                    for key in rem_keys_db:
                        us.sshkey.remove(key)
                        self.dbsession.delete(key)

    def sshkeys_add(self, projects_users, sshkeys):
        interested_users = set([up['user']['id'] for up in projects_users])

        for key in sshkeys:
            if key['user']['id'] not in interested_users:
                continue

            try:
                us = self.dbsession.query(User).filter(User.person_uniqueid == key['user']['username']).one()

            except MultipleResultsFound as exc:
                self.logger.error(exc)
                self.logger.error('{} - Troublesome DB entry: {}'.format(self.sshkeys_add.__name__, repr(key)))
                raise SystemExit(1)

            if key['fingerprint'] not in us.sshkeys_api:
                us.sshkeys_api.append(key['fingerprint'])

            # same key unfortunately can be added from two
            # different users, that's why we require uid_api as well
            try:
                dbkey = self.dbsession.query(SshKey).filter(
                    and_(
                        SshKey.fingerprint == key['fingerprint'],
                        SshKey.uid_api == key['user']['id']
                    )).one()
            except NoResultFound:
                dbkey = SshKey(name=key['name'],
                               fingerprint=key['fingerprint'],
                               public_key=key['public_key'],
                               uid_api=key['user']['id'])

            if dbkey not in us.sshkey and self.args.initset:
                us.sshkey.append(dbkey)
                self.dbsession.add(us)
            else:
                self.dbsession.add(dbkey)
                self.dbsession.add(us)

    def users_projects_del(self, projects_users):
        hzsi_api_user_projects = dict()

        for uspr in projects_users:
            if uspr['user']['username'] not in hzsi_api_user_projects:
                hzsi_api_user_projects.update({
                    uspr['user']['username']: list()
                })
            if uspr['project']['identifier'] not in hzsi_api_user_projects[uspr['user']['username']]:
                hzsi_api_user_projects[uspr['user']['username']].\
                    append(uspr['project']['identifier'])

        visited_users = set()
        for uspr in projects_users:
            if uspr['user']['id'] in visited_users:
                continue

            try:
                us = self.dbsession.query(User).filter(User.person_oib == uspr['user']['person_oib']).one()

            except MultipleResultsFound as exc:
                self.logger.error(exc)
                self.logger.error('{} - Troublesome DB entry: {}'.format(self.users_projects_del.__name__, repr(uspr)))
                raise SystemExit(1)

            if len(us.projects_api) > len(hzsi_api_user_projects[uspr['user']['username']]):
                prjs_diff = list(
                    set(us.projects_api)
                    .difference(
                        set(hzsi_api_user_projects[uspr['user']['username']])
                    ))
                prjs_diff_db = self.dbsession.query(Project).filter(Project.identifier.in_(prjs_diff)).all()

                us.projects_api = hzsi_api_user_projects[uspr['user']['username']]

                if self.args.initset:
                    for pr in prjs_diff_db:
                        us.project.remove(pr)

                if self.confopts['email']['project_email']:
                    for pr in prjs_diff_db:
                        del us.mail_project_is_opensend[pr.identifier]
                        del us.mail_project_is_sshkeyadded[pr.identifier]

            visited_users.update([uspr['user']['id']])

    def users_projects_add(self, projects_users):
        for uspr in projects_users:
            try:
                pr = self.dbsession.query(Project).filter(
                    Project.identifier == uspr['project']['identifier']).one()
                # update staff_resources_type with latest value
                pr.staff_resources_type_api = uspr['project']['staff_resources_type']
            except NoResultFound:
                pr = Project(name=uspr['project']['name'],
                             identifier=uspr['project']['identifier'],
                             prjid_api=uspr['project']['id'],
                             type=uspr['project']['project_type'],
                             is_dir_created=True if self.args.initset else False,
                             is_pbsfairshare_added=True if self.args.initset else False,
                             staff_resources_type_api=uspr['project']['staff_resources_type'],
                             ldap_gid=0)

            try:
                # use person_oib as unique identifier of user
                us = self.dbsession.query(User).filter(
                    User.person_oib == uspr['user']['person_oib']).one()
                projects_api = us.projects_api
                # always up-to-date projects_api field with project associations
                if not projects_api:
                    projects_api = list()
                if uspr['project']['identifier'] not in projects_api:
                    projects_api.append(uspr['project']['identifier'])
                us.projects_api = projects_api
                if self.confopts['email']['project_email'] == True:
                    mail_project_is_opensend = us.mail_project_is_opensend
                    if uspr['project']['identifier'] not in mail_project_is_opensend.keys():
                        mail_project_is_opensend.update(
                            {
                                uspr['project']['identifier']: True if self.args.initset else False
                            }
                        )
                    mail_project_is_sshkeyadded = us.mail_project_is_sshkeyadded
                    if uspr['project']['identifier'] not in mail_project_is_sshkeyadded.keys():
                        mail_project_is_sshkeyadded.update(
                            {
                                uspr['project']['identifier']: True if self.args.initset else False
                            }
                        )
                # always up to date fields
                us.person_mail = uspr['user']['person_mail']
                us.person_uniqueid = uspr['user']['username']
                us.is_active = uspr['user']['status']
                us.uid_api = uspr['user']['id']

            except NoResultFound:
                if self.confopts['email']['project_email'] == True:
                    us = User(first_name=only_alnum(unidecode(uspr['user']['first_name'])),
                              is_active=uspr['user']['status'],
                              is_opened=True if self.args.initset else False,
                              is_dir_created=True if self.args.initset else False,
                              is_deactivated=True if self.args.initset else False,
                              mail_is_opensend=False,
                              mail_is_subscribed=False,
                              mail_is_sshkeyadded=False,
                              mail_project_is_opensend={uspr['project']['identifier']: True if self.args.initset else False},
                              mail_project_is_sshkeyadded={uspr['project']['identifier']: True if self.args.initset else False},
                              mail_name_sshkey=list(),
                              is_staff=uspr['user']['is_staff'],
                              last_name=only_alnum(unidecode(uspr['user']['last_name'])),
                              person_mail=uspr['user']['person_mail'],
                              projects_api=[uspr['project']['identifier']],
                              sshkeys_api=list(),
                              person_uniqueid=uspr['user']['username'],
                              person_oib=uspr['user']['person_oib'],
                              uid_api=uspr['user']['id'],
                              ldap_uid=0,
                              ldap_gid=0,
                              ldap_username='',
                              type_create='api')
                else:
                    us = User(first_name=only_alnum(unidecode(uspr['user']['first_name'])),
                              is_active=uspr['user']['status'],
                              is_opened=True if self.args.initset else False,
                              is_dir_created=True if self.args.initset else False,
                              is_deactivated=True if self.args.initset else False,
                              mail_is_opensend=True if self.args.initset else False,
                              mail_is_subscribed=True if self.args.initset else False,
                              mail_is_sshkeyadded=True if self.args.initset else False,
                              mail_project_is_opensend=dict(),
                              mail_project_is_sshkeyadded=dict(),
                              mail_name_sshkey=list(),
                              is_staff=uspr['user']['is_staff'],
                              last_name=only_alnum(unidecode(uspr['user']['last_name'])),
                              person_mail=uspr['user']['person_mail'],
                              projects_api=[uspr['project']['identifier']],
                              sshkeys_api=list(),
                              person_uniqueid=uspr['user']['username'],
                              person_oib=uspr['user']['person_oib'],
                              uid_api=uspr['user']['id'],
                              ldap_uid=0,
                              ldap_gid=0,
                              ldap_username='',
                              type_create='api')

            except MultipleResultsFound as exc:
                self.logger.error(exc)
                self.logger.error('{} - Troublesome DB entry: {}'.format(self.users_projects_add.__name__, repr(uspr)))

            # sync (user, project) relations to cache
            # only if --init-set
            if us not in pr.user and self.args.initset:
                pr.user.append(us)
                self.dbsession.add(pr)
            elif not self.args.initset:
                self.dbsession.add(pr)
                self.dbsession.add(us)

    def check_users_without_projects(self, apiusers):
        users_db = self.dbsession.query(User)
        uids_db = [user.uid_api for user in users_db.all()
                   if not user.is_deactivated and not user.type_create == 'manual']
        uids_not_onapi = set()
        for uid in uids_db:
            if uid not in apiusers:
                uids_not_onapi.add(uid)

        if uids_not_onapi:
            user_without_projects = users_db.filter(User.uid_api.in_(uids_not_onapi))
            self.logger.info("Found users in local DB without any registered project on HRZOO-SIGNUP-API: {}"
                             .format(', '.join([user.ldap_username for user in user_without_projects])))
            self.logger.info("Nullifying user.projects_api and setting user.is_active=0,ldap_gid=0 for such")
            self.dbsession.execute(
                update(User),
                [{"id": user.id, "projects_api": [], "ldap_gid": 0, "is_active": 0} for user in user_without_projects]
            )

    async def fetch_data(self):
        token = self.confopts['hzsiapi']['token']
        session = SessionWithRetry(self.logger, self.confopts, token=token, handle_session_close=True)

        coros = [
            session.http_get(
                self.confopts['hzsiapi']['sshkeys'],
            ),
            session.http_get(
                self.confopts['hzsiapi']['userproject'],
            )
        ]

        start = timeit.default_timer()
        fetched_data = await asyncio.gather(*coros, return_exceptions=True)
        end = timeit.default_timer()

        await session.close()

        if all_none(fetched_data):
            self.logger.error("Error while trying to fetch data, exiting")
            raise SystemExit(1)

        exc_raised, exc = contains_exception(fetched_data)
        if exc_raised:
            raise exc

        else:
            self.logger.info(f"Fetched data in {format(end - start, '.2f')} seconds")
            sshkeys, userproject = fetched_data

            sshkeys = json.loads(sshkeys)
            userproject = json.loads(userproject)
            return sshkeys, userproject

    async def run(self):
        try:
            sshkeys, userproject = await self.fetch_data()

        except SyncHttpError:
            self.logger.error('Data fetch did not succeed')
            raise SystemExit(1)

        if self.confopts['hzsiapi']['replacestring_map']:
            with open(self.confopts['hzsiapi']['replacestring_map'], mode='r') as fp:
                fieldsreplace = json.loads(fp.read())
            projectsfields = [field for field in fieldsreplace if field.get('field').startswith('project.')]

        stats = dict({'users': set(), 'fullusers': set(), 'fullprojects': set(), 'projects': set(), 'keys': set()})
        projects_users = list()
        visited_users, interested_users_api = set(), set()
        # build of projects_users association list
        # user has at least one key added - enough at this point
        # filter project according to interested state and approved
        # resources
        for key in sshkeys:
            stats['keys'].add('{}{}'.format(key['fingerprint'], key['user']['id']))
            stats['fullusers'].add(key['user']['id'])
            for up in userproject:
                if (up['project']['state']
                        not in self.confopts['hzsiapi']['project_state']):
                    continue
                stats['fullprojects'].add(up['project']['id'])
                if projectsfields:
                    replace_projectsapi_fields(projectsfields, up)
                rt_found = False
                for rt in up['project']['staff_resources_type']:
                    if rt in self.confopts['hzsiapi']['project_resources']:
                        rt_found = True
                if not rt_found:
                    continue
                if up['user']['id'] == key['user']['id']:
                    projects_users.append(up)
                    stats['users'].add(key['user']['id'])
                stats['projects'].add(up['project']['id'])
                interested_users_api.add(up['user']['id'])
            visited_users.update([key['user']['id']])

        self.logger.info(f"Interested in ({','.join(self.confopts['hzsiapi']['project_resources'])}) projects={len(stats['projects'])}/{len(stats['fullprojects'])}  users={len(stats['users'])}/{len(stats['fullusers'])} keys={len(stats['keys'])}")

        self.check_users_without_projects(interested_users_api)
        self.users_projects_add(projects_users)
        self.users_projects_del(projects_users)
        self.sshkeys_add(projects_users, sshkeys)
        self.sshkeys_del(projects_users, sshkeys)

        self.logger.info(f"APISYNC {id(self.logger)} {self.logger}")

        self.dbsession.commit()
        self.dbsession.close()
