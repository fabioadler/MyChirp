"""Memories tab: QTableView grid + operations toolbar + edit dialog.

Mirrors the flet MemoriesScreen semantics but powered by
QAbstractTableModel/QTableView: shared pagination-free scrollable grid,
empty-channel overlay, channel ops toolbar, undo/redo-aware ops and
file cross-paste.
"""

import logging

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from mychirp import chirp_common
from mychirp import memory_ops
from mychirp.pysideui.i18n import _
from mychirp.pysideui.services.radio_service import get_service
from mychirp.pysideui.dialogs.memory_edit import MemoryEditDialog

LOG = logging.getLogger(__name__)


_FREQ_MAX_HZ = 2_000_000_000

# Same column logic as the flet UI
COLUMN_LABELS = {
    "loc": _("Loc"),
    "freq": _("Frequency"),
    "name": _("Name"),
    "tmode": _("Tone Mode"),
    "rtone": _("Tone"),
    "ctone": _("ToneSql"),
    "dtcs": _("DTCS Code"),
    "duplex": _("Duplex"),
    "offset": _("Offset"),
    "mode": _("Mode"),
    "tuning_step": _("Tune Step"),
    "skip": _("Skip"),
    "power": _("Power"),
    "comment": _("Comment"),
}


def _visible_columns(features):
    checks = {
        "freq": True,
        "name": lambda: getattr(features, "has_name", False),
        "tmode": lambda: bool(getattr(features, "valid_tmodes", None)),
        "rtone": lambda: bool(getattr(features, "valid_tones", None)),
        "ctone": lambda: bool(getattr(features, "valid_tones", None)),
        "dtcs": lambda: bool(getattr(features, "valid_dtcs_codes", None)),
        "duplex": lambda: bool(getattr(features, "valid_duplexes", None)),
        "offset": lambda: getattr(features, "has_offset", True),
        "mode": lambda: bool(getattr(features, "valid_modes", None)),
        "tuning_step": lambda: bool(
            getattr(features, "valid_tuning_steps", None)),
        "skip": lambda: bool(getattr(features, "valid_skips", None)),
        "power": lambda: bool(
            getattr(features, "valid_power_levels", None)
        ) or getattr(features, "has_variable_power", False),
        "comment": lambda: getattr(features, "has_comment", False),
    }
    out = []
    for name, check in checks.items():
        try:
            if check() if callable(check) else check:
                out.append(name)
        except Exception:
            pass
        if callable(check):
            pass
    # filters must run: evaluate
    out = []
    for name, check in checks.items():
        try:
            ok = check() if callable(check) else check
        except Exception:
            ok = False
        if ok:
            out.append(name)
    return out


def _used_tone_columns(mem):
    """Tone columns that matter for the memory's current tmode,
    mirroring the CHIRP memedit (others render blank)."""
    tmode = mem.tmode
    if tmode == "Tone":
        return {"rtone"}
    if tmode == "TSQL":
        return {"rtone", "ctone"}
    if tmode == "DTCS":
        return {"dtcs"}
    if tmode == "Cross":
        tx, _, rx = (mem.cross_mode or "").partition("->")
        used = set()
        if tx == "Tone":
            used.add("rtone")
        elif tx == "DTCS":
            used.add("dtcs")
        if rx == "Tone":
            used.add("ctone")
        elif rx == "DTCS":
            used.add("dtcs")
        return used
    return set()


def _render(name, mem):
    if mem is None or mem.empty:
        return ""
    try:
        if name == "freq":
            return chirp_common.format_freq(mem.freq)
        if name == "offset":
            if mem.duplex in ("+", "-", "split"):
                return chirp_common.format_freq(mem.offset)
            return ""
        if name == "power":
            return str(mem.power) if mem.power else ""
        if name in ("rtone", "ctone", "dtcs"):
            if name not in _used_tone_columns(mem):
                return ""
            if name == "dtcs":
                return "%03i" % mem.dtcs
            return "%.1f" % getattr(mem, name)
        if name == "tuning_step":
            return "%.1f" % getattr(mem, name)
        return str(getattr(mem, name, ""))
    except Exception as e:
        LOG.debug("render %s failed: %s", name, e)
        return ""


class CellDelegate:
    """Per-column editor factory (CHIRP memedit parity:

    - dropdown for tone/duplex/mode/skip/power/step lists (pick from
      the radio's valid_* features)
    - spin box for frequencies (freq, offset)
    - line edit for name/comment
    """

    @staticmethod
    def make(editor_type, parent, options=None, minimum=None, maximum=None,
             single_step=1.0, text=""):
        from PySide6.QtWidgets import (
            QComboBox, QDoubleSpinBox, QLineEdit)
        if editor_type == "combo":
            w = QComboBox(parent)
            w.setEditable(False)
            w.addItems([str(o) for o in (options or [])])
            if text and str(text) in [str(o) for o in options]:
                w.setCurrentText(str(text))
            elif text:
                w.insertItem(0, str(text))
                w.setCurrentIndex(0)
        elif editor_type == "spin":
            w = QDoubleSpinBox(parent)
            w.setRange(minimum or 0, maximum or 1e9)
            w.setSingleStep(single_step)
            w.setDecimals(5 if text and "." in str(text) else 0)
            try:
                w.setValue(float(text) if text else minimum or 0)
            except (ValueError, TypeError):
                w.setValue(minimum or 0)
        else:
            w = QLineEdit(parent)
            w.setText(str(text) if text is not None else "")
        return w

    @staticmethod
    def value(editor_type, editor):
        from PySide6.QtWidgets import QComboBox, QDoubleSpinBox
        if isinstance(editor, QComboBox):
            return editor.currentText()
        if isinstance(editor, QDoubleSpinBox):
            return editor.value()
        return editor.text()


class MemoryChunkDelegate(__import__("PySide6.QtWidgets", fromlist=[
        "QStyledItemDelegate"]).QStyledItemDelegate):
    """Inline editor for the columns CHIRP exposes as dropdowns."""
    # column name -> editor spec
    COLUMNS = {
        "tmode": "combo",
        "rtone": "combo",
        "ctone": "combo",
        "dtcs": "combo",
        "duplex": "combo",
        "mode": "combo",
        "skip": "combo",
        "power": "combo",
        "tuning_step": "combo",
        "freq": "spin",
        "offset": "spin",
        "name": "line",
        "comment": "line",
    }

    def __init__(self, columns, features, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.features = features

    def _spec(self, col_name):
        """Return (editor_type, options, min, max, step) for @col_name."""
        f = self.features
        if col_name == "tmode":
            return ("combo", list(getattr(f, "valid_tmodes") or []),
                    None, None, None)
        if col_name == "duplex":
            return ("combo", list(getattr(f, "valid_duplexes") or []),
                    None, None, None)
        if col_name == "mode":
            return ("combo", list(getattr(f, "valid_modes") or []),
                    None, None, None)
        if col_name == "skip":
            return ("combo", list(getattr(f, "valid_skips") or []),
                    None, None, None)
        if col_name in ("rtone", "ctone"):
            return ("combo", ["%.1f" % t for t in chirp_common.TONES],
                    None, None, None)
        if col_name == "dtcs":
            return ("combo", [str(c) for c in chirp_common.DTCS_CODES],
                    None, None, None)
        if col_name == "power":
            lvls = getattr(f, "valid_power_levels", None) or []
            return ("combo", [str(lvl) for lvl in lvls], None, None, None)
        if col_name == "tuning_step":
            steps = getattr(f, "valid_tuning_steps", None) or []
            return ("combo", ["%.1f" % s for s in steps], None, None, None)
        if col_name in ("freq", "offset"):
            return ("spin", None, 0, _FREQ_MAX_HZ // 1000000, 0.005)
        return ("line", None, None, None, None)

    def createEditor(self, parent, option, index):
        col = self.columns[index.column()]
        kind, options, minimum, maximum, step = self._spec(col)
        if kind == "spin":
            from PySide6.QtCore import QRegularExpression
            from PySide6.QtGui import QRegularExpressionValidator
            from PySide6.QtWidgets import QLineEdit
            w = QLineEdit(parent)
            w.setPlaceholderText("000.000000")
            w.setValidator(QRegularExpressionValidator(
                QRegularExpression(r"^\d{1,4}\.\d{1,6}$"), w))
            w.setMinimumHeight(30)
            return w
        w = CellDelegate.make(kind, parent, options=options,
                              minimum=minimum, maximum=maximum,
                              single_step=step)
        w.setMinimumHeight(30)
        return w

    def setEditorData(self, editor, index):
        col = self.columns[index.column()]
        mem = index.model().row_memory(index.row())
        kind = self._spec(col)[0]
        raw = getattr(mem, col, "")
        if kind == "combo":
            editor.setCurrentText(
                str(mem.power) if col == "power" and mem.power
                else str(raw))
            if editor.findText(str(raw)) == -1 and str(raw):
                editor.insertItem(0, str(raw))
                editor.setCurrentIndex(0)
        elif kind == "spin":
            try:
                editor.setText(chirp_common.format_freq(raw)
                               if isinstance(raw, int) else str(raw or ""))
            except Exception:
                editor.setText("")
        else:
            editor.setText(str(raw))

    def setModelData(self, editor, model, index):
        col = self.columns[index.column()]
        mem = index.model().row_memory(index.row())
        kind = self._spec(col)[0]
        new_val = CellDelegate.value(kind, editor)
        try:
            if col in ("freq", "offset"):
                # Decimal point is mandatory (CHIRP-style): 435.72500
                if "." not in str(new_val).strip():
                    raise ValueError(
                        "Use '.' na frequência, ex.: 435.72500")
                new_val = chirp_common.parse_freq(str(new_val).strip())
            elif col == "power":
                new_val = _power_from_text(self.features, new_val)
            elif col in ("rtone", "ctone", "tuning_step"):
                new_val = float(new_val or "88.5")
            elif col == "dtcs":
                new_val = int(new_val or 23)
            was_empty = mem.empty
            setattr(mem, col, new_val)
            mem.empty = False
            if was_empty and mem.power is None:
                mem.power = _default_power(self.features)
            model.dataChanged.emit(index, index)
        except (ValueError, TypeError) as e:
            LOG.debug("invalid value %r for %s: %s", new_val, col, e)


class MemoryModel(QAbstractTableModel):
    """Table model over a dict {number: Memory}."""

    READ_ONLY = {"loc"}

    def __init__(self, columns, features, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.features = features
        self._rows: list = []

    # ----- Qt API -----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if not (0 <= index.row() < len(self._rows)):
            return None
        mem = self._rows[index.row()]
        col = self.columns[index.column()]

        if role == Qt.ItemDataRole.ForegroundRole and mem.empty:
            return QColor("#888888")
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == "loc":
                return _loc_value(mem)
            if role == Qt.ItemDataRole.EditRole:
                return getattr(mem, col, "")
            return _render(col, mem)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        col = self.columns[index.column()]
        mem = self._rows[index.row()]
        try:
            if col in ("freq", "offset"):
                value = chirp_common.parse_freq(value) if value else 0
            elif col in ("rtone", "ctone", "tuning_step"):
                value = float(value) if value else 88.5
            elif col == "dtcs":
                value = int(value) if value else 23
            setattr(mem, col, value)
            mem.empty = False
            self.dataChanged.emit(index, index, [role])
            return True
        except (ValueError, TypeError) as e:
            LOG.debug("invalid value %r for %s: %s", value, col, e)
            return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.columns):
                return COLUMN_LABELS.get(
                    self.columns[section], self.columns[section].title())
        return super().headerData(section, orientation, role)

    def flags(self, index):
        f = super().flags(index)
        if not index.isValid():
            return f
        if self.columns[index.column()] != "loc":
            f |= Qt.ItemFlag.ItemIsEditable
        return f | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    # ----- helpers -----
    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row_memory(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def index_of_number(self, number):
        for i, m in enumerate(self._rows):
            if m.number == number:
                return i
        return -1

    @staticmethod
    def _loc(mem):
        extd = getattr(mem, "extd_number", None)
        return extd if extd else str(mem.number)


def _loc_value(mem):
    extd = getattr(mem, "extd_number", None)
    return extd if extd else str(mem.number)


def _power_from_text(features, text):
    """Resolve a power combo string back to the radio's PowerLevel
    object (CHIRP memedit parity). Empty -> None (radio default)."""
    text = str(text or "").strip()
    levels = getattr(features, "valid_power_levels", None) or []
    for level in levels:
        if text == str(level):
            return level
    return None


def _default_power(features):
    """First entry of valid_power_levels is the highest ("High")."""
    levels = getattr(features, "valid_power_levels", None) or []
    return levels[0] if levels else None


class MemoriesTab(QWidget):
    """Memory grid with toolbar + inline cell editing."""

    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state
        self.columns = ["loc"] + _visible_columns(eset.features)
        self.model = MemoryModel(self.columns, eset.features)
        self._rows_all: list = []
        self.hide_empty = False
        self.on_loaded = None
        self._build()

    # ----- layout -----
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Filter row
        top = QHBoxLayout()
        top.setSpacing(8)

        from PySide6.QtWidgets import QLineEdit
        line = QLineEdit()
        line.setPlaceholderText(self.tr(_("Filter channels...")))
        self.filter_edit = line
        self.filter_edit.returnPressed.connect(self.apply_filter)
        self.filter_edit.textChanged.connect(self.apply_filter)
        top.addWidget(self.filter_edit)

        self.find_btn = QPushButton("⏷ " + _("Find next"))
        self.find_btn.clicked.connect(self.find_next)
        top.addWidget(self.find_btn)

        top.addStretch(1)

        # Navigation
        for icon, tip, fn in (
            ("⏮", _("First page"), lambda: self._goto(0)),
            ("◀", _("Previous page"),
             lambda: self._goto(self.model.rowCount() - 1
                                if False else self._page - 1)),
            ("▶", _("Next page"),
             lambda: self._goto(self._page + 1)),
        ):
            btn = QPushButton(icon)
            btn.setFixedWidth(36)
            btn.setToolTip(tip)
            btn.clicked.connect(fn)
            top.addWidget(btn)

        self.page_info = QLabel("")
        self.page_info.setProperty("muted", True)
        top.addWidget(self.page_info)

        root.addLayout(top)

        # Ops toolbar
        ops = QHBoxLayout()
        ops.setSpacing(8)
        for icon, text, fn, accent in [
            ("⧉", _("Copy"), self.op_copy, False),
            ("📋", _("Paste"), self.op_paste, False),
            ("➕", _("Insert above"), self.op_insert, False),
            ("🗑", _("Delete"), self.op_delete_menu, False),
            ("↑", _("Move up"), lambda: self.op_move(-1), False),
            ("↓", _("Move down"), lambda: self.op_move(1), False),
            ("◎", _("Go to channel"), self.op_goto, False),
            ("↶", _("Undo"), self.op_undo, False),
            ("↷", _("Redo"), self.op_redo, False),
            ("📤", _("Export CSV"), self.op_export, False),
        ]:
            btn = QPushButton(icon + " " + text)
            btn.setToolTip(text)
            btn.clicked.connect(fn)
            if accent:
                btn.setProperty("accent", True)
            ops.addWidget(btn)
        ops.addStretch(1)
        root.addLayout(ops)

        # Table
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.verticalHeader().setMinimumSectionSize(34)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(
            self._sort_by_column)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked)
        self.model.dataChanged.connect(self._on_cells_edited)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._add_context_actions()
        self.table.setItemDelegate(
            MemoryChunkDelegate(self.columns, self.eset.features,
                                parent=self.table))
        root.addWidget(self.table, 1)

        # State
        self.sort_column = None
        self.sort_reverse = False
        self._page = 0

    def _add_context_actions(self):
        from PySide6.QtGui import QAction
        act_edit = QAction(_("Edit channel..."), self)
        act_edit.triggered.connect(self._edit_selected)
        self.table.addAction(act_edit)
        act_copy = QAction(_("Copy"), self)
        act_copy.triggered.connect(self.op_copy)
        self.table.addAction(act_copy)
        act_past = QAction(_("Paste"), self)
        act_past.triggered.connect(self.op_paste)
        self.table.addAction(act_past)

    # ----- data -----
    def load_memories(self):
        service = get_service(self.state.main_window)

        self.state.set_status(_("Reading memories..."))

        def done(job):
            self.state.set_status("")
            if job.error:
                LOG.exception("load_memories failed")
                self.state.set_status(_("Failed to read memories"))
                self.model.set_rows([])
                return
            self.eset.memories = job.result
            self.state.set_status(
                _("%i channels loaded") % len(job.result))
            self._refresh_rows()
            if self.on_loaded:
                try:
                    self.on_loaded()
                except Exception:
                    LOG.exception("on_loaded callback failed")

        service.load_memories(self.eset.radio, done)

    def _filtered_rows(self):
        items = sorted(self.eset.memories.items(),
                       key=lambda kv: (isinstance(kv[0], str), kv[0]))
        rows = []
        for number, mem in items:
            if self.hide_empty and mem.empty:
                continue
            if self.filter_edit.text():
                haystack = " ".join(
                    _render(c, mem) for c in self.columns).lower()
                if self.filter_edit.text().lower() not in haystack:
                    continue
            rows.append(mem)
        if self.sort_column:
            try:
                rows = sorted(
                    rows,
                    key=lambda m: (
                        m.number is None, getattr(
                            m, self.sort_column, "")),
                    reverse=self.sort_reverse)
            except Exception:
                LOG.exception("sort failed")
        return rows

    def _refresh_rows(self, page=None):
        rows = self._filtered_rows()
        self._rows_all = rows
        if page is not None:
            self._page = page
        pages = max(1, -(-len(rows) // 50))
        self._page = max(0, min(self._page, pages - 1))
        start = self._page * 50
        self.model.set_rows(rows[start:start + 50])
        self.page_info.setText(_("%i-%i / %i") % (
            start + 1 if rows else 0,
            min(start + 50, len(rows)), len(rows)))

    # ----- actions -----
    def apply_filter(self):
        self._page = 0
        self._refresh_rows()

    def _on_hide_toggled(self, checked):
        self.hide_empty = bool(checked)
        self._page = 0
        self._refresh_rows()

    def _goto(self, page):
        self._page = max(0, page)
        self._refresh_rows()

    def _sort_by_column(self, index):
        col = self.columns[index]
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._page = 0
        self._refresh_rows()

    def _selected_rows(self):
        """All selected row indexes (sorted), for batch operations."""
        rows = sorted(
            r.row() for r in self.table.selectionModel().selectedRows())
        return rows

    def _selected_memories_list(self):
        """All selected memories as Memory objects, in row order."""
        rows = self._selected_rows()
        return [self.model.row_memory(r) for r in rows]

    def _selected_number(self):
        rows = self._selected_rows()
        if not rows:
            return None
        mem = self.model.row_memory(rows[0])
        return mem.number if mem is not None else None

    def _selected_mem(self):
        rows = self._selected_rows()
        if not rows:
            return None
        mem = self.model.row_memory(rows[0])
        return mem

    def select_all(self):
        if self.model.rowCount():
            self.table.selectRow(0)

    def find_next(self):
        query = self.filter_edit.text().strip().lower()
        if not query:
            return
        rows = self._filtered_rows()
        if not rows:
            self.state.set_status(_("No match"))
            return
        cur = self._selected_number()
        start = 0
        if cur is not None:
            for i, m in enumerate(rows):
                if m.number == cur:
                    start = i + 1
                    break
        for i in range(len(rows)):
            mem = rows[(start + i) % len(rows)]
            haystack = " ".join(
                _render(c, mem) for c in self.columns).lower()
            if query in haystack:
                idx = self.model.index_of_number(mem.number)
                if idx >= 0:
                    self.table.selectRow(idx)
                    self.table.scrollTo(self.model.index(idx, 0))
                self.state.set_status(_("Found channel %s") % mem.number)
                return
        self.state.set_status(_("No match"))

    # ----- memory operations -----
    def _require_selection(self):
        if self._selected_number() is None:
            self.state.set_status(_("Select a channel first"))
            return False
        return True

    def _run_op(self, fn, *args, on_done=None):
        service = get_service(self.state.main_window)
        self.state.set_status(_("Working..."))
        service.run_memory_op(fn, self.eset.radio, *args,
                              on_done=on_done or self._op_done)

    def _op_done(self, job):
        self.state.set_status("")
        if job.error:
            LOG.exception("memory op failed")
            self.state.set_status(str(job.error))
            return
        result = job.result
        if (isinstance(result, tuple) and len(result) == 2
                and callable(result[0]) and callable(result[1])):
            label = getattr(job.fn, "__name__", _("edit"))
            self.eset.undo_stack.push(label, result[0], result[1])
        self.eset.modified = True
        self.load_memories()

    def op_copy(self):
        mems = self._selected_memories_list()
        if not mems:
            self.state.set_status(_("Select a channel to copy first"))
            return
        # multi-row copy stores the selection as an ordered list; paste
        # will re-apply them contiguously (CHIRP behavior)
        self.state.memory_clipboard = (
            [m.dupe() for m in mems], self.eset.features)
        self.state.set_status(
            _("Copied %i channel(s)") % len(mems))

    def op_paste(self):
        if not self._require_selection():
            return
        if not self.state.memory_clipboard:
            self.state.set_status(_("Clipboard is empty"))
            return
        src_mems, src_features = self.state.memory_clipboard
        dst_number = self._selected_number()
        for i, src_mem in enumerate(src_mems):
            self._run_op(
                memory_ops.undoable_paste, src_mem, src_features,
                dst_number + i)

    def op_insert(self):
        if not self._require_selection():
            return
        count = len(self._selected_rows())
        if count < 1:
            count = 1
        self._run_op(memory_ops.undoable_insert,
                     self._selected_number(), count)

    def op_delete_menu(self):
        if not self._require_selection():
            return
        mems = self._selected_memories_list()
        count = len(mems)
        menu = QMessageBox(self)
        menu.setWindowTitle(_("Delete"))
        label = _("Delete channel %s?") % _loc_value(mems[0]) if count == 1 \
            else _("Delete %i channels?") % count
        menu.setText(label)
        simple = menu.addButton(
            _("Delete"), QMessageBox.ButtonRole.AcceptRole)
        shift_block = menu.addButton(
            _("Delete + shift block up"),
            QMessageBox.ButtonRole.DestructiveRole)
        shift_all = menu.addButton(
            _("Delete + shift everything"),
            QMessageBox.ButtonRole.DestructiveRole)
        cancel = menu.addButton(QMessageBox.StandardButton.Cancel)
        menu.exec()
        clicked = menu.clickedButton()
        if clicked is cancel:
            return
        numbers = [m.number for m in mems]
        if clicked is simple:
            self._run_op(memory_ops.undoable_delete, numbers, None)
        elif clicked is shift_block:
            self._run_op(memory_ops.undoable_delete, numbers, "block")
        elif clicked is shift_all:
            self._run_op(memory_ops.undoable_delete, numbers, "all")

    def op_move(self, delta):
        if not self._require_selection():
            return
        self._run_op(
            memory_ops.undoable_move, self._selected_number(), delta)

    def op_goto(self):
        lo, hi = self.eset.features.memory_bounds
        number, ok = QInputDialog.getInt(
            self, _("Go to channel"),
            _("Channel number (%i-%i):") % (lo, hi),
            value=lo, min=lo, max=hi)
        if not ok:
            return
        idx = self.model.index_of_number(number)
        if idx >= 0:
            self.table.selectRow(idx)
            self.table.scrollTo(self.model.index(idx, 0))
        else:
            self.state.set_status(_("Channel %s not found") % number)

    def op_undo(self):
        if not self.eset.undo_stack.can_undo():
            self.state.set_status(_("Nothing to undo"))
            return
        self._run_op(lambda: self.eset.undo_stack.undo())

    def op_redo(self):
        if not self.eset.undo_stack.can_redo():
            self.state.set_status(_("Nothing to redo"))
            return
        self._run_op(lambda: self.eset.undo_stack.redo())

    def op_export(self):
        if self.state.main_window:
            self.state.main_window.export_current_csv()

    # ----- edit -----
    def _persist_memory(self, mem):
        """Write an edited memory back into the radio's image (undoable)."""
        service = get_service(self.state.main_window)

        def done(job):
            if job.error:
                LOG.exception("set_memory failed")
                self.state.set_status(str(job.error))
                return
            result = job.result
            if (isinstance(result, tuple) and len(result) == 2
                    and callable(result[0]) and callable(result[1])):
                self.eset.undo_stack.push(
                    _("Edit channel %s") % _loc_value(mem),
                    result[0], result[1])
            self.eset.modified = True
            self._refresh_rows()
            self.state.set_status(
                _("Memory %s updated") % _loc_value(mem))

        service.run_memory_op(
            memory_ops.undoable_set, self.eset.radio, mem.dupe(),
            on_done=done)

    def _on_cells_edited(self, first, last, _roles):
        seen = set()
        for row in range(first.row(), last.row() + 1):
            mem = self.model.row_memory(row)
            if mem is None or mem.number in seen:
                continue
            seen.add(mem.number)
            if not mem.freq:
                bands = getattr(self.eset.features, "valid_bands", None)
                if bands:
                    mem.freq = bands[0][0]
            self._persist_memory(mem)

    def _edit_selected(self):
        mem = self._selected_mem()
        if mem is None:
            return
        dlg = MemoryEditDialog(self, mem, self.eset.features)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            was_empty = mem.empty
            dlg.apply()
            if not mem.freq:
                mem.freq = self.eset.features.valid_bands[0][0]
            if was_empty and mem.power is None:
                mem.power = _default_power(self.eset.features)
            mem.empty = False
            self._persist_memory(mem)

    # ----- keyboard helpers used by the main window shortcuts -----
    def copy_selected(self):
        self.op_copy()

    def paste_selected(self):
        self.op_paste()

    def cut_selected(self):
        if not self._require_selection():
            return
        self.op_copy()
        self._run_op(memory_ops.undoable_delete,
                     [self._selected_number()], None)

    def delete_selected(self, shift=None):
        if not self._require_selection():
            return
        self._run_op(memory_ops.undoable_delete,
                     [self._selected_number()], shift)

    def goto_channel_dialog(self):
        self.op_goto()

    def undo(self):
        self.op_undo()

    def redo(self):
        self.op_redo()

    def find_next_action(self):
        self.find_next()

    # ----- re-theme -----
    def retheme(self):
        self._refresh_rows()
