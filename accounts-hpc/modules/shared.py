from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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

    def __init__(self, caller):
        if not getattr(self.__class__, 'log', False):
            self.__class__.log = dict()
        self.__class__.log[caller] = Logger(caller)

        if not getattr(self.__class__, 'confopts', False):
            confopts = parse_config()
            self.__class__.confopts = confopts

        engine = create_engine("sqlite:///{}".format(self.__class__.confopts['db']['path']))
        Session = sessionmaker(engine)
        if not getattr(self.__class__, 'dbsession', False):
            self.__class__.dbsession = dict()
        self.__class__.dbsession[caller] = Session()
