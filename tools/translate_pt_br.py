"""Add pt_BR translations for the PySide6 UI strings and rebuild the .mo.

Reads the existing pt_BR.po, extends with new translations, then writes
the compiled .mo via polib (msgfmt is unavailable).
"""

import os
import re

import polib

BASE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "mychirp", "locale"))

TRANSLATIONS = {
    # Texto original / pt_BR
    "%i banks · %i channels": "%i bancos · %i canais",
    "%i channels loaded": "%i canais carregados",
    "%i-%i / %i": "%i-%i / %i",
    "%s · %i KB": "%s · %i KB",
    "&Edit": "&Editar",
    "&File": "&Arquivo",
    "&Help": "&Ajuda",
    "&Open file": "&Abrir arquivo",
    "&Open...": "&Abrir...",
    "&Quit": "&Sair",
    "&Radio": "&Rádio",
    "&Refresh data": "&Atualizar dados",
    "&Save": "&Salvar",
    "&View": "&Visualizar",
    "Apply to radio": "Aplicar no rádio",
    "Applying settings...": "Aplicando configurações...",
    "Channel %s not found": "Canal %s não encontrado",
    "Channel number (%i-%i):": "Número do canal (%i-%i):",
    "Clear recent files": "Limpar arquivos recentes",
    "Clear recent files?": "Limpar arquivos recentes?",
    "Clipboard is empty": "Área de transferência vazia",
    "Close Tab": "Fechar aba",
    "Communicating with radio...": "Comunicando com o rádio...",
    "Copied channel %s": "Canal %s copiado",
    "DTCS Code": "Código DTCS",
    "Delete + shift block up": "Excluir + subir bloco",
    "Delete + shift everything": "Excluir + subir tudo",
    "Delete channel": "Excluir canal",
    "Delete channel %s?": "Excluir canal %s?",
    "Disable session restore": "Desativar restauração de sessão",
    "Downloaded %s": "Baixado %s",
    "Edit Memory %s": "Editar memória %s",
    "Edit channel...": "Editar canal...",
    "Enable session restore": "Ativar restauração de sessão",
    "Export CSV": "Exportar CSV",
    "Export failed": "Exportação falhou",
    "Exported %i channels to %s": "%i canais exportados para %s",
    "Exporting to %s...": "Exportando para %s...",
    "Failed to apply settings": "Falha ao aplicar configurações",
    "Failed to download": "Falha no download",
    "Failed to export": "Falha na exportação",
    "Failed to open file": "Falha ao abrir arquivo",
    "Failed to read memories": "Falha ao ler memórias",
    "Failed to read settings": "Falha ao ler configurações",
    "Failed to save": "Falha ao salvar",
    "Failed to upload": "Falha no upload",
    "Files you open will appear here": "Arquivos abertos aparecerão aqui",
    "Filter channels...": "Filtrar canais...",
    "Find next": "Localizar próximo",
    "First page": "Primeira página",
    "Found channel %s": "Canal %s encontrado",
    "Go to channel": "Ir para canal",
    "Go to channel...": "Ir para canal...",
    "Insert above": "Inserir acima",
    "Invalid value(s)": "Valor(es) inválido(s)",
    "Loaded %s": "Carregado %s",
    "Memory %s updated": "Memória %s atualizada",
    "Model:": "Modelo:",
    "Modern radio programming software": "Software moderno de programação de rádios",
    "Next page": "Próxima página",
    "No match": "Sem correspondência",
    "No recent files yet": "Nenhum arquivo recente ainda",
    "No settings available": "Nenhuma configuração disponível",
    "Nothing to export": "Nada para exportar",
    "Nothing to redo": "Nada para refazer",
    "Nothing to restore": "Nada para restaurar",
    "Nothing to save": "Nada para salvar",
    "Nothing to undo": "Nada para desfazer",
    "Open a radio first": "Abra um rádio primeiro",
    "Open radio image": "Abrir imagem de rádio",
    "Opening %s...": "Abrindo %s...",
    "Port:": "Porta:",
    "Previous page": "Página anterior",
    "Proceed anyway?": "Continuar mesmo assim?",
    "Reading memories...": "Lendo memórias...",
    "Reading settings...": "Lendo configurações...",
    "Recent files": "Arquivos recentes",
    "Recent files cleared": "Arquivos recentes limpos",
    "Refresh": "Atualizar",
    "Restore last session": "Restaurar última sessão",
    "Restored %i radio(s)": "%i rádio(s) restaurado(s)",
    "Restored %i radio(s) from last session": "Restaurado %i rádio(s) da última sessão",
    "Save As...": "Salvar como...",
    "Save radio image": "Salvar imagem de rádio",
    "Saved %s": "Salvo %s",
    "Saving to %s...": "Salvando em %s...",
    "Select a channel first": "Selecione um canal primeiro",
    "Select a channel to copy first": "Selecione um canal para copiar primeiro",
    "Select vendor, model and port": "Selecione o fabricante, modelo e porta",
    "Session restore disabled": "Restauração de sessão desativada",
    "Session restore enabled": "Restauração de sessão ativada",
    "Settings applied": "Configurações aplicadas",
    "Settings loaded": "Configurações carregadas",
    "Some settings reported warnings:": "Algumas configurações relataram avisos:",
    "Switch to Dark Theme": "Mudar para tema escuro",
    "Switch to Light Theme": "Mudar para tema claro",
    "ToneSql": "TomSq",
    "Tune Step": "Passo de frequência",
    "Unknown model": "Modelo desconhecido",
    "Upload": "Enviar",
    "Upload complete": "Envio concluído",
    "Use File > Open or Ctrl+D to download from a radio": "Use Arquivo > Abrir ou Ctrl+D para baixar do rádio",
    "Vendor:": "Fabricante:",
    "Version %s": "Versão %s",
    "Working...": "Trabalhando...",
    "file not found": "arquivo não encontrado",
}


def main():
    po_path = os.path.join(BASE, "pt_BR.po")
    po = polib.pofile(po_path)
    existing = {e.msgid: e for e in po}

    added = updated = 0
    for en, pt in TRANSLATIONS.items():
        e = existing.get(en)
        if e is None:
            entry = polib.POEntry(msgid=en, msgstr=pt)
            po.append(entry)
            added += 1
        elif not e.msgstr or e.msgstr != pt:
            e.msgstr = pt
            updated += 1

    po.save(po_path)

    mo_dir = os.path.join(BASE, "pt_BR", "LC_MESSAGES")
    os.makedirs(mo_dir, exist_ok=True)
    mo_path = os.path.join(mo_dir, "CHIRP.mo")
    po.save_as_mofile(mo_path)
    print("pt_BR.po: +%i novas, %i atualizadas" % (added, updated))
    print("mo:", mo_path)


if __name__ == "__main__":
    main()
