"""Recent files tab: cards with name, path, mtime, one-click open."""

import os
import time

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from mychirp.pysideui.i18n import _
from mychirp.pysideui.theme import AppColors

_CARD_MAX_W = 360


class RecentTab(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._layout_root = QVBoxLayout(self)
        self._layout_root.setContentsMargins(24, 24, 24, 24)
        self._layout_root.setSpacing(12)

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

        self._layout_root.addLayout(header)

        sep = QLabel(" ")
        sep.setStyleSheet("border-bottom: 1px solid palette(mid);")
        self._layout_root.addWidget(sep)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._cards = QGridLayout(self._content)
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(12)
        self._scroll.setWidget(self._content)
        self._layout_root.addWidget(self._scroll, 1)

        self.refresh()

    def _card(self, filename):
        w = QWidget()
        p = AppColors.for_mode(self.state.is_dark())
        w.setStyleSheet(
            "background-color: %s; border: 1px solid %s; "
            "border-radius: 8px; padding: 12px;" % (
                p.bg_panel, p.border_soft))
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(w)

        left = QLabel(self.tr("📻"))
        left.setStyleSheet("font-size: 24px;")
        row.addWidget(left)

        col = QVBoxLayout()
        name = os.path.basename(filename)
        dirname = os.path.dirname(filename) or filename
        try:
            stamp = os.path.getmtime(filename)
            modified = time.strftime(
                "%d/%m/%Y %H:%M", time.localtime(stamp))
            size = os.path.getsize(filename) // 1024
            extra = _("%s · %i KB") % (modified, size)
        except OSError:
            extra = _("file not found")
        title = QLabel(name)
        title.setStyleSheet("font-weight: 600;")
        col.addWidget(title)
        sub = QLabel(dirname)
        sub.setProperty("muted", True)
        col.addWidget(sub)
        meta = QLabel(extra)
        meta.setProperty("muted", True)
        meta.setStyleSheet("font-size: 10px;")
        col.addWidget(meta)
        row.addLayout(col, 1)

        open_btn = QPushButton(_("Open"))
        open_btn.setMaximumWidth(90)
        open_btn.clicked.connect(
            lambda _checked=False, fn=filename: self._on_open(fn))
        row.addWidget(open_btn)
        return w

    def refresh(self):
        while self._cards.count():
            item = self._cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recents = [
            f for f in self.state.get_recent_files() if os.path.exists(f)]
        if not recents:
            col = QVBoxLayout()
            col.addStretch(1)
            sub = QLabel(
                _("No recent files yet"))
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setProperty("muted", True)
            sub.setStyleSheet("font-size: 15px;")
            col.addWidget(sub)
            sub2 = QLabel(
                _("Files you open will appear here"))
            sub2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub2.setProperty("muted", True)
            col.addWidget(sub2)
            col.addStretch(1)
            holder = QWidget()
            holder.setLayout(col)
            self._cards.addWidget(holder, 0, 0, 1, 3)
            return

        per_row = 3
        for i, fn in enumerate(recents):
            self._cards.addWidget(
                self._card(fn), i // per_row, i % per_row)

    def _on_open(self, filename):
        if self.state.main_window:
            self.state.main_window.open_file(filename)

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
