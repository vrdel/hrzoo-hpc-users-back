#!/usr/bin/env python

import asyncio
import sys
import signal
import timeit
import datetime
import os

from datetime import timedelta

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

    def _initial_delay(self):
        now = datetime.datetime.now()
        next_run_minute = (now.minute // self.confopts['tasks']['every_min'] + 1) * self.confopts['tasks']['every_min']
        if next_run_minute >= 60:
            next_run_minute = 0
        next_run_time = now.replace(minute=next_run_minute, second=0, microsecond=0)
        if next_run_time < now:
            next_run_time = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        initial_delay = (next_run_time - now).total_seconds()

        return initial_delay

    def _next_delay(self):
        now = datetime.datetime.now()
        min_mark = (now.replace(second=0, microsecond=0).minute // self.confopts['tasks']['every_min']) * self.confopts['tasks']['every_min']
        delay = now.replace(minute=min_mark, second=0, microsecond=0) + timedelta(minutes=self.confopts['tasks']['every_min']) - now
        return delay.total_seconds()

    def _is_running(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    def _write_pidfile(self):
        try:
            with open(self.confopts['tasks']['pidfile'], 'w') as f:
                f.write(str(os.getpid()))
        except OSError:
            self.logger.exception('PIDFile create failed')
            raise AhTaskError

    def _read_pidfile(self):
        try:
            with open(self.confopts['tasks']['pidfile'], 'r') as f:
                pid = int(f.read())
                return pid
        except OSError:
            return 0

    async def run(self):
        try:
            self.task_apisync, self.task_usermetadata, self.task_ldapupdate = None, None, None
            self.task_fairshare, self.task_createdirectories, self.task_emailsend = None, None, None
            initial_delay, initial_done = self._initial_delay(), False

            runpid, is_running = self._read_pidfile(), False
            if runpid:
                is_running = self._is_running(runpid)

            if runpid and is_running:
                self.logger.info(f'{CALLER_NAME} already running')
                raise SystemExit(1)
            elif runpid and not is_running:
                self.logger.info(f'{CALLER_NAME} cleaning stale pidfile')
                os.remove(self.confopts['tasks']['pidfile'])

            self._write_pidfile()

            while True:
                calls_str = ', '.join(self.confopts['tasks']['call_list'])
                self.logger.info(f"* Scheduled tasks ({calls_str}) every {self.confopts['tasks']['every_min']} minutes...")
                if initial_delay and not initial_done:
                    self.logger.info(f"* Initial delay ({initial_delay})...")
                    await asyncio.sleep(initial_delay)
                    initial_done = True

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

                if scheduled:
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

                await asyncio.sleep(self._next_delay())

        except AhTaskError:
            self.logger.error('Critical error, can not continue')
            self._cancel_tasks()

        except asyncio.CancelledError:
            self._cancel_tasks()
            self.logger.info("* Stopping task runner...")
            os.remove(self.confopts['tasks']['pidfile'])


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
