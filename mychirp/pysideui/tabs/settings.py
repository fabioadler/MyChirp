"""Settings tab: NavigationRail-like group list + form body.

Mirrors the CHIRP Treebook: left column lists RadioSettingGroups, the
right shows controls typed by RadioSettingValue, Apply writes back.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
    QSpinBox,
    QLineEdit,
    QCheckBox,
)

from mychirp import settings as chirp_settings
from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.radio_service import get_service
from mychirp.pysideui.theme import AppColors

LOG = logging.getLogger(__name__)

_GROUP_WIDTH = 230
_CONTROL_WIDTH = 360


class GroupListItem(QListWidgetItem):
    def __init__(self, group):
        super().__init__(group.get_shortname())
        self.group = group


class SettingsTab(QWidget):
    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state
        self.groups: list = []
        self._controls: list = []  # list of (setting, widget)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        self.group_list = QListWidget()
        self.group_list.setMaximumWidth(_GROUP_WIDTH)
        self.group_list.itemSelectionChanged.connect(self._on_group_selected)
        splitter.addWidget(self.group_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(12)

        self.group_title = QLabel("")
        self.group_title.setProperty("heading", True)
        self.group_title.setStyleSheet("font-size: 16px;")
        right_layout.addWidget(self.group_title)

        self.fields_scroll = QScrollArea()
        self.fields_scroll.setWidgetResizable(True)
        self.fields_widget = QWidget()
        self.fields_form = QFormLayout(self.fields_widget)
        self.fields_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.fields_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.fields_scroll.setWidget(self.fields_widget)
        right_layout.addWidget(self.fields_scroll, 1)

        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        self.apply_btn = QPushButton(_("Apply to radio"))
        self.apply_btn.setProperty("accent", True)
        self.apply_btn.clicked.connect(self._on_apply)
        apply_row.addWidget(self.apply_btn)
        right_layout.addLayout(apply_row)

        splitter.addWidget(right)
        splitter.setSizes([_GROUP_WIDTH, 600])

    # ----- data -----
    def load_settings(self):
        service = get_service(self.state.main_window)

        self.state.set_status(_("Reading settings..."))

        def done(job):
            self.state.set_status("")
            if job.error or job.result is None:
                self.state.set_status(_("Failed to read settings"))
                LOG.error("settings load failed: %s", job.error)
                self.groups = []
                self._rebuild_groups()
                return
            self.groups = list(job.result)
            self.state.set_status(_("Settings loaded"))
            self._rebuild_groups()

        service.load_settings(self.eset.radio, done)

    def _rebuild_groups(self):
        self.group_list.clear()
        for g in self.groups:
            self.group_list.addItem(GroupListItem(g))
        if self.groups:
            self.group_list.setCurrentRow(0)
            self._show_group(self.groups[0])
        else:
            self.group_title.setText(_("No settings available"))
            self._clear_form()

    def _clear_form(self):
        while self.fields_form.rowCount():
            self.fields_form.removeRow(0)
        self._controls.clear()

    def _show_group(self, group):
        self.group_title.setText(group.get_shortname())
        self._clear_form()

        def render(container, depth=0):
            for name, element in container.items():
                if isinstance(element, chirp_settings.RadioSetting):
                    self._add_setting_row(element, depth)
                elif isinstance(element, chirp_settings.RadioSettingGroup):
                    subtitle = QLabel(element.get_shortname())
                    subtitle.setStyleSheet(
                        "font-size: 13px; font-weight: 600; "
                        "margin-top: 16px;")
                    self.fields_form.addRow(subtitle)
                    render(element, depth + 1)

        render(group)

    def _add_setting_row(self, setting, depth=0):
        value = setting.value
        mutable = value.get_mutable()
        text = _(setting.get_shortname())
        doc = _(setting.__doc__) if setting.__doc__ else None

        label_layout = QVBoxLayout()
        name = QLabel(text)
        name.setStyleSheet("font-size: 13px; font-weight: 500;")
        label_layout.addWidget(name)
        if doc:
            d = QLabel(doc)
            d.setProperty("muted", True)
            d.setWordWrap(True)
            d.setStyleSheet("font-size: 10px;")
            label_layout.addWidget(d)

        container = QWidget()
        container.setLayout(label_layout)

        control = self._control_for(setting, value)
        control.setMinimumWidth(180)
        control.setMaximumWidth(_CONTROL_WIDTH)
        control.setToolTip(setting.get_name())
        if not mutable:
            control.setEnabled(False)

        self.fields_form.addRow(container, control)
        self._controls.append((setting, control))

    def _control_for(self, setting, value):
        """Return a typed widget for one RadioSettingValue."""
        try:
            val = value.get_value()
        except Exception:
            val = None

        if isinstance(value, chirp_settings.RadioSettingValueBoolean):
            cb = QCheckBox()
            cb.setChecked(bool(val))
            return cb

        if isinstance(value, chirp_settings.RadioSettingValueList):
            combo = QComboBox()
            options = [str(o) for o in value.get_options()]
            combo.addItems(options)
            if val is not None and str(val) in options:
                combo.setCurrentText(str(val))
            elif val is not None:
                combo.addItem(str(val))
                combo.setCurrentText(str(val))
            return combo

        if isinstance(value, chirp_settings.RadioSettingValueInteger):
            spin = QSpinBox()
            spin.setRange(value.get_min(), value.get_max())
            if val is not None:
                try:
                    spin.setValue(int(val))
                except (TypeError, ValueError):
                    pass
            return spin

        if isinstance(value, chirp_settings.RadioSettingValueFloat):
            spin = QDoubleSpinBox()
            spin.setRange(value.get_min(), value.get_max())
            spin.setDecimals(value._pre)
            if val is not None:
                try:
                    spin.setValue(float(val))
                except (TypeError, ValueError):
                    pass
            return spin

        if isinstance(value, chirp_settings.RadioSettingValueString):
            edit = QLineEdit()
            edit.setMaxLength(value.maxlength)
            if val is not None:
                edit.setText(str(val).rstrip())
            return edit

        # Unknown value: read-only
        edit = QLineEdit(str(val) if val is not None else "")
        edit.setReadOnly(True)
        return edit

    def _collect(self):
        """Read dialog controls back into RadioSetting values.

        Disabled (read-only) controls and settings flagged immutable are
        skipped: they can't be changed by the user, so validation would
        fire spurious errors/warnings on apply.
        """
        errors, warnings = [], []
        for setting, control in self._controls:
            value = setting.value
            # Skip read-only / immutable settings entirely
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
            except Exception as e:
                errors.append("%s: %s" % (setting.get_shortname(), e))
                continue
            w = setting.get_warning(value.get_value())
            if w:
                warnings.append(w)
        return errors, warnings

    def _on_apply(self):
        errors, warnings = self._collect()
        if errors:
            QMessageBox.warning(
                self, _("Invalid value(s)"), "\n".join(errors))
            return
        if warnings:
            reply = QMessageBox.question(
                self, _("Warning"),
                _("Some settings reported warnings:") + "\n\n"
                + "\n".join(warnings) + "\n\n" + _("Proceed anyway?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._do_apply()

    def _do_apply(self):
        service = get_service(self.state.main_window)
        self.state.set_status(_("Applying settings..."))

        def done(job):
            self.state.set_status("")
            if job.error:
                self.state.set_status(_("Failed to apply settings"))
                LOG.exception("apply failed: %s", job.error)
                QMessageBox.warning(
                    self, _("Error applying settings"), str(job.error))
            else:
                self.eset.modified = True
                self.state.set_status(_("Settings applied"))

        service.save_settings(self.eset.radio, self.groups, done)

    def retheme(self):
        pass

    def _on_group_selected(self):
        items = self.group_list.selectedItems()
        if items:
            self._show_group(items[0].group)
