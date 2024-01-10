#!/usr/bin/env python

import sys
import asyncio
import argparse

from accounts_hpc.tasks.emailsend import SendEmail


async def main():
    parser = argparse.ArgumentParser(description="""Send email for newly opened user and added SSH keys""")
    args = parser.parse_args()

    await SendEmail(sys.argv[0], args).run()


if __name__ == '__main__':
    asyncio.run(main())
