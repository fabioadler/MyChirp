import logging
import os

import flet as ft

from mychirp import directory
from mychirp import logger as chirp_logger
from mychirp.fletui.components.layout import AppShell
from mychirp.fletui.services.app_state import MODE_DARK, MODE_LIGHT, get_state
from mychirp.fletui.theme import AppColors, get_theme

LOG = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


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

    def on_disconnect(e):
        pass

    page.window.prevent_close = True

    LOG.info("MyChirp flet UI started")


def run():
    """Launch the application."""
    ft.run(
        main,
        assets_dir=ASSETS_DIR,
    )


if __name__ == "__main__":
    run()
