"""Offscreen tests for the write/restore GUI path (Qt)."""

import os
import tempfile
import time

import pytest

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)

from mychirp import directory, fwtool
from mychirp.pysideui.dialogs.fw_restore import FirmwareRestoreDialog
from mychirp.pysideui.services.radio_service import RadioJob


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def parent_widget(qapp):
    return QWidget()


@pytest.fixture
def tmp_state(tmp_path):
    from mychirp.config import ChirpConfig, ChirpConfigProxy
    from mychirp.pysideui.services.app_state import AppState
    state = AppState()
    state.conf = ChirpConfigProxy(ChirpConfig(str(tmp_path)), "state")
    return state


@pytest.fixture
def bf777_rclass():
    directory.import_drivers()
    r = directory.get_radio("Baofeng_BF-777S")
    assert r.PROGRAM_CMD == fwtool.H777_PROGRAM_CMD  # família h777
    return r


def _select(dlg, rclass):
    dlg.vendor.setCurrentText(rclass.VENDOR)
    label = ("%s %s" % (rclass.MODEL, getattr(rclass, "VARIANT", "")
                        or "")).strip()
    dlg.model.setCurrentText(label)


def test_h777_supported_and_other_refused(qapp, tmp_state, parent_widget,
                                          bf777_rclass):
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    _select(dlg, bf777_rclass)
    assert dlg._restore_supported(bf777_rclass)

    other = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if getattr(r, "PROGRAM_CMD", None) != fwtool.H777_PROGRAM_CMD),
        None)
    if other is not None:
        _select(dlg, other)
        assert not dlg._restore_supported(other)
        assert dlg.warn_label.text()


def test_image_picker_size_validation(qapp, tmp_state, parent_widget,
                                      bf777_rclass, tmp_path):
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    _select(dlg, bf777_rclass)

    good = tmp_path / "good.bin"
    good.write_bytes(b"\x00" * fwtool.H777_WINDOW_END)
    dlg._set_image(str(good))
    assert dlg.image_path == str(good)
    assert "SIZE MISMATCH" not in dlg.img_label.text()

    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\x00" * 77)
    dlg._set_image(str(bad))
    assert "SIZE MISMATCH" in dlg.img_label.text()


def _fake_input_class(text_holder):
    class _FakeInput:
        def __init__(self, *a, **k):
            pass
        def exec(self):
            return 1
        def textValue(self):
            return text_holder["text"]
        def setWindowTitle(self, t):
            pass
        def setLabelText(self, t):
            pass
        def setTextValue(self, t):
            pass
        def setTextEchoMode(self, m):
            pass
    return _FakeInput


def test_confirmation_flow_word(qapp, tmp_state, parent_widget,
                                bf777_rclass, monkeypatch):
    """Sem a palavra exata: escrita cancelada (sem tocar no rádio)."""
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    _select(dlg, bf777_rclass)

    # confirmação 1 respondendo No: cancela
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.No)
    assert dlg._confirm(bf777_rclass) is False

    # confirmação 1 Yes, palavra errada: cancela (com aviso modal
    # mockado — QString warning real travaria offscreen)
    text_holder = {"text": "ERRADO"}
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(
        "mychirp.pysideui.dialogs.fw_restore.QInputDialog",
        _fake_input_class(text_holder))
    assert dlg._confirm(bf777_rclass) is False

    # palavra exata "GRAVAR": confirma de fato
    text_holder["text"] = "GRAVAR"
    assert dlg._confirm(bf777_rclass) is True


def test_restore_service_calls_fwtool(qapp, tmp_state, bf777_rclass,
                                      monkeypatch):
    from mychirp.pysideui.services import radio_service as rs
    calls = []

    def fake_restore(radio_id, port, image):
        calls.append((radio_id, port, len(image)))
        return {"ok": True, "diffs": [], "aborted": None,
                "sha_old": "aa" * 32, "sha_new": "bb" * 32,
                "pre_path": "/p", "post_path": "/q"}

    fd, img_path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(fd, "wb") as f:
        f.write(b"\x00" * fwtool.H777_WINDOW_END)

    monkeypatch.setattr(rs.directory, "get_driver",
                        lambda r: "Baofeng_BF-777S")
    import mychirp.fwtool as real_fwtool
    monkeypatch.setattr(real_fwtool, "restore_h777_image", fake_restore)

    svc = rs.RadioService()
    done = []
    svc.fw_restore(bf777_rclass, "/dev/ttyFAKE", img_path,
                   on_done=done.append)
    deadline = time.time() + 5
    while len(done) < 1 and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert done and done[0].error is None
    rep = done[0].result
    assert ("Baofeng_BF-777S", "/dev/ttyFAKE",
            fwtool.H777_WINDOW_END) == calls[0]
    assert rep["ok"] is True and rep["diffs"] == []


def test_restore_dialog_done_report(qapp, tmp_state, parent_widget):
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    job = RadioJob(lambda: None)
    job.result = {"ok": True, "diffs": [], "aborted": None,
                  "sha_old": "a" * 64, "sha_new": "b" * 64,
                  "pre_path": "/p.bin", "post_path": "/p_post.bin"}
    dlg._restore_done(job)
    assert "0 divergências" in dlg.progress_label.text()
    assert not dlg._busy

    dlg2 = FirmwareRestoreDialog(parent_widget, tmp_state)
    job = RadioJob(lambda: None)
    job.error = RuntimeError("boom")
    dlg2._restore_done(job)
    assert "boom" in dlg2.progress_label.text()
    assert not dlg2._busy
