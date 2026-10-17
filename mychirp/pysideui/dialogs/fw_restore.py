"""Firmware restore dialog: write the memory window back to the radio.

HIGH-RISK operation, gated by a double confirmation flow:
  1. modal warning explaining limits (same-unit backup, read-only
     pre-dump, abort on NACK)
  2. exact-phrase confirmation dialog ("GRAVAR")
Only enabled for the validated h777 clone family (PROGRAM handshake,
992 B window); other drivers are refused with a clear message.
"""

import hashlib
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from mychirp import fwtool
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
    PortProbeError,
    is_serial_error,
    probe_port,
)

LOG = logging.getLogger(__name__)

CONFIRM_WORD = "GRAVAR"


class FirmwareRestoreDialog(QDialog):
    """Write a memory-image window back to the radio (read-only
    pre-dump + block-validated writes + post re-read diff)."""

    def __init__(self, parent, state, eset=None):
        super().__init__(parent)
        self.state = state
        self.eset = eset
        self._busy = False
        self.image_path = None

        self.setWindowTitle(_("Firmware restore (WRITE)"))
        self._icon_text = "⚠"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        info = QLabel(
            _("Grava os bytes de uma imagem de clone na janela de "
              "memória do rádio (operação de ESCRITA).\n\n"
              "Segurança integrada: dump prévio da unidade é salvo "
              "automaticamente; cada bloco exige ACK (aborto em \n"
              "NACK/timeout); re-leitura com diff no fim. Use "
              "APENAS o backup da MESMA unidade."))
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

        pick = QHBoxLayout()
        self.pick_btn = QPushButton(_("Choose image (.bin)..."))
        self.pick_btn.clicked.connect(self._pick_image)
        pick.addWidget(self.pick_btn, 1)
        form.addRow(_("Image:"), pick)
        root.addLayout(form)

        self.img_label = QLabel(_("No image selected"))
        self.img_label.setProperty("muted", True)
        self.img_label.setWordWrap(True)
        root.addWidget(self.img_label)

        self.warn_label = QLabel("")
        self.warn_label.setStyleSheet("color: palette(mid);")
        self.warn_label.setWordWrap(True)
        root.addWidget(self.warn_label)

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
            _("Restore"))
        root.addWidget(buttons)

        self.setMinimumWidth(520)

        # preselect the radio driving the eset, if any
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

    # ----- helpers -----
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

    def _restore_supported(self, rclass):
        return bool(rclass) and getattr(rclass, "PROGRAM_CMD", None) == \
            fwtool.H777_PROGRAM_CMD

    def _on_vendor(self, vendor):
        if not vendor:
            return
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(list_models(vendor))
        self.model.blockSignals(False)
        self._on_model(self.model.currentText())

    def _on_model(self, label):
        rclass = self._current_rclass()
        if self._restore_supported(rclass):
            self.warn_label.clear()
        else:
            self.warn_label.setText(
                _("Escrita validada apenas na família h777 "
                  "(handshake PROGRAM; ex.: Baofeng BF-777S). "
                  "Selecione um modelo da família."))

    def _pick_image(self):
        from mychirp import fwtool as _fw
        start = _fw.fw_backup_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, _("Choose the image (.bin) to restore"),
            start, _("Raw clone images (*.bin)"))
        if not path:
            return
        self._set_image(path)

    def _set_image(self, path):
        try:
            data = open(path, "rb").read()
        except OSError as e:
            self.img_label.setText(str(e))
            self.image_path = None
            return
        self.image_path = path
        sha16 = hashlib.sha256(data).hexdigest()[:16]
        rclass = self._current_rclass()
        expected = fwtool.H777_WINDOW_END if self._restore_supported(
            rclass) else None
        ok_size = expected is not None and len(data) == expected
        extra = ""
        if not ok_size:
            extra = _("  [SIZE MISMATCH]")
        self.img_label.setText(
            _("%s\nsha256: %s…  %d B%s") % (path, sha16, len(data), extra))

    def _finish_label(self, text):
        self.progress_label.setText(text)
        self.progress_label.setStyleSheet("color: palette(mid);")
        self.progress_label.setVisible(True)

    def _set_busy(self, busy):
        self._busy = busy
        self.progress.setVisible(busy)
        self.progress_label.setVisible(busy)
        if busy:
            self.progress_label.setText(
                _("Pre-dump + write + verify in progress (do NOT touch "
                  "the radio)..."))

    # ----- confirmation flow (double) -----
    def _confirm(self, rclass=None):
        reply = QMessageBox.question(
            self, _("Firmware restore"),
            _("Write the selected image to the radio memory?\n\n"
              "This overwrites the current radio memory window. The "
              "radio's own pre-write dump is saved automatically.\n"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return False
        dlg = QInputDialog(self)
        dlg.setWindowTitle(_("Final confirmation"))
        dlg.setLabelText(
            _("Type %s to confirm writing to the radio NOW:" %
              CONFIRM_WORD))
        dlg.setTextValue("")
        dlg.setTextEchoMode(QLineEdit.Normal)
        if not dlg.exec():
            return False
        if dlg.textValue() != CONFIRM_WORD:
            QMessageBox.warning(
                self, _("Aviso"),
                _("Unexpected confirmation text; write canceled."))
            return False
        return True

    # ----- run -----
    def _on_start(self):
        if self._busy:
            return
        port = self.port.currentText()
        rclass = self._current_rclass()
        if rclass is None or not port:
            self._finish_label(_("Select vendor, model and port"))
            return
        if not self._restore_supported(rclass):
            self._finish_label(
                _("Driver not supported for restore (validated: h777 "
                  "family)"))
            return
        if not self.image_path:
            self._finish_label(_("No image selected"))
            return
        data = open(self.image_path, "rb").read()
        if len(data) != fwtool.H777_WINDOW_END:
            self._finish_label(_("Image size mismatch (%d B)") % len(data))
            return
        try:
            probe_port(port, rclass, timeout=2.0)
        except PortProbeError as e:
            QMessageBox.warning(self, _("Aviso"), str(e))
            return
        if not self._confirm(rclass):
            self.progress_label.setVisible(True)
            self._finish_label(_("Write canceled by user"))
            return
        self._set_busy(True)
        self.state.conf.set("clone_last_port", port, "state")
        self.state.conf.save()
        get_service(self).fw_restore(
            rclass, port, self.image_path, on_done=self._restore_done)

    def _restore_done(self, job):
        self._set_busy(False)
        if job.error:
            self.state.set_status(_("Firmware restore failed"))
            msg = str(job.error)
            if is_serial_error(job.error):
                QMessageBox.warning(self, _("Aviso"), msg)
            self._finish_label(msg)
            return
        rep = job.result
        if rep["ok"] and rep.get("diffs") == []:
            head = _("RESTORE OK: 0 divergências (re-leitura idêntica)")
        elif rep.get("aborted") is not None or rep.get("diffs") is None:
            head = _("RESTORE PITFALL: gravação incompleta (abortada)")
        else:
            head = ("%d divergências pós-gravação" % len(rep["diffs"]))
        self._finish_label(
            "%s\nsha_antigo: %s…\nsha_novo:   %s…\npre: %s\npost: %s" % (
                head, (rep["sha_old"] or "-")[:16],
                (rep["sha_new"] or "-")[:16],
                rep["pre_path"], rep["post_path"]))
        self.state.set_status(
            _("Firmware restore: %s") % head)
