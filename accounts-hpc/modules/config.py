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