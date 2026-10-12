"""Main window (QMainWindow) assembling menus, tabs and the status bar.

Structure mirrors the original CHIRP layout (menubar + tabbed central
area + 3-field status bar), but styled with the shared design tokens
(logos/tokens preserved from mychirp/share/).
"""

import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
    QWidget,
)

from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.app_state import AppState, EditorSetState
from mychirp.pysideui.services.radio_service import get_service
from mychirp.pysideui.tabs.memories import MemoriesTab
from mychirp.pysideui.tabs.settings import SettingsTab
from mychirp.pysideui.tabs.welcome import WelcomeTab
from mychirp.pysideui.tabs.recent import RecentTab
from mychirp.pysideui.dialogs.clone import CloneDialog
from mychirp.pysideui.dialogs.about import AboutDialog

LOG = logging.getLogger(__name__)

ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "share"))


class RadioTabWidget(QTabWidget):
    """One opened radio: Memories | Banks | Settings inner tabs."""

    close_requested = Signal(object)

    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state

        self.memories = MemoriesTab(eset, state)
        self.addTab(self.memories, _("Memories"))

        if (getattr(eset.features, "has_bank", False)
                and hasattr(eset.radio, "get_bank_model")):
            try:
                from mychirp.pysideui.tabs.banks import BanksTab
                self.banks = BanksTab(eset, state)
                self.addTab(self.banks, _("Banks"))
            except Exception:
                LOG.exception("Failed to build banks tab")
                self.banks = None
        else:
            self.banks = None

        if eset.has_settings():
            self.settings = SettingsTab(eset, state)
            self.addTab(self.settings, _("Settings"))
        else:
            self.settings = None

    def refresh_data(self):
        self.memories.on_loaded = self._memories_loaded
        self.memories.load_memories()
        if self.settings:
            self.settings.load_settings()

    def _memories_loaded(self):
        if self.banks:
            self.banks.refresh()

    def apply_theme(self):
        self.memories.retheme()
        if self.banks:
            self.banks.retheme()
        if self.settings:
            self.settings.retheme()


class MainWindow(QMainWindow):
    """CHIRP-style main window with modern theming."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("MyChirp")

        self._build_menus_and_toolbar()
        self._build_statusbar()
        self._build_central()

        state.status_changed.connect(self.show_status)
        state.theme_changed.connect(self._apply_theme)
        state.editorset_added.connect(self._on_editorset_added)
        state.editorset_removed.connect(self._on_editorset_removed)

    # ----- construction -----
    def _build_menus_and_toolbar(self):
        self.toolbar = self.addToolBar(_("Main toolbar"))
        self.toolbar.setMovable(False)
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setIconSize(self.toolbar.iconSize() * 0.75)

        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(_("&File"))

        self.action_open = QAction(_("&Open..."), self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.pick_open)
        file_menu.addAction(self.action_open)

        file_menu.addSeparator()

        self.action_save = QAction(_("&Save"), self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self.save_current)
        file_menu.addAction(self.action_save)

        self.action_saveas = QAction(_("Save As..."), self)
        self.action_saveas.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_saveas.triggered.connect(
            lambda: self.save_current(as_new=True))
        file_menu.addAction(self.action_saveas)

        self.action_export = QAction(_("Export to CSV..."), self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.triggered.connect(self.export_current_csv)
        file_menu.addAction(self.action_export)

        file_menu.addSeparator()

        self.action_restore = QAction(_("Restore last session"), self)
        self.action_restore.setShortcut("Ctrl+Shift+T")
        self.action_restore.triggered.connect(self.restore_session)
        file_menu.addAction(self.action_restore)

        self.action_close_tab = QAction(_("Close Tab"), self)
        self.action_close_tab.setShortcut(QKeySequence.StandardKey.Close)
        self.action_close_tab.triggered.connect(self.close_current)
        file_menu.addAction(self.action_close_tab)

        file_menu.addSeparator()

        self.action_quit = QAction(_("&Quit"), self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        # Edit menu
        edit_menu = menubar.addMenu(_("&Edit"))
        self.action_copy = QAction(_("Copy"), self)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        edit_menu.addAction(self.action_copy)
        self.action_cut = QAction(_("Cut"), self)
        self.action_cut.setShortcut(QKeySequence.StandardKey.Cut)
        edit_menu.addAction(self.action_cut)
        self.action_paste = QAction(_("Paste"), self)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        edit_menu.addAction(self.action_paste)
        edit_menu.addSeparator()
        self.action_delete = QAction(_("Delete channel"), self)
        self.action_delete.setShortcut(QKeySequence.StandardKey.Delete)
        edit_menu.addAction(self.action_delete)
        edit_menu.addSeparator()
        self.action_undo = QAction(_("Undo"), self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(self.action_undo)
        self.action_redo = QAction(_("Redo"), self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        self.action_goto = QAction(_("Go to channel..."), self)
        self.action_goto.setShortcut(QKeySequence("Ctrl+G"))
        edit_menu.addAction(self.action_goto)
        self.action_find_next = QAction(_("Find next"), self)
        self.action_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        edit_menu.addAction(self.action_find_next)

        # View menu
        view_menu = menubar.addMenu(_("&View"))

        self.action_theme = QAction(self._theme_label(), self)
        self.action_theme.triggered.connect(self.state.toggle_theme)
        view_menu.addAction(self.action_theme)

        self.action_refresh = QAction(_("&Refresh data"), self)
        self.action_refresh.setShortcut(Qt.Key.Key_F5)
        self.action_refresh.triggered.connect(self.refresh_current)
        view_menu.addAction(self.action_refresh)

        self.action_session = QAction(self._session_label(), self)
        self.action_session.triggered.connect(self.toggle_session_restore)
        view_menu.addAction(self.action_session)

        # Radio menu
        radio_menu = menubar.addMenu(_("&Radio"))
        self.action_download = QAction(_("Download from radio"), self)
        self.action_download.setShortcut("Ctrl+D")
        self.action_download.triggered.connect(self.download_from_radio)
        radio_menu.addAction(self.action_download)
        self.action_upload = QAction(_("Upload to radio"), self)
        self.action_upload.setShortcut("Ctrl+U")
        self.action_upload.triggered.connect(self.upload_to_radio)
        radio_menu.addAction(self.action_upload)

        # Help menu
        help_menu = menubar.addMenu(_("&Help"))
        self.action_about = QAction(_("About"), self)
        self.action_about.triggered.connect(self.show_about)
        help_menu.addAction(self.action_about)

        # toolbar icons (shortcuts mirrored)
        logo = os.path.join(ASSETS_DIR, "mychirp-logo.png")
        if os.path.exists(logo):
            self.setWindowIcon(QIcon(logo))
        self.toolbar.addAction(self.action_download)
        self.toolbar.addAction(self.action_upload)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_save)
        self.toolbar.addAction(self.action_export)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_theme)

        def _mk_shortcut(action, fn):
            action.triggered.connect(fn)

        _mk_shortcut(self.action_copy,
                     lambda: self._mem_op("copy_selected"))
        _mk_shortcut(self.action_cut,
                     lambda: self._mem_op("cut_selected"))
        _mk_shortcut(self.action_paste,
                     lambda: self._mem_op("paste_selected"))
        _mk_shortcut(self.action_delete,
                     lambda: self._mem_op("delete_selected"))
        _mk_shortcut(self.action_undo, lambda: self._mem_op("undo"))
        _mk_shortcut(self.action_redo, lambda: self._mem_op("redo"))
        _mk_shortcut(self.action_goto,
                     lambda: self._mem_op("goto_channel_dialog"))
        _mk_shortcut(self.action_find_next,
                     lambda: self._mem_op("find_next"))

    def _build_central(self):
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._tab_close_requested)
        self.tabs.currentChanged.connect(self._update_statusbar_for_tab)
        self.setCentralWidget(self.tabs)

        self.welcome = WelcomeTab(self.state)
        self.recent = RecentTab(self.state)
        self.tabs.addTab(self.welcome, QIcon(), _("Welcome"))
        self.tabs.addTab(self.recent, QIcon(), _("Recent files"))
        self.tabs.tabBar().setTabButton(
            self.tabs.indexOf(self.welcome),
            self.tabs.tabBar().ButtonPosition.RightSide, None)
        self.tabs.tabBar().setTabButton(
            self.tabs.indexOf(self.recent),
            self.tabs.tabBar().ButtonPosition.RightSide, None)

    def _build_statusbar(self):
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(False)
        self._status_fields = [
            QLabel(""), QLabel(""), QLabel("")]
        for field in self._status_fields:
            self.status.addWidget(field, 1)

    # ----- helpers -----
    def show_status(self, message, field=0):
        if 0 <= field < len(self._status_fields):
            self._status_fields[field].setText(message)
            self._status_fields[field].setProperty("muted", field != 0)
            self._status_fields[field].style().unpolish(
                self._status_fields[field])
            self._status_fields[field].style().polish(
                self._status_fields[field])

    def _theme_label(self):
        return (_("Switch to Light Theme")
                if self.state.is_dark() else _("Switch to Dark Theme"))

    def _session_label(self):
        return (_("Disable session restore")
                if self.state.session_restore_enabled()
                else _("Enable session restore"))

    def _apply_theme(self, dark):
        from mychirp.pysideui.theme import apply_theme
        apply_theme(QApplication.instance(), dark)
        self.action_theme.setText(self._theme_label())
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if hasattr(view, "retheme"):
                try:
                    view.retheme()
                except Exception:
                    LOG.exception("retheme failed for tab %i", i)

    def _mem_op(self, method: str):
        es = self.current_editorset
        if es is None:
            return
        view = self.tabs.currentWidget()
        if isinstance(view, RadioTabWidget):
            mems = view.memories
        else:
            mems = None
        if mems is None:
            return
        fn = getattr(mems, method, None)
        if fn:
            fn()

    # ----- editorsets / tabs -----
    @property
    def current_editorset(self) -> EditorSetState | None:
        view = self.tabs.currentWidget()
        if isinstance(view, RadioTabWidget):
            return view.eset
        return None

    def _on_editorset_added(self, eset):
        view = RadioTabWidget(eset, self.state)
        index = self.tabs.addTab(view, QIcon(), eset.tab_title)
        self.tabs.setCurrentIndex(index)
        # Welcome tab is dropped once a real radio is open
        welcome_index = self.tabs.indexOf(self.welcome)
        if welcome_index >= 0:
            self.tabs.removeTab(welcome_index)
        view.refresh_data()
        self._update_statusbar_for_tab(index)

    def _on_editorset_removed(self, eset):
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if isinstance(view, RadioTabWidget) and view.eset is eset:
                self.tabs.removeTab(i)
                break
        if not any(isinstance(self.tabs.widget(i), RadioTabWidget)
                   for i in range(self.tabs.count())):
            self.tabs.addTab(self.welcome, _("Welcome"))
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

    def _tab_close_requested(self, index):
        view = self.tabs.widget(index)
        if isinstance(view, RadioTabWidget):
            self.state.remove_editorset(view.eset)

    def _update_statusbar_for_tab(self, index=None):
        if index is None:
            index = self.tabs.currentIndex()
        es = self.state.editorsets and self.current_editorset
        if isinstance(view := self.tabs.widget(index), RadioTabWidget):
            self.show_status(view.eset.radio_label, 1)
            self.show_status(
                _("Unsaved changes") if view.eset.modified else "", 2)
        else:
            self.show_status("", 1)
            self.show_status("", 2)

    # ----- file actions -----
    def pick_open(self):
        filename, _filter = QFileDialog.getOpenFileName(
            self, _("Open radio image"), "",
            "Radio image files (*.img *.csv *.chirp);;All files (*)")
        if filename:
            self.open_file(filename)

    def open_file(self, filename, record_recent=True):
        self.state.set_status(_("Opening %s...") % filename)
        service = get_service(self)

        def done(job):
            if job.error:
                self._error_dialog(_("Failed to open file"), job.error)
                return
            radio = job.result
            eset = EditorSetState(radio, filename)
            if record_recent:
                self.state.push_recent_file(filename)
            try:
                self.recent.refresh()
            except Exception:
                pass
            self.state.add_editorset(eset)
            self.state.set_status(
                _("Loaded %s") % os.path.basename(filename))

        service.open_file(filename, done)

    def save_current(self, as_new=False, target=None):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Nothing to save"))
            return
        if target is None and as_new:
            filename, _filter = QFileDialog.getSaveFileName(
                self, _("Save radio image"),
                eset.default_filename,
                "Radio image files (*.img *.csv);;All files (*)")
            if not filename:
                return
            target = filename
        filename = target or eset.filename
        eset.filename = filename
        self.state.set_status(_("Saving to %s...") % filename)
        service = get_service(self)

        def done(job):
            if job.error:
                self._error_dialog(_("Failed to save"), job.error)
            else:
                eset.modified = False
                self.state.set_status(_("Saved %s") % filename)
                self._update_statusbar_for_tab()

        service.save_radio(eset.radio, filename, done)

    def close_current(self):
        index = self.tabs.currentIndex()
        self._tab_close_requested(index)

    def export_current_csv(self):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        filename, _filter = QFileDialog.getSaveFileName(
            self, _("Export to CSV"),
            "%s.csv" % eset.default_filename.rsplit(".", 1)[0],
            "CSV files (*.csv);;All files (*)")
        if not filename:
            return
        self._do_export_csv(filename)

    def _do_export_csv(self, path):
        eset = self.current_editorset
        if not eset:
            return
        service = get_service(self)
        self.state.set_status(_("Exporting to %s...") % path)

        def done(job):
            if job.error:
                self.state.set_status(_("Export failed"))
                self._error_dialog(_("Failed to export"), job.error)
                return
            count = job.result or 0
            if not count:
                self.state.set_status(_("Nothing to export"))
                return
            self.state.set_status(
                _("Exported %i channels to %s") % (
                    count, os.path.basename(path)))

        service.export_csv(eset.radio, path, done)

    def restore_session(self):
        restored = self.state.restore_session()
        if restored:
            self.state.set_status(_("Restored %i radio(s)") % restored)
        else:
            self.state.set_status(_("Nothing to restore"))

    def toggle_session_restore(self):
        enabled = not self.state.session_restore_enabled()
        self.state.set_session_restore(enabled)
        self.action_session.setText(self._session_label())
        self.state.set_status(
            _("Session restore enabled") if enabled
            else _("Session restore disabled"))

    def refresh_current(self):
        view = self.tabs.currentWidget()
        if isinstance(view, RadioTabWidget):
            view.refresh_data()

    # ----- radio actions -----
    def download_from_radio(self):
        dlg = CloneDialog(self, self.state, mode="download")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pass  # dialog already pushed the editorset

    def upload_to_radio(self):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return

        reply = QMessageBox.question(
            self, _("Upload to radio"),
            _("Write the image back to the radio? This overwrites the "
              "radio memory. Continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        dlg = CloneDialog(self, self.state, mode="upload", eset=eset)
        dlg.exec()

    # ----- about -----
    def show_about(self):
        AboutDialog(self, self.state).exec()

    def _error_dialog(self, title, error):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(str(error))
        box.setIcon(QMessageBox.Icon.Warning)
        box.exec()

    # ----- events -----
    def keyPressEvent(self, event):
        key = event.key()
        mod = event.modifiers()
        if mod & Qt.KeyboardModifier.ControlModifier:
            es = self.current_editorset
            if es is None:
                return
            view = self.tabs.currentWidget()
            mems = getattr(view, "memories", None)
            if mems is None:
                return
            if key == Qt.Key.Key_A:
                mems.select_all()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.state.save_session()
        super().closeEvent(event)
