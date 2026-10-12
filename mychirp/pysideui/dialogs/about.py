"""About dialog: logo + credits + company logo."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from mychirp import CHIRP_VERSION
from mychirp.pysideui.i18n import _

SHARE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "share"))


class AboutDialog(QDialog):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle(_("About"))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(os.path.join(SHARE, "mychirp_logo_transparente.png"))
        if not pix.isNull():
            logo.setPixmap(pix.scaledToWidth(
                200, Qt.TransformationMode.SmoothTransformation))
        root.addWidget(logo)

        title = QLabel("MyChirp")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("heading", True)
        root.addWidget(title)

        ver = QLabel(_("Version %s") % (CHIRP_VERSION,))
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setProperty("muted", True)
        root.addWidget(ver)

        credits = QLabel(
            _("Original project: CHIRP by Dan Smith (GPLv3)\n"
              "https://chirp.danplanet.com\n\n"
              "Developed by: Fábio Adler de Luna Gomes"))
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setProperty("muted", True)
        credits.setWordWrap(True)
        root.addWidget(credits)

        company = QLabel()
        company.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(os.path.join(SHARE, "logo_empresa.png"))
        if not pix.isNull():
            company.setPixmap(pix.scaledToWidth(
                160, Qt.TransformationMode.SmoothTransformation))
        root.addWidget(company)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
