import logging

from mychirp import logger
from tests.unit import base


class TestLogger(base.BaseTest):
    def test_log_history(self):
        drv_log = logging.getLogger('mychirp.drivers.foo')
        ui_log = logging.getLogger('mychirp.fletui.foo')
        root_log = logging.getLogger()

        root_log.setLevel(logging.DEBUG)

        def log_all():
            for log in (drv_log, ui_log, root_log):
                log.debug('debug')
                log.warning('warning')
                log.error('error')

        # Log to everything
        log_all()

        with logger.log_history(logging.WARNING, 'mychirp.drivers') as h:
            log_all()
            history = h.get_history()

        # We should only have the error,warning messages from drivers
        # since we started the capture, not before
        self.assertEqual(2, len(history))

        with logger.log_history(logging.WARNING, 'mychirp.drivers') as h:
            log_all()
            history = h.get_history()

        # Make sure we only have the captured logs, not any leftover from
        # the previous run
        self.assertEqual(2, len(history))
