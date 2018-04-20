import sys
import pdb


class ServerMgrException(Exception):
    def __init__(self, msg, ret_code = 0):
        self.msg = msg
        self.ret_code = ret_code

    def __str__(self):
        return repr(self.msg)


