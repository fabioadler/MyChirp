"""PySide6 entry point.

Run with: python -m mychirp.pysideui  (or the `mychirp` console script).
"""

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from mychirp import logger as chirp_logger  # noqa: F401  (sets up logging)

LOG = logging.getLogger(__name__)

ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "share"))


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("MyChirp")
    app.setOrganizationName("MyChirp")

    from mychirp.pysideui.services.app_state import AppState
    state = AppState()

    from mychirp.pysideui.theme import apply_theme
    apply_theme(app, state.is_dark())

    from mychirp.pysideui.widgets.main_window import MainWindow
    win = MainWindow(state)
    state.main_window = win
    win.show()

    restored = state.restore_session()
    if restored:
        state.set_status(
            "Restored %i radio(s) from last session" % restored)

    return app.exec()


def run():
    """Launch the application."""
    sys.exit(main())


if __name__ == "__main__":
    run()
