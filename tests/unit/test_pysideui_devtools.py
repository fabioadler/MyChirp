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


def test_bug_report_dialog_popup(qapp, state):
    """Popup de reporte: logos + e-mail de contato + cópia de logs."""
    from mychirp.pysideui.dialogs.devtools import BugReportDialog
    dlg = BugReportDialog(None, state, None)

    # e-mail de contato visível e clicável (mailto:)
    assert BugReportDialog.CONTACT_EMAIL == "adlercyberlab@gmail.com"
    assert BugReportDialog.CONTACT_EMAIL in dlg.email_label.text()
    assert dlg.email_label.openExternalLinks()

    # logos da empresa e do sistema criados (assets do share/)
    assert dlg.company_logo is not None
    assert dlg.system_logo is not None

    # copiar e-mail coloca o endereço no clipboard
    dlg.copy_email()
    assert QApplication.clipboard().text() == \
        BugReportDialog.CONTACT_EMAIL

    # copiar logs coloca conteúdo (log real ou aviso de ausência)
    dlg.copy_logs()
    text = QApplication.clipboard().text()
    assert isinstance(text, str) and text
    dlg.close()


def test_bug_report_dialog_no_legacy_home_fallback(state):
    """O caminho do log vive DENTRO da pasta do projeto (sem fallback
    ~/.chirp legado)."""
    from mychirp.pysideui.dialogs import devtools
    path = devtools.debug_log_path()
    assert "logs" in path
    assert os.path.normpath(path).startswith(
        os.path.normpath(os.path.join(
            os.path.dirname(devtools.__file__), "..", "..", "..")))


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
    # popup de reporte com rádio aberto: contato + logs continuam
    # disponíveis (o popup não depende do estado do editor)
    assert BugReportDialog.CONTACT_EMAIL in bug.email_label.text()
    bug.copy_logs()
    assert QApplication.clipboard().text()
    bug.close()


def test_main_window_report_bug_action_enabled(qapp, state):
    """A ação 'Report a bug...' do menu Help está habilitada."""
    from mychirp.pysideui.widgets.main_window import MainWindow
    win = MainWindow(state)
    state.main_window = win
    assert win.action_report_bug.isEnabled()
    win.close()
