#!/usr/bin/env python

import asyncio
import sys
import signal
import timeit

from accounts_hpc.tasks.apisync import ApiSync
from accounts_hpc.tasks.usermetadata import UserMetadata
from accounts_hpc.tasks.ldapupdate import LdapUpdate
from accounts_hpc.tasks.createdirectories import DirectoriesCreate
from accounts_hpc.tasks.emailsend import SendEmail
from accounts_hpc.tasks.fairshare import FairshareUpdate
from accounts_hpc.shared import Shared
from accounts_hpc.exceptions import AhTaskError
from accounts_hpc.utils import contains_exception


CALLER_NAME = "ah-taskd"


class FakeArgs(object):
    def __init__(self):
        self.initset = False
        self.new = False


class AhDaemon(object):
    def __init__(self):
        self.fakeargs = FakeArgs()
        shared = Shared(CALLER_NAME, daemon=True)
        self.confopts = shared.confopts
        self.logger = shared.log[CALLER_NAME].get()

    def _cancel_tasks(self):
        if self.task_apisync:
            self.task_apisync.cancel()
        if self.task_usermetadata:
            self.task_usermetadata.cancel()
        if self.task_ldapupdate:
            self.task_ldapupdate.cancel()
        if self.task_fairshare:
            self.task_fairshare.cancel()
        if self.task_createdirectories:
            self.task_createdirectories.cancel()
        if self.task_emailsend:
            self.task_emailsend.cancel()

    async def run(self):
        try:
            self.task_apisync, self.task_usermetadata, self.task_ldapupdate = None, None, None
            self.task_fairshare, self.task_createdirectories, self.task_emailsend = None, None, None

            while True:
                calls_str = ', '.join(self.confopts['tasks']['call_list'])
                self.logger.info(f"* Scheduled tasks ({calls_str})...")
                if 'apisync' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling apisync task")
                    start = timeit.default_timer()
                    self.task_apisync = asyncio.create_task(
                        ApiSync(f'{CALLER_NAME}.apisync', self.fakeargs, daemon=True).run()
                    )
                    await self.task_apisync
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended apisync in {format(end - start, '.2f')} seconds")

                if 'usermetadata' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling usermetadata task")
                    start = timeit.default_timer()
                    self.task_usermetadata = asyncio.create_task(
                        UserMetadata(f'{CALLER_NAME}.usermetadata', self.fakeargs, daemon=True).run()
                    )
                    await self.task_usermetadata
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended usermetadata in {format(end - start, '.2f')} seconds")

                if 'ldapupdate' in self.confopts['tasks']['call_list']:
                    self.logger.info("> Calling ldapupdate task")
                    start = timeit.default_timer()
                    self.task_ldapupdate = asyncio.create_task(
                        LdapUpdate(f'{CALLER_NAME}.ldapupdate', self.fakeargs, daemon=True).run()
                    )
                    await self.task_ldapupdate
                    end = timeit.default_timer()
                    self.logger.info(f"> Ended ldapupdate in {format(end - start, '.2f')} seconds")

                scheduled = []
                if 'fairshare' in self.confopts['tasks']['call_list']:
                    self.task_fairshare = asyncio.create_task(
                        FairshareUpdate(f'{CALLER_NAME}.fairshare', self.fakeargs, daemon=True).run()
                    )
                    scheduled.append('fairshare')

                if 'createdirectories' in self.confopts['tasks']['call_list']:
                    self.task_createdirectories = asyncio.create_task(
                        DirectoriesCreate(f'{CALLER_NAME}.createdirectories', self.fakeargs, daemon=True).run()
                    )
                    scheduled.append('createdirectories')

                if 'emailsend' in self.confopts['tasks']['call_list']:
                    self.task_emailsend = asyncio.create_task(
                        SendEmail(f'{CALLER_NAME}.emailsend', self.fakeargs, daemon=True).run()
                    )
                    scheduled.append('emailsend')

                self.logger.info(f"> Calling {', '.join(scheduled)} tasks")
                start = timeit.default_timer()
                tasks_concur = []
                if self.task_fairshare:
                    tasks_concur.append(self.task_fairshare)
                if self.task_createdirectories:
                    tasks_concur.append(self.task_createdirectories)
                if self.task_emailsend:
                    tasks_concur.append(self.task_emailsend)
                ret_concur = await asyncio.gather(*tasks_concur, return_exceptions=True)
                exc_raised, exc = contains_exception(ret_concur)
                if exc_raised:
                    for ret in ret_concur:
                        if isinstance(ret, AhTaskError):
                            self.logger.error("Error in concurrently running tasks")
                            raise ret
                        elif isinstance(ret, asyncio.CancelledError):
                            self.logger.error("Concurrent task cancelled")

                end = timeit.default_timer()
                self.logger.info(f"> Ended {', '.join(scheduled)} in {format(end - start, '.2f')} seconds")

                await asyncio.sleep(float(self.confopts['tasks']['every_sec']))

        except AhTaskError:
            self.logger.error('Critical error, can not continue')
            self._cancel_tasks()

        except asyncio.CancelledError:
            self._cancel_tasks()
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

