#!/usr/bin/env python

import asyncio
import sys

from accounts_hpc.tasks.apisync import ApiSync


class FakeArgs(object):
    def __init__(self):
        self.initset = False


class AhDaemon(object):
    def __init__(self):
        self.fakeargs = FakeArgs()

    async def run(self):
        await ApiSync('ah-daemon', self.fakeargs).run()
        import ipdb; ipdb.set_trace()


def main():
    ahd = AhDaemon()
    loop = asyncio.new_event_loop()

    try:
        loop.run_until_complete(ahd.run())

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

