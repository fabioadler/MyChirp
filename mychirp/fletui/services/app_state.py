import logging
import os
import weakref

import flet as ft

from mychirp.wxui import config

LOG = logging.getLogger(__name__)

_states: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"
MODES = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)


class EditorSetState:
    """State of one opened radio (tab)."""

    def __init__(self, radio, filename):
        self.radio = radio
        self.filename = filename
        self.modified = not os.path.exists(filename)
        self.features = radio.get_features()
        self.memories = {}
        self.settings = None

    @property
    def tab_title(self):
        try:
            base = os.path.basename(self.filename)
            return base if base else self.default_filename
        except Exception:
            return self.default_filename

    @property
    def default_filename(self):
        vendor = getattr(self.radio, "VENDOR", "Radio")
        model = getattr(self.radio, "MODEL", "")
        return "%s.%s" % (vendor, getattr(self.radio, "FILE_EXTENSION", "img"))

    @property
    def radio_label(self):
        return "%s %s" % (getattr(self.radio, "VENDOR", ""),
                           getattr(self.radio, "MODEL", "")).strip()

    def has_settings(self):
        return bool(getattr(self.features, "has_settings", False))


class AppState:
    """Application-wide state shared by every screen.

    One instance per flet Page; stored on page.session so screens and
    dialogs can reach it without globals.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.conf = config.get()

        configured = self.conf.get("theme_mode", "state") or MODE_DARK
        self.theme_mode = configured if configured in MODES else MODE_DARK

        self.editorsets: list[EditorSetState] = []
        self.status_message = ""
        self.shell = None
        self._file_picker: ft.FilePicker | None = None

    # ----- theme -----
    def is_dark(self) -> bool:
        if self.theme_mode == MODE_DARK:
            return True
        if self.theme_mode == MODE_LIGHT:
            return False
        try:
            return self.page.platform_brightness == ft.Brightness.DARK
        except Exception:
            return False

    def toggle_theme(self):
        self.set_theme_mode(MODE_LIGHT if self.is_dark() else MODE_DARK)

    def set_theme_mode(self, mode: str):
        if mode not in MODES:
            return
        self.theme_mode = mode
        self.conf.set("theme_mode", mode, "state")
        dark = self.is_dark()
        self.page.theme_mode = (
            ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        )
        if self.shell:
            self.shell.apply_theme()

    # ----- status -----
    def set_status(self, message: str, field: int = 0):
        if self.shell:
            self.shell.set_status(message, field)

    # ----- editorsets -----
    def add_editorset(self, eset: EditorSetState, select: bool = True):
        self.editorsets.append(eset)
        if self.shell:
            self.shell.add_radio_tab(eset, select=select)

    def remove_editorset(self, eset: EditorSetState):
        if eset in self.editorsets:
            self.editorsets.remove(eset)
        if self.shell:
            self.shell.remove_radio_tab(eset)

    @property
    def current_editorset(self) -> EditorSetState | None:
        if self.shell:
            return self.shell.current_editorset
        return None

    # ----- recent files -----
    def get_recent_files(self) -> list[str]:
        raw = self.conf.get("last_open", "state") or ""
        return [x for x in raw.split("$") if x][:8]

    def push_recent_file(self, filename: str):
        files = self.get_recent_files()
        files = [filename] + [f for f in files if f != filename]
        files = files[:8]
        self.conf.set("last_open", "$".join(files), "state")


def get_state(page: ft.Page) -> AppState:
    """Return the AppState attached to the page (creating if needed)."""
    state = _states.get(page)
    if state is None:
        state = AppState(page)
        _states[page] = state
    return state
