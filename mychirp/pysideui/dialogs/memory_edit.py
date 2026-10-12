"""Memory edit dialog used by MemoriesTab (double-click or context menu)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from mychirp import chirp_common
from mychirp.pysideui.i18n import _


class MemoryEditDialog(QDialog):
    """One-channel editor with typed controls matching the CHIRP memedit."""

    def __init__(self, parent, mem, eset_features):
        super().__init__(parent)
        self.mem = mem
        self._fields: dict[str, any] = {}
        self.setWindowTitle(
            _("Edit Memory %s")
            % (getattr(mem, "extd_number", None) or mem.number))
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(form)

        self._fields["freq"] = QLineEdit(
            chirp_common.format_freq(mem.freq) if not mem.empty else "")
        form.addRow(_("Frequency") + ":", self._fields["freq"])

        self._fields["offset"] = QLineEdit(
            chirp_common.format_freq(mem.offset) if not mem.empty else "")
        form.addRow(_("Offset") + ":", self._fields["offset"])

        self._fields["name"] = QLineEdit(mem.name or "")
        form.addRow(_("Name") + ":", self._fields["name"])

        feats = eset_features
        tones = ["%.1f" % t for t in chirp_common.TONES]
        dtcs_list = [str(c) for c in chirp_common.DTCS_CODES]

        def add_combo(key, label, options, current):
            w = QComboBox()
            w.addItems([str(o) for o in options])
            if current is not None and str(current) in [str(o) for o in options]:
                w.setCurrentText(str(current))
            elif current is not None and str(current) != "":
                w.addItem(str(current))
                w.setCurrentText(str(current))
            form.addRow(label + ":", w)
            self._fields[key] = w

        if getattr(feats, "valid_tmodes", None):
            add_combo("tmode", _("Tone Mode"), feats.valid_tmodes, mem.tmode)
        if getattr(feats, "valid_tones", None):
            add_combo("rtone", _("Tone"), tones, "%.1f" % mem.rtone)
            add_combo("ctone", _("ToneSql"), tones, "%.1f" % mem.ctone)
        if getattr(feats, "valid_dtcs_codes", None):
            add_combo("dtcs", _("DTCS Code"), dtcs_list, str(mem.dtcs))
        if getattr(feats, "valid_duplexes", None):
            add_combo("duplex", _("Duplex"), feats.valid_duplexes, mem.duplex)
        if getattr(feats, "valid_modes", None):
            add_combo("mode", _("Mode"), feats.valid_modes, mem.mode)
        if getattr(feats, "valid_tuning_steps", None):
            steps = ["%.1f" % s for s in feats.valid_tuning_steps]
            add_combo("tuning_step", _("Tune Step"), steps,
                      "%.1f" % mem.tuning_step)
        if getattr(feats, "valid_skips", None):
            add_combo("skip", _("Skip"), feats.valid_skips, mem.skip)
        if getattr(feats, "valid_power_levels", None):
            levels = [str(l) for l in feats.valid_power_levels]
            add_combo("power", _("Power"), levels,
                      str(mem.power) if mem.power else "")
        if getattr(feats, "has_comment", False):
            self._fields["comment"] = QLineEdit(getattr(mem, "comment", ""))
            form.addRow(_("Comment") + ":", self._fields["comment"])

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def apply(self):
        """Write dialog values into the memory object.
        Returns the modified Memory on success."""
        mem = self.mem
        for name, control in self._fields.items():
            raw = (control.currentText() if isinstance(control, QComboBox)
                   else control.text())
            if name in ("freq", "offset"):
                setattr(mem, name, chirp_common.parse_freq(raw) if raw else 0)
            elif name in ("rtone", "ctone", "tuning_step"):
                setattr(mem, name, float(raw) if raw else 88.5)
            elif name == "dtcs":
                setattr(mem, name, int(raw) if raw else 23)
            else:
                setattr(mem, name, raw)
        return mem
