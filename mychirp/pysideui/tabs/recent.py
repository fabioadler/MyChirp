"""Recent files tab: compact clickable list of the last 10 files."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mychirp.pysideui.i18n import _

_MAX_ITEMS = 10


class RecentTab(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(_("Recent files"))
        title.setProperty("heading", True)
        header.addWidget(title)
        header.addStretch(1)

        self.clear_btn = QPushButton(_("Clear recent files"))
        self.clear_btn.clicked.connect(self._on_clear)
        header.addWidget(self.clear_btn)

        self.refresh_btn = QPushButton(_("Refresh"))
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        sep = QLabel(" ")
        sep.setStyleSheet("border-bottom: 1px solid palette(mid);")
        layout.addWidget(sep)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget::item { padding: 6px 8px; }")
        self._list.itemClicked.connect(self._on_item)
        layout.addWidget(self._list, 1)

        self.refresh()

    def refresh(self):
        self._list.clear()

        recents = [
            f for f in self.state.get_recent_files() if os.path.exists(f)][:
            _MAX_ITEMS]
        if not recents:
            item = QListWidgetItem(_("No recent files yet"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setData(Qt.ItemDataRole.UserRole, None)
            self._list.addItem(item)
            return

        for fn in recents:
            name = os.path.basename(fn)
            dirname = os.path.dirname(fn)
            item = QListWidgetItem(_("%1 — %2").replace("%1", name).replace(
                "%2", dirname))
            item.setData(Qt.ItemDataRole.UserRole, fn)
            item.setToolTip(fn)
            self._list.addItem(item)

    def _on_item(self, item):
        fn = item.data(Qt.ItemDataRole.UserRole)
        if fn and self.state.main_window:
            self.state.main_window.open_file(fn)

    def _on_clear(self):
        reply = QMessageBox.question(
            self,
            _("Clear recent files?"),
            _("This removes the list only; the files on disk are not "
              "deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.state.clear_recent_files()
        self.refresh()
        self.state.set_status(_("Recent files cleared"))

    def retheme(self):
        self.refresh()
