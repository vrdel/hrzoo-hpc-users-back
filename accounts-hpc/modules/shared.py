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
        self.__class__.log = Logger(caller)
        if not getattr(self.__class__, 'confopts', False):
            confopts = parse_config()
            self.__class__.confopts = confopts
        if not getattr(self.__class__, 'dbsession', False):
            engine = create_engine("sqlite:///{}".format(confopts['db']['path']))
            Session = sessionmaker(engine)
            self.__class__.dbsession = Session()
