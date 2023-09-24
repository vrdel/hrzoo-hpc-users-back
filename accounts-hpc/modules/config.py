import configparser
import os
import sys


conf = f"{os.environ['VIRTUAL_ENV']}/etc/accounts-hpc/accounts-hpc.conf"


def parse_config(logger=None):
    confopts = dict()

    try:
        config = configparser.ConfigParser()
        if config.read(conf):
            for section in config.sections():
                if section.startswith('ldap'):
                    confopts['ldap'] = ({'server': config.get(section, 'server')})
                    confopts['ldap'].update({'user': config.get(section, 'user')})
                    confopts['ldap'].update({'password': config.get(section, 'password')})
                    confopts['ldap'].update({'basedn': config.get(section, 'basedn')})

                if section.startswith('db'):
                    confopts['db'] = ({'path': config.get(section, 'path')})

                if section.startswith('hzsiapi'):
                    confopts['hzsiapi'] = ({'sshkeys': config.get(section, 'sshkeys')})
                    confopts['hzsiapi'].update({'userproject': config.get(section, 'userproject')})
                    confopts['hzsiapi'].update({'project_state': config.get(section, 'project_state')})
                    confopts['hzsiapi'].update({'project_resources': config.get(section, 'project_resources')})
                    confopts['hzsiapi'].update({'replacestring_map': config.get(section, 'replacestring_map')})
                    confopts['hzsiapi']['project_resources'] = \
                            [rt.strip() for rt in confopts['hzsiapi']['project_resources'].split(',')]

                if section.startswith('connection'):
                    confopts['connection'] = ({'timeout': config.get(section, 'timeout')})
                    confopts['connection'].update({'retry': config.get(section, 'retry')})
                    confopts['connection'].update({'sleepretry': config.get(section, 'sleepretry')})

                if section.startswith('authentication'):
                    confopts['authentication'] = ({'verifyservercert': config.get(section, 'verifyservercert')})
                    confopts['authentication'].update({'cafile': config.get(section, 'cafile')})
                    confopts['authentication'].update({'token': config.get(section, 'token')})

                if section.startswith('email'):
                    confopts['email'] = ({'from': config.get(section, 'from')})
                    confopts['email'].update({'bcc': config.get(section, 'bcc')})
                    confopts['email'].update({'smtp': config.get(section, 'smtp')})
                    confopts['email'].update({'template_newuser': config.get(section, 'template_newuser')})
                    confopts['email'].update({'template_newkey': config.get(section, 'template_newkey')})
                    confopts['email'].update({'port': config.getint(section, 'port')})
                    confopts['email'].update({'user': config.get(section, 'user')})
                    confopts['email'].update({'password': config.get(section, 'password')})
                    confopts['email'].update({'tls': config.getboolean(section, 'tls')})
                    confopts['email'].update({'ssl': config.getboolean(section, 'ssl')})
                    confopts['email'].update({'timeout': config.getint(section, 'timeout')})

                if section.startswith('mailinglist'):
                    confopts['mailinglist'] = ({'name': config.get(section, 'name')})
                    confopts['mailinglist'].update({'server': config.get(section, 'server')})
                    confopts['mailinglist'].update({'credentials': config.get(section, 'credentials')})
                    confopts['mailinglist'].update({'timeout': config.getint(section, 'timeout')})

                if section.startswith('usersetup'):
                    confopts['usersetup'] = ({'uid_offset': config.getint(section, 'uid_offset')})
                    confopts['usersetup'].update({'gid_offset': config.getint(section, 'gid_offset')})
                    confopts['usersetup'].update({'uid_ops_offset': config.getint(section, 'uid_ops_offset')})
                    confopts['usersetup'].update({'gid_ops_offset': config.getint(section, 'gid_ops_offset')})
                    confopts['usersetup'].update({'default_groups': config.get(section, 'default_groups')})
                    confopts['usersetup']['default_groups'] = \
                            [gr.strip() for gr in confopts['usersetup']['default_groups'].split(',')]
                    confopts['usersetup'].update({'resource_groups': config.get(section, 'resource_groups')})
                    if confopts['usersetup']['resource_groups']:
                        confopts['usersetup']['resource_groups'] = \
                                [gr.strip() for gr in confopts['usersetup']['resource_groups'].split(',')]
                    confopts['usersetup'].update({'homeprefix': config.get(section, 'homeprefix')})
                    confopts['usersetup'].update({'usermap': config.get(section, 'usermap')})
                    confopts['usersetup'].update({'userdirs_in': config.get(section, 'userdirs_in')})
                    if confopts['usersetup']['userdirs_in']:
                        confopts['usersetup']['userdirs_in'] = \
                                [dir.strip() for dir in confopts['usersetup']['userdirs_in'].split(',')]
                    confopts['usersetup'].update({'groupdirs_in': config.get(section, 'groupdirs_in')})
                    if confopts['usersetup']['groupdirs_in']:
                        confopts['usersetup']['groupdirs_in'] = \
                                [dir.strip() for dir in confopts['usersetup']['groupdirs_in'].split(',')]
                    confopts['usersetup'].update({'pbsfairshare_path': config.get(section, 'pbsfairshare_path')})
                    confopts['usersetup'].update({'pbsprocname': config.get(section, 'pbsprocname')})

            if 'DEFAULT' in config:
                confopts['DEFAULT'] = ({'VENV': config.get('DEFAULT', 'VENV')})

            return confopts

        else:
            if logger:
                logger.error('Missing %s' % conf)
            else:
                sys.stderr.write('Missing %s\n' % conf)
            raise SystemExit(1)

    except (configparser.NoOptionError, configparser.NoSectionError) as e:
        if logger:
            logger.error(e)
        else:
            sys.stderr.write('%s\n' % e)
        raise SystemExit(1)

    except (configparser.MissingSectionHeaderError, configparser.ParsingError, SystemExit) as e:
        if getattr(e, 'filename', False):
            if logger:
                logger.error(e.filename + ' is not a valid configuration file')
                logger.error(' '.join(e.args))
            else:
                sys.stderr.write(e.filename + ' is not a valid configuration file\n')
                sys.stderr.write(' '.join(e.args) + '\n')
        raise SystemExit(1)

    return confopts
