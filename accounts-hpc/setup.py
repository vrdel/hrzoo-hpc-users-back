from setuptools import setup
import os
import glob
import sys

NAME = 'accountshpc'


def get_files(install_prefix, directory):
    files = []
    for root, _, filenames in os.walk(directory):
        subdir_files = []
        for filename in filenames:
            subdir_files.append(os.path.join(root, filename))
        if filenames and subdir_files:
            files.append((os.path.join(install_prefix, root), subdir_files))
    return files


setup(
    name=NAME,
    version='0.1.0',
    description="""
        Set of backend tools that run on frontend node of HRZOO HPC clusters,
        sync with HRZOO Signup API and opens user accounts in LDAP and performs
        other actions for user to get access
    """,
    author='SRCE',
    author_email='dvrcic@srce.hr',
    license='Apache License 2.0',
    url='https://github.com/vrdel/hrzoo-hpc-users-back',
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ),
    install_requires=['aiohttp', 'alembic', 'bonsai', 'psutil', 'requests',
                      'SQLAlchemy', 'sqlalchemy-json', 'Unidecode'],
    scripts=['bin/1-api-sync.py', 'bin/2-user-metadata-setup.py', 'bin/3-ldap-update.py',
             'bin/4-directories-create.py', 'bin/5-fairshare-update.py', 'bin/6-email-send.py',
             'bin/7-mailinglist-subscribe.py', 'bin/db-tool.py'],
    data_files=[
        ('bin/', glob.glob('bin/*')),
        ('etc/accounts-hpc', ['config/email-template-new-key.txt',
                              'config/email-template-new-user.txt',
                              'config/accounts-hpc.conf.template',
                              'config/replacestring_map.json',
                              'config/users_map.json']),
        ('etc/cron.d/', ['cron/empty']),
        ('var/log/', ['helpers/empty']),
        ('var/lib/', ['helpers/empty']),
        ('alembic/', ['alembic/README', 'alembic/env.py', 'alembic/script.py.mako']),
        ('alembic/versions', glob.glob('alembic/versions/*')),
        ('', ['requirements.txt', 'alembic.ini']),
    ],
    include_package_data=True,
    packages=['accounts_hpc'],
    package_dir={
        'accounts_hpc': 'modules/',
    }
)