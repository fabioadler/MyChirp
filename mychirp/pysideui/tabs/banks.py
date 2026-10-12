"""Banks tab: memory × bank matrix with checkboxes, indexes and import."""

import logging

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMenu,
    QInputDialog,
    QSpinBox,
    QStyledItemDelegate,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from mychirp import import_logic
from mychirp.pysideui.i18n import _

LOG = logging.getLogger(__name__)


class _IndexSpinDelegate(QStyledItemDelegate):
    """QSpinBox editor for the per-memory bank index column."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model

    def createEditor(self, parent, option, index):
        spin = QSpinBox(parent)
        try:
            lo, hi = self.model.tab.bank_model.get_index_bounds()
            spin.setRange(lo, hi)
        except Exception:
            LOG.exception("Failed to read bank index bounds")
        return spin

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole)
        try:
            editor.setValue(int(value))
        except (TypeError, ValueError):
            pass

    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


class BanksModel(QAbstractTableModel):
    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.banks = []
        self.memories = []
        self.index_supported = False

    def _bank_col_offset(self):
        return 3 if self.index_supported else 2

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.memories)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self._bank_col_offset() + len(
            self.banks)

    def memory_bank(self, mem):
        """First bank @mem belongs to, or None."""
        try:
            mappings = self.tab.bank_model.get_memory_mappings(mem)
        except Exception:
            LOG.exception("Failed to get memory mappings for %i",
                          getattr(mem, "number", -1))
            return None
        return mappings[0] if mappings else None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        mem = self.memories[index.row()]
        col = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 0:
                return str(mem.number)
            if col == 1:
                return mem.name or ""
            if self.index_supported and col == 2:
                bank = self.memory_bank(mem)
                if bank is None:
                    return ""
                try:
                    return self.tab.bank_model.get_memory_index(mem, bank)
                except Exception:
                    LOG.exception("Failed to get bank index of memory %i",
                                  mem.number)
                    return ""
        elif role == Qt.ItemDataRole.CheckStateRole:
            if col >= self._bank_col_offset():
                bank = self.banks[col - self._bank_col_offset()]
                try:
                    members = {
                        b.get_index() for b in
                        self.tab.bank_model.get_memory_mappings(mem)}
                    return (
                        Qt.CheckState.Checked if bank.get_index() in members
                        else Qt.CheckState.Unchecked)
                except Exception:
                    LOG.exception("Failed to check membership of memory %i",
                                  mem.number)
                    return Qt.CheckState.Unchecked
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        mem = self.memories[index.row()]
        col = index.column()
        offset = self._bank_col_offset()
        if role == Qt.ItemDataRole.CheckStateRole:
            if col < offset:
                return False
            bank = self.banks[col - offset]
            try:
                if value == Qt.CheckState.Checked.value or value is True:
                    self.tab.bank_model.add_memory_to_mapping(mem, bank)
                    if self.index_supported:
                        self.tab.bank_model.set_memory_index(
                            mem, bank,
                            self.tab.bank_model.get_next_mapping_index(bank))
                else:
                    self.tab.bank_model.remove_memory_from_mapping(mem, bank)
                self.tab.eset.modified = True
                self.dataChanged.emit(index, index, [role])
                return True
            except Exception:
                LOG.exception("Failed toggling bank membership")
                return False
        if role == Qt.ItemDataRole.EditRole and self.index_supported \
                and col == 2:
            bank = self.memory_bank(mem)
            if bank is None:
                return False
            try:
                self.tab.bank_model.set_memory_index(mem, bank, int(value))
                self.tab.eset.modified = True
                self.dataChanged.emit(index, index, [role])
                return True
            except Exception:
                LOG.exception("Failed to set bank index of memory %i",
                              mem.number)
                return False
        return False

    def headerData(self, section, orientation,
                   role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == 0:
                return _("Loc")
            if section == 1:
                return _("Name")
            if self.index_supported and section == 2:
                return _("Index")
            bank = self.banks[section - self._bank_col_offset()]
            return bank.get_name()
        return super().headerData(section, orientation, role)

    def flags(self, index):
        f = super().flags(index)
        f |= Qt.ItemFlag.ItemIsEnabled
        col = index.column()
        if col >= self._bank_col_offset():
            f |= Qt.ItemFlag.ItemIsUserCheckable
        elif self.index_supported and col == 2:
            mem = self.memories[index.row()]
            if self.memory_bank(mem) is not None:
                f |= Qt.ItemFlag.ItemIsEditable
        return f


class _ImportBankDialog(QDialog):
    def __init__(self, sources, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Import bank"))
        self.sources = sources
        self.source_banks = []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.radio_combo = QComboBox(self)
        for eset, _bm in sources:
            self.radio_combo.addItem(eset.tab_title)
        self.radio_combo.currentIndexChanged.connect(self._fill_banks)
        form.addRow(_("Source radio:"), self.radio_combo)

        self.bank_combo = QComboBox(self)
        form.addRow(_("Bank:"), self.bank_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._fill_banks(0)

    def _fill_banks(self, _row):
        self.bank_combo.clear()
        self.source_banks = []
        if not self.sources:
            return
        _eset, bm = self.sources[self.radio_combo.currentIndex()]
        try:
            for bank in bm.get_mappings():
                self.bank_combo.addItem(str(bank.get_name()))
                self.source_banks.append(bank)
        except Exception:
            LOG.exception("Failed to list source banks")

    def selection(self):
        if not self.sources or not self.source_banks:
            return None, None
        eset, _bm = self.sources[self.radio_combo.currentIndex()]
        return eset, self.source_banks[self.bank_combo.currentIndex()]


class BanksTab(QWidget):
    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state
        self.bank_model = eset.radio.get_bank_model()
        self._index_supported = self._supports_index()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        toolbar = QToolBar(self)
        toolbar.setMovable(False)
        self.import_action = toolbar.addAction(
            _("Import bank..."), self.import_bank)
        root.addWidget(toolbar)

        self.info = QLabel("")
        self.info.setProperty("muted", True)
        root.addWidget(self.info)

        self.model = BanksModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        if self._index_supported:
            self.table.setItemDelegateForColumn(
                2, _IndexSpinDelegate(self.model, self.table))

        header = self.table.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_menu)

        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_row_menu)

        root.addWidget(self.table, 1)

    def _supports_index(self):
        return all(hasattr(self.bank_model, name) for name in (
            "get_memory_index", "set_memory_index"))

    # ----- rename -----
    def _bank_supports_rename(self, bank):
        return hasattr(self.bank_model, "rename_bank") or hasattr(
            bank, "set_name")

    def _on_header_menu(self, pos):
        header = self.table.horizontalHeader()
        section = header.logicalIndexAt(pos)
        if section < self.model._bank_col_offset():
            return
        bank = self.model.banks[section - self.model._bank_col_offset()]
        if not self._bank_supports_rename(bank):
            return
        name, ok = QInputDialog.getText(
            self, _("Rename bank"), _("New name for bank %s:")
            % bank.get_name(), text=bank.get_name())
        if not ok or not name.strip():
            return
        try:
            if hasattr(self.bank_model, "rename_bank"):
                self.bank_model.rename_bank(bank, name.strip())
            else:
                bank.set_name(name.strip())
            self.eset.modified = True
            self.model.headerDataChanged.emit(
                Qt.Orientation.Horizontal, section, section)
            self.refresh()
        except Exception:
            LOG.exception("Failed to rename bank")

    # ----- row context menu -----
    def _on_row_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        mem = self.model.memories[index.row()]
        try:
            current = {b.get_index()
                       for b in self.bank_model.get_memory_mappings(mem)}
        except Exception:
            LOG.exception("Failed to read mappings of memory %i",
                          mem.number)
            current = set()

        menu = QMenu(self)
        add_menu = menu.addMenu(_("Add to bank"))
        remove_menu = menu.addMenu(_("Remove from bank"))
        for bank in self.model.banks:
            if bank.get_index() in current:
                remove_menu.addAction(
                    bank.get_name(),
                    lambda b=bank: self._remove_from_bank(mem, b))
            else:
                add_menu.addAction(
                    bank.get_name(),
                    lambda b=bank: self._add_to_bank(mem, b))
        add_menu.setEnabled(bool(add_menu.actions()))
        remove_menu.setEnabled(bool(remove_menu.actions()))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _add_to_bank(self, mem, bank):
        try:
            self.bank_model.add_memory_to_mapping(mem, bank)
            if self._index_supported:
                self.bank_model.set_memory_index(
                    mem, bank, self.bank_model.get_next_mapping_index(bank))
            self.eset.modified = True
            self.refresh()
        except Exception:
            LOG.exception("Failed to add memory %i to bank %s",
                          mem.number, bank.get_name())

    def _remove_from_bank(self, mem, bank):
        try:
            self.bank_model.remove_memory_from_mapping(mem, bank)
            self.eset.modified = True
            self.refresh()
        except Exception:
            LOG.exception("Failed to remove memory %i from bank %s",
                          mem.number, bank.get_name())

    # ----- import -----
    def import_bank(self):
        sources = []
        for es in self.state.editorsets:
            if es is self.eset:
                continue
            try:
                bm = es.radio.get_bank_model()
            except Exception:
                LOG.exception("Failed to get bank model of %s",
                              es.tab_title)
                continue
            if bm is not None:
                sources.append((es, bm))
        if not sources:
            self.state.set_status(
                _("No other open radio with banks to import from"))
            return

        dialog = _ImportBankDialog(sources, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        src_eset, src_bank = dialog.selection()
        if src_eset is None:
            return
        try:
            src_bm = src_eset.radio.get_bank_model()
            count = 0
            for src_mem in src_bm.get_mapping_memories(src_bank):
                try:
                    dst_mem = self.eset.radio.get_memory(src_mem.number)
                except Exception:
                    LOG.exception("Failed to get destination memory %i",
                                  src_mem.number)
                    continue
                import_logic.import_bank(
                    self.eset.radio, src_eset.radio, dst_mem, src_mem)
                count += 1
            self.eset.modified = True
            self.state.set_status(
                _("Imported %i memories from bank %s")
                % (count, src_bank.get_name()))
        except Exception:
            LOG.exception("Failed to import bank")
        self.refresh()

    def refresh(self):
        try:
            self.model.banks = list(self.bank_model.get_mappings())
        except Exception:
            LOG.exception("Failed to list banks")
            self.model.banks = []

        self.model.index_supported = self._index_supported

        mems = [
            m for m in self.eset.memories.values()
            if not m.empty and isinstance(m.number, int)
        ]
        mems.sort(key=lambda m: m.number)
        self.model.memories = mems
        self.model.layoutChanged.emit()
        self.info.setText(
            _("%i banks · %i channels") % (len(self.model.banks), len(mems)))

    def retheme(self):
        pass
