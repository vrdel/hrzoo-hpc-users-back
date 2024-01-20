#!/usr/bin/env python

import sys
import argparse
import asyncio

from accounts_hpc.db import Base  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore

from alembic.config import Config
from alembic import command

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker


async def main():
    parser = argparse.ArgumentParser(description='DB tool that help with initial create and evolution of database')
    parser.add_argument('--init', dest='init', action='store_true',
                        help='Create database with table structure')

    args = parser.parse_args()

    shared = Shared(sys.argv[0])
    confopts = shared.confopts

    engine = create_async_engine("sqlite+aiosqlite:///{}".format(confopts['db']['path']), echo=True)

    if args.init:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")


if __name__ == '__main__':
    asyncio.run(
        main()
    )
