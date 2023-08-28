class AccountsHPCError(Exception):
    def __init__(self, msg=None):
        self.msg = msg


class SyncHttpError(AccountsHPCError):
    def __init__(self, msg=None):
        self.msg = msg
