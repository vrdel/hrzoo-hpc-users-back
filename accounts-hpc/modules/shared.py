from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore


class Shared(object):
    """
       Global runtime object used to store configuration, loggers, and
       database sessions that need to be shared throughout the code.
    """
    def __new__(cls, *args, **kwargs):
        if not getattr(cls, '_globalobj', None):
            cls._globalobj = object.__new__(cls)
        return cls._globalobj

    def __init__(self, caller=None, daemon=False, dry_run=False):
        if not getattr(self, '_initialized', False):
            self.reset()
            self._initialized = True

        if caller is not None:
            self.init(caller, daemon=daemon, dry_run=dry_run)

    def reset(self):
        self.confopts = None
        self.log = dict()
        self.dbsession = dict()
        self.dbsession_sync = dict()
        self.dry_run = False
        self._dry_run_engine = None
        self._dry_run_engine_sync = None
        self.caller = None
        self.logger = None

    def init(self, caller, daemon=False, dry_run=False):
        self.caller = caller

        if self.confopts is None:
            self.confopts = parse_config()

        if dry_run:
            self.dry_run = True

        if caller not in self.log.keys():
            conf_loggers = self.confopts.get('general', None)
            if conf_loggers:
                conf_loggers = conf_loggers.get('loggers', None)
            self.log[caller] = Logger(caller, daemon, conf_loggers)

        if caller not in self.dbsession:
            if self.dry_run:
                if self._dry_run_engine is None:
                    self._dry_run_engine = create_async_engine(
                        "sqlite+aiosqlite://",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool
                    )
                engine = self._dry_run_engine
            else:
                engine = create_async_engine(
                    "sqlite+aiosqlite:///{}".format(self.confopts['db']['path'])
                )
            async_session = sessionmaker(
                bind=engine, expire_on_commit=False, class_=AsyncSession
            )
            self.dbsession[caller] = async_session()

        if caller not in self.dbsession_sync:
            if self.dry_run:
                if self._dry_run_engine_sync is None:
                    self._dry_run_engine_sync = create_engine(
                        "sqlite://",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool
                    )
                engine = self._dry_run_engine_sync
            else:
                engine = create_engine(
                    "sqlite:///{}".format(self.confopts['db']['path'])
                )
            Session = sessionmaker(engine)
            self.dbsession_sync[caller] = Session()

        self.logger = self.log[caller].get()
        return self


shared = Shared()


def init(caller, daemon=False, dry_run=False):
    return shared.init(caller, daemon=daemon, dry_run=dry_run)


def reset():
    shared.reset()
