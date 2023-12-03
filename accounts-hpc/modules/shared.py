from accounts_hpc.config import parse_config  # type: ignore
from accounts_hpc.log import Logger # type: ignore


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
        if not getattr(self.__class__, '_confopts', False):
            confopts = parse_config()
            self.__class__.confopts = confopts
        self.__class__.log = Logger(caller)
