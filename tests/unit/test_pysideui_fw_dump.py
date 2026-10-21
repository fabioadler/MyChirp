"""Offscreen tests for the read-only firmware dump feature (Qt)."""

import os

import pytest

from PySide6.QtWidgets import QApplication

from mychirp import directory
from mychirp.pysideui.dialogs.fw_dump import FirmwareDumpDialog
from mychirp.pysideui.services.radio_service import RadioJob


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tmp_state(tmp_path):
    from mychirp.config import ChirpConfig, ChirpConfigProxy
    from mychirp.pysideui.services.app_state import AppState
    state = AppState()
    # Proxy como na produção (ChirpConfig cru não tem get_bool/set_bool)
    state.conf = ChirpConfigProxy(ChirpConfig(str(tmp_path)), "state")
    return state


@pytest.fixture
def bom_rclass():
    directory.import_drivers()
    for rclass in directory.DRV_TO_RADIO.values():
        if getattr(rclass, "VENDOR", "") == "BOMVINK":
            return rclass
    pytest.skip("BOMVINK driver not registered")


@pytest.fixture
def parent_widget(qapp):
    from PySide6.QtWidgets import QWidget
    return QWidget()


def _select(dlg, rclass):
    dlg.vendor.setCurrentText(rclass.VENDOR)
    label = ("%s %s" % (rclass.MODEL, getattr(rclass, "VARIANT", "")
                        or "")).strip()
    dlg.model.setCurrentText(label)


def test_bom5701_full_window_supported(qapp, tmp_state, parent_widget, bom_rclass):
    dlg = FirmwareDumpDialog(parent_widget, tmp_state)
    _select(dlg, bom_rclass)
    assert dlg.full_window.isEnabled()
    assert hasattr(bom_rclass, "download_full_window")


def test_fw_dump_prefills_and_validates(qapp, tmp_state, parent_widget, bom_rclass):
    from types import SimpleNamespace

    class _Radio:
        VENDOR = bom_rclass.VENDOR
        MODEL = bom_rclass.MODEL
        VARIANT = ""

    eset = SimpleNamespace(radio=_Radio())  # o diálogo só lê V/M/V
    dlg = FirmwareDumpDialog(parent_widget, tmp_state, eset=eset)
    assert dlg.vendor.currentText() == _Radio.VENDOR
    assert _Radio.MODEL in dlg.model.currentText()

    # start sem porta válida (índice -1): não entra em busy nem abre
    # probe real — só avisa no label
    dlg.port.setCurrentIndex(-1)
    dlg._on_start()
    assert not dlg._busy
    assert dlg.progress_label.text()


def test_fw_dump_done_success_and_failure(qapp, tmp_state, parent_widget, bom_rclass,
                                          tmp_path):
    dlg = FirmwareDumpDialog(parent_widget, tmp_state)
    # stub do prompt modal de destino (bloquearia offscreen)
    dlg._ask_save_dest = lambda default_name: ""

    # sucesso: label recebe bin + yaml + sha
    bin_path = str(tmp_path / "fake.bin")
    yaml_path = str(tmp_path / "fake.yaml")
    with open(bin_path, "wb") as f:
        f.write(b"x" * 10)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("sha256: deadbeef" + "0" * 56 + "\nsize: 10\n")
    job = RadioJob(lambda: None)
    job.result = (bin_path, yaml_path)
    dlg._dump_done(job)
    assert not dlg._busy
    assert "fake.bin" in dlg.progress_label.text()
    assert "deadbeef" in dlg.progress_label.text()

    # falha serial: aparece no label, sem quebrar
    dlg._busy = True
    dlg._set_busy(True)
    job = RadioJob(lambda: None)
    job.error = RuntimeError("port gone")
    dlg._dump_done(job)
    assert not dlg._busy
    assert "port gone" in dlg.progress_label.text()


def test_fw_dump_service_method(qapp, tmp_state, parent_widget, bom_rclass, monkeypatch):
    """fw_dump roda o caminho certo (clone × full window) no worker."""
    from mychirp.pysideui.services import radio_service as rs

    calls = []

    class _FakeFwtool:
        @staticmethod
        def dump_clone(radio_id, port, out=None, backup=False):
            calls.append(("clone", radio_id, backup))
            return "/tmp/%s.bin" % radio_id

        @staticmethod
        def dump_full_window(radio_id, port, out=None, backup=False):
            calls.append(("full", radio_id, backup))
            return "/tmp/%s.bin" % radio_id

    monkeypatch.setattr(rs.directory, "get_driver",
                        lambda r: "FAKE_DRIVER")
    svc = rs.RadioService()
    # fwtool é importado dentro do closure; patch mariado no módulo alvo
    import mychirp.fwtool as fwtool
    monkeypatch.setattr(fwtool, "dump_clone", _FakeFwtool.dump_clone)
    monkeypatch.setattr(fwtool, "dump_full_window",
                        _FakeFwtool.dump_full_window)

    done = []

    def on_done(job):
        done.append(job)

    svc.fw_dump(bom_rclass, "/dev/ttyFAKE", full_window=True,
                on_done=on_done)
    # espera o job do pool terminar
    import time
    deadline = time.time() + 5
    while len(done) < 1 and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert done and done[0].error is None
    assert calls and calls[0][0] == "full" and calls[0][2] is True
    assert done[0].result[0] == "/tmp/FAKE_DRIVER.bin"
    assert os.path.splitext(done[0].result[1])[0] == "/tmp/FAKE_DRIVER"

    calls.clear()
    svc.fw_dump(bom_rclass, "/dev/ttyFAKE", full_window=False,
                on_done=on_done)
    done.clear()
    deadline = time.time() + 5
    while len(done) < 1 and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    assert done and done[0].error is None
    assert calls and calls[0][0] == "clone" and calls[0][2] is True


def test_fwtool_full_window_requires_support(qapp, bom_rclass, tmp_path):
    from mychirp import fwtool
    # porta vazia: erro explícito
    with pytest.raises(fwtool.FwDumpError):
        fwtool.dump_full_window("BOMVINK_BOM-5701", None)
    # driver sem download_full_window: erro explícito
    directory.import_drivers()
    plain = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if not hasattr(r, "download_full_window")), None)
    if plain is not None:
        with pytest.raises(fwtool.FwDumpError):
            fwtool.dump_full_window(
                directory.get_driver(plain),
                str(tmp_path / "port"))
