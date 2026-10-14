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

    # Default to pt_BR unless the user already configured a language
    # (config `state.lang` or LANG/LANGUAGE env override). This makes the
    # whole interface come up in Portuguese by default.
    from mychirp import config as chirp_config
    conf = chirp_config.get()
    if not conf.get("lang", "state") and not any(
            os.environ.get(v) for v in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")):
        conf.set("lang", "pt_BR", "state")
        conf.save()
    from mychirp.pysideui import i18n
    i18n._install()  # ensure catalog loads before any UI is built

    from mychirp.pysideui.services.app_state import AppState
    state = AppState()

    # Import every driver so image detection works
    from mychirp import directory
    directory.import_drivers()

    from mychirp.pysideui.theme import apply_theme
    apply_theme(app, state.is_dark())

    from mychirp.pysideui.widgets.main_window import MainWindow
    win = MainWindow(state)
    state.main_window = win
    win.show()

    restored, purged = state.restore_session()
    if purged:
        # Um único aviso agregado: vários pop-ups parecem erro
        win.warn_deleted_files(purged)
    if restored:
        state.set_status(
            "Restored %i radio(s) from last session" % restored)

    return app.exec()


def run():
    """Launch the application."""
    sys.exit(main())


if __name__ == "__main__":
    run()
