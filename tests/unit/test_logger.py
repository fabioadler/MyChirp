import logging
import os

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


class TestProjectLog(base.BaseTest):
    """Log do sistema em <projeto>/logs/log.txt (append, sempre ativo)."""

    def test_project_log_file_created_and_appends(self):
        path = logger.project_log_file()
        self.assertTrue(path.endswith(os.path.join("logs", "log.txt")))
        # Logger já criou o arquivo no import (se não existisse)
        self.assertTrue(os.path.exists(path))
        size_before = os.path.getsize(path)
        logging.getLogger("mychirp.test_project_log").debug("marcador-x9")
        for handler in logging.getLogger().handlers:
            handler.flush()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn("marcador-x9", content)
        self.assertGreaterEqual(os.path.getsize(path), size_before)

    def test_clear_project_log_truncates_and_keeps_logging(self):
        logging.getLogger("mychirp.test_project_log").debug("antes-limpeza")
        logger.Logger.instance.clear_project_log()
        path = logger.project_log_file()
        logging.getLogger("mychirp.test_project_log").debug("pos-limpeza")
        for handler in logging.getLogger().handlers:
            handler.flush()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        # histórico antigo foi limpo...
        self.assertNotIn("antes-limpeza", content)
        # ...e o logging continua ativo (handler reanexado)
        self.assertIn("pos-limpeza", content)
        self.assertIn("log do sistema limpo", content)
