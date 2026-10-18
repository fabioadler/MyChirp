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


@pytest.fixture
def bom5701_rclass():
    directory.import_drivers()
    r = directory.get_radio("BOMVINK_BOM-5701")
    assert getattr(r, "_aux_first", False) and \
        getattr(r, "_aux_block", False)  # família aux-first
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
    assert not dlg.warn_label.text()

    # Modelos de famílias não testadas (não h777 PROGRAM_CMD e não
    # aux-first) não aparecem na lista filtrada de modelos.
    other = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if getattr(r, "PROGRAM_CMD", None) != fwtool.H777_PROGRAM_CMD
         and not (getattr(r, "_aux_first", False) and
                  getattr(r, "_aux_block", False))),
        None)
    if other is not None:
        label = ("%s %s" % (other.MODEL, getattr(other, "VARIANT", "")
                            or "")).strip()
        _select(dlg, other)
        # Modelo não suportado não está na lista filtrada do vendor
        assert dlg.model.findText(label) < 0


def test_auxfirst_supported_and_size_map(qapp, tmp_state, parent_widget,
                                         bom5701_rclass):
    """Família UV-5R-aux-first (BOM-5701) aceita no diálogo com a
    janela de 0x1948 B; tamanho errado (h777) marca SIZE MISMATCH."""
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    _select(dlg, bom5701_rclass)
    assert dlg._restore_supported(bom5701_rclass)
    assert not dlg.warn_label.text()
    assert fwtool.UV5R_AUX_FIRST_IMAGE_END in \
        dlg._family_sizes(bom5701_rclass)

    # imagem de janela h777 (992 B) é tamanho ERRADO para esta família
    with tempfile.TemporaryDirectory() as td:
        wrong = os.path.join(td, "small.bin")
        with open(wrong, "wb") as f:
            f.write(b"\x00" * fwtool.H777_WINDOW_END)
        dlg._set_image(wrong)
        assert "SIZE MISMATCH" in dlg.img_label.text()

        right = os.path.join(td, "bom.bin")
        with open(right, "wb") as f:
            f.write(b"\x00" * fwtool.UV5R_AUX_FIRST_IMAGE_END)
        dlg._set_image(right)
        assert dlg.image_path == right
        assert "SIZE MISMATCH" not in dlg.img_label.text()

        # imagem full window (8.192 B) também é aceita (convertida
        # internamente no fwtool ao gravar)
        full = os.path.join(td, "full.bin")
        with open(full, "wb") as f:
            f.write(b"\x00" * 0x2000)
        dlg._set_image(full)
        assert dlg.image_path == full
        assert "SIZE MISMATCH" not in dlg.img_label.text()


def test_auxfirst_start_size_guard_blocks_send(qapp, tmp_state,
                                               parent_widget,
                                               bom5701_rclass, monkeypatch):
    """_on_start com imagem de tamanho errado: falha amigável e NÃO
    dispara a gravação (serviço nem chamado)."""
    dlg = FirmwareRestoreDialog(parent_widget, tmp_state)
    _select(dlg, bom5701_rclass)
    with tempfile.TemporaryDirectory() as td:
        wrong = os.path.join(td, "small.bin")
        with open(wrong, "wb") as f:
            f.write(b"\x00" * fwtool.H777_WINDOW_END)
        dlg._set_image(wrong)
        refusals = []

        import mychirp.pysideui.dialogs.fw_restore as mod
        monkeypatch.setattr(mod, "get_service", lambda d: refusals.append(1))

        dlg._on_start()
        assert not refusals  # serviço não chamado
        assert "mismatch" in dlg.progress_label.text().lower() \
            or "Image size mismatch" in dlg.progress_label.text()


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
    monkeypatch.setattr(real_fwtool, "restore_image", fake_restore)

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
