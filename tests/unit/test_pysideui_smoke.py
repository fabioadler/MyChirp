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

        view = win.tabs.widget(win.tabs.count() - 1)
        st = view.settings
        assert st.groups, "settings groups not loaded"
        for i in range(st.group_list.count()):
            if st.group_list.item(i).group.get_name() == 'other':
                st.group_list.setCurrentRow(i)
                qapp.processEvents()
                break
        names = [s.get_name() for s, _ in st._controls]
        assert 'limits_new.vhf.lower' in names
        assert 'limits_new.uhf.lower' in names
        lower = next(
            c for s, c in st._controls
            if s.get_name() == 'limits_new.vhf.lower')
        from PySide6.QtWidgets import QSpinBox
        assert isinstance(lower, QSpinBox)
        assert lower.value() == 128


# ---------------------------------------------------------------------------
# UX de tons CTCSS/DCS (tone_fields): tipo primeiro, limpeza automática
# ---------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from mychirp import chirp_common  # noqa: E402
from mychirp.pysideui.tone_fields import (  # noqa: E402
    clear_unused_tones,
    used_tone_columns_for,
)


def _tone_mem(**kwargs):
    mem = chirp_common.Memory()
    mem.number = 1
    mem.freq = 146520000
    mem.empty = False
    for k, v in kwargs.items():
        setattr(mem, k, v)
    return mem


def test_tone_fields_logic():
    """Mapeamento tmode -> campos usados (tipo primeiro)."""
    assert used_tone_columns_for("") == set()
    assert used_tone_columns_for("Tone") == {"rtone"}
    assert used_tone_columns_for("TSQL") == {"rtone", "ctone"}
    assert used_tone_columns_for("DTCS") == {"dtcs"}
    assert used_tone_columns_for("Cross", "Tone->DTCS") == {"rtone", "dtcs"}
    assert used_tone_columns_for("Cross", "DTCS->Tone") == {"ctone", "dtcs"}


def test_clear_unused_tones():
    """Trocar de tipo limpa os campos que não pertencem ao novo tmode."""
    mem = _tone_mem(tmode="TSQL", rtone=123.0, ctone=100.0, dtcs=145)
    # TSQL -> DTCS: mantém só dtcs
    clear_unused_tones(mem, "DTCS")
    assert mem.dtcs == 145
    assert mem.rtone == 88.5
    assert mem.ctone == 88.5
    # qualquer tipo -> vazio: todos limpos
    clear_unused_tones(mem, "")
    assert mem.dtcs == 23
    assert mem.rtone == 88.5
    assert mem.ctone == 88.5


def _tone_test_model(qapp):
    from mychirp.pysideui.tabs.memories import MemoryModel
    columns = ["loc", "freq", "tmode", "rtone", "ctone", "dtcs"]
    feats = SimpleNamespace(
        valid_tmodes=["", "Tone", "TSQL", "DTCS", "Cross"],
        valid_tones=chirp_common.TONES,
        valid_dtcs_codes=chirp_common.DTCS_CODES,
        valid_duplexes=["", "+", "-"],
        valid_modes=["FM", "NFM"],
        valid_tuning_steps=[5.0, 10.0],
        valid_skips=["", "S"],
        valid_power_levels=[],
        has_name=False,
        has_comment=False,
    )
    mem = _tone_mem(tmode="", rtone=100.0, ctone=107.2, dtcs=111)
    model = MemoryModel(columns, feats)
    model.set_rows([mem])
    return model, columns, feats, mem


def test_grid_tone_editor_blocked(qapp):
    """Sem tmode, campos de tom não abrem editor (tipo primeiro)."""
    from PySide6.QtWidgets import QStyleOptionViewItem, QTableView
    from mychirp.pysideui.tabs.memories import MemoryChunkDelegate

    model, columns, feats, mem = _tone_test_model(qapp)
    table = QTableView()
    delegate = MemoryChunkDelegate(columns, feats, parent=table)
    calls = []
    delegate.blocked_hint = lambda: calls.append(1)
    option = QStyleOptionViewItem()

    rtone_idx = model.index(0, columns.index("rtone"))
    assert delegate.createEditor(table, option, rtone_idx) is None
    assert calls, "blocked_hint não foi chamado"

    # com tmode selecionado, o editor abre
    mem.tmode = "Tone"
    editor = delegate.createEditor(table, option, rtone_idx)
    assert editor is not None
    # ctone continua bloqueada para tmode "Tone"
    calls.clear()
    ctone_idx = model.index(0, columns.index("ctone"))
    assert delegate.createEditor(table, option, ctone_idx) is None
    assert calls


def test_grid_tmode_change_clears_tones(qapp):
    """Trocar o tmode no grid limpa os tons dos outros tipos e o
    render mostra em branco os campos bloqueados."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem, QTableView
    from mychirp.pysideui.tabs.memories import MemoryChunkDelegate

    model, columns, feats, mem = _tone_test_model(qapp)
    mem.tmode = "Tone"
    mem.rtone = 123.0
    mem.ctone = 100.0
    mem.dtcs = 145
    table = QTableView()
    table.setModel(model)
    delegate = MemoryChunkDelegate(columns, feats, parent=table)
    option = QStyleOptionViewItem()

    tmode_idx = model.index(0, columns.index("tmode"))
    editor = QComboBox()
    editor.addItems(list(feats.valid_tmodes))
    editor.setCurrentText("DTCS")
    delegate.setModelData(editor, model, tmode_idx)

    assert mem.tmode == "DTCS"
    assert mem.dtcs == 145        # do tipo atual: mantido
    assert mem.rtone == 88.5      # do outro tipo: limpo
    assert mem.ctone == 88.5
    # render: dtcs visível, rtone/ctone em branco
    def disp(col):
        idx = model.index(0, columns.index(col))
        return model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert disp("dtcs") == "145"
    assert disp("rtone") == ""
    assert disp("ctone") == ""

    # tmode vazio: todos os tons limpos e render em branco
    model.setData(tmode_idx, "")
    assert mem.rtone == 88.5 and mem.ctone == 88.5 and mem.dtcs == 23
    assert disp("dtcs") == ""
    assert disp("rtone") == ""
    assert disp("ctone") == ""


def test_tone_dialog_states(qapp):
    """Dialog: campos de tom bloqueados/vazios sem tmode; liberados
    apenas para o tipo selecionado."""
    from mychirp.pysideui.dialogs.memory_edit import MemoryEditDialog
    from PySide6.QtWidgets import QComboBox

    feats = SimpleNamespace(
        valid_tmodes=["", "Tone", "TSQL", "DTCS", "Cross"],
        valid_tones=chirp_common.TONES,
        valid_dtcs_codes=chirp_common.DTCS_CODES,
    )
    mem = _tone_mem()
    dlg = MemoryEditDialog(None, mem, feats)

    rtone = dlg._fields["rtone"]
    ctone = dlg._fields["ctone"]
    dtcs = dlg._fields["dtcs"]
    # sem tmode: todos bloqueados e vazios
    assert not rtone.isEnabled() and not ctone.isEnabled() \
        and not dtcs.isEnabled()
    assert rtone.currentText() == "" and ctone.currentText() == "" \
        and dtcs.currentText() == ""

    # seleciona Tone: libera rtone (com default), outros seguem bloqueados
    dlg._fields["tmode"].setCurrentText("Tone")
    assert rtone.isEnabled() and rtone.currentText() == "88.5"
    assert not ctone.isEnabled() and not dtcs.isEnabled()
    assert ctone.currentText() == "" and dtcs.currentText() == ""

    # troca para DTCS: limpa/bloqueia rtone, libera dtcs com default
    dlg._fields["tmode"].setCurrentText("DTCS")
    assert dtcs.isEnabled() and dtcs.currentText() == "23"
    assert not rtone.isEnabled() and rtone.currentText() == ""
    assert not ctone.isEnabled()

    # aplica: tmode DTCS gravado, rtone volta ao default limpo
    dlg.apply()
    assert mem.tmode == "DTCS"
    assert mem.dtcs == 23
    assert mem.rtone == 88.5
    assert mem.ctone == 88.5

    # volta para vazio: todos bloqueados/vazios e apply limpa tudo
    dlg._fields["tmode"].setCurrentText("")
    assert not rtone.isEnabled() and not ctone.isEnabled() \
        and not dtcs.isEnabled()
    dlg.apply()
    assert mem.tmode == ""
    assert mem.rtone == 88.5 and mem.ctone == 88.5 and mem.dtcs == 23


# ---------------------------------------------------------------------------
# Arquivos recentes: limite de 10, promoção e purga de arquivo apagado
# ---------------------------------------------------------------------------

def _tmp_state(tmp_path):
    """AppState com config descartável (não toca o ~/.chirp real)."""
    from mychirp.config import ChirpConfig, ChirpConfigProxy
    from mychirp.pysideui.services.app_state import AppState
    state = AppState()
    # Proxy como na produção (ChirpConfig cru não tem get_bool/set_bool)
    state.conf = ChirpConfigProxy(ChirpConfig(str(tmp_path)), "state")
    return state


def test_recent_files_limit_10(tmp_path):
    state = _tmp_state(tmp_path)
    for i in range(12):
        state.push_recent_file("/f/radio-%02d.img" % i)
    recents = state.get_recent_files()
    # exatamente 10, do mais novo para o mais antigo, 2 mais velhos fora
    assert len(recents) == 10
    assert recents[0] == "/f/radio-11.img"
    assert recents[1] == "/f/radio-10.img"
    assert recents[-1] == "/f/radio-02.img"
    assert "/f/radio-01.img" not in recents
    assert "/f/radio-00.img" not in recents


def test_recent_files_promote_existing(tmp_path):
    state = _tmp_state(tmp_path)
    for f in ("/a.img", "/b.img", "/c.img"):
        state.push_recent_file(f)
    assert state.get_recent_files() == ["/c.img", "/b.img", "/a.img"]
    # reabrir um existente promove à primeira posição (sem duplicar);
    # a ordem relativa dos demais é preservada
    state.push_recent_file("/a.img")
    assert state.get_recent_files() == ["/a.img", "/c.img", "/b.img"]
    state.push_recent_file("/b.img")
    assert state.get_recent_files() == ["/b.img", "/a.img", "/c.img"]


def test_forget_file_removes_from_recent_and_session(tmp_path):
    state = _tmp_state(tmp_path)
    state.conf.set("last_open", "/a.img$/b.img", "state")
    state.conf.set("last_session", "/b.img$/c.img", "state")
    state.conf.save()
    state.forget_file("/b.img")
    assert state.get_recent_files() == ["/a.img"]
    assert (state.conf.get("last_session", "state") or "") == "/c.img"
    # ausente: no-op
    state.forget_file("/nao-estava.img")
    assert state.get_recent_files() == ["/a.img"]
    assert (state.conf.get("last_session", "state") or "") == "/c.img"


def test_open_file_missing_recent_popup_purges(qapp, tmp_path,
                                                monkeypatch):
    """Clique em um recente apagado: pop-up individual + purga dupla."""
    from PySide6.QtWidgets import QMessageBox
    from mychirp.pysideui.widgets.main_window import MainWindow

    state = _tmp_state(tmp_path)
    state.conf.set("last_open", "/gone/x.img", "state")
    state.conf.set("last_session", "/gone/x.img", "state")
    state.conf.save()
    win = MainWindow(state)
    state.main_window = win

    calls = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: calls.append(a))
    win.open_file("/gone/x.img")

    # um único pop-up, nomeando o arquivo
    assert len(calls) == 1
    assert "/gone/x.img" in str(calls[0])
    # purgado dos recentes E da última sessão
    assert "/gone/x.img" not in state.get_recent_files()
    assert "/gone/x.img" not in (state.conf.get("last_session", "state")
                                 or "").split("$")
    # nada foi aberto
    qapp.processEvents()
    assert not state.editorsets


def test_restore_session_purges_and_aggregates(qapp, tmp_path,
                                                monkeypatch):
    """Boot com sessão contendo apagados: um único pop-up agregado,
    purga dos dois lugares, existentes restaurados."""
    from PySide6.QtWidgets import QMessageBox
    from mychirp.pysideui.widgets.main_window import MainWindow

    real_img = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "images",
                     "Baofeng_UV-5R.img"))
    state = _tmp_state(tmp_path)
    state.conf.set(
        "last_session",
        "$".join([real_img, "/gone/x.img", "/gone/y.img"]), "state")
    state.conf.set("last_open", "$".join([real_img, "/gone/x.img"]),
                   "state")
    state.conf.save()
    win = MainWindow(state)
    state.main_window = win

    calls = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *a, **k: calls.append(a))

    # ação de restaurar (mesma usada no boot via state.restore_session)
    restored, purged = state.restore_session()
    assert restored == 1
    assert purged == ["/gone/x.img", "/gone/y.img"]
    win.warn_deleted_files(purged)  # como fazem main.py e a ação do menu

    # UM pop-up agregado com os dois nomes
    assert len(calls) == 1
    assert "x.img" in str(calls[0]) and "y.img" in str(calls[0])

    # purgados saíram dos recentes e da sessão persistida
    recents = state.get_recent_files()
    assert "/gone/x.img" not in recents and "/gone/y.img" not in recents
    session = (state.conf.get("last_session", "state") or "").split("$")
    assert "/gone/x.img" not in session and "/gone/y.img" not in session

    # o arquivo existente foi restaurado de verdade
    import time as _time
    deadline = _time.time() + 5
    while _time.time() < deadline and not state.editorsets:
        qapp.processEvents()
        _time.sleep(0.05)
    assert any(es.filename == real_img for es in state.editorsets)
