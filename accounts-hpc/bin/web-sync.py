#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base  # type: ignore
from accounts_hpc.http import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError

import asyncio


from sqlalchemy import create_engine


def contains_exception(list):
    for a in list:
        if isinstance(a, Exception):
            return (True, a)

    return (False, None)


async def run(logger, confopts):
    session = SessionWithRetry(logger, confopts, handle_session_close=True)

    coros = [
        session.http_get(
            confopts['hzsiapi']['users'],
        ),
        session.http_get(
            confopts['hzsiapi']['projects'],
        ),
        session.http_get(
            confopts['hzsiapi']['sshkeys'],
        ),
        session.http_get(
            confopts['hzsiapi']['userproject'],
        )
    ]
    fetched_data = await asyncio.gather(*coros, return_exceptions=True)
    print(fetched_data)
    await session.close()

    exc_raised, exc = contains_exception(fetched_data)
    if exc_raised:
        logger.error('Data fetch did not succeed')
        raise SystemExit(1)


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    # engine = create_engine("sqlite:///{}".format(confopts['db']['path']), echo=True)

    loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run(logger, confopts))

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
