#!/usr/bin/env python

import sys
import os

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Project  # type: ignore

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import argparse
import psutil
import signal


def send_sighup(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == process_name:
            os.kill(proc.info['pid'], signal.SIGHUP)


def update_cacheflag(projectsdb):
    for project in projectsdb:
        if not project.is_pbsfairshare_added:
            project.is_pbsfairshare_added = True


def update_file(fsobj, projids, nlines):
    nline = nlines + 1
    fs_lines_write = list()
    if nlines == 0:
        fs_lines_write.append("{0:<32} {1:03} root 100\n".format("hpc", 1))
        nline += 1
    for ident in projids:
        line_to_write = '{0:<32} {1:03} root 100\n'.format(ident, nline)
        nline += 1
        fs_lines_write.append(line_to_write)
    fsobj.writelines(fs_lines_write)


def main():
    lobj = Logger(sys.argv[0])
    logger = lobj.get()
    is_updated = False

    parser = argparse.ArgumentParser(description="""Update PBS fairshare resource_group""")
    parser.add_argument('--new', dest='new', action='store_true', help='create new resource_group from scratch')
    args = parser.parse_args()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    fairshare_path = confopts['usersetup']['pbsfairshare_path']
    pbsprocname = confopts['usersetup']['pbsprocname']

    if fairshare_path:
        fsobj = None

        try:
            if args.new:
                fsobj = open(fairshare_path, "x")
            else:
                fsobj = open(fairshare_path, "r+")
        except (FileNotFoundError, FileExistsError) as exc:
            logger.error(exc)
            raise SystemExit(1)

        projects = session.query(Project).all()
        all_projids = list()
        for project in projects:
            all_projids.append(project.identifier)

        if args.new:
            update_file(fsobj, all_projids, 0)
            update_cacheflag(projects)
            is_updated = True
        else:
            fs_lines = fsobj.readlines()
            all_projids_infile = [line.split(' ')[0] for line in fs_lines]
            new_projids = set(all_projids).difference(set(all_projids_infile))
            if new_projids:
                update_file(fsobj, new_projids, len(fs_lines))
                update_cacheflag(projects)
                is_updated = True

        fsobj.close()

        if is_updated and not args.new:
            logger.info(f"PBS fairshare updated with {', '.join(new_projids)}, sending SIGHUP...")
            send_sighup(pbsprocname)
        elif is_updated and args.new:
            logger.info("Created new PBS fairshare, sending SIGHUP...")
            send_sighup(pbsprocname)

    session.commit()
    session.close()


if __name__ == '__main__':
    main()
