"""Main window (QMainWindow) assembling menus, tabs and the status bar.

Structure mirrors the original CHIRP layout (menubar + tabbed central
area + 3-field status bar), but styled with the shared design tokens
(logos/tokens preserved from mychirp/share/).
"""

import logging
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
)

from mychirp.pysideui.i18n import (
    _,
    available_languages,
    language_display_name,
    set_language,
    get_current_language,
)
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


class NetworkSourceDialog(QDialog):
    """Prompt for a host:port network radio source."""

    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle(_("Network source..."))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.address = QLineEdit()
        self.address.setPlaceholderText(_("hostname:port"))
        last = state.conf.get("network_source_last", "state")
        if last:
            self.address.setText(last)
        form.addRow(_("Source:"), self.address)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self):
        address = self.address.text().strip()
        if ":" not in address:
            QMessageBox.warning(
                self, _("Network source"),
                _("Enter the source as host:port"))
            return
        host, _sep, port = address.rpartition(":")
        try:
            from mychirp.sources import base as _base
            radio = _base.NetworkResultRadio()
            radio._nethost = host
            radio._netport = int(port)
        except Exception:
            LOG.exception("Failed to create network radio source")
            QMessageBox.warning(
                self, _("Network source"),
                _("Could not create the network radio source."))
            return
        self.state.conf.set("network_source_last", address, "state")
        self.state.conf.save()
        base = "Network_%s_%s" % (host, port)
        eset = EditorSetState(radio, "%s.img" % base.replace(" ", "_"))
        self.state.add_editorset(eset)
        self.state.set_status(_("Added network source %s") % address)
        super().accept()


class MainWindow(QMainWindow):
    """CHIRP-style main window with modern theming."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("MyChirp")

        # 16:9 default with a larger base font, sized so the memory grid
        # and settings forms fit without resizing the window on 1080p
        # screens (falls back to 80% of smaller displays).
        self._apply_window_geometry()
        self._build_menus()
        self._build_statusbar()
        self._build_central()

        state.status_changed.connect(self.show_status)
        state.theme_changed.connect(self._apply_theme)
        state.editorset_added.connect(self._on_editorset_added)
        state.editorset_removed.connect(self._on_editorset_removed)

        self._known_ports = set()
        self._hotplug_label = None
        self._hotplug_button = None
        self._hotplug_timer = QTimer(self)
        self._hotplug_timer.setInterval(1500)
        self._hotplug_timer.timeout.connect(self._poll_serial_ports)
        self._hotplug_timer.start()

    # ----- hotplug programmer detection -----
    def _poll_serial_ports(self):
        from mychirp.pysideui.services.radio_service import list_serial_ports
        from mychirp.pysideui.services.serial_probe import (
            is_programmer_device)
        try:
            current = set(list_serial_ports())
        except Exception:
            return
        new = current - self._known_ports
        self._known_ports = current
        if not new:
            return
        for port in sorted(new):
            if is_programmer_device(port):
                self._notify_programmer_port(port)
                break

    def _notify_programmer_port(self, port):
        """Show a non-modal statusbar hint with a connect button."""
        if self._clone_active():
            return
        self._clear_hotplug_widgets()
        self._hotplug_label = QLabel(
            _("Programming cable detected on %s — use it?") % port)
        self._hotplug_button = QToolButton(self)
        self._hotplug_button.setText(_("Connect"))
        self._hotplug_button.setAutoRaise(True)
        self._hotplug_button.clicked.connect(
            lambda checked=False, p=port: self._on_hotplug_connect(p))
        self.status.addPermanentWidget(self._hotplug_label)
        self.status.addPermanentWidget(self._hotplug_button)
        self._hotplug_label.show()
        self._hotplug_button.show()

    def _clear_hotplug_widgets(self):
        for widget in (self._hotplug_label, self._hotplug_button):
            if widget is not None:
                self.status.removeWidget(widget)
                widget.deleteLater()
        self._hotplug_label = None
        self._hotplug_button = None

    def _clone_active(self):
        app = QApplication.instance()
        return app is not None and app.activeModalWidget() is not None

    def _on_hotplug_connect(self, port):
        self._clear_hotplug_widgets()
        if port:
            self.state.conf.set("clone_last_port", port, "state")
            self.state.conf.save()
        self.download_from_radio()

    # ----- window geometry -----
    def _apply_window_geometry(self):
        """16:9 default, large font. Never exceeds available screen."""
        screen = QApplication.primaryScreen().availableGeometry()
        # comfortable 16:9 window fitting most modern displays
        w = min(1600, screen.width() - 40)
        h = min(950, screen.height() - 60)
        self.resize(w, h)
        # Center on screen
        x = (screen.width() - w) // 2
        y = (screen.height() - h) // 2
        self.move(x, y)

    # ----- construction -----
    def _build_menus(self):
        menubar = self.menuBar()

        # File menu
        self._menu_file = menubar.addMenu(_("&File"))

        self.action_open = QAction(_("&Open..."), self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self.pick_open)
        self._menu_file.addAction(self.action_open)

        self._menu_file.addSeparator()

        self.action_save = QAction(_("&Save"), self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self.save_current)
        self._menu_file.addAction(self.action_save)

        self.action_saveas = QAction(_("Save As..."), self)
        self.action_saveas.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.action_saveas.triggered.connect(
            lambda: self.save_current(as_new=True))
        self._menu_file.addAction(self.action_saveas)

        self.action_export = QAction(_("Export to CSV..."), self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_export.triggered.connect(self.export_current_csv)
        self._menu_file.addAction(self.action_export)

        self.action_export_itm = QAction(_("Export to ITM..."), self)
        self.action_export_itm.triggered.connect(
            lambda: self.export_current_csv(fmt='itm'))
        self._menu_file.addAction(self.action_export_itm)

        self.action_export_hmk = QAction(_("Export to HMK..."), self)
        self.action_export_hmk.triggered.connect(
            lambda: self.export_current_csv(fmt='hmk'))
        self._menu_file.addAction(self.action_export_hmk)

        self._menu_file.addSeparator()

        self._menu_file.addSeparator()

        self.action_print = QAction(_("&Print..."), self)
        self.action_print.setShortcut(QKeySequence.StandardKey.Print)
        self.action_print.triggered.connect(self.print_current)
        self._menu_file.addAction(self.action_print)

        self.action_import = QAction(_("&Import..."), self)
        self.action_import.triggered.connect(self.import_into_current)
        self._menu_file.addAction(self.action_import)


        self._menu_file.addSeparator()

        self.action_restore = QAction(_("Restore last session"), self)
        self.action_restore.setShortcut("Ctrl+Shift+T")
        self.action_restore.triggered.connect(self.restore_session)
        self._menu_file.addAction(self.action_restore)

        self.action_close_tab = QAction(_("Close Tab"), self)
        self.action_close_tab.setShortcut(QKeySequence.StandardKey.Close)
        self.action_close_tab.triggered.connect(self.close_current)
        self._menu_file.addAction(self.action_close_tab)

        self._menu_file.addSeparator()

        self.action_quit = QAction(_("&Quit"), self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.triggered.connect(self.close)
        self._menu_file.addAction(self.action_quit)

        # Edit menu
        self._menu_edit = menubar.addMenu(_("&Edit"))
        self.action_copy = QAction(_("Copy"), self)
        self.action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self._menu_edit.addAction(self.action_copy)
        self.action_cut = QAction(_("Cut"), self)
        self.action_cut.setShortcut(QKeySequence.StandardKey.Cut)
        self._menu_edit.addAction(self.action_cut)
        self.action_paste = QAction(_("Paste"), self)
        self.action_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self._menu_edit.addAction(self.action_paste)
        self._menu_edit.addSeparator()
        self.action_delete = QAction(_("Delete channel"), self)
        self.action_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self._menu_edit.addAction(self.action_delete)
        self._menu_edit.addSeparator()
        self.action_undo = QAction(_("Undo"), self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._menu_edit.addAction(self.action_undo)
        self.action_redo = QAction(_("Redo"), self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._menu_edit.addAction(self.action_redo)
        self._menu_edit.addSeparator()
        self.action_goto = QAction(_("Go to channel..."), self)
        self.action_goto.setShortcut(QKeySequence("Ctrl+G"))
        self._menu_edit.addAction(self.action_goto)
        self.action_find_next = QAction(_("Find next"), self)
        self.action_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        self._menu_edit.addAction(self.action_find_next)

        # View menu
        self._menu_view = menubar.addMenu(_("&View"))

        self.action_theme = QAction(self._theme_label(), self)
        self.action_theme.triggered.connect(self.state.toggle_theme)
        self._menu_view.addAction(self.action_theme)

        self.action_refresh = QAction(_("&Refresh data"), self)
        self.action_refresh.setShortcut(Qt.Key.Key_F5)
        self.action_refresh.triggered.connect(self.refresh_current)
        self._menu_view.addAction(self.action_refresh)

        self.action_session = QAction(self._session_label(), self)
        self.action_session.triggered.connect(self.toggle_session_restore)
        self._menu_view.addAction(self.action_session)

        self.action_developer_mode = QAction(_("Developer mode"), self)
        self.action_developer_mode.setCheckable(True)
        self.action_developer_mode.setChecked(
            self.state.conf.get_bool("developer_mode", "state",
                                     default=False))
        self.action_developer_mode.triggered.connect(
            self.toggle_developer_mode)
        self._menu_view.addAction(self.action_developer_mode)

        self.action_devtools = QAction(_("Developer tools (raw dump)"), self)
        self.action_devtools.triggered.connect(self.show_devtools)
        self._menu_view.addAction(self.action_devtools)

        # Language submenu
        self._build_language_menu(self._menu_view)

        bandplan_menu = self._menu_view.addMenu(_("Band plan"))
        self._bandplan_group = QActionGroup(self)
        self._bandplan_group.setExclusive(True)
        current_plan = self.state.conf.get("set_bandplan", "state") or ""
        for shortname, details in sorted(
                self._bandplan_registry().items(),
                key=lambda item: item[1][0]):
            name = details[0]
            act = QAction(name, self)
            act.setCheckable(True)
            act.setData(shortname)
            act.setChecked(shortname == current_plan)
            act.triggered.connect(
                lambda checked, sn=shortname, label=name:
                    self.set_bandplan(sn, label))
            self._bandplan_group.addAction(act)
            bandplan_menu.addAction(act)
        if not self._bandplan_group.checkedAction() and bandplan_menu.actions():
            first = bandplan_menu.actions()[0]
            first.setChecked(True)

        # Radio menu
        self._menu_radio = menubar.addMenu(_("&Radio"))
        self.action_download = QAction(_("Download from radio"), self)
        self.action_download.setShortcut("Ctrl+D")
        self.action_download.triggered.connect(self.download_from_radio)
        self._menu_radio.addAction(self.action_download)
        self.action_upload = QAction(_("Upload to radio"), self)
        self.action_upload.setShortcut("Ctrl+U")
        self.action_upload.triggered.connect(self.upload_to_radio)
        self._menu_radio.addAction(self.action_upload)

        self.action_fw_dump = QAction(_("Firmware dump..."), self)
        self.action_fw_dump.setShortcut("Ctrl+Shift+D")
        self.action_fw_dump.setToolTip(
            _("Read-only raw dump of the radio memory (clone image or "
              "full window), saved to ~/.chirp/fw-backups/"))
        self.action_fw_dump.triggered.connect(self.firmware_dump)
        self._menu_radio.addAction(self.action_fw_dump)
        self.action_fw_restore = QAction(_("Firmware restore (write)..."),
                                         self)
        self.action_fw_restore.setShortcut("Ctrl+Shift+W")
        self.action_fw_restore.setToolTip(
            _("WRITE a clone image into the radio memory window "
              "(h777 and UV-5R-aux-first families; double "
              "confirmation + automatic pre/post backups)"))
        self.action_fw_restore.triggered.connect(self.firmware_restore)
        self._menu_radio.addAction(self.action_fw_restore)

        self._menu_radio.addSeparator()

        self.action_network_source = QAction(_("Network source..."), self)
        self.action_network_source.triggered.connect(self.open_network_source)
        self._menu_radio.addAction(self.action_network_source)

        self._menu_radio.addSeparator()

        query_menu = self._menu_radio.addMenu(_("Query Source"))
        from mychirp.pysideui.dialogs.query_source import SOURCES
        for source_name, (_module, _class, label) in SOURCES.items():
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked=False, name=source_name:
                    self.query_source(name))
            query_menu.addAction(action)

        # Help menu
        self._menu_help = menubar.addMenu(_("&Help"))
        self.action_report_bug = QAction(_("Report a bug..."), self)
        self.action_report_bug.triggered.connect(self.report_bug)
        self._menu_help.addAction(self.action_report_bug)
        self.action_clear_logs = QAction(_("Clear logs"), self)
        self.action_clear_logs.triggered.connect(self.clear_logs)
        self._menu_help.addAction(self.action_clear_logs)
        self.action_about = QAction(_("About"), self)
        self.action_about.triggered.connect(self.show_about)
        self._menu_help.addAction(self.action_about)

        # window icon
        logo = os.path.join(ASSETS_DIR, "mychirp-logo.png")
        if os.path.exists(logo):
            self.setWindowIcon(QIcon(logo))

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
        # Qt pode recriar o botão de fechar ao arrastar abas
        self.tabs.tabBar().tabMoved.connect(self._hide_fixed_tab_buttons)
        self.setCentralWidget(self.tabs)

        self.welcome = WelcomeTab(self.state)
        self.recent = RecentTab(self.state)
        self.tabs.addTab(self.welcome, QIcon(), _("Welcome"))
        self.tabs.addTab(self.recent, QIcon(), _("Recent files"))
        self._hide_fixed_tab_buttons()

    def _hide_tab_close_button(self, widget):
        """Remove o botão de fechar da aba de @widget: Welcome e Recent
        nunca fecham (o botão só fica nas abas de arquivos abertos)."""
        index = self.tabs.indexOf(widget)
        if index >= 0:
            bar = self.tabs.tabBar()
            for side in (bar.ButtonPosition.LeftSide,
                         bar.ButtonPosition.RightSide):
                bar.setTabButton(index, side, None)

    def _hide_fixed_tab_buttons(self, *args):
        """Reaplica a remoção dos botões de Welcome/Recent (após
        re-adicionar a Welcome ou mover abas)."""
        self._hide_tab_close_button(self.welcome)
        self._hide_tab_close_button(self.recent)

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
        self._apply_developer_tab(view)
        eset.modified_changed.connect(
            lambda _mod, v=view: self._update_tab_title(v))
        self._update_tab_title(view)
        view.refresh_data()
        self._update_statusbar_for_tab(index)

    def _update_tab_title(self, view):
        """Prefix the tab with '*' while the editorset has unsaved
        changes (modified flag mirrors the original CHIRP)."""
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is view:
                title = view.eset.tab_title
                if view.eset.modified:
                    title = "* %s" % title
                self.tabs.setTabText(i, title)
                break

    def _on_editorset_removed(self, eset):
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if isinstance(view, RadioTabWidget) and view.eset is eset:
                self.tabs.removeTab(i)
                break
        if not any(isinstance(self.tabs.widget(i), RadioTabWidget)
                   for i in range(self.tabs.count())):
            self.tabs.addTab(self.welcome, _("Welcome"))
            # re-adicionada: sem botão de fechar (Welcome nunca fecha)
            self._hide_tab_close_button(self.welcome)
            self.tabs.setCurrentIndex(self.tabs.count() - 1)

    UNSAVED_SAVE = "save"
    UNSAVED_DISCARD = "discard"
    UNSAVED_CANCEL = "cancel"

    def _prompt_unsaved(self, eset):
        """Ask what to do with an editorset that has unsaved changes.
        Returns UNSAVED_SAVE / UNSAVED_DISCARD / UNSAVED_CANCEL."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_("Unsaved changes"))
        box.setText(
            _("Save changes to %s before closing?") % eset.tab_title)
        box.setInformativeText(
            _("If you don't save, the changes will be lost."))
        save_btn = box.addButton(
            _("Save"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(
            _("Don't Save"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_btn:
            return self.UNSAVED_SAVE
        if clicked is discard_btn:
            return self.UNSAVED_DISCARD
        return self.UNSAVED_CANCEL

    def _save_eset_blocking(self, eset):
        """Save synchronously (GUI thread) for close prompts.
        Returns True when the image was actually written."""
        filename = eset.filename
        if not filename or not os.path.exists(filename):
            filename, _filter = QFileDialog.getSaveFileName(
                self, _("Save radio image"), eset.default_filename,
                "Radio image files (*.img *.csv);;All files (*)")
            if not filename:
                return False
            eset.filename = filename
        try:
            eset.radio.save(filename)
        except Exception as e:
            self._error_dialog(_("Failed to save"), e)
            return False
        eset.modified = False
        self.state.set_status(_("Saved %s") % filename)
        return True

    def _tab_close_requested(self, index):
        view = self.tabs.widget(index)
        if isinstance(view, RadioTabWidget):
            eset = view.eset
            if eset.modified:
                action = self._prompt_unsaved(eset)
                if action == self.UNSAVED_CANCEL:
                    return
                if action == self.UNSAVED_SAVE and not \
                        self._save_eset_blocking(eset):
                    return
            self.state.remove_editorset(eset)

    def _update_statusbar_for_tab(self, index=None):
        if index is None:
            index = self.tabs.currentIndex()
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
        # Arquivo apagado que consta nos recentes/sessão: purga dos dois,
        # avisa com pop-up e não tenta abrir (a sessão é pré-filtrada no
        # boot, então este pop-up por arquivo cobre o clique na lista)
        known = (filename in self.state.get_recent_files() or
                 filename in (self.state.conf.get("last_session", "state")
                              or "").split("$"))
        if not os.path.exists(filename) and known:
            self.state.forget_file(filename)
            try:
                self.recent.refresh()
            except Exception:
                pass
            self.warn_deleted_files([filename])
            self.state.set_status(
                _("File deleted: %s") % os.path.basename(filename))
            return

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

    def import_into_current(self):
        """CHIRP-next parity: File > Import merges another image/CSV into
        the currently open radio (via import_logic.import_mem), instead
        of opening a separate tab."""
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        filename, _filter = QFileDialog.getOpenFileName(
            self, _("Import into open radio"), "",
            "Radio image files (*.img *.csv *.chirp);;All files (*)")
        if not filename:
            return
        self.state.set_status(_("Importing %s...") % filename)
        service = get_service(self)

        def _do_import():
            from mychirp import directory
            src = directory.get_radio_by_image(filename)
            from mychirp import import_logic
            count = 0
            for number, mem in src.get_memories():
                if mem.empty:
                    continue
                if not isinstance(number, int):
                    continue
                try:
                    import_logic.import_mem(
                        eset.radio,
                        src.get_features(),
                        mem,
                        overrides={"number": number, "empty": False})
                    count += 1
                except Exception as e:
                    LOG.warning("import %s failed: %s", number, e)
            return count

        def done(job):
            if job.error:
                self._error_dialog(_("Import failed"), job.error)
                self.state.set_status("")
                return
            eset.modified = True
            self.state.set_status(
                _("Imported %i channel(s)") % job.result)
            # Reload the grid
            view = self.tabs.currentWidget()
            if isinstance(view, RadioTabWidget):
                view.refresh_data()

        service.run_memory_op(_do_import, eset.radio, on_done=done)

    def export_current_csv(self, fmt="csv"):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        default_name = "%s.%s" % (
            eset.default_filename.rsplit(".", 1)[0], fmt)
        filename, _filter = QFileDialog.getSaveFileName(
            self, _("Export to %s") % fmt.upper(),
            default_name,
            "%s files (*.%s);;All files (*)" % (fmt.upper(), fmt))
        if not filename:
            return
        self._do_export_csv(filename, fmt)

    def _do_export_csv(self, path, fmt="csv"):
        eset = self.current_editorset
        if not eset:
            return
        self.state.set_status(_("Exporting to %s...") % path)

        def _export(fmt_name=fmt, out_path=path, radio=eset.radio,
                    features=eset.features):
            if fmt_name == "csv":
                from mychirp import memory_ops
                return memory_ops.export_csv(radio, out_path)
            # Kenwood ITM / HMK use the same CSV writer but via the
            # specialised driver classes that emit compatible headers
            radio_cls = None
            if fmt_name == "itm":
                from mychirp.drivers.kenwood_itm import ITMRadio
                radio_cls = ITMRadio
            elif fmt_name == "hmk":
                from mychirp.drivers.kenwood_hmk import HMKRadio
                radio_cls = HMKRadio
            if radio_cls is None:
                return 0

            radio_out = radio_cls(None)
            count = 0
            lo, hi = features.memory_bounds
            for number in range(lo, hi + 1):
                mem = radio.get_memory(number)
                if mem.empty or not isinstance(mem.number, int):
                    continue
                radio_out.set_memory(mem)
                count += 1
            if count:
                radio_out.save(out_path)
            return count

        svc = get_service(self)
        svc.run_memory_op(_export, eset.radio, on_done=self._export_done)

    def _export_done(self, job):
        self.state.set_status("")
        if job.error:
            self.state.set_status(_("Export failed"))
            self._error_dialog(_("Failed to export"), job.error)
            return
        count = job.result or 0
        if not count:
            self.state.set_status(_("Nothing to export"))
            return
        self.state.set_status(
            _("Exported %i channels to %s")
            % (count, os.path.basename(job.result
               if isinstance(job.result, str) else "")))

    def print_current(self):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        except ImportError:
            self.state.set_status(_("Printing not available"))
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        from PySide6.QtGui import QTextDocument
        html = self._build_print_html(eset)
        doc = QTextDocument()
        doc.setHtml(html)
        doc.print(printer)
        self.state.set_status(_("Print sent"))

    def _build_print_html(self, eset):
        def esc(s):
            return str(s).replace("&", "&amp;").replace(
                "<", "&lt;").replace(">", "&gt;")
        rows = []
        rows.append("<h2>%s</h2>" % esc(eset.radio_label))
        rows.append(
            "<table border='1' cellspacing='0' cellpadding='4'>"
            "<tr><th>Loc</th><th>Name</th><th>Freq (MHz)</th>"
            "<th>Duplex</th><th>Offset</th><th>Tone</th><th>Power</th></tr>")
        mems = sorted(eset.memories.items(),
                      key=lambda kv: (isinstance(kv[0], str), kv[0]))
        for _n, mem in mems:
            if mem.empty:
                continue
            rows.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                "<td>%s</td><td>%s</td><td>%s</td></tr>" % (
                    esc(getattr(mem, "extd_number", None) or mem.number),
                    esc(mem.name or ""),
                    "%.5f" % (mem.freq / 1e6) if mem.freq else "",
                    esc(mem.duplex or ""), esc(
                        "%.5f" % (mem.offset / 1e6) if mem.offset else ""),
                    esc(mem.rtone if mem.rtone else ""),
                    esc(mem.power or ""),
                ))
        rows.append("</table>")
        return "".join(rows)

    def warn_deleted_files(self, files):
        """Pop-up de arquivos apagados: um nome único (clique em um
        recente) ou agregado (restauração da sessão no boot)."""
        from PySide6.QtWidgets import QMessageBox
        files = [f for f in files if f]
        if not files:
            return
        if len(files) == 1:
            QMessageBox.warning(
                self, _("File not found"),
                _("The file %s was deleted from disk. "
                  "It was removed from the recent list.")
                % files[0])
        else:
            listing = "\n".join("- %s" % f for f in files)
            QMessageBox.warning(
                self, _("Files not found"),
                _("The following files were deleted from disk and were "
                  "removed from the recent list:\n%s") % listing)

    def restore_session(self):
        restored, purged = self.state.restore_session()
        if purged:
            self.warn_deleted_files(purged)
            try:
                self.recent.refresh()
            except Exception:
                pass
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

    def open_network_source(self):
        dlg = NetworkSourceDialog(self, self.state)
        dlg.exec()

    def firmware_dump(self):
        eset = self.current_editorset
        from mychirp.pysideui.dialogs.fw_dump import FirmwareDumpDialog
        FirmwareDumpDialog(self, self.state, eset=eset).exec()

    def firmware_restore(self):
        eset = self.current_editorset
        from mychirp.pysideui.dialogs.fw_restore import FirmwareRestoreDialog
        FirmwareRestoreDialog(self, self.state, eset=eset).exec()

    # ----- band plan -----
    def _bandplan_registry(self):
        """Known band plans: {shortname: (display name, module)}."""
        from mychirp import bandplan
        return bandplan.BandPlans(self.state.conf).plans

    def set_bandplan(self, shortname, label):
        try:
            self.state.conf.set("set_bandplan", shortname, "state")
            for plan_shortname in self._bandplan_registry():
                self.state.conf.set_bool(
                    plan_shortname, plan_shortname == shortname, "bandplan")
            self.state.conf.save()
            for i in range(self.tabs.count()):
                view = self.tabs.widget(i)
                if isinstance(view, RadioTabWidget):
                    view.memories.retheme()
            self.state.set_status(_("Band plan: %s") % label)
        except Exception:
            LOG.exception("Failed to set band plan")

    # ----- language menu -----
    def _build_language_menu(self, parent_menu):
        """Build/rebuild the View → Language submenu.

        Rebuildable at runtime to reflect the current language choice
        immediately after a switch.
        """
        # Remove existing Language menu if present
        old = getattr(self, "_language_menu", None)
        if old:
            parent_menu.removeAction(old.menuAction())
            old.deleteLater()

        lang_menu = parent_menu.addMenu(_("Language"))
        self._language_menu = lang_menu
        self._language_actions = {}

        current = get_current_language()  # None = system default
        langs = available_languages()

        # "System default" action
        act_sys = QAction(_("System default"), self)
        act_sys.setCheckable(True)
        act_sys.setChecked(current is None)
        act_sys.setData(None)
        act_sys.triggered.connect(
            lambda checked, a=act_sys: self._on_language_change(a))
        lang_menu.addAction(act_sys)
        self._language_actions[None] = act_sys

        lang_menu.addSeparator()

        # Available languages
        for code in sorted(langs, key=lambda c: language_display_name(c)):
            name = language_display_name(code)
            act = QAction(name, self)
            act.setCheckable(True)
            act.setChecked(code == current)
            act.setData(code)
            act.triggered.connect(
                lambda checked, a=act: self._on_language_change(a))
            lang_menu.addAction(act)
            self._language_actions[code] = act

    def _on_language_change(self, action):
        """Handle language selection from the menu."""
        lang_code = action.data()  # None for system default
        if lang_code == get_current_language():
            return  # already active
        if not set_language(lang_code):
            return
        # Rebuild Language submenu to update checkmarks
        self._build_language_menu(self._menu_view)
        # Update immediate UI texts (menu bar, status tip, window title)
        self._refresh_ui_texts()
        self.state.set_status(_("Language changed to %s") %
                              (language_display_name(lang_code)
                               if lang_code else _("System default")))

    def _refresh_ui_texts(self):
        """Refresh texts that are cached on the main window.

        Called after language change; re-translates menu titles and
        action texts that were set once at startup. Widgets inside tabs
        will update when they are recreated (e.g., tab switch, dialog
        reopen).
        """
        self._menu_file.setTitle(_("&File"))
        self._menu_edit.setTitle(_("&Edit"))
        self._menu_view.setTitle(_("&View"))
        self._menu_radio.setTitle(_("&Radio"))
        self._menu_help.setTitle(_("&Help"))

        # Theme action label
        self.action_theme.setText(self._theme_label())
        # Session action label
        self.action_session.setText(self._session_label())
        # Developer tools
        self.action_devtools.setText(_("Developer tools (raw dump)"))
        # Band plan menu title (rebuilt on language change via _build_language_menu)
        # Window title
        self.setWindowTitle("MyChirp")
        self.state.set_status(_("Ready"))

        # Permanent tabs (Welcome / Recent files): tab titles + cached
        # texts inside them re-translate instantly on language switch.
        idx = self.tabs.indexOf(self.welcome)
        if idx >= 0:
            self.tabs.setTabText(idx, _("Welcome"))
            self.welcome.retranslate()
        idx = self.tabs.indexOf(self.recent)
        if idx >= 0:
            self.tabs.setTabText(idx, _("Recent files"))
            self.recent.retranslate()

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

    def query_source(self, source_name):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        from mychirp.pysideui.dialogs.query_source import QuerySourceDialog
        dlg = QuerySourceDialog(self, self.state, eset, source_name)
        dlg.exec()

    def developer_mode_enabled(self) -> bool:
        return self.state.conf.get_bool("developer_mode", "state",
                                        default=False)

    def toggle_developer_mode(self):
        enabled = self.action_developer_mode.isChecked()
        self.state.conf.set_bool("developer_mode", enabled, "state")
        self.state.conf.save()
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if isinstance(view, RadioTabWidget):
                self._apply_developer_tab(view)
        self.state.set_status(
            _("Developer mode enabled") if enabled
            else _("Developer mode disabled"))

    def _apply_developer_tab(self, view):
        """Show/hide the Developer inner tab on a RadioTabWidget."""
        has_tab = hasattr(view, "developer") and view.developer is not None
        want_tab = self.developer_mode_enabled()
        if want_tab and not has_tab:
            try:
                from mychirp.pysideui.tabs.devtools import DeveloperTab
                view.developer = DeveloperTab(view.eset, self.state)
                view.addTab(view.developer, _("Developer"))
            except Exception:
                LOG.exception("Failed to build developer tab")
                view.developer = None
        elif has_tab and not want_tab:
            index = view.indexOf(view.developer)
            if index >= 0:
                view.removeTab(index)
            view.developer.deleteLater()
            view.developer = None

    def show_devtools(self):
        if not self.developer_mode_enabled():
            self.state.set_status(
                _("Enable View > Developer mode first"))
        from mychirp.pysideui.dialogs.devtools import DeveloperDialog
        DeveloperDialog(self, self.state, self.current_editorset).exec()

    def report_bug(self):
        # Popup de contato (logos + e-mail do suporte) + cópia dos
        # últimos logs: o usuário escreve e envia o próprio e-mail.
        from mychirp.pysideui.dialogs.devtools import BugReportDialog
        BugReportDialog(self, self.state, self.current_editorset).exec()

    def clear_logs(self):
        """Limpa o histórico do log do sistema (logs/log.txt)."""
        from mychirp import logger as chirp_logger
        reply = QMessageBox.question(
            self, _("Clear logs"),
            _("Clear the system log history (logs/log.txt)?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        chirp_logger.Logger.instance.clear_project_log()
        self.state.set_status(_("Logs cleared"))

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
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if not (isinstance(view, RadioTabWidget) and view.eset.modified):
                continue
            action = self._prompt_unsaved(view.eset)
            if action == self.UNSAVED_CANCEL:
                event.ignore()
                return
            if action == self.UNSAVED_SAVE and not \
                    self._save_eset_blocking(view.eset):
                event.ignore()
                return
        self.state.save_session()
        super().closeEvent(event)
