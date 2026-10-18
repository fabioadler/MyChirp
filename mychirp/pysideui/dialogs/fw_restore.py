"""Firmware restore dialog: write the memory window back to the radio.

HIGH-RISK operation, gated by a double confirmation flow:
  1. modal warning explaining limits (same-unit backup, read-only
     pre-dump, abort on NACK)
  2. exact-phrase confirmation dialog ("GRAVAR")
Only enabled for validated clone families: h777 (PROGRAM handshake,
992 B window) and UV-5R aux-first (BOM-5701; 0x1948 image). Other
drivers are refused with a clear message.
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

from mychirp import directory
from mychirp import fwtool
from mychirp import chirp_common
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

        self.setWindowTitle(_("Firmware gravar (ESCRITA)"))
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
        self.vendor.addItems(self._supported_vendors())
        self.vendor.currentTextChanged.connect(self._on_vendor)
        self.vendor.currentTextChanged.connect(self._validate_start)
        form.addRow(_("Vendor:"), self.vendor)

        self.model = QComboBox()
        self.model.currentTextChanged.connect(self._on_model)
        self.model.currentTextChanged.connect(self._validate_start)
        form.addRow(_("Model:"), self.model)

        self.port = QComboBox()
        ports = list_serial_ports()
        self.port.addItems(ports)
        last = state.conf.get("clone_last_port", "state")
        if last:
            idx = self.port.findText(last)
            if idx >= 0:
                self.port.setCurrentIndex(idx)
        self.port.currentTextChanged.connect(self._validate_start)
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
            _("Gravar"))
        self._gravar_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._gravar_btn.setEnabled(False)
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

        self._validate_start()
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

    def _fw_family(self, rclass):
        """Família de escrita validada: 'h777', 'aux-first' ou None."""
        if not rclass:
            return None
        if getattr(rclass, "PROGRAM_CMD", None) == \
                fwtool.H777_PROGRAM_CMD:
            return "h777"
        if getattr(rclass, "_aux_first", False) and \
                getattr(rclass, "_aux_block", False):
            return "aux-first"
        return None

    def _family_sizes(self, rclass):
        """Tamanhos de imagem aceitáveis para a família de escrita do
        modelo (h777: 992 B; aux-first: 6.472 B clone OU 8.192 B full
        window). Retorna tupla, ou None quando não suportado."""
        family = self._fw_family(rclass)
        if family == "h777":
            return (fwtool.H777_WINDOW_END,)
        if family == "aux-first":
            return (fwtool.UV5R_AUX_FIRST_IMAGE_END, 0x2000)
        return None

    def _restore_supported(self, rclass):
        return self._fw_family(rclass) is not None

    def _restore_supported(self, rclass):
        return self._fw_family(rclass) is not None

    def _on_vendor(self, vendor):
        if not vendor:
            return
        self.model.blockSignals(True)
        self.model.clear()
        self.model.addItems(self._supported_restore_models(vendor))
        self.model.blockSignals(False)
        self._on_model(self.model.currentText())

    def _supported_vendors(self):
        """Retorna vendors que possuem ao menos um modelo com família
        de gravação testada (h777 PROGRAM_CMD ou UV-5R-aux-first)."""
        directory.import_drivers()
        vendors = set()
        for rclass in directory.DRV_TO_RADIO.values():
            if self._fw_family(rclass) is not None:
                vendors.add(rclass.VENDOR)
        return sorted(vendors)

    def _supported_restore_models(self, vendor):
        """Lista apenas modelos do vendor com família de gravação testada
        (h777 PROGRAM_CMD ou UV-5R-aux-first)."""
        directory.import_drivers()
        models = []
        seen = set()
        for rclass in directory.DRV_TO_RADIO.values():
            if rclass.VENDOR != vendor:
                continue
            if self._fw_family(rclass) is None:
                continue
            label = "%s %s" % (rclass.MODEL, rclass.VARIANT or "")
            label = label.strip()
            if label not in seen:
                seen.add(label)
                models.append(label)
        return sorted(models)

    def _on_model(self, label):
        rclass = self._current_rclass()
        if self._restore_supported(rclass):
            self.warn_label.clear()
        else:
            self.warn_label.setText(
                _("Escrita validada apenas nas famílias h777 "
                  "(handshake PROGRAM; ex.: Baofeng BF-777S) e "
                  "UV-5R-aux-first (ex.: BOMVINK BOM-5701). "
                  "Selecione um modelo de uma dessas famílias."))
        self._validate_start()

    def _validate_start(self):
        """Habilita o botão Gravar apenas quando todos os campos
        obrigatórios estão preenchidos e válidos."""
        ok = False
        port = self.port.currentText()
        rclass = self._current_rclass()
        if (port and rclass is not None
                and self._restore_supported(rclass)
                and self.image_path):
            ok = True
        self._gravar_btn.setEnabled(ok)

    def _pick_image(self):
        from mychirp import fwtool as _fw
        start = _fw.fw_backup_dir()
        path = QFileDialog.getOpenFileName(
            self, _("Choose the image (.bin) to restore"),
            start, _("Raw clone images (*.bin)"))[0]
        if not path:
            return
        self._set_image(path)

    def _set_image(self, path):
        try:
            data = open(path, "rb").read()
        except OSError as e:
            self.img_label.setText(str(e))
            self.image_path = None
            self._validate_start()
            return
        self.image_path = path
        sha16 = hashlib.sha256(data).hexdigest()[:16]
        rclass = self._current_rclass()
        sizes = self._family_sizes(rclass)
        family_name = self._fw_family(rclass) or "?"
        ok_size = sizes is not None and len(data) in sizes
        extra = ""
        if not ok_size:
            if sizes:
                extra = _("  [SIZE MISMATCH: esperado %s B para %s]") % (
                    " / ".join(str(s) for s in sizes), family_name)
        self.img_label.setText(
            _("%s\nsha256: %s…  %d B%s") % (path, sha16, len(data), extra))
        self._validate_start()

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
                  "family and UV-5R aux-first)"))
            return
        if not self.image_path:
            self._finish_label(_("No image selected"))
            return
        data = open(self.image_path, "rb").read()
        sizes = self._family_sizes(rclass)
        if sizes is None or len(data) not in sizes:
            family_name = self._fw_family(rclass) or "desconhecida"
            esperado = " / ".join(str(s) for s in sizes) if sizes else "?"
            self._finish_label(
                _("Image size mismatch: %d B (esperado %s B para "
                  "família %s)") % (len(data), esperado, family_name))
            return

        # aviso de risco explícito antes da gravação
        reply = QMessageBox.warning(
            self, _("Aviso de risco — gravação de firmware"),
            _("Esta operação GRAVA na memória do rádio e pode torná-lo "
              "inutilizável se usada incorretamente.\n\n"
              "Use APENAS um backup da MESMA unidade.\n"
              "O dump prévio é salvo automaticamente antes de gravar.\n\n"
              "Deseja continuar?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            self._finish_label(_("Operação cancelada pelo usuário"))
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
        elif rep.get("aborted") or rep.get("diffs") is None:
            head = _("RESTORE PITFALL: gravação incompleta (abortada)")
        else:
            head = ("%d divergências pós-gravação" % len(rep["diffs"]))
        notes = ""
        if rep.get("preserve_diffs"):
            notes = _("\nNOTA: %d faixa(s) de proteção não gravada(s) "
                      "pelo driver (conteúdo da unidade preservado)."
                      ) % len(rep["preserve_diffs"])
        self._finish_label(
            "%s%s\nsha_antigo: %s…\nsha_novo:   %s…\npre: %s\npost: %s" % (
                head, notes, (rep["sha_old"] or "-")[:16],
                (rep["sha_new"] or "-")[:16],
                rep["pre_path"], rep["post_path"]))
        self.state.set_status(
            _("Firmware restore: %s") % head)
