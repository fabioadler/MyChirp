"""Welcome tab: centered logo + quick actions."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mychirp.pysideui.i18n import _
from mychirp.pysideui.theme import AppColors

LOGO = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "share",
    "mychirp_logo_transparente.png"))
LOGO_SIZE = 300


class WelcomeTab(QWidget):
    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.addStretch(1)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if os.path.exists(LOGO):
            pix = QPixmap(LOGO).scaled(
                LOGO_SIZE, LOGO_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(pix)
        root.addWidget(self.logo)

        title = QLabel("MyChirp")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("heading", True)
        root.addWidget(title)

        subtitle = QLabel(_("Modern radio programming software"))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setProperty("muted", True)
        root.addWidget(subtitle)

        root.addSpacing(24)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addStretch(1)

        self.open_btn = QPushButton(_("&Open file"))
        self.open_btn.setProperty("accent", True)
        self.open_btn.clicked.connect(self._on_open)
        row.addWidget(self.open_btn)

        self.download_btn = QPushButton(_("Download from radio"))
        self.download_btn.setProperty("accent", True)
        self.download_btn.clicked.connect(self._on_download)
        row.addWidget(self.download_btn)

        row.addStretch(1)
        root.addLayout(row)

        root.addSpacing(12)
        hint = QLabel(
            _("Use File > Open or Ctrl+D to download from a radio"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setProperty("muted", True)
        root.addWidget(hint)
        root.addStretch(1)

    def _on_open(self):
        if self.state.main_window:
            self.state.main_window.pick_open()

    def _on_download(self):
        if self.state.main_window:
            self.state.main_window.download_from_radio()

    def retheme(self):
        pass
