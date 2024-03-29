import argparse
import aiofiles
import asyncio
import psutil
import signal
import os

from sqlalchemy import select

from accounts_hpc.db import Project  # type: ignore
from accounts_hpc.shared import Shared  # type: ignore
from accounts_hpc.exceptions import AhTaskError


def send_sighup(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            os.kill(proc.info['pid'], signal.SIGHUP)


def update_cacheflag(projectsdb):
    for project in projectsdb:
        if not project.is_pbsfairshare_added:
            project.is_pbsfairshare_added = True


async def update_file(fsobj, projids, nlines):
    nline = nlines + 1
    fs_lines_write = list()
    if nlines == 0:
        fs_lines_write.append("{0:<32} {1:03} root 100\n".format("hpc", 1))
        nline += 1
    for ident in projids:
        line_to_write = '{0:<32} {1:03} root 100\n'.format(ident, nline)
        nline += 1
        fs_lines_write.append(line_to_write)
    await fsobj.writelines(fs_lines_write)


class FairshareUpdate(object):
    def __init__(self, caller, args, daemon=False):
        shared = Shared(caller, daemon)
        self.confopts = shared.confopts
        self.logger = shared.log[caller].get()
        self.dbsession = shared.dbsession[caller]
        self.args = args
        self.daemon = daemon

    async def run(self):
        try:
            is_updated = False
            fairshare_path = self.confopts['usersetup']['pbsfairshare_path']
            pbsprocname = self.confopts['usersetup']['pbsprocname']

            if fairshare_path:
                fsobj = None

                try:
                    if self.args.new:
                        fsobj = await aiofiles.open(fairshare_path, "x")
                    else:
                        fsobj = await aiofiles.open(fairshare_path, "r+")
                except (FileNotFoundError, FileExistsError) as exc:
                    self.logger.error(exc)
                    raise SystemExit(1)

                projects = await self.dbsession.execute(select(Project))
                projects = projects.scalars().all()
                all_projids = list()
                for project in projects:
                    all_projids.append(project.identifier)

                if self.args.new:
                    await update_file(fsobj, all_projids, 0)
                    update_cacheflag(projects)
                    is_updated = True
                else:
                    fs_lines = await fsobj.readlines()
                    all_projids_infile = [line.split(' ')[0] for line in fs_lines]
                    new_projids = set(all_projids).difference(set(all_projids_infile))
                    if new_projids:
                        await update_file(fsobj, new_projids, len(fs_lines))
                        update_cacheflag(projects)
                        is_updated = True

                await fsobj.close()

                if is_updated and not self.args.new:
                    self.logger.info(f"PBS fairshare updated with {', '.join(new_projids)}, sending SIGHUP...")
                    send_sighup(pbsprocname)
                elif is_updated and self.args.new:
                    self.logger.info("Created new PBS fairshare, sending SIGHUP...")
                    send_sighup(pbsprocname)

        except asyncio.CancelledError as exc:
            self.logger.info('* Cancelling fairshare...')
            raise exc

        finally:
            await self.dbsession.commit()
            await self.dbsession.close()
