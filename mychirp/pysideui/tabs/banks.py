"""Banks tab: memory × bank matrix with checkboxes."""

import logging

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from mychirp.pysideui.i18n import _

LOG = logging.getLogger(__name__)


class BanksModel(QAbstractTableModel):
    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.banks = []
        self.memories = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.memories)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 2 + len(self.banks)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        mem = self.memories[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return str(mem.number)
            if index.column() == 1:
                return mem.name or ""
        elif role == Qt.ItemDataRole.CheckStateRole:
            if index.column() >= 2:
                bank = self.banks[index.column() - 2]
                try:
                    members = {
                        b.get_index() for b in
                        self.tab.bank_model.get_memory_mappings(mem)}
                    return (
                        Qt.CheckState.Checked if bank.get_index() in members
                        else Qt.CheckState.Unchecked)
                except Exception:
                    return Qt.CheckState.Unchecked
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.CheckStateRole:
            return False
        if index.column() < 2:
            return False
        mem = self.memories[index.row()]
        bank = self.banks[index.column() - 2]
        try:
            if value == Qt.CheckState.Checked.value or value is True:
                self.tab.bank_model.add_memory_to_bank(mem, bank)
            else:
                self.tab.bank_model.remove_memory_from_bank(mem, bank)
            self.tab.eset.modified = True
            return True
        except Exception:
            LOG.exception("Failed toggling bank membership")
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
            bank = self.banks[section - 2]
            return bank.get_name()
        return super().headerData(section, orientation, role)

    def flags(self, index):
        f = super().flags(index)
        f |= Qt.ItemFlag.ItemIsEnabled
        if index.column() >= 2:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f


class BanksTab(QWidget):
    def __init__(self, eset, state, parent=None):
        super().__init__(parent)
        self.eset = eset
        self.state = state
        self.bank_model = eset.radio.get_bank_model()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

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
        root.addWidget(self.table, 1)

    def refresh(self):
        try:
            self.model.banks = list(self.bank_model.get_mappings())
        except Exception:
            LOG.exception("Failed to list banks")
            self.model.banks = []

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
