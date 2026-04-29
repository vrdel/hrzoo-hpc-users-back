#!/usr/bin/env python

import sys
import asyncio
import argparse

from accounts_hpc.tasks.emailsend import SendEmail
from accounts_hpc.shared import init as init_shared


async def main():
    parser = argparse.ArgumentParser(description="""Send email for newly opened user and added SSH keys""")
    args = parser.parse_args()

    init_shared(sys.argv[0])

    await SendEmail(args).run()


if __name__ == '__main__':
    asyncio.run(main())
