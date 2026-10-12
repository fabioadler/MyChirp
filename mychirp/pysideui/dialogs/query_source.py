"""Query network sources (RepeaterBook, DMR-MARC, ...) and import results."""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
)

from mychirp import chirp_common
from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.radio_service import get_service
from mychirp.pysideui.theme import AppColors
from mychirp.sources import base as source_base

LOG = logging.getLogger(__name__)

# name -> (module, class, extra fields builder key)
SOURCES = {
    "repeaterbook": ("mychirp.sources.repeaterbook", "RepeaterBook",
                     "RepeaterBook"),
    "radioreference": ("mychirp.sources.radioreference",
                       "RadioReferenceRadio", "RadioReference"),
    "dmrmarc": ("mychirp.sources.dmrmarc", "DMRMARCRadio", "DMR-MARC"),
    "przemienniki_eu": ("mychirp.sources.przemienniki_eu",
                        "PrzemiennikiEu", "przemienniki.eu"),
    "mapy73": ("mychirp.sources.mapy73pl", "Mapy73Pl", "mapy73.pl"),
    "amsat": ("mychirp.sources.amsats", "RadioAmateurSatellites", "AMSAT"),
    "satnogs": ("mychirp.sources.amsats", "SatNOGS", "SatNOGS"),
}


def load_source(source_name):
    """Import and instantiate the radio class for @source_name."""
    import importlib
    module_name, class_name, label = SOURCES[source_name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(), module, label


class _GuiStatus(source_base.QueryStatus):
    """QueryStatus that also forwards to a Qt signal (queued delivery)."""

    def __init__(self, signal):
        self._signal = signal

    def send_status(self, status, percent):
        super().send_status(status, percent)
        self._signal.emit(str(status), int(percent))

    def send_fail(self, reason):
        super().send_fail(reason)
        self._signal.emit(str(reason), -1)


class QuerySourceDialog(QDialog):
    """Search a network source and import results into the open radio."""

    progress = Signal(str, int)

    COLS = (_("Loc"), _("Name"), _("Frequency"), _("Mode"),
            _("Duplex"), _("Comment"))

    def __init__(self, parent, state, eset, source_name):
        super().__init__(parent)
        self.state = state
        self.eset = eset
        self.source_name = source_name
        self._source = None
        self._busy = False

        _unused, _module_name, label = SOURCES[source_name]
        self.setWindowTitle(_("Query %s") % label)
        self.resize(860, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Source-specific fields
        self._fields = {}
        self._build_source_fields(form)

        self.loc = QSpinBox()
        self.loc.setRange(0, 998)
        self.loc.setValue(0)
        form.addRow(_("Import starting at channel:"), self.loc)

        self.count = QSpinBox()
        self.count.setRange(1, 200)
        self.count.setValue(25)
        form.addRow(_("Number of memories:"), self.count)

        root.addLayout(form)

        top = QHBoxLayout()
        self.search_btn = QPushButton(_("Search"))
        self.search_btn.clicked.connect(self.search)
        top.addWidget(self.search_btn)

        self.progressbar = QProgressBar()
        self.progressbar.setMaximumHeight(12)
        self.progressbar.setTextVisible(False)
        self.progressbar.setVisible(False)
        top.addWidget(self.progressbar, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("muted", True)
        top.addWidget(self.status_label, 2)
        root.addLayout(top)

        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(self.COLS)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QTableView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText(
            _("Import"))
        buttons.accepted.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        # clicked(Apply) goes to apply() not accepted() in some styles
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply)
        root.addWidget(buttons)

        self.progress.connect(self._on_progress)

    # ----- source-specific fields -----
    def _add_field(self, form, key, label, widget):
        self._fields[key] = widget
        form.addRow(label, widget)

    def _text(self, form, key, label, default="", password=False):
        w = QLineEdit(default)
        if password:
            w.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_field(form, key, label, w)
        return w

    def _check(self, form, key, label, default=True):
        w = QCheckBox()
        w.setChecked(default)
        self._add_field(form, key, label, w)
        return w

    def _build_source_fields(self, form):
        name = self.source_name
        if name == "repeaterbook":
            try:
                from mychirp.sources import repeaterbook
                countries = repeaterbook.COUNTRIES
            except Exception:
                LOG.exception("Failed to load RepeaterBook countries")
                countries = []
            self.country = QComboBox()
            self.country.addItems(countries)
            self.country.currentTextChanged.connect(self._on_rb_country)
            self._add_field(form, "country", _("Country:"), self.country)
            self.state_combo = QComboBox()
            self._add_field(form, "state", _("State/Province:"),
                            self.state_combo)
            self._text(form, "filter", _("Filter:"))
            self._check(form, "openonly", _("Open repeaters only"))
            self._on_rb_country(self.country.currentText())
        elif name == "radioreference":
            self._text(form, "username", _("Username:"))
            self._text(form, "password", _("Password:"), password=True)
            combo = QComboBox()
            combo.addItems(["US", "CA"])
            self._add_field(form, "country", _("Country:"), combo)
            self._text(form, "zipcounty", _("ZIP (US) / County ID (CA):"))
        elif name == "dmrmarc":
            self._text(form, "country", _("Country:"))
            self._text(form, "state", _("State:"))
            self._text(form, "city", _("City:"))
        elif name == "przemienniki_eu":
            self._text(form, "band", _("Band (optional):"))
        elif name == "mapy73":
            self._text(form, "api_option", _("Filter (optional):"))
        elif name == "amsat" or name == "satnogs":
            pass

    def _on_rb_country(self, country):
        try:
            from mychirp.sources import repeaterbook
            states = repeaterbook.STATES.get(country, [])
        except Exception:
            LOG.exception("Failed to load RepeaterBook states")
            states = []
        self.state_combo.clear()
        if states:
            self.state_combo.setEnabled(True)
            self.state_combo.addItems(states)
        else:
            self.state_combo.setEnabled(False)
            self.state_combo.addItem(_("All"))

    # ----- parameter assembly -----
    def _field_text(self, key):
        w = self._fields.get(key)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def _build_params(self):
        name = self.source_name
        if name == "repeaterbook":
            return {
                "country": self.country.currentText(),
                "state": (self.state_combo.currentText()
                          if self.state_combo.isEnabled() else "all"),
                "service": "",
                "service_display": "",
                "lat": "", "lon": "", "dist": 0,
                "filter": self._field_text("filter"),
                "bands": [], "modes": [],
                "fmconv": False,
                "openonly": self._fields["openonly"].isChecked(),
                "cached": False,
            }
        if name == "radioreference":
            return {
                "country": self._fields["country"].currentText(),
                "zipcounty": self._field_text("zipcounty"),
            }
        if name == "dmrmarc":
            return {
                "country": self._field_text("country"),
                "state": self._field_text("state"),
                "city": self._field_text("city"),
            }
        if name == "przemienniki_eu":
            band = self._field_text("band")
            return {"band": band} if band else {}
        if name == "mapy73":
            return {"api_option": self._field_text("api_option")}
        return {}

    # ----- search -----
    def _set_busy(self, busy):
        self._busy = busy
        self.progressbar.setVisible(busy)
        self.search_btn.setEnabled(not busy)
        if busy:
            self.progressbar.setRange(0, 100)
            self.progressbar.setValue(0)

    def _on_progress(self, text, percent):
        colors = AppColors.for_mode(self.state.is_dark())
        if percent < 0:
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: %s" % colors.error)
        else:
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: %s" % colors.fg_muted)
            self.progressbar.setValue(min(percent, 100))

    def search(self):
        if self._busy:
            return
        try:
            source, _module, _label = load_source(self.source_name)
        except Exception:
            LOG.exception("Failed to load source %s", self.source_name)
            self._on_progress(_("Failed to load source"), -1)
            return

        if self.source_name == "radioreference":
            try:
                source.set_auth(self._field_text("username"),
                                self._field_text("password"))
            except Exception:
                LOG.exception("RadioReference auth setup failed")

        params = self._build_params()
        status = _GuiStatus(self.progress)
        self.model.removeRows(0, self.model.rowCount())
        self._set_busy(True)
        self._on_progress(_("Querying..."), 0)

        def _fetch():
            source.do_fetch(status, params)
            return source

        service = get_service(self)
        service.run_memory_op(_fetch, source, on_done=self._search_done)

    def _search_done(self, job):
        self._set_busy(False)
        if job.error:
            LOG.exception("Query failed")
            self._on_progress(_("Query failed: %s") % job.error, -1)
            return
        self._source = job.result
        try:
            features = self._source.get_features()
            lo, hi = features.memory_bounds
        except Exception:
            LOG.exception("Failed to read source features")
            lo, hi = 0, -1
        results = []
        for number in range(lo, hi + 1):
            try:
                mem = self._source.get_memory(number)
            except Exception:
                continue
            if mem is None or getattr(mem, "empty", False):
                continue
            results.append(mem)
        self._populate(results)
        self._on_progress(_("%i result(s)") % len(results), 100)

    def _populate(self, memories):
        self.model.removeRows(0, self.model.rowCount())
        for mem in memories:
            check = QStandardItem()
            check.setCheckable(True)
            check.setCheckState(Qt.CheckState.Checked)
            check.setEditable(False)
            number = QStandardItem(str(mem.number))
            vals = [
                number,
                QStandardItem(str(mem.name or "")),
                QStandardItem(chirp_common.format_freq(mem.freq)),
                QStandardItem(str(mem.mode or "")),
                QStandardItem(str(mem.duplex or "")),
                QStandardItem(str(mem.comment or "")),
            ]
            self.model.appendRow([check] + vals)
        self.table.resizeColumnsToContents()

    # ----- import -----
    def _selected_rows(self):
        rows = [r for r in range(self.model.rowCount())
                if self.model.item(r, 0).checkState()
                == Qt.CheckState.Checked]
        if not rows:
            rows = sorted({i.row() for i in
                           self.table.selectionModel().selectedRows()})
        return rows

    def _on_double_click(self, index):
        rows = [index.row()]
        if self._import_rows(rows):
            self.accept()

    def _on_apply(self):
        if not self._busy:
            self._import_rows(self._selected_rows())

    def _import_rows(self, rows):
        if self._source is None or not rows:
            return False
        if self.eset is None:
            self._on_progress(_("Open a radio first"), -1)
            return False
        max_count = self.count.value()
        rows = rows[:max_count]
        loc = self.loc.value()
        source = self._source
        eset = self.eset

        def _do_import():
            from mychirp import import_logic
            count = 0
            for i, row in enumerate(rows):
                try:
                    mem = source.get_memory(row)
                    import_logic.import_mem(
                        eset.radio,
                        source.get_features(),
                        mem,
                        overrides={"number": loc + i, "empty": False})
                    count += 1
                except Exception as e:
                    LOG.warning("import %s failed: %s", row, e)
            return count

        def done(job):
            if job.error:
                LOG.exception("Import failed")
                self._on_progress(_("Import failed: %s") % job.error, -1)
                return
            eset.modified = True
            self._on_progress(
                _("Imported %i channel(s)") % job.result, 100)
            parent = self.parent()
            if hasattr(parent, "refresh_current"):
                parent.refresh_current()

        service = get_service(self)
        service.run_memory_op(_do_import, eset.radio, on_done=done)
        return True
