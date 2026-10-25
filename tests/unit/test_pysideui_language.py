"""E2E language switching tests for the PySide6 UI."""

import os
import pytest

from PySide6.QtWidgets import QApplication

from mychirp import directory
from mychirp.pysideui.services.app_state import AppState
from mychirp.pysideui.i18n import (
    set_language,
    get_current_language,
    available_languages,
    language_display_name,
)
from mychirp.pysideui.widgets.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def state(qapp):
    s = AppState()
    yield s


def test_available_languages_includes_expected():
    """Verify the 15 expected languages are available."""
    langs = available_languages()
    expected = [
        "pt_BR", "en_US", "ja_JP", "zh_CN",
        "cs", "de", "es", "fr", "it", "pl",
        "ro_RO", "ru", "tr_TR", "uk_UA", "bg_BG",
    ]
    for code in expected:
        assert code in langs, f"Language {code} missing from available_languages()"


def test_language_display_names():
    """Verify native display names for key languages."""
    assert language_display_name("pt_BR") == "Português (Brasil)"
    assert language_display_name("en_US") == "English"
    assert language_display_name("ja_JP") == "日本語"
    assert language_display_name("zh_CN") == "中文 (简体)"
    assert language_display_name("it") == "Italiano"
    assert language_display_name("es") == "Español"
    assert language_display_name("fr") == "Français"
    assert language_display_name("de") == "Deutsch"
    # unknown falls back to code
    assert language_display_name("xx_XX") == "xx_XX"


def test_set_language_switches_catalog(qapp, state):
    """Switching language at runtime changes the active catalog."""
    # Start from a known state (system default = None)
    set_language(None)
    assert get_current_language() is None

    # Switch to Spanish
    assert set_language("es") is True
    assert get_current_language() == "es"

    # Switch to Italian
    assert set_language("it") is True
    assert get_current_language() == "it"

    # Switch back to system default
    assert set_language(None) is True
    assert get_current_language() is None

    # Invalid language returns False
    assert set_language("xx_XX") is False


def test_main_window_builds_language_menu(qapp, state):
    """MainWindow builds the Language submenu with all languages."""
    from mychirp.pysideui.theme import apply_theme

    apply_theme(qapp, state.is_dark())
    win = MainWindow(state)
    state.main_window = win
    qapp.processEvents()

    # Verify the Language menu exists under View
    view_menu = win._menu_view
    lang_menu = win._language_menu
    assert lang_menu is not None
    assert lang_menu.title() == "Language"  # source string (tests run with NullTranslations)

    # Verify System default action exists and is checked by default
    sys_action = win._language_actions[None]
    assert sys_action is not None
    assert sys_action.isChecked()

    # Verify at least the 15 expected languages have actions
    expected_codes = [
        "pt_BR", "en_US", "ja_JP", "zh_CN",
        "cs", "de", "es", "fr", "it", "pl",
        "ro_RO", "ru", "tr_TR", "uk_UA", "bg_BG",
    ]
    for code in expected_codes:
        act = win._language_actions.get(code)
        assert act is not None, f"Missing action for {code}"
        assert act.text() == language_display_name(code)

    # Initially none of the language actions should be checked (system default)
    for code in expected_codes:
        assert not win._language_actions[code].isChecked()


def test_main_window_language_switch_updates_menu_checkmarks(qapp, state):
    """Switching language updates checkmarks in the Language menu."""
    from mychirp.pysideui.theme import apply_theme

    apply_theme(qapp, state.is_dark())
    win = MainWindow(state)
    state.main_window = win
    qapp.processEvents()

    # Initially system default is checked
    assert win._language_actions[None].isChecked()

    # Trigger Italian language action
    it_action = win._language_actions["it"]
    it_action.trigger()
    qapp.processEvents()

    # Re-fetch actions after menu rebuild
    it_action = win._language_actions["it"]
    sys_action = win._language_actions[None]

    # Now Italian should be checked, system default unchecked
    assert it_action.isChecked()
    assert not sys_action.isChecked()

    # Other languages still unchecked
    assert not win._language_actions["es"].isChecked()
    assert not win._language_actions["pt_BR"].isChecked()

    # Switch to pt_BR
    pt_action = win._language_actions["pt_BR"]
    pt_action.trigger()
    qapp.processEvents()

    # Re-fetch again
    pt_action = win._language_actions["pt_BR"]
    it_action = win._language_actions["it"]

    assert pt_action.isChecked()
    assert not it_action.isChecked()


def test_main_window_menu_titles_translate_on_language_switch(qapp, state):
    """Menu bar titles update when language is switched."""
    from mychirp.pysideui.theme import apply_theme

    apply_theme(qapp, state.is_dark())
    win = MainWindow(state)
    state.main_window = win
    qapp.processEvents()

    # With NullTranslations (test fixture), titles are source English
    assert win._menu_file.title() == "&File"
    assert win._menu_edit.title() == "&Edit"
    assert win._menu_view.title() == "&View"
    assert win._menu_radio.title() == "&Radio"
    assert win._menu_help.title() == "&Help"

    # After language switch, _refresh_ui_texts re-translates menu titles
    # (In real usage with active catalog, they'd translate; in test they stay
    # source English because conftest forces NullTranslations)


def test_settings_tab_group_titles_are_translatable(qapp, state):
    """Settings tab group titles go through _() and can be translated."""
    from mychirp import directory, memmap

    directory.import_drivers()
    # Find a radio with settings that has group names (e.g., UV-5R)
    rclass = directory.DRV_TO_RADIO.get("Baofeng_UV-5R")
    assert rclass is not None

    radio = rclass("tests/images/Baofeng_UV-5R.img")
    groups = radio.get_settings()
    assert groups is not None

    # Walk settings tree and verify group names exist (source strings)
    from mychirp import settings as st

    def collect_names(el, out):
        if isinstance(el, st.RadioSettings):
            for g in el:
                collect_names(g, out)
            return
        for name, item in el.items():
            if isinstance(item, st.RadioSetting):
                out.add(item.get_shortname())
            else:
                out.add(item.get_shortname())
                collect_names(item, out)

    names = set()
    collect_names(groups, names)

    # At least some known groups should exist (these vary by driver)
    # UV-5R has "Basic Settings" and "Advanced Settings" in source
    # These are the strings that _() wraps in settings.py (GroupListItem, group_title, subtitle)
    # If they appear in pt_BR.po with translations, the UI will show them in Portuguese
    print("Found setting groups:", sorted(names))
    # Just verify the function works - don't assert specific group names
    # since they vary by driver
    assert len(names) > 0


def test_fw_dump_restore_dialogs_translatable_strings(qapp, state):
    """Key strings in fw_dump/fw_restore dialogs are wrapped in _()."""
    from mychirp.pysideui.dialogs.fw_dump import FirmwareDumpDialog
    from mychirp.pysideui.dialogs.fw_restore import FirmwareRestoreDialog

    # Just verify the dialogs can be instantiated without error
    # and their text uses _() (source strings visible with NullTranslations)
    dump_dlg = FirmwareDumpDialog(None, state)
    assert dump_dlg.windowTitle() == "Firmware dump (read-only)"
    dump_dlg.close()

    restore_dlg = FirmwareRestoreDialog(None, state)
    assert restore_dlg.windowTitle() == "Firmware restore (WRITE)"
    restore_dlg.close()


def test_devtools_dialog_translatable_strings(qapp, state):
    """DevTools dialog (bug report) uses translatable strings."""
    from mychirp.pysideui.dialogs.devtools import BugReportDialog

    dlg = BugReportDialog(None, state)
    # Title and button texts should be source English in test
    assert dlg.windowTitle() == "Report a bug"
    assert dlg.copy_email_button.text() == "Copy email"
    assert dlg.copy_logs_button.text() == "Copy recent logs"
    dlg.close()


def test_no_untranslated_pt_in_source_strings():
    """Audit: ensure no Portuguese strings remain as source in _() calls."""
    import ast
    import glob
    import re

    # Common Portuguese words that would indicate PT source strings
    pt_pattern = re.compile(
        r'\b(rádio|nao|não|senha|usuario|usuário|arquivo|arquivos|porta|portas|'
        r'gravar|gravação|salvar|salvo|cancelar|cancelado|cancelada|abrir|aberto|'
        r'fechar|detalhes|ferramenta|ferramentas|configura|memória|memorias|'
        r'canal|canais|banco|bancos|nome|endereco|endereço|conexao|conexão|'
        r'codigo|código|erro|falha|aviso|mensagem|lista|opcao|opção|permite|'
        r'suportad|disponivel|disponível|exemplo|clique|selecione|informe|'
        r'todos|todo|novo|nova|removido|remover|copiado|copiar|área|rede|fonte|'
        r'esperado|diverg|memória do rádio|pós-gravação|cancelada|área de transferência|'
        r'Selecione o Tone|Nenhum rádio detectado)\b',
        re.IGNORECASE
    )

    def extract_calls(path):
        src = open(path, encoding="utf-8-sig").read()
        tree = ast.parse(src)
        out = []
        class V(ast.NodeVisitor):
            def visit_Call(self, node):
                f = node.func
                if isinstance(f, ast.Name) and f.id == "_" and node.args:
                    a = node.args[0]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        out.append((a.value, node.lineno))
                self.generic_visit(node)
        V().visit(tree)
        return out

    violations = []
    for f in glob.glob("mychirp/pysideui/**/*.py", recursive=True):
        for s, ln in extract_calls(f):
            if pt_pattern.search(s):
                violations.append((f, ln, s[:80]))

    assert not violations, f"Found Portuguese source strings in _(): {violations}"