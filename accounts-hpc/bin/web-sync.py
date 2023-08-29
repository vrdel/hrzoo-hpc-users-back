#!/usr/bin/env python

import sys

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base  # type: ignore
from accounts_hpc.http import SessionWithRetry
from accounts_hpc.exceptions import SyncHttpError

import asyncio


from sqlalchemy import create_engine


async def fetch_data(logger, confopts, feed, token):
    session = SessionWithRetry(logger, confopts, token, handle_session_close=True)

    try:
        res = await session.http_get(feed)

        return res

    except SyncHttpError as exc:
        await session.close()
        raise exc


async def run(logger, confopts):
    res = await fetch_data(
        logger, confopts,
        confopts['hzsiapi']['users'],
        confopts['authentication']['token']
    )
    logger.info(res)


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    # engine = create_engine("sqlite:///{}".format(confopts['db']['path']), echo=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run(logger, confopts))


if __name__ == '__main__':
    main()
