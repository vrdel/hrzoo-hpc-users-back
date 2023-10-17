#!/usr/bin/env python3

import requests
import socket
import json
import sys
import configparser

conf = '/home/galaxy/galaxy_root/venv/lib/python3.8/site-packages/social_core/backends/hzsi_srce.conf'

def parse_config():
    confopts = dict()

    try:
        config = configparser.ConfigParser()
        if config.read(conf):
            for section in config.sections():
                if section.startswith('general'):
                    confopts['fqdn'] = config.get(section, 'fqdn')
                    confopts['tag'] = config.get(section, 'tag')
                    confopts['apikey'] = config.get(section, 'apikey')

            return confopts

    except (configparser.NoOptionError, configparser.NoSectionError) as e:
        sys.stderr.write('%s\n' % e)
        raise SystemExit(1)

    except (configparser.MissingSectionHeaderError, configparser.ParsingError, SystemExit) as e:
        sys.stderr.write(e.filename + ' is not a valid configuration file\n')
        sys.stderr.write(' '.join(e.args) + '\n')
        raise SystemExit(1)


def hzsi_users():
    confopts = parse_config()
    headers = {
        'Authorization': f"Api-Key {confopts['apikey']}"
    }
    allowed_users = set()

    try:
        resp = requests.get(f"http://{confopts['fqdn']}/api/v1/usersprojects?tags={confopts['tag']}", headers=headers)

        if resp.status_code == 200:
            users_projects = json.loads(resp.content)
            for up in users_projects:
                allowed_users.add(up['user']['username'])

        return allowed_users

    except (requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout, socket.error,
            json.decoder.JSONDecodeError) as exc:
        raise SystemExit(1)


# def main():
    # interested_users = hzsi_users()
    # print(interested_users)

# if __name__ == '__main__':
    # main()
