"""Memories tab: QTableView grid + operations toolbar + edit dialog.

Mirrors the flet MemoriesScreen semantics but powered by
QAbstractTableModel/QTableView: shared pagination-free scrollable grid,
empty-channel overlay, channel ops toolbar, undo/redo-aware ops and
file cross-paste.
"""

import logging
import os

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
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
from mychirp.pysideui.theme import AppColors
from mychirp.pysideui.dialogs.memory_edit import MemoryEditDialog

LOG = logging.getLogger(__name__)


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


def _render(name, mem):
    if mem is None or mem.empty:
        return ""
    try:
        if name == "freq":
            return chirp_common.format_freq(mem.freq)
        if name == "offset":
            return chirp_common.format_freq(mem.offset)
        if name == "power":
            return str(mem.power) if mem.power else ""
        if name in ("rtone", "ctone"):
            return "%.1f" % getattr(mem, name)
        if name == "tuning_step":
            return "%.1f" % getattr(mem, name)
        return str(getattr(mem, name, ""))
    except Exception as e:
        LOG.debug("render %s failed: %s", name, e)
        return ""


class MemoryModel(QAbstractTableModel):
    """Table model over a dict {number: Memory}."""

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self._rows: list = []  # list of Memory in display order
        self._editing = False

    # ----- Qt API -----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        if not (0 <= index.row() < len(self._rows)):
            return None
        mem = self._rows[index.row()]
        col = self.columns[index.column()]
        if col == "loc":
            return self._loc(mem)
        return _render(col, mem)

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


class MemoriesTab(QWidget):
    """Memory grid with toolbar + inline cell editing."""

    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state
        self.columns = ["loc"] + _visible_columns(eset.features)
        self.model = MemoryModel(self.columns)
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
            QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(
            self._sort_by_column)
        self.table.doubleClicked.connect(self._edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._add_context_actions()
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

    def _selected_number(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        mem = self.model.row_memory(rows[0].row())
        return mem.number if mem is not None else None

    def _selected_mem(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        mem = self.model.row_memory(rows[0].row())
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
        self.eset.modified = True
        self.load_memories()

    def op_copy(self):
        mem = self._selected_mem()
        if mem is None:
            self.state.set_status(_("Select a channel to copy first"))
            return
        self.state.memory_clipboard = (mem.dupe(), self.eset.features)
        self.state.set_status(
            _("Copied channel %s") % self._loc(mem))

    def op_paste(self):
        if not self._require_selection():
            return
        if not self.state.memory_clipboard:
            self.state.set_status(_("Clipboard is empty"))

            return
        src_mem, src_features = self.state.memory_clipboard
        self._run_op(
            memory_ops.paste_memory, src_mem, src_features,
            self._selected_number())

    def op_insert(self):
        if not self._require_selection():
            return
        self._run_op(memory_ops.insert_memories,
                     self._selected_number(), 1)

    def op_delete_menu(self):
        if not self._require_selection():
            return
        mem = self._selected_mem()
        menu = QMessageBox(self)
        menu.setWindowTitle(_("Delete"))
        menu.setText(_("Delete channel %s?") % self._loc(mem))
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
        if clicked is simple:
            self._run_op(memory_ops.delete_memories,
                         [self._selected_number()], None)
        elif clicked is shift_block:
            self._run_op(memory_ops.delete_memories,
                         [self._selected_number()], "block")
        elif clicked is shift_all:
            self._run_op(memory_ops.delete_memories,
                         [self._selected_number()], "all")

    def op_move(self, delta):
        if not self._require_selection():
            return
        self._run_op(memory_ops.move_memory, self._selected_number(), delta)

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
        self._run_op(memory_ops.undoable_delete, []),
        try:
            self.eset.undo_stack.undo()
        except Exception as e:
            self.state.set_status(str(e))
            return
        self.load_memories()

    def op_redo(self):
        if not self.eset.undo_stack.can_redo():
            self.state.set_status(_("Nothing to redo"))
            return
        try:
            self.eset.undo_stack.redo()
        except Exception as e:
            self.state.set_status(str(e))
            return
        self.load_memories()

    def op_export(self):
        if self.state.main_window:
            self.state.main_window.export_current_csv()

    # ----- edit -----
    def _edit_selected(self):
        mem = self._selected_mem()
        if mem is None:
            return
        from mychirp.pysideui.dialogs.memory_edit import MemoryEditDialog
        dlg = MemoryEditDialog(self, mem, self.eset.features)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dlg.apply()
            self.eset.modified = True
            self.load_memories()
            self.state.set_status(
                _("Memory %s updated") % self._loc(mem))

    # ----- keyboard helpers used by the main window shortcuts -----
    def copy_selected(self):
        self.op_copy()

    def paste_selected(self):
        self.op_paste()

    def cut_selected(self):
        if not self._require_selection():
            return
        self.op_copy()
        self._run_op(memory_ops.delete_memories,
                     [self._selected_number()], None)

    def delete_selected(self, shift=None):
        if not self._require_selection():
            return
        self._run_op(memory_ops.delete_memories,
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
