"""Developer tools and bug-report dialogs (CHIRP parity helpers).

Pure presentation: any data gathering that could block (radio mmap,
image serialization) happens on the shared radio service thread pool.
"""

import logging
import os
import platform
import subprocess
import sys

from PySide6.QtCore import qVersion
from PySide6.QtCore import __version__ as PYSIDE_VERSION
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.radio_service import (
    get_service, list_serial_ports)

LOG = logging.getLogger(__name__)

DEBUG_LOG_TAIL_LINES = 200


def debug_log_path():
    """Best-effort path of the CHIRP debug log (~/.chirp/debug.log)."""
    try:
        from mychirp import platform as chirp_platform
        path = chirp_platform.get_platform().config_file("debug.log")
        if path:
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), ".chirp", "debug.log")


def read_debug_log_tail(lines=DEBUG_LOG_TAIL_LINES):
    """Return the last ``lines`` of the debug log, or a hint message."""
    path = debug_log_path()
    if not os.path.exists(path):
        return _("No debug log found at %s") % path
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except Exception as e:
        return _("Could not read debug log: %s") % e


def versions_text():
    return "\n".join([
        "Python:  %s" % sys.version.replace("\n", " "),
        "Qt:      %s" % qVersion(),
        "PySide6: %s" % PYSIDE_VERSION,
        "OS:      %s" % platform.platform(),
    ])


def serial_ports_text():
    ports = list_serial_ports()
    if not ports:
        return _("No serial ports detected")
    return "\n".join(ports)


def features_text(features):
    """Render a RadioFeatures object as aligned 'key: value' lines."""
    lines = []
    for name in sorted(features._valid_map):
        try:
            value = getattr(features, name)
        except Exception as e:
            value = _("<error: %s>") % e
        if isinstance(value, (list, tuple)) and len(str(value)) > 200:
            value = _("<%i items>") % len(value)
        lines.append("%s: %s" % (name, value))
    return "\n".join(lines)


def hexdump_text(data, base=0, width=16):
    """Classic hex + ASCII dump."""
    out = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        hexpart = " ".join("%02x" % (b if isinstance(b, int) else ord(b))
                           for b in chunk)
        asciipart = "".join(
            chr(b) if isinstance(b, int) and 32 <= b < 127 else (
                b if isinstance(b, str) and 32 <= ord(b) < 127 else ".")
            for b in chunk)
        out.append("%08x  %-*s  %s" % (
            base + offset, width * 3 - 1, hexpart, asciipart))
    return "\n".join(out)


def radio_dump_bytes(radio):
    """Serialized raw image: mmap for clone-mode radios, else save()."""
    mmap = getattr(radio, "get_mmap", None)
    if callable(mmap):
        try:
            mm = mmap()
            if mm is not None:
                data = mm.get_packed()
                if data is not None:
                    if isinstance(data, str):
                        data = data.encode("latin-1")
                    return bytes(data)
        except Exception:
            LOG.exception("mmap dump failed")
    process = getattr(radio, "process_mmap", None)
    if callable(process):
        try:
            mmap_fn = getattr(radio, "_mmap", None)
            if mmap_fn is not None:
                data = mmap_fn.get_packed()
                if isinstance(data, str):
                    data = data.encode("latin-1")
                return bytes(data)
        except Exception:
            LOG.exception("_mmap fallback failed")
    raise RuntimeError(_("No raw image available for this radio"))


def make_monospace(edit):
    from PySide6.QtGui import QFont
    font = QFont("Monospace")
    font.setStyleHint(QFont.StyleHint.TypeWriter)
    edit.setFont(font)


class DeveloperDialog(QDialog):
    """View > Developer tools (raw dump): Features | Raw dump | Logs."""

    def __init__(self, parent, state, eset=None):
        super().__init__(parent)
        self.state = state
        self.eset = eset
        self.setWindowTitle(_("Developer tools"))
        self.setMinimumSize(760, 500)
        self.resize(900, 620)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs)

        # Features tab: radio features dict + versions + serial ports
        self.features_view = QTextEdit()
        self.features_view.setReadOnly(True)
        make_monospace(self.features_view)
        self.tabs.addTab(self.features_view, _("Features"))
        self._fill_features()

        # Raw dump tab
        self.dump_view = QTextEdit()
        self.dump_view.setReadOnly(True)
        make_monospace(self.dump_view)
        self.tabs.addTab(self.dump_view, _("Raw dump"))
        self._fill_dump()

        # Logs tab
        self.logs_view = QTextEdit()
        self.logs_view.setReadOnly(True)
        make_monospace(self.logs_view)
        self.logs_view.setPlainText(read_debug_log_tail())
        self.tabs.addTab(self.logs_view, _("Logs"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _fill_features(self):
        lines = [versions_text(), ""]
        lines.append(_("Serial ports:"))
        lines.append(serial_ports_text())
        lines.append("")
        if self.eset is not None:
            lines.append(_("Radio: %s") % self.eset.radio_label)
            lines.append(
                _("Class: %s") % type(self.eset.radio).__name__)
            bounds = getattr(self.eset.features, "memory_bounds", None)
            if bounds:
                lines.append(
                    _("Memory bounds: %s..%s") % (bounds[0], bounds[1]))
            valid = getattr(self.eset.features, "valid_tones", None)
            lines.append(_("Has valid tones: %s") % bool(valid))
            lines.append("")
            lines.append(features_text(self.eset.features))
        else:
            lines.append(_("No radio open"))
        self.features_view.setPlainText("\n".join(lines))

    def _fill_dump(self):
        if self.eset is None:
            self.dump_view.setPlainText(_("No radio open"))
            return
        self.dump_view.setPlainText(_("Loading raw image..."))
        service = get_service(self)

        def _dump():
            return hexdump_text(radio_dump_bytes(self.eset.radio))

        def done(job):
            if job.error:
                self.dump_view.setPlainText(
                    _("Failed to read image: %s") % job.error)
            else:
                self.dump_view.setPlainText(job.result)

        service.run_memory_op(_dump, self.eset.radio, on_done=done)


class BugReportDialog(QDialog):
    """Help > Report a bug: form + copyable diagnostics."""

    def __init__(self, parent, state, eset=None):
        super().__init__(parent)
        self.state = state
        self.eset = eset
        self.setWindowTitle(_("Report a bug"))
        self.setMinimumSize(560, 440)
        self.resize(560, 480)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.summary = QLineEdit()
        form.addRow(_("Summary:"), self.summary)
        self.steps = QLineEdit()
        form.addRow(_("Steps to reproduce:"), self.steps)
        root.addLayout(form)

        root.addWidget(QLabel(_("Description:")))
        self.description = QTextEdit()
        root.addWidget(self.description, 1)

        self.copy_button = QPushButton(_("Copy diagnostics"))
        self.copy_button.clicked.connect(self.copy_diagnostics)
        root.addWidget(self.copy_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def diagnostics_report(self):
        lines = [
            "== MyChirp bug report ==",
            "",
            versions_text(),
            "Git commit: %s" % _git_revision(),
        ]
        if self.eset is not None:
            radio = self.eset.radio
            lines.append("Radio: %s" % self.eset.radio_label)
            lines.append("Driver class: %s" % type(radio).__name__)
            lines.append("Driver module: %s" % type(radio).__module__)
            lines.append("File: %s" % self.eset.filename)
        else:
            lines.append("Radio: (none open)")
        if self.summary.text().strip():
            lines.append("Summary: %s" % self.summary.text().strip())
        return "\n".join(lines)

    def copy_diagnostics(self):
        QApplication.clipboard().setText(self.diagnostics_report())
        self.state.set_status(_("Diagnostics copied to clipboard"))


def _git_revision():
    """Short git revision of the source tree, if available."""
    root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, stderr=subprocess.DEVNULL, timeout=5)
        return out.decode().strip()
    except Exception:
        return _("unknown")
