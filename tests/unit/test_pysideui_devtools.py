"""Offscreen tests for the developer tools and bug report dialogs."""

import os

import pytest
from PySide6.QtWidgets import QApplication

from mychirp.pysideui.services.app_state import AppState, EditorSetState

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def state(qapp):
    yield AppState()


def test_developer_dialog_no_radio(qapp, state):
    from mychirp.pysideui.dialogs.devtools import DeveloperDialog
    dlg = DeveloperDialog(None, state, None)
    assert dlg.tabs.count() == 3
    assert "Python" in dlg.features_view.toPlainText()
    dlg.close()


def test_bug_report_dialog_copy(qapp, state):
    from mychirp.pysideui.dialogs.devtools import BugReportDialog
    dlg = BugReportDialog(None, state, None)
    dlg.summary.setText("test summary")
    dlg.copy_diagnostics()
    text = QApplication.clipboard().text()
    assert "PySide6" in text
    assert "test summary" in text
    assert "(none open)" in text
    dlg.close()


def test_debug_log_tail(state):
    from mychirp.pysideui.dialogs import devtools
    text = devtools.read_debug_log_tail()
    assert isinstance(text, str) and text


def test_hexdump():
    from mychirp.pysideui.dialogs.devtools import hexdump_text
    out = hexdump_text(b"hello world!")
    assert "68656c6c6f" not in out  # spaced hex
    assert "68 65 6c 6c 6f" in out
    assert "hello world!" in out


def test_dialogs_with_radio(qapp, state, tmp_path):
    from mychirp.drivers.generic_csv import CSVRadio
    from mychirp.pysideui.dialogs.devtools import (
        BugReportDialog, DeveloperDialog)

    img = str(tmp_path / "test.csv")
    with open(img, "w") as f:
        f.write("Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,"
                "cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,"
                "URCALL,RPT1CALL,RPT2CALL,DVCODE\n"
                "1,Test,146.520000,,0.600000,,88.5,88.5,023,NN,FM,5.00,"
                ",,,,,\n")
    radio = CSVRadio(img)
    eset = EditorSetState(radio, img)

    dlg = DeveloperDialog(None, state, eset)
    assert "Memory bounds" in dlg.features_view.toPlainText()
    dlg.close()

    bug = BugReportDialog(None, state, eset)
    bug.copy_diagnostics()
    text = QApplication.clipboard().text()
    assert "Driver module" in text
    assert "CSVRadio" in text
    bug.close()
