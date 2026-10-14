"""Clone dialog: vendor/model/port combos + progress for Qt."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.app_state import EditorSetState
from mychirp.pysideui.services.radio_service import (
    get_service,
    list_models,
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


class CloneDialog(QDialog):
    """Download from / upload to radio dialog."""

    def __init__(self, parent, state, mode="download", eset=None):
        super().__init__(parent)
        self.state = state
        self.mode = mode
        self.eset = eset
        self._busy = False

        downloading = (mode == "download")
        if downloading:
            self.setWindowTitle(_("Download from radio"))
            self._icon_text = "⬇"
        else:
            self.setWindowTitle(_("Upload to radio"))
            self._icon_text = "⬆"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignCenter)

        if downloading:
            self.vendor = QComboBox()
            self.vendor.addItems(list_vendors())
            self.vendor.currentTextChanged.connect(self._on_vendor)
            form.addRow(_("Vendor:"), self.vendor)

            self.model = QComboBox()
            form.addRow(_("Model:"), self.model)

            self.port = QComboBox()
            ports = list_serial_ports()
            self.port.addItems(ports)
            form.addRow(_("Port:"), self._port_row(ports))
        else:
            r = eset.radio if eset else None
            vendor = getattr(r, "VENDOR", "") if r else ""
            model_str = getattr(r, "MODEL", "") if r else ""
            form.addRow(_("Vendor:"), QLabel(vendor))
            form.addRow(_("Model:"), QLabel(model_str))

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

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.progress.setMaximumHeight(12)
        root.addWidget(self.progress)

        self.progress_label = QLabel("")
        self.progress_label.setProperty("muted", True)
        self.progress_label.setVisible(False)
        root.addWidget(self.progress_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_start)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            _("Download") if downloading else _("Upload"))
        root.addWidget(buttons)

        self.setMinimumWidth(460)
        self.adjustSize()

    def _port_row(self, ports):
        """Combo plus an "(auto-detect)" hint when there's exactly one port."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.port, 1)
        if len(ports) == 1:
            hint = QLabel(_("(auto-detect)"))
            hint.setProperty("muted", True)
            row.addWidget(hint)
        return row

    def _no_radio_dialog(self, message=None):
        """Aviso de porta/rádio; @message sobrepõe o texto padrão
        (ex.: motivo da porta ocupada)."""
        QMessageBox.warning(
            self, _("Aviso"), message or NO_RADIO_MESSAGE)

    def _on_vendor(self, vendor):
        if not vendor:
            return
        self.model.clear()
        self.model.addItems(list_models(vendor))

    def _set_busy(self, busy):
        self._busy = busy
        self.progress.setVisible(busy)
        self.progress_label.setVisible(busy)
        if busy:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress_label.setText(_("Communicating with radio..."))

    def _on_progress(self, status):
        try:
            if status.max:
                self.progress.setValue(100 * status.cur // status.max)
            self.progress_label.setText(status.msg or "")
        except Exception:
            pass

    def _on_start(self):
        if self._busy:
            return
        port = self.port.currentText()
        if self.mode == "download":
            vendor = self.vendor.currentText()
            label = self.model.currentText()
            if not (vendor and label and port):
                self.progress_label.setText(
                    _("Select vendor, model and port"))
                self.progress_label.setVisible(True)
                return
            rclass = model_label_to_class(vendor, label)
            if rclass is None:
                self.progress_label.setText(_("Unknown model"))
                self.progress_label.setVisible(True)
                return
            try:
                probe_port(port, rclass, timeout=2.0)
            except PortProbeError as e:
                self._no_radio_dialog(str(e))
                return
            self._busy = True
            self._set_busy(True)
            self.state.conf.set("clone_last_port", port, "state")
            self.state.conf.save()
            svc = get_service(self)
            svc.download_radio(
                rclass, port, self._download_done,
                on_progress=self._on_progress)
        else:
            if not (self.eset and port):
                return
            try:
                probe_port(port, type(self.eset.radio), timeout=2.0)
            except PortProbeError as e:
                self._no_radio_dialog(str(e))
                return
            self._busy = True
            self._set_busy(True)
            svc = get_service(self)
            svc.upload_radio(
                self.eset.radio, port, self._upload_done,
                on_progress=self._on_progress)

    def _download_done(self, job):
        self._busy = False
        self._set_busy(False)
        if job.error:
            self.state.set_status(_("Failed to download"))
            if is_serial_error(job.error):
                self._no_radio_dialog()
                return
            self.progress_label.setText(str(job.error))
            self.progress_label.setStyleSheet("color: palette(mid);")
            self.progress_label.setVisible(True)
            return
        radio = job.result
        base = "%s_%s" % (getattr(radio, "VENDOR", "Radio"),
                          getattr(radio, "MODEL", ""))
        eset = EditorSetState(radio, "%s.img" % base.replace(" ", "_"))
        self.state.add_editorset(eset)
        self.state.set_status(_("Downloaded %s") % eset.radio_label)
        self.accept()

    def _upload_done(self, job):
        self._busy = False
        self._set_busy(False)
        if job.error:
            self.state.set_status(_("Failed to upload"))
            if is_serial_error(job.error):
                self._no_radio_dialog()
                return
            self.progress_label.setText(str(job.error))
            self.progress_label.setVisible(True)
            return
        self.state.set_status(_("Upload complete"))
        self.accept()
