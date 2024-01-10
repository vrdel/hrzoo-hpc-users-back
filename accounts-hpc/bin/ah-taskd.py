#!/usr/bin/env python

import asyncio
import sys
import signal
import timeit

from accounts_hpc.tasks.apisync import ApiSync
from accounts_hpc.tasks.usermetadata import UserMetadata
from accounts_hpc.tasks.ldapupdate import LdapUpdate
from accounts_hpc.tasks.createdirectories import DirectoriesCreate
from accounts_hpc.tasks.fairshare import FairshareUpdate
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
            task_apisync, task_usermetadata, task_ldapupdate = None, None, None

            while True:
                calls_str = ', '.join(self.confopts['tasks']['call_list'])
                self.logger.info(f"* Scheduled tasks ({calls_str})...")
                if 'apisync' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling apisync task")
                    start = timeit.default_timer()
                    task_apisync = asyncio.create_task(
                        ApiSync(f'{CALLER_NAME}.apisync', self.fakeargs, daemon=True).run()
                    )
                    await task_apisync
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended apisync in {format(end - start, '.2f')} seconds")

                if 'usermetadata' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling usermetadata task")
                    start = timeit.default_timer()
                    task_usermetadata = asyncio.create_task(
                        UserMetadata(f'{CALLER_NAME}.usermetadata', self.fakeargs, daemon=True).run()
                    )
                    await task_usermetadata
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended usermetadata in {format(end - start, '.2f')} seconds")

                if 'ldapupdate' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling ldapupdate task")
                    start = timeit.default_timer()
                    task_ldapupdate = asyncio.create_task(
                        LdapUpdate(f'{CALLER_NAME}.ldapupdate', self.fakeargs, daemon=True).run()
                    )
                    await task_ldapupdate
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended ldapupdate in {format(end - start, '.2f')} seconds")

                coros, scheduled = [], []
                if 'fairshare' in self.confopts['tasks']['call_list']:
                    coros.append(
                        FairshareUpdate(f'{CALLER_NAME}.fairshare', self.fakeargs, daemon=True).run()
                    )
                    scheduled.append('fairshare')

                if 'createdirectories' in self.confopts['tasks']['call_list']:
                    coros.append(
                        DirectoriesCreate(f'{CALLER_NAME}.createdirectories', self.fakeargs, daemon=True).run()
                    )
                    scheduled.append('createdirectories')

                self.logger.info(f"> Calling {', '.join(scheduled)} tasks")
                start = timeit.default_timer()
                coros_ret = await asyncio.gather(*coros, return_exceptions=True)
                end = timeit.default_timer()
                self.logger.info(f"> Ended {', '.join(scheduled)} in {format(end - start, '.2f')} seconds")

                await asyncio.sleep(float(self.confopts['tasks']['every_sec']))

        except asyncio.CancelledError:
            if task_apisync:
                task_apisync.cancel()
            if task_usermetadata:
                task_usermetadata.cancel()
            if task_ldapupdate:
                task_ldapupdate.cancel()
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

