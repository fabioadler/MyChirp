import builtins
import os

import pytest

# Driver code uses the gettext shorthand `_()` which the GUI and CLI
# applications install as a builtin. Make it available to all tests
# so drivers can be exercised without the wxui/CLI entry points.
builtins._ = lambda s: s


def pytest_configure(config):
    """Registra dinamicamente os marks por módulo de driver.

    O loader de testes (tests/__init__.py) aplica
    ``pytest.mark.<driver_module>`` em cada classe gerada; sem o
    registro, o pytest emite PytestUnknownMarkWarning para cada uma.
    """
    try:
        from mychirp import directory
        directory.import_drivers()
        modules = {rclass.__module__.split('.')[-1]
                   for rclass in directory.DRV_TO_RADIO.values()}
        for module in sorted(modules):
            config.addinivalue_line("markers", "%s: driver module" % module)
    except Exception as e:
        import warnings
        warnings.warn("Falha ao registrar marks de driver: %s" % e)


def pytest_collection_modifyitems(config, items):
    xfails = os.path.join(os.path.dirname(__file__), 'xfails.txt')
    with open(xfails) as f:
        lines = [x.strip() for x in f.readlines() if not x.startswith('#')]
    msg = ('Test marked for XFAIL in tests/xfails.txt, but did not fail. '
           'If this test is now fixed, remove it from the file.')
    for item in items:
        if item.nodeid in lines:
            mark = pytest.mark.xfail(reason=msg)
            item.add_marker(mark)
