"""Offscreen smoke tests for the PySide6 UI (Qt, no display)."""

import os
import pytest

from PySide6.QtWidgets import QApplication

from mychirp import directory
from mychirp.pysideui.services.app_state import AppState, EditorSetState


IMG = "/media/f/HD/F/eletronica/radio/imagens/Meu_Radio_BOMVINK_BOM-5701.img"
IMG_FALLBACK = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "images", "Baofeng_UV-5R.img"))


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def state(qapp):
    s = AppState()
    yield s


@pytest.fixture
def bom_radio():
    directory.import_drivers()
    for rclass in directory.DRV_TO_RADIO.values():
        if getattr(rclass, "VENDOR", "") == "BOMVINK":
            return rclass
    pytest.skip("BOMVINK driver not registered")


def test_state_defaults(state):
    assert state.theme_mode in ("system", "light", "dark")
    assert isinstance(state.get_recent_files(), list)


def test_editorset_roundtrip(state, bom_radio):
    radio = bom_radio(None)
    eset = EditorSetState(radio, "fake.img")
    assert eset.radio is radio
    # a not-yet-saved editor set starts out modified by design
    assert eset.modified is True
    assert eset.undo_stack is not None
    assert eset.has_settings() is True


def test_image_open_offscreen(qapp, state, bom_radio):
    """Open the BOM-5701 image end-to-end offscreen (falls back to a
    stock UV-5R image when the owner's capture is unavailable)."""
    from mychirp.pysideui.theme import apply_theme
    from mychirp.pysideui.widgets.main_window import MainWindow

    img = IMG if os.path.exists(IMG) else IMG_FALLBACK

    apply_theme(qapp, state.is_dark())
    win = MainWindow(state)
    state.main_window = win
    qapp.processEvents()

    win.open_file(img)
    qapp.processEvents()
    import time
    deadline = time.time() + 5
    while not state.editorsets and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    assert state.editorsets
    eset = state.editorsets[0]
    assert eset.has_settings()

    deadline = time.time() + 5
    while time.time() < deadline:
        qapp.processEvents()
        if eset.memories:
            break
        time.sleep(0.05)
    assert eset.memories

    # settings group 'other' must expose VHF/UHF limits initialized
    if "BOM-5701" in eset.radio_label:
        other = eset.radio.get_settings()['other']
        assert other['limits_new.vhf.lower'].value.get_value() == 128
        assert other['limits_new.vhf.upper'].value.get_value() == 176
        assert other['limits_new.uhf.lower'].value.get_value() == 384
        assert other['limits_new.uhf.upper'].value.get_value() == 524
