#!/usr/bin/env python

import asyncio
import sys
import signal

from accounts_hpc.tasks.apisync import ApiSync
from accounts_hpc.tasks.usermetadata import UserMetadata
from accounts_hpc.tasks.ldapupdate import LdapUpdate
from accounts_hpc.shared import Shared


CALLER_NAME = "ah-taskd"


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
        try:
            task_apisync, task_usermetadata = None, None

            while True:
                calls_str = ', '.join(self.confopts['tasks']['call_list'])
                self.logger.info(f"* Scheduled tasks ({calls_str})...")
                if 'apisync' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling apisync task")
                    task_apisync = asyncio.create_task(
                        ApiSync(f'{CALLER_NAME}.apisync', self.fakeargs, daemon=True).run()
                    )
                    await task_apisync

                if 'usermetadata' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling usermetadata task")
                    task_usermetadata = asyncio.create_task(
                        UserMetadata(f'{CALLER_NAME}.usermetadata', self.fakeargs, daemon=True).run()
                    )
                    await task_usermetadata

                if 'ldapupdate' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling ldapupdate task")
                    LdapUpdate(f'{CALLER_NAME}.ldapupdate', self.fakeargs, daemon=True).run()

                await asyncio.sleep(float(self.confopts['tasks']['every_sec']))

        except asyncio.CancelledError:
            if task_apisync:
                task_apisync.cancel()
            if task_usermetadata:
                task_usermetadata.cancel()
            self.logger.info("* Stopping task runner...")


def main():
    ahd = AhDaemon()
    loop = asyncio.get_event_loop()

    def clean_exit(sigstr):
        ahd.logger.info(f"* Exiting on {sigstr}...")
        scheduled_tasks = asyncio.all_tasks(loop=loop)
        for task in scheduled_tasks:
            task.cancel()

    loop.add_signal_handler(signal.SIGINT, clean_exit, 'SIGINT')
    loop.add_signal_handler(signal.SIGTERM, clean_exit, 'SIGTERM')

    try:
        loop.run_until_complete(ahd.run())
    finally:
        loop.close()


if __name__ == '__main__':
    main()

