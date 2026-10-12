import logging
import os

import flet as ft

from mychirp import directory
from mychirp import logger as chirp_logger
from mychirp.fletui.components.layout import AppShell
from mychirp.fletui.services.app_state import MODE_DARK, MODE_LIGHT, get_state
from mychirp.fletui.theme import AppColors, get_theme
from mychirp.fletui.i18n import _

LOG = logging.getLogger(__name__)

# The flet transport logs every protocol frame at DEBUG, which is far
# too verbose (and caused reentrant writes to the shared debug log)
logging.getLogger("flet").setLevel(logging.INFO)
logging.getLogger("flet_transport").setLevel(logging.WARNING)

# Single source of assets: mychirp/share (logos, icons)
ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "share"))


def main(page: ft.Page):
    """MyChirp Flet entry point."""
    page.title = "MyChirp"
    page.padding = 0
    page.spacing = 0
    page.theme = get_theme(dark=True)
    page.dark_theme = get_theme(dark=False)

    state = get_state(page)
    dark = state.is_dark()
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT

    # Import every driver so the radio lists are ready
    directory.import_drivers()

    shell = AppShell(page)
    page.add(shell)

    LOG.info("MyChirp flet UI started")


def run():
    """Launch the application."""
    ft.run(
        main,
        assets_dir=ASSETS_DIR,
    )


if __name__ == "__main__":
    run()
