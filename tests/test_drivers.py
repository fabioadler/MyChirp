from mychirp import directory
from tests import load_tests

__builtins__['_'] = lambda s: s


class SuiteAdapter(object):
    """Adapter for pytest since it doesn't support the loadTests() protocol.

    Named without the 'Test' prefix so pytest doesn't try to collect it
    (it has a __init__ constructor and isn't a test class).
    """

    def __init__(self, locals):
        self.locals = locals

    def loadTestsFromTestCase(self, test_cls):
        self.locals[test_cls.__name__] = test_cls

    @staticmethod
    def addTests(tests):
        pass


directory.import_drivers()
adapter = SuiteAdapter(locals())
load_tests(adapter, None, None, suite=adapter)
