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
        sync with HRZOO Signup API, set user entries in LDAP and performs
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
    install_requires=['aiohttp', 'aiofiles', 'aiosqlite', 'aioshutil', 'aiosmtplib',
                      'alembic', 'bonsai', 'psutil', 'requests', 'SQLAlchemy',
                      'sqlalchemy-json', 'Unidecode', 'rich'],
    scripts=['bin/ah-api-sync.py', 'bin/ah-user-metadata-setup.py', 'bin/ah-ldap-update.py',
             'bin/ah-directories-create.py', 'bin/ah-fairshare-update.py', 'bin/ah-email-send.py',
             'bin/ah-db-tool.py', 'bin/ah-all-flags-set.py',
             'bin/ah-user-manage.py', 'bin/ah-project-manage.py',
             'bin/ah-taskd.py'],
    data_files=[
        ('bin/', glob.glob('bin/*')),
        ('etc/accounts-hpc', ['config/email-template-new-key.txt',
                              'config/email-template-new-user.txt',
                              'config/email-template-activate-user.txt',
                              'config/email-template-deactivate-user.txt',
                              'config/accounts-hpc.conf.template',
                              'config/replacestring_map.json',
                              'config/deploy-config.sh',
                              'config/users_map.json']),
        ('etc/logrotate.d/', ['logrotate/cache', 'logrotate/logfile']),
        ('var/log/', ['helpers/empty']),
        ('var/lib/', ['helpers/empty']),
        ('var/lib/backup/', ['helpers/empty']),
        ('alembic/', ['alembic/README', 'alembic/env.py', 'alembic/script.py.mako']),
        ('alembic/versions', glob.glob('alembic/versions/*')),
        ('', ['requirements.txt', 'alembic.ini']),
    ],
    include_package_data=True,
    packages=['accounts_hpc', 'accounts_hpc.tasks'],
    package_dir={
        'accounts_hpc': 'modules/',
        'accounts_hpc.tasks': 'modules/tasks'
    }
)
