from typing import Any, Union
from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.db import User  # type: ignore


def latest_project(username):
    shared = Shared('utils.latest_project()')
    dbsession = shared.dbsession
    user = dbsession.query(User).filter(User.ldap_username == username).one()
    last_project = user.project[-1]
    return last_project


def chunk_list(self, lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def get_ssh_key_fingerprint(ssh_key):
    # How to get fingerprint from ssh key:
    # http://stackoverflow.com/a/6682934/175349
    # http://www.ietf.org/rfc/rfc4716.txt Section 4.
    import base64
    import hashlib

    key_body = base64.b64decode(ssh_key.strip().split()[1].encode('ascii'))
    fp_plain = hashlib.md5(key_body).hexdigest()  # noqa: S303
    return ':'.join(a + b for a, b in zip(fp_plain[::2], fp_plain[1::2]))


def only_alnum(s: str) -> str:
    if '-' in s:
        s = s.split('-')
        s = ''.join(s)
    if ' ' in s:
        s = s.split(' ')
        s = ''.join(s)

    return s


def contains_exception(list: list[Exception]) -> tuple[bool, Any]:
    for a in list:
        if isinstance(a, Exception):
            return (True, a)

    return (False, None)


def all_none(list: list) -> bool:
    if all(list):
        return False
    else:
        return True
