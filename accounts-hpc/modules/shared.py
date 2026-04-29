from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


class Shared(object):
    def __init__(self):
        self.caller = ""
        self.daemon = False
        self.dry_run = False
        self.confopts = {}
        self.logger = None
        self.dbsession = None
        self.dbsession_sync = None
        self._async_engine = None
        self._sync_engine = None
        self._initialized = False


shared = Shared()


def init(caller, daemon=False, dry_run=False):
    if shared._initialized:
        if shared.caller != caller:
            raise RuntimeError(
                f"shared already initialized for {shared.caller!r}, "
                f"refusing re-init for {caller!r}"
            )
        return shared

    shared.caller = caller
    shared.daemon = daemon
    shared.dry_run = dry_run
    shared.confopts = parse_config()

    conf_loggers = (shared.confopts.get("general") or {}).get("loggers")
    shared.logger = Logger(caller, daemon, conf_loggers).get()

    if dry_run:
        shared._async_engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        shared._sync_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        db_path = shared.confopts["db"]["path"]
        shared._async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        shared._sync_engine = create_engine(f"sqlite:///{db_path}")

    shared.dbsession = sessionmaker(
        bind=shared._async_engine, expire_on_commit=False, class_=AsyncSession
    )()
    shared.dbsession_sync = sessionmaker(shared._sync_engine)()

    shared._initialized = True
    return shared


def reset():
    global shared
    shared.__init__()
