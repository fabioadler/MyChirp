"""Memory edit dialog used by MemoriesTab (double-click or context menu)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from mychirp import chirp_common
from mychirp import settings as chirp_settings
from mychirp.pysideui.i18n import _


class MemoryEditDialog(QDialog):
    """One-channel editor with typed controls matching the CHIRP memedit."""

    def __init__(self, parent, mem, eset_features):
        super().__init__(parent)
        self.mem = mem
        self._features = eset_features
        self._fields: dict[str, any] = {}
        self._extra_controls: list = []
        self.setWindowTitle(
            _("Edit Memory %s")
            % (getattr(mem, "extd_number", None) or mem.number))
        self.setMinimumWidth(560)

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
            levels = [str(lvl) for lvl in feats.valid_power_levels]
            add_combo("power", _("Power"), levels,
                      str(mem.power) if mem.power else "")
        if getattr(feats, "has_comment", False):
            self._fields["comment"] = QLineEdit(getattr(mem, "comment", ""))
            form.addRow(_("Comment") + ":", self._fields["comment"])

        def render_extra(container):
            if isinstance(container, chirp_settings.RadioSettings):
                elements = [(e.get_name(), e) for e in container]
            else:
                elements = container.items()
            for name, element in elements:
                if isinstance(element, chirp_settings.RadioSetting):
                    if not name or name.startswith("_"):
                        continue
                    doc = getattr(element, "__doc__", None) or ""
                    if "hidden" in doc.lower():
                        continue
                    self._add_extra_row(element, form)
                elif isinstance(element, chirp_settings.RadioSettingGroup):
                    subtitle = QLabel(element.get_shortname())
                    subtitle.setStyleSheet(
                        "font-size: 12px; font-weight: 600; "
                        "margin-top: 4px;")
                    form.addRow(subtitle)
                    render_extra(element)

        extra = getattr(mem, "extra", None)
        if isinstance(extra, (chirp_settings.RadioSettings,
                              chirp_settings.RadioSettingGroup)) \
                and len(extra) > 0:
            section = QLabel(_("Extra"))
            section.setStyleSheet(
                "font-size: 13px; font-weight: 600; margin-top: 8px;")
            form.addRow(section)
            render_extra(extra)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.adjustSize()

    def _add_extra_row(self, setting, form):
        value = setting.value
        try:
            val = value.get_value()
        except Exception:
            val = None

        if isinstance(value, chirp_settings.RadioSettingValueBoolean):
            control = QCheckBox()
            control.setChecked(bool(val))
        elif isinstance(value, chirp_settings.RadioSettingValueList):
            control = QComboBox()
            options = [str(o) for o in value.get_options()]
            control.addItems(options)
            if val is not None and str(val) in options:
                control.setCurrentText(str(val))
            elif val is not None:
                control.addItem(str(val))
                control.setCurrentText(str(val))
        elif isinstance(value, chirp_settings.RadioSettingValueInteger):
            control = QSpinBox()
            control.setRange(value.get_min(), value.get_max())
            if val is not None:
                try:
                    control.setValue(int(val))
                except (TypeError, ValueError):
                    pass
        elif isinstance(value, chirp_settings.RadioSettingValueFloat):
            control = QDoubleSpinBox()
            control.setRange(value.get_min(), value.get_max())
            control.setDecimals(value._pre)
            if val is not None:
                try:
                    control.setValue(float(val))
                except (TypeError, ValueError):
                    pass
        elif isinstance(value, chirp_settings.RadioSettingValueString):
            control = QLineEdit()
            control.setMaxLength(value.maxlength)
            if val is not None:
                control.setText(str(val).rstrip())
        else:
            control = QLineEdit(str(val) if val is not None else "")
            control.setReadOnly(True)

        if not value.get_mutable():
            control.setEnabled(False)
        try:
            warning = setting.get_warning(val)
        except Exception:
            warning = None
        if warning:
            control.setToolTip(warning)

        form.addRow(_(setting.get_shortname()) + ":", control)
        self._extra_controls.append((setting, control))

    def apply(self):
        """Write dialog values into the memory object.
        Returns the modified Memory on success."""
        mem = self.mem
        for name, control in self._fields.items():
            raw = (control.currentText() if isinstance(control, QComboBox)
                   else control.text())
            if name == "power":
                level = None
                levels = getattr(
                    self._features, "valid_power_levels", None) or []
                for cand in levels:
                    if raw == str(cand):
                        level = cand
                        break
                setattr(mem, name, level)
            elif name in ("freq", "offset"):
                setattr(mem, name, chirp_common.parse_freq(raw) if raw else 0)
            elif name in ("rtone", "ctone", "tuning_step"):
                setattr(mem, name, float(raw) if raw else 88.5)
            elif name == "dtcs":
                setattr(mem, name, int(raw) if raw else 23)
            else:
                setattr(mem, name, raw)
        for setting, control in self._extra_controls:
            value = setting.value
            if not control.isEnabled() or not value.get_mutable():
                continue
            if isinstance(control, QCheckBox):
                new_val = control.isChecked()
            elif isinstance(control, QComboBox):
                new_val = control.currentText()
            elif isinstance(control, QSpinBox):
                new_val = control.value()
            elif isinstance(control, QDoubleSpinBox):
                new_val = float(control.value())
            else:
                new_val = control.text()
            try:
                value.set_value(new_val)
            except Exception:
                pass
        return mem
