from typing import Any, Union


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
