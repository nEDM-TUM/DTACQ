from .digitizer_utils import ReadoutException

def notRunning(func):
    def _wrap(self, *args, **kw):
        if self.isRunning:
            raise ReadoutException("Cannot call function while readout running")
        return func(self, *args, **kw)
    return _wrap

def isRunning(func):
    def _wrap(self, *args, **kw):
        if not self.isRunning:
            raise ReadoutException("Cannot call function while readout running")
        return func(self, *args, **kw)
    return _wrap


