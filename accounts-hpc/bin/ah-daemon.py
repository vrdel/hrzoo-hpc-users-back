#!/usr/bin/env python

import asyncio
import sys

from accounts_hpc.tasks.apisync import ApiSync
from accounts_hpc.tasks.usermetadata import UserMetadata
from accounts_hpc.tasks.ldapupdate import LdapUpdate
from accounts_hpc.shared import Shared


CALLER_NAME = "ah-daemon"


class FakeArgs(object):
    def __init__(self):
        self.initset = False


class AhDaemon(object):
    def __init__(self):
        self.fakeargs = FakeArgs()
        shared = Shared(CALLER_NAME, daemon=True)
        self.confopts = shared.confopts
        self.logger = shared.log[CALLER_NAME].get()


    async def run(self):
        while True:
            calls_str = ', '.join(self.confopts['tasks']['call_list'])
            self.logger.info(f"* Scheduled tasks ({calls_str})...")
            if 'apisync' in self.confopts['tasks']['call_list']:
                self.logger.info("> Calling apisync task")
                await ApiSync(f'{CALLER_NAME}.apisync', self.fakeargs, daemon=True).run()

            if 'usermetadata' in self.confopts['tasks']['call_list']:
                self.logger.info("> Calling usermetadata task")
                UserMetadata(f'{CALLER_NAME}.usermetadata', self.fakeargs, daemon=True).run()

            if 'ldapupdate' in self.confopts['tasks']['call_list']:
                self.logger.info("> Calling ldapupdate task")
                LdapUpdate(f'{CALLER_NAME}.ldapupdate', self.fakeargs, daemon=True).run()

            await asyncio.sleep(float(self.confopts['tasks']['every_sec']))


def main():
    ahd = AhDaemon()
    try:
        asyncio.run(ahd.run())
    except KeyboardInterrupt:
        ahd.logger.info("* Stopping")

if __name__ == '__main__':
    main()

