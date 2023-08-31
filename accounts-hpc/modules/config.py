import configparser
import os
import sys


conf = '/opt/hrzoo-accounts-hpc/etc/accounts-hpc/accounts-hpc.conf'


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

                if section.startswith('connection'):
                    confopts['connection'] = ({'timeout': config.get(section, 'timeout')})
                    confopts['connection'].update({'retry': config.get(section, 'retry')})
                    confopts['connection'].update({'sleepretry': config.get(section, 'sleepretry')})

                if section.startswith('authentication'):
                    confopts['authentication'] = ({'verifyservercert': config.get(section, 'verifyservercert')})
                    confopts['authentication'].update({'cafile': config.get(section, 'cafile')})
                    confopts['authentication'].update({'token': config.get(section, 'token')})

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
