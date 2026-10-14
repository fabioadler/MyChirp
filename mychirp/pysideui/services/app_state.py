"""Application state for the PySide6 UI (Qt-free logic mostly).

EditorSetState and AppState mirror the flet UI's app_state module but
swap the flet Page anchor for a plain QObject. Shared config keys and
semantics (recent files, session save/restore) are kept identical.
"""

import logging
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from mychirp import config
from mychirp.memory_ops import UndoStack

LOG = logging.getLogger(__name__)


MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"
MODES = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)

# Máximo de arquivos no histórico de recentes: reabrir promove à
# primeira posição; lotado, o mais antigo (11º) é descartado.
MAX_RECENT_FILES = 10


class EditorSetState(QObject):
    """State of one opened radio (tab)."""

    modified_changed = Signal(bool)

    def __init__(self, radio, filename, parent=None):
        super().__init__(parent)
        self.radio = radio
        self.filename = filename
        self._modified = not os.path.exists(filename)
        self.features = radio.get_features()
        self.memories = {}
        self.settings = None
        self.undo_stack = UndoStack()

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        value = bool(value)
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

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
        return "%s.%s" % (
            vendor, getattr(self.radio, "FILE_EXTENSION", "img"))

    @property
    def radio_label(self):
        label = "%s %s" % (getattr(self.radio, "VENDOR", ""),
                           getattr(self.radio, "MODEL", ""))
        return label.strip()

    def has_settings(self):
        return bool(getattr(self.features, "has_settings", False))


class AppState(QObject):
    """Application-wide state shared by every window/tab."""

    status_changed = Signal(str, int)           # (message, field)
    theme_changed = Signal(bool)                # dark
    editorset_added = Signal(object)            # EditorSetState
    editorset_removed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conf = config.get()

        configured = self.conf.get("theme_mode", "state") or MODE_DARK
        self.theme_mode = configured if configured in MODES else MODE_DARK

        self.editorsets: list[EditorSetState] = []
        self.status_message = ""
        self.main_window = None
        self.memory_clipboard: tuple | None = None

    # ----- theme -----
    def is_dark(self) -> bool:
        if self.theme_mode == MODE_DARK:
            return True
        if self.theme_mode == MODE_LIGHT:
            return False
        try:
            hints = QGuiApplication.styleHints()
            scheme = hints.colorScheme()
            # Qt6: ColorScheme.Light = 1, Dark = 2, Unknown = 0
            return int(scheme) == 2
        except Exception:
            return False

    def toggle_theme(self):
        self.set_theme_mode(MODE_LIGHT if self.is_dark() else MODE_DARK)

    def set_theme_mode(self, mode: str):
        if mode not in MODES:
            return
        self.theme_mode = mode
        self.conf.set("theme_mode", mode, "state")
        self.conf.save()
        dark = self.is_dark()
        self.theme_changed.emit(dark)

    # ----- status -----
    def set_status(self, message: str, field: int = 0):
        self.status_changed.emit(message, field)

    # ----- editorsets -----
    def add_editorset(self, eset: EditorSetState, select: bool = True):
        self.editorsets.append(eset)
        self.editorset_added.emit(eset)
        self.save_session()

    def remove_editorset(self, eset: EditorSetState):
        if eset in self.editorsets:
            self.editorsets.remove(eset)
        self.editorset_removed.emit(eset)
        self.save_session()

    @property
    def current_editorset(self) -> EditorSetState | None:
        if self.main_window:
            return self.main_window.current_editorset
        return None

    # ----- recent files -----
    def get_recent_files(self) -> list[str]:
        raw = self.conf.get("last_open", "state") or ""
        return [x for x in raw.split("$") if x][:MAX_RECENT_FILES]

    def push_recent_file(self, filename: str):
        files = self.get_recent_files()
        files = [filename] + [f for f in files if f != filename]
        files = files[:MAX_RECENT_FILES]
        self.conf.set("last_open", "$".join(files), "state")
        self.conf.save()

    def forget_file(self, filename: str):
        """Remove @filename dos recentes (last_open) e da última
        sessão (last_session). No-op se não constar em nenhum."""
        changed = False
        for key in ("last_open", "last_session"):
            raw = self.conf.get(key, "state") or ""
            files = [x for x in raw.split("$") if x]
            if filename in files:
                files.remove(filename)
                self.conf.set(key, "$".join(files), "state")
                changed = True
        if changed:
            self.conf.save()

    def clear_recent_files(self):
        """Forget the recent files list and the persisted session."""
        try:
            self.conf.remove_option("last_open", "state")
        except Exception:
            LOG.debug("No recent files to clear")
        try:
            self.conf.remove_option("last_session", "state")
        except Exception:
            LOG.debug("No session to clear")
        self.conf.save()

    # ----- session persistence -----
    def save_session(self):
        """Persist the open radios and theme for the next startup."""
        files = [
            eset.filename for eset in self.editorsets
            if os.path.exists(eset.filename)
        ]
        self.conf.set("last_session", "$".join(files), "state")
        self.conf.set_bool("restore_session",
                           self.session_restore_enabled(), "state")
        self.conf.save()

    def session_restore_enabled(self) -> bool:
        return self.conf.get_bool("restore_session", "state", default=True)

    def set_session_restore(self, enabled: bool):
        self.conf.set_bool("restore_session", bool(enabled), "state")
        self.conf.save()

    def restore_session(self) -> tuple[int, list[str]]:
        """Reopen the radios saved by save_session.

        Files from the last session that no longer exist on disk are
        purged from both the recent list and the session, and reported
        back so the caller can show a single aggregated warning.

        Returns (restored_count, purged_files).
        """
        if not self.session_restore_enabled() or not self.main_window:
            return 0, []
        raw = self.conf.get("last_session", "state") or ""
        restored = 0
        purged = []
        for filename in [x for x in raw.split("$") if x]:
            if not os.path.exists(filename):
                # Arquivo apagado: sai dos recentes e da sessão;
                # chamador mostra o aviso agregado
                self.forget_file(filename)
                purged.append(filename)
                continue
            if filename in (es.filename for es in self.editorsets):
                continue
            try:
                self.main_window.open_file(filename, record_recent=False)
                restored += 1
            except Exception:
                LOG.exception("Failed to restore %s", filename)
        return restored, purged
