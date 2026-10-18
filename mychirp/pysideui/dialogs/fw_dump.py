"""Firmware dump dialog: read-only backup of clone/full-window memory.

Runs the same validated paths as ``mychirp-fw --dump/--full-window``
(``fwtool.dump_clone`` / ``fwtool.dump_full_window``) on the shared
thread pool, saving a RAW .bin + YAML sidecar into
``~/.chirp/fw-backups/`` with the sha256-signed name. No write
command ever reaches the radio.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from mychirp import directory
from mychirp import chirp_common
from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.app_state import EditorSetState
from mychirp.pysideui.services.radio_service import (
    get_service,
    list_serial_ports,
    list_vendors,
    model_label_to_class,
)
from mychirp.pysideui.services.serial_probe import (
    NO_RADIO_MESSAGE,
    PortProbeError,
    is_serial_error,
    probe_port,
)

LOG = logging.getLogger(__name__)


class FirmwareDumpDialog(QDialog):
    """Read-only firmware dump (clone image or full memory window)."""

    def __init__(self, parent, state, eset=None):
        super().__init__(parent)
        self.state = state
        self.eset = eset
        self._busy = False

        self.setWindowTitle(_("Firmware dump (read-only)"))
        self._icon_text = "🔒"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        info = QLabel(
            _("Saves a raw dump + signed YAML sidecar into "
              "~/.chirp/fw-backups/. Read-only: no byte is ever "
              "written to the radio."))
        info.setProperty("muted", True)
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignCenter)

        self.vendor = QComboBox()
        self.vendor.addItems(list_vendors())
        self.vendor.currentTextChanged.connect(self._on_vendor)
        form.addRow(_("Vendor:"), self.vendor)

        self.model = QComboBox()
        self.model.currentTextChanged.connect(self._on_model)
        form.addRow(_("Model:"), self.model)

        self.port = QComboBox()
        ports = list_serial_ports()
        self.port.addItems(ports)
        last = state.conf.get("clone_last_port", "state")
        if last:
            idx = self.port.findText(last)
            if idx >= 0:
                self.port.setCurrentIndex(idx)
        form.addRow(_("Port:"), self._port_row(ports))

        root.addLayout(form)

        # save-to selector (user chooses where to write the dump .bin)
        save_row = QHBoxLayout()
        self.save_path = QLineEdit()
        self.save_path.setPlaceholderText(
            _("Leave empty to save to ~/.chirp/fw-backups/ (default)"))
        self.save_btn = QPushButton(_("Choose file…"))
        self.save_btn.setToolTip(_("Choose where to save the dump .bin"))
        self.save_btn.clicked.connect(self._pick_save_file)
        save_row.addWidget(QLabel(_("Save to:")))
        save_row.addWidget(self.save_path, 1)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

        self.full_window = QCheckBox(
            _("Full memory window (adds factory calibration area)"))
        self.full_window.setEnabled(False)
        self.full_window.setToolTip(
            _("Only supported on drivers that expose the complete "
              "cable-visible window (e.g. aux-first clones). Includes "
              "the factory calibration area the standard image omits."))
        root.addWidget(self.full_window)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setMaximumHeight(12)
        root.addWidget(self.progress)

        self.progress_label = QLabel("")
        self.progress_label.setProperty("muted", True)
        self.progress_label.setVisible(False)
        self.progress_label.setWordWrap(True)
        root.addWidget(self.progress_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_start)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            _("Dump"))
        root.addWidget(buttons)

        self.setMinimumWidth(480)

        # preselect the currently open radio, if any
        if eset and eset.radio is not None:
            r = eset.radio
            idx = self.vendor.findText(getattr(r, "VENDOR", "") or "")
            if idx >= 0:
                self.vendor.setCurrentIndex(idx)
                label = ("%s %s" % (getattr(r, "MODEL", ""),
                                    getattr(r, "VARIANT", "") or ""))
                m = self.model.findText(label.strip())
                if m >= 0:
                    self.model.setCurrentIndex(m)
        elif self.vendor.count():
            self._on_vendor(self.vendor.currentText())

        self.adjustSize()

    def _port_row(self, ports):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.port, 1)
        if len(ports) == 1:
            hint = QLabel(_("(auto-detect)"))
            hint.setProperty("muted", True)
            row.addWidget(hint)
        return row

    def _current_rclass(self):
        vendor = self.vendor.currentText()
        label = self.model.currentText()
        if not (vendor and label):
            return None
        return model_label_to_class(vendor, label)

    def _on_vendor(self, vendor):
        if not vendor:
            return
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(self._supported_dump_models(vendor))
        self.model.blockSignals(False)
        self._on_model(self.model.currentText())

    def _supported_dump_models(self, vendor):
        """Lista apenas modelos do vendor que suportam dump (CloneModeRadio)."""
        models = []
        seen = set()
        for rclass in directory.DRV_TO_RADIO.values():
            if rclass.VENDOR != vendor:
                continue
            if not issubclass(rclass, chirp_common.CloneModeRadio):
                continue
            label = "%s %s" % (rclass.MODEL, rclass.VARIANT or "")
            label = label.strip()
            if label not in seen:
                seen.add(label)
                models.append(label)
        return sorted(models)

    def _pick_save_file(self):
        """Abre QFileDialog para o usuário escolher onde salvar o .bin do dump."""
        start = self.save_path.text() or None
        path = QFileDialog.getSaveFileName(
            self, _("Salvar firmware dump como"),
            start, _("Raw clone images (*.bin);;Todos os arquivos (*)"))[0]
        if path:
            self.save_path.setText(path)

    def _on_model(self, label):
        rclass = self._current_rclass()
        supported = bool(rclass) and issubclass(rclass, chirp_common.CloneModeRadio)
        self.full_window.setEnabled(
            supported and hasattr(rclass, "download_full_window"))
        if not supported:
            self.full_window.setChecked(False)

    def _set_busy(self, busy):
        self._busy = busy
        self.progress.setVisible(busy)
        self.progress_label.setVisible(busy)
        if busy:
            self.progress_label.setText(
                _("Communicating with radio... (read-only)"))

    def _finish_label(self, text):
        self.progress_label.setText(text)
        self.progress_label.setStyleSheet("color: palette(mid);")
        self.progress_label.setVisible(True)

    def _on_start(self):
        if self._busy:
            return
        port = self.port.currentText()
        rclass = self._current_rclass()
        if rclass is None or not port:
            self._finish_label(_("Select vendor, model and port"))
            return
        try:
            probe_port(port, rclass, timeout=2.0)
        except PortProbeError as e:
            QMessageBox.warning(
                self, _("Aviso"), str(e) or NO_RADIO_MESSAGE)
            return
        self._set_busy(True)
        self.state.conf.set("clone_last_port", port, "state")
        self.state.conf.save()
        out = self.save_path.text().strip() or None
        get_service(self).fw_dump(
            rclass, port,
            full_window=self.full_window.isChecked() and
            hasattr(rclass, "download_full_window"),
            out=out,
            on_done=self._dump_done)

    def _dump_done(self, job):
        self._set_busy(False)
        if job.error:
            self.state.set_status(_("Firmware dump failed"))
            if is_serial_error(job.error):
                QMessageBox.warning(
                    self, _("Aviso"), NO_RADIO_MESSAGE)
                self._finish_label(str(job.error))
                return
            self._finish_label(str(job.error))
            return
        bin_path, yaml_path = job.result
        sha = size = None
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
            sha, size = meta.get("sha256"), meta.get("size")
        except Exception:
            LOG.debug("sidecar readback failed", exc_info=True)
        msg = _("Saved: %s (%s bytes)\nsha256: %s\nmeta: %s") % (
            bin_path, size or "?", (sha or "-")[:16] + "…"
            if sha else "-", yaml_path)
        self._finish_label(msg)
        self.state.set_status(
            _("Firmware dump saved to %s") % bin_path)
