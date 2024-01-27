from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


class Shared(object):
    """
       Singleton object used to store configuration options and some runtime
       options that need to be shared throughout the code
    """
    def __new__(cls, *args, **kwargs):
        if getattr(cls, 'sharedobj', False):
            return cls.sharedobj
        else:
            setattr(cls, 'sharedobj', object.__new__(cls))
            return cls.sharedobj

    def __init__(self, caller, daemon=False):
        if not getattr(self.__class__, 'log', False):
            self.__class__.log = dict()
        if caller not in self.__class__.log.keys():
            self.__class__.log[caller] = Logger(caller, daemon)

        if not getattr(self.__class__, 'confopts', False):
            confopts = parse_config()
            self.__class__.confopts = confopts

        if not getattr(self.__class__, 'dbsession', False):
            self.__class__.dbsession = dict()
        if caller not in self.__class__.dbsession:
            engine = create_async_engine("sqlite+aiosqlite:///{}".format(self.__class__.confopts['db']['path']))
            async_session = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
            self.__class__.dbsession[caller] = async_session()

        if not getattr(self.__class__, 'dbsession_sync', False):
            self.__class__.dbsession_sync = dict()
        if caller not in self.__class__.dbsession_sync:
            engine = create_engine("sqlite:///{}".format(self.__class__.confopts['db']['path']))
            Session = sessionmaker(engine)
            self.__class__.dbsession_sync[caller] = Session()
