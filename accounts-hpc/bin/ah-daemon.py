#!/usr/bin/env python

import asyncio
import sys

from accounts_hpc.tasks.apisync import ApiSync
from accounts_hpc.tasks.usermetadata import UserMetadata
from accounts_hpc.shared import Shared


CALLER_NAME="ah-daemon"


class FakeArgs(object):
    def __init__(self):
        self.initset = False


class AhDaemon(object):
    def __init__(self):
        self.fakeargs = FakeArgs()
        shared = Shared(CALLER_NAME)
        self.confopts = shared.confopts
        self.logger = shared.log.get()


    async def run(self):
        if 'apisync' in self.confopts['tasks']['call_list']:
            self.logger.info("Calling apisync task")
            await ApiSync(CALLER_NAME, self.fakeargs).run()

        if 'usermetadata' in self.confopts['tasks']['call_list']:
            self.logger.info("Calling usermetadata task")
            UserMetadata(CALLER_NAME, self.fakeargs).run()


def main():
    ahd = AhDaemon()
    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(ahd.run())

    except KeyboardInterrupt:
        pass

    finally:
        loop.close()


if __name__ == '__main__':
    main()

