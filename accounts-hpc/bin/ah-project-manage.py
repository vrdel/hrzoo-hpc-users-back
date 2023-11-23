#!/usr/bin/env python

import sys
import argparse

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from accounts_hpc.db import Base, Project, User, SshKey  # type: ignore
from accounts_hpc.utils import only_alnum, all_none, contains_exception, get_ssh_key_fingerprint

from rich import print
from rich.columns import Columns
from rich.table import Table
from rich.console import Console
from rich.pretty import pprint

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


def project_list(logger, args, session):
    projects = session.query(Project).all()
    table = Table(title="Found projects", title_justify="left", box=None, show_lines=True, title_style="")
    table.add_column(justify="right")
    table.add_column()
    table.add_column()

    for project in projects:
        if (args.name and args.name.lower() in project.name.lower()) or \
           (args.identifier and args.identifier.lower() in project.identifier.lower()):
            users = ', '.join([user.ldap_username for user in project.user])
            resources = ', '.join(project.staff_resources_type_api)
            table.add_row('Name =', project.name)
            table.add_row('Identifier =', project.identifier)
            table.add_row('Resources =', resources)
            table.add_row('LDAP GID =', str(project.ldap_gid))
            table.add_row('API ID =', str(project.prjid_api))
            table.add_row('Type create =', str(project.type))
            table.add_row('Directory =', str(project.is_dir_created))
            table.add_row('PBS =', str(project.is_dir_created))
            table.add_row('Users =', users)
            table.add_row(' ')
        if not args.name and not args.identifier:
            users = ', '.join([user.ldap_username for user in project.user])
            resources = ', '.join(project.staff_resources_type_api)
            table.add_row('Name =', project.name)
            table.add_row('Identifier =', project.identifier)
            table.add_row('Resources =', resources)
            table.add_row('LDAP GID =', str(project.ldap_gid))
            table.add_row('API ID =', str(project.prjid_api))
            table.add_row('Directory =', str(project.is_dir_created))
            table.add_row('PBS =', str(project.is_dir_created))
            table.add_row('Users =', users)
            table.add_row(' ')
    if table.row_count:
        console = Console()
        console.print(table)


def project_update(logger, args, session):
    try:
        pr = session.query(Project).filter(
            Project.identifier == args.identifier).one()

        if args.name:
            pr.name = args.name
            logger.info(f"Update project {args.identifier} with new name with {args.name}")

        if args.newidentifier:
            pr.identifier = args.newidentifier
            logger.info(f"Update identifier for project {args.identifier} with new {args.newidentifier}")

        if args.resourcetypes:
            pr.staff_resources_type_api = args.resourcetypes
            logger.info(f"Update resources for project {args.identifier} with {args.resourcetypes}")

        if args.apiid:
            pr.prjid_api = args.apiid
            logger.info(f"Update API ID for project {args.identifier} with {args.apiid}")

        if args.typecreate:
            pr.type = args.typecreate
            logger.info(f"Update type_create for project {args.identifier} with {args.typecreate}")

        if args.flagisdircreated and args.flagisdircreated > 0:
            pr.is_dir_created = True
            logger.info(f"Set is_dir_created for project {args.identifier}")
        elif args.flagisdircreated == 0:
            pr.is_dir_created = False
            logger.info(f"Unset is_dir_created for project {args.identifier}")

        if args.flagfairshare and args.flagfairshare > 0:
            pr.is_pbsfairshare_added = True
            logger.info(f"Set is_pbsfairshare_added for project {args.identifier}")
        elif args.flagfairshare == 0:
            pr.is_pbsfairshare_added = False
            logger.info(f"Unset is_pbsfairshare_added for project {args.identifier}")

        if args.nullgid:
            pr.ldap_gid = 0
            logger.info(f"Set 0 for LDAL GID for project {args.identifier}")

    except MultipleResultsFound:
        logger.error("Multiple projects found with the same identifier or name")
        raise SystemExit(1)

    except NoResultFound:
        logger.error("No project found")
        raise SystemExit(1)

def project_delete(logger, args, session):
    try:
        pr = session.query(Project).filter(
            Project.identifier == args.identifier).one()

        if pr:
            logger.info(f"Projects found with {args.identifier}")
            logger.info("This will delete the project from cache DB and deassociate users from it\nAre you sure you want to continue? (yes/no): ")
            decision = input('--> ')
            if decision.lower() != 'yes' and decision.lower() != 'no':
                logger.error("Cannot interpret the answer, skipping action")
            elif decision.lower() == 'yes':
                for us in pr.user:
                    us.projects_api.remove(args.identifier)
                if not args.force:
                    logger.info("Project and its users deleted")
                else:
                    for us in pr.user:
                        pr.user.remove(us)
                    session.delete(pr)
                    logger.info("Project and its users DB relation deleted")

    except MultipleResultsFound:
        logger.error("Multiple projects found with the same identifier or name")
        raise SystemExit(1)

    except NoResultFound:
        logger.error("No project found")
        raise SystemExit(1)


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
    parser.add_argument('--force', dest='force', action='store_true',
                        required=False, help='Make changes in DB relations')

    parser_create = subparsers.add_parser('create', help='Create project based on passed metadata')
    parser_create.add_argument('--name', dest='name', type=str, required=True,
                               help='Project name')
    parser_create.add_argument('--resource-types', dest='resourcetypes',
                               type=str, nargs='+', required=True,
                               help='Resource types')

    parser_delete = subparsers.add_parser('delete',
                                          help='Delete project')
    parser_delete.add_argument('--identifier', dest='identifier', type=str, required=False,
                               help='Project identifier')
    parser_update = subparsers.add_parser('update', help='Update project metadata')
    parser_update.add_argument('--identifier', dest='identifier', type=str, required=True,
                               help='String that will be matched with the project name')
    parser_update.add_argument('--new-identifier', dest='newidentifier', type=str, required=False,
                               help='New project identifier')
    parser_update.add_argument('--name', dest='name', type=str, required=False,
                               help='New project name')
    parser_update.add_argument('--null-gid', dest='nullgid', default=False, action='store_true',
                               required=False, help='Set LDAP GID for project to 0')
    parser_update.add_argument('--type-create', dest='typecreate', type=str, metavar='api/manual',
                               required=False, help='Set type_create')
    parser_update.add_argument('--api-id', dest='apiid', type=int,
                               required=False, help='Update project API ID')
    parser_update.add_argument('--resource-types', dest='resourcetypes', type=str,
                               required=False, nargs='+', help='Update resource types')
    parser_update.add_argument('--flag-dircreated', dest='flagisdircreated', type=int, metavar='0/1',
                               required=False, help='Set flag is_dir_created')
    parser_update.add_argument('--flag-fairshare', dest='flagfairshare', type=int, metavar='0/1',
                               required=False, help='Set flag is_pbsfairshare_added')
    parser_list = subparsers.add_parser('list', help='List projects based on passed metadata')
    parser_list.add_argument('--name', dest='name', type=str, required=False,
                             help='String that will be matched with the project name')
    parser_list.add_argument('--identifier', dest='identifier', type=str, required=False,
                             help='String that will be matched with the project identifier')

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
    elif args.command == "update":
        project_update(logger, args, session)
    elif args.command == "list":
        project_list(logger, args, session)

    try:
        session.commit()
        session.close()
    except (IntegrityError, StaleDataError) as exc:
        logger.error(f"Error with {args.command}")
        logger.error(exc)


if __name__ == '__main__':
    main()
