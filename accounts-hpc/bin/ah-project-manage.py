#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, all_none, contains_exception, get_ssh_key_fingerprint

from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import NoResultFound, IntegrityError, MultipleResultsFound
from unidecode import unidecode

import datetime


def gen_id(session, confopts):
    id = gen_gid(session, confopts) - confopts['usersetup']['gid_manual_offset']
    now = datetime.datetime.now()
    return "NRM-{:%Y}-{:%m}-{:03}".format(now, now, id)


def gen_gid(session, confopts):
    manual_projects = session.query(Project).filter(Project.type == 'manual').all()
    defgroups = confopts['usersetup']['default_groups']
    resgroups = confopts['usersetup']['resource_groups']
    gid_offset = confopts['usersetup']['gid_manual_offset']

    return gid_offset + 1 \
        + len(manual_projects) \
        + len(defgroups) \
        + len(resgroups)


def project_delete(logger, args, session):
    pass


def project_add(logger, args, session, confopts):
    try:
        pr = session.query(Project).filter(
            Project.name == args.name).one()
        # update staff_resources_type with latest value
        pr.staff_resources_type_api = args.resourcetypes
    except NoResultFound:
        pr = Project(name=args.name,
                     identifier=gen_id(session, confopts),
                     prjid_api=0,
                     type='manual',
                     is_dir_created=False,
                     is_pbsfairshare_added=False,
                     staff_resources_type_api=args.resourcetypes,
                     ldap_gid=gen_gid(session, confopts))

    session.add(pr)
    return pr


def main():
    parser = argparse.ArgumentParser(description='Manage project create and delete manually with needed metadata about it')
    subparsers = parser.add_subparsers(help="Project subcommands", dest="command")

    parser_create = subparsers.add_parser('create', help='Create project based on passed metadata')
    parser_create.add_argument('--name', dest='name', type=str, required=True,
                               help='Project name')
    parser_create.add_argument('--resource-types', dest='resourcetypes',
                               type=str, nargs='+', required=True,
                               help='Resource types')

    parser_delete = subparsers.add_parser('delete',
                                          help='Delete project metadata')
    parser_delete.add_argument('--name', dest='name', type=str, required=True,
                               help='Project name')

    args = parser.parse_args()

    lobj = Logger(sys.argv[0])
    logger = lobj.get()

    confopts = parse_config()

    engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
    Session = sessionmaker(engine)
    session = Session()

    if args.command == "create":
        new_project = project_add(logger, args, session, confopts)
        logger.info(f"Created project \"{new_project.name}\" with ID {new_project.identifier}")
    elif args.command == "delete":
        project_delete(logger, args, session)

    try:
        session.commit()
        session.close()
    except (IntegrityError, StaleDataError) as exc:
        logger.error(f"Error with {args.command}")
        logger.error(exc)


if __name__ == '__main__':
    main()
