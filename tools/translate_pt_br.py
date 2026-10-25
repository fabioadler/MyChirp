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

# ---------------------------------------------------------------------------
# Auditoria i18n (2026-10): strings da GUI PySide6 adicionadas pelo fork e
# entradas vazias herdadas do catálogo upstream.
TRANSLATIONS.update({
    # --- GUI: firmware dump/restore (U2 renomeou as fontes para EN) ---
    "\nNOTE: %d protection range(s) not written by the driver (unit "
    "content preserved).":
        "\nNOTA: %d faixa(s) de proteção não gravada(s) pelo driver "
        "(conteúdo da unidade preservado).",
    "  [SIZE MISMATCH: expected %s B for %s]":
        "  [TAMANHO INCOMPATÍVEL: esperado %s B para %s]",
    "%d differences after write": "%d divergências após a gravação",
    "%s\nsha256: %s…  %d B%s": "%s\nsha256: %s…  %d B%s",
    "Choose image (.bin)...": "Escolher imagem (.bin)...",
    "Choose the image (.bin) to restore": "Escolha a imagem (.bin) a restaurar",
    "Could not save to %s: %s\nThe original backup was kept at %s":
        "Não foi possível salvar em %s: %s\nO backup original foi mantido em %s",
    "Dump complete!\nSaved to: %s (%s bytes)\nsha256: %s\nmeta: %s":
        "Dump concluído!\nSalvo em: %s (%s bytes)\nsha256: %s\nmeta: %s",
    "Driver not supported for restore (validated: h777 family and "
    "UV-5R aux-first)":
        "Driver sem suporte para restauração (validados: família h777 "
        "e UV-5R aux-first)",
    "Final confirmation": "Confirmação final",
    "Firmware dump (read-only)": "Dump de firmware (somente leitura)",
    "Firmware dump failed": "Falha no dump de firmware",
    "Firmware dump saved to %s": "Dump de firmware salvo em %s",
    "Firmware dump...": "Dump de firmware...",
    "Firmware restore": "Restauração de firmware",
    "Firmware restore (WRITE)": "Restauração de firmware (ESCRITA)",
    "Firmware restore (write)...": "Restauração de firmware (gravação)...",
    "Firmware restore failed": "Falha na restauração de firmware",
    "Firmware restore: %s": "Restauração de firmware: %s",
    "Firmware write risk warning": "Aviso de risco — gravação de firmware",
    "Full memory window (adds factory calibration area)":
        "Janela de memória completa (inclui a área de calibração de fábrica)",
    "Image size mismatch: %d B (expected %s B for family %s)":
        "Tamanho de imagem incompatível: %d B (esperado %s B para a "
        "família %s)",
    "Image:": "Imagem:",
    "Loading raw image...": "Carregando imagem bruta...",
    "No image selected": "Nenhuma imagem selecionada",
    "No raw image available for this radio":
        "Nenhuma imagem bruta disponível para este rádio",
    "Only supported on drivers that expose the complete cable-visible "
    "window (e.g. aux-first clones). Includes the factory calibration "
    "area the standard image omits.":
        "Suportado apenas em drivers que expõem a janela completa visível "
        "ao cabo (ex.: clones aux-first). Inclui a área de calibração de "
        "fábrica que a imagem padrão omite.",
    "Operation canceled by user": "Operação cancelada pelo usuário",
    "Pre-dump + write + verify in progress (do NOT touch the radio)...":
        "Pré-dump + gravação + verificação em andamento "
        "(NÃO mexa no rádio)...",
    "Raw clone images (*.bin)": "Imagens clone brutas (*.bin)",
    "Raw clone images (*.bin);;All files (*)":
        "Imagens clone brutas (*.bin);;Todos os arquivos (*)",
    "Raw dump": "Dump bruto",
    "Read-only raw dump of the radio memory (clone image or full "
    "window), saved to ~/.chirp/fw-backups/":
        "Dump bruto somente leitura da memória do rádio (imagem clone ou "
        "janela completa), salvo em ~/.chirp/fw-backups/",
    "RESTORE OK: 0 differences (readback identical)":
        "RESTORE OK: 0 divergências (re-leitura idêntica)",
    "RESTORE PITFALL: incomplete write (aborted)":
        "RESTORE PITFALL: gravação incompleta (abortada)",
    "Saves a raw dump + signed YAML sidecar into ~/.chirp/fw-backups/. "
    "Read-only: no byte is ever written to the radio.":
        "Salva um dump bruto + sidecar YAML assinado em "
        "~/.chirp/fw-backups/. Somente leitura: nenhum byte é gravado "
        "no rádio.",
    "Save firmware dump as": "Salvar dump de firmware como",
    "This operation WRITES to the radio memory and can render it "
    "unusable if used incorrectly.\n\nUse ONLY a backup from the SAME "
    "unit.\nThe pre-write dump is saved automatically before "
    "writing.\n\nContinue?":
        "Esta operação GRAVA na memória do rádio e pode torná-lo "
        "inutilizável se usada incorretamente.\n\nUse APENAS um backup "
        "da MESMA unidade.\nO dump prévio é salvo automaticamente antes "
        "de gravar.\n\nContinuar?",
    "Unexpected confirmation text; write canceled.":
        "Texto de confirmação inesperado; gravação cancelada.",
    "WRITE a clone image into the radio memory window (h777 and "
    "UV-5R-aux-first families; double confirmation + automatic "
    "pre/post backups)":
        "GRAVAR uma imagem de clone na janela de memória do rádio "
        "(famílias h777 e UV-5R-aux-first; dupla confirmação + backups "
        "automáticos pré/pós)",
    "Write": "Gravar",
    "Write canceled by user": "Gravação cancelada pelo usuário",
    "Write is validated only for the h777 family (PROGRAM handshake; "
    "e.g. Baofeng BF-777S) and UV-5R-aux-first (e.g. BOMVINK "
    "BOM-5701). Select a model from one of these families.":
        "A gravação é validada apenas nas famílias h777 (handshake "
        "PROGRAM; ex.: Baofeng BF-777S) e UV-5R-aux-first (ex.: BOMVINK "
        "BOM-5701). Selecione um modelo de uma dessas famílias.",
    "Write the image back to the radio? This overwrites the radio "
    "memory. Continue?":
        "Gravar a imagem de volta no rádio? Isso sobrescreve a memória "
        "do rádio. Continuar?",
    "Write the selected image to the radio memory?\n\nThis overwrites "
    "the current radio memory window. The radio's own pre-write dump "
    "is saved automatically.\n":
        "Gravar a imagem selecionada na memória do rádio?\n\nIsso "
        "sobrescreve a janela de memória atual do rádio. O dump "
        "pré-gravação do próprio rádio é salvo automaticamente.\n",
    "Writes the bytes of a clone image into the radio memory window "
    "(WRITE operation).\n\nBuilt-in safety: a pre-write dump of the "
    "unit is saved automatically; every block requires an ACK "
    "(aborted on NACK/timeout); read-back with a final diff. Use ONLY "
    "a backup from the SAME unit.":
        "Grava os bytes de uma imagem de clone na janela de memória do "
        "rádio (operação de ESCRITA).\n\nSegurança integrada: o dump "
        "prévio da unidade é salvo automaticamente; cada bloco exige ACK "
        "(abortado em NACK/timeout); re-leitura com diff no final. Use "
        "APENAS um backup da MESMA unidade.",
    # --- GUI: menus, diálogos e status ---
    "%1 — %2": "%1 — %2",
    "%i result(s)": "%i resultado(s)",
    "&Import...": "&Importar...",
    "&Print...": "&Imprimir...",
    "(auto-detect)": "(detecção automática)",
    "<%i items>": "<%i itens>",
    "<error: %s>": "<erro: %s>",
    "Add to bank": "Adicionar ao banco",
    "Added network source %s": "Fonte de rede %s adicionada",
    "Band (optional):": "Faixa (opcional):",
    "Band plan": "Plano de bandas",
    "Band plan: %s": "Plano de bandas: %s",
    "Bank:": "Banco:",
    "City:": "Cidade:",
    "Class: %s": "Classe: %s",
    "Clear logs": "Limpar logs",
    "Clear the system log history (logs/log.txt)?":
        "Limpar o histórico de logs do sistema (logs/log.txt)?",
    "Communicating with radio... (read-only)":
        "Comunicando com o rádio... (somente leitura)",
    "Connect": "Conectar",
    "Contact email:": "E-mail de contato:",
    "Copied %i channel(s)": "%i canal(is) copiado(s)",
    "Copy email": "Copiar e-mail",
    "Copy recent logs": "Copiar últimos logs",
    "Could not create the network radio source.":
        "Não foi possível criar a fonte de rádio de rede.",
    "Could not read debug log: %s":
        "Não foi possível ler o log de depuração: %s",
    "Country:": "País:",
    "Delete %i channels?": "Excluir %i canais?",
    "Developer": "Desenvolvedor",
    "Developer mode": "Modo desenvolvedor",
    "Developer mode disabled": "Modo desenvolvedor desativado",
    "Developer mode enabled": "Modo desenvolvedor ativado",
    "Developer tools": "Ferramentas de desenvolvedor",
    "Developer tools (raw dump)":
        "Ferramentas de desenvolvedor (dump bruto)",
    "Don't Save": "Não salvar",
    "Dump": "Dump",
    "Edit channel %s": "Editar canal %s",
    "Email copied to clipboard":
        "E-mail copiado para a área de transferência",
    "Enable View > Developer mode first":
        "Ative primeiro Exibir > Modo desenvolvedor",
    "Enter the source as host:port": "Informe a fonte como host:porta",
    "Export to %s": "Exportar para %s",
    "Export to HMK...": "Exportar para HMK...",
    "Export to ITM...": "Exportar para ITM...",
    "Failed to load source": "Falha ao carregar a fonte",
    "Failed to read image: %s": "Falha ao ler a imagem: %s",
    "File deleted: %s": "Arquivo apagado: %s",
    "File not found": "Arquivo não encontrado",
    "Files not found": "Arquivos não encontrados",
    "Filter (optional):": "Filtro (opcional):",
    "Filter:": "Filtro:",
    "Has valid tones: %s": "Possui tons válidos: %s",
    "If you don't save, the changes will be lost.":
        "Se você não salvar, as alterações serão perdidas.",
    "Import bank": "Importar banco",
    "Import bank...": "Importar banco...",
    "Import failed": "Falha na importação",
    "Import failed: %s": "Falha na importação: %s",
    "Import into open radio": "Importar para o rádio aberto",
    "Import starting at channel:": "Importar a partir do canal:",
    "Imported %i channel(s)": "%i canal(is) importado(s)",
    "Imported %i memories from bank %s":
        "%i memórias importadas do banco %s",
    "Importing %s...": "Importando %s...",
    "Loc": "Loc",
    "Logs": "Logs",
    "Logs cleared": "Logs limpos",
    "Logs copied to clipboard":
        "Logs copiados para a área de transferência",
    "Memory bounds: %s..%s": "Limites de memória: %s..%s",
    "Move down": "Mover para baixo",
    "Move up": "Mover para cima",
    "Name": "Nome",
    "Network source": "Fonte de rede",
    "Network source...": "Fonte de rede...",
    "New name for bank %s:": "Novo nome para o banco %s:",
    "No debug log found at %s":
        "Nenhum log de depuração encontrado em %s",
    "No other open radio with banks to import from":
        "Nenhum outro rádio aberto com bancos para importar",
    "No radio detected on this port. Check the cable and try another "
    "port.":
        "Nenhum rádio detectado nesta porta. Verifique o cabo e tente "
        "outra porta.",
    "No radio open": "Nenhum rádio aberto",
    "Number of memories:": "Número de memórias:",
    "Original project: CHIRP by Dan Smith (GPLv3)\n"
    "https://chirp.danplanet.com\n\n"
    "Developed by: Fábio Adler de Luna Gomes":
        "Projeto original: CHIRP por Dan Smith (GPLv3)\n"
        "https://chirp.danplanet.com\n\n"
        "Desenvolvido por: Fábio Adler de Luna Gomes",
    "Password:": "Senha:",
    "Print sent": "Impressão enviada",
    "Printing not available": "Impressão não disponível",
    "Programming cable detected on %s — use it?":
        "Cabo programador detectado em %s — usar?",
    "Query failed: %s": "Consulta falhou: %s",
    "Querying...": "Consultando...",
    "Radio: %s": "Rádio: %s",
    "Remove from bank": "Remover do banco",
    "Report a bug": "Reportar um bug",
    "Report a bug...": "Reportar um bug...",
    "Save changes to %s before closing?":
        "Salvar alterações em %s antes de fechar?",
    "Search": "Pesquisar",
    "Select the Tone Mode first": "Selecione o Tone Mode primeiro",
    "Serial ports:": "Portas seriais:",
    "Serial ports:\n%s\n\n%s": "Portas seriais:\n%s\n\n%s",
    "Source radio:": "Rádio de origem:",
    "Source:": "Fonte:",
    "State/Province:": "Estado/Província:",
    "State:": "Estado:",
    "System": "Sistema",
    "System logs: %s": "Logs do sistema: %s",
    "The file %s was deleted from disk. It was removed from the "
    "recent list.":
        "O arquivo %s foi apagado do disco. Ele foi removido da lista "
        "de recentes.",
    "The following files were deleted from disk and were removed from "
    "the recent list:\n%s":
        "Os seguintes arquivos foram apagados do disco e removidos da "
        "lista de recentes:\n%s",
    "This removes the list only; the files on disk are not deleted.":
        "Isto remove apenas a lista; os arquivos no disco não são "
        "apagados.",
    "Username:": "Usuário:",
    "ZIP (US) / County ID (CA):": "CEP (EUA) / ID de condado (CA):",
    "edit": "editar",
    "hostname:port": "host:porta",
    # --- backend/drivers: entradas vazias herdadas do upstream ---
    "%i Memories and shift all up": "%i memórias e subir tudo",
    "%i Memory": "%i memória",
    "%i Memory and shift block up": "%i memória e subir bloco",
    "%s %s, row %d": "%s %s, linha %d",
    "Aircraft frequencies must be aligned to 25kHz, 8.33kHz, be or a "
    "valid channel":
        "Frequências aeronáuticas devem estar alinhadas a 25kHz, "
        "8.33kHz ou ser um canal válido",
    "Channel frequencies are from the repeater's point of view. The "
    "receive frequency is the 467 MHz input. Duplex is minus and the "
    "offset is 5 MHz, so the repeater transmits on the 462 MHz "
    "output. A station using this repeater listens on the repeater "
    "output and transmits on the input.":
        "As frequências dos canais são do ponto de vista do repetidor. "
        "A frequência de recepção é a entrada de 467 MHz. O duplex é "
        "negativo e o offset é de 5 MHz, portanto o repetidor transmite "
        "na saída de 462 MHz. Uma estação usando este repetidor escuta "
        "na saída do repetidor e transmite na entrada.",
    "Cluster %i memory": "Agrupar %i memória",
    "Disabling Transit Function disables repeating. The repeater will "
    "not repeat until this setting is enabled.":
        "Desativar a Função de Transmissão desativa a repetição. O "
        "repetidor não repetirá até que esta configuração seja ativada.",
    "Driver": "Driver",
    "Enter information about the bug including a short but meaningful "
    "subject and information about the radio model (if applicable) in "
    "question. In the next step you will have a chance to add more "
    "details about the problem. Before proceeding, please search for "
    "duplicate issues!":
        "Informe dados sobre o bug incluindo um assunto curto, porém "
        "significativo, e informações sobre o modelo de rádio em questão "
        "(se aplicável). Na próxima etapa você poderá adicionar mais "
        "detalhes sobre o problema. Antes de prosseguir, pesquise issues "
        "duplicadas!",
    "Frequency %s is out of supported ranges %s":
        "A frequência %s está fora das faixas suportadas %s",
    "Frequency in this range not supported by firmware":
        "Frequência nesta faixa não é suportada pelo firmware",
    "Group: %s": "Grupo: %s",
    "I have": "Eu",
    "Internal driver error: Attempt to modify frozen memory; Please "
    "report this as a bug using \"Report or update a bug\" in the "
    "Help menu":
        "Erro interno do driver: tentativa de modificar memória "
        "congelada; relate isso como um bug usando \"Reportar ou "
        "atualizar um bug\" no menu Ajuda",
    "Memory List": "Lista de memórias",
    "Radio Info: Driver": "Informações do rádio: Driver",
    "Radio Info: Features": "Informações do rádio: Recursos",
    "Radio Info: Icom": "Informações do rádio: Icom",
    "Radio Info: Image Metadata":
        "Informações do rádio: Metadados da imagem",
    "Restore %i tab": "Restaurar %i aba",
    "SatNOGS DB provides a live, community-maintained database\n"
    "of satellite transmitter information. This source queries\n"
    "the SatNOGS API directly for the most granular and\n"
    "up-to-date transmitter data.":
        "O SatNOGS DB fornece um banco de dados vivo, mantido pela\n"
        "comunidade, com informações de transmissores de satélites.\n"
        "Esta fonte consulta a API do SatNOGS diretamente para os\n"
        "dados de transmissores mais granulares e atualizados.",
    "Select Modes to Import": "Selecione os modos a importar",
    "Settings: %s": "Configurações: %s",
    "Sort %i memory": "Ordenar %i memória",
    "Sort %i memory ascending": "Ordenar %i memória em ordem crescente",
    "Sort %i memory descending": "Ordenar %i memória em ordem decrescente",
    "This image is read-only due to being from a radio with "
    "unsupported firmware":
        "Esta imagem é somente leitura por ser de um rádio com firmware "
        "não suportado",
    "This source provides a curated list of active amateur radio\n"
    "satellites, mirrored from the JE9PEL database via GitHub.\n"
    "It is a stable, simplified list of popular frequencies.":
        "Esta fonte fornece uma lista curada de satélites ativos de\n"
        "rádio amador, espelhada do banco JE9PEL via GitHub.\n"
        "É uma lista estável e simplificada de frequências populares.",
    "checkbox": "caixa de seleção",
    "checked": "marcado",
    "empty": "vazio",
    "list": "lista",
    "locked": "bloqueado",
    "number": "número",
    "searched for duplicate issues": "pesquisei issues duplicadas",
    "text": "texto",
    "unchecked": "desmarcado",
    "unspecified": "não especificado",
    # --- backend/drivers: instruções de clone (Icom/FT-8x, vazias) ---
    "1. Turn radio off.\n2. Connect cable to MIC/SP jack.\n"
    "3. Press and hold [FW] while turning radio on to put into CLONE "
    "mode.\n4. Press OK on chirp prompt.\n5. <b>After clicking OK</b>, "
    "press the [DWN] button on radio to send image. The radio will say "
    "CLN OUT while downloading.\n":
        "1. Desligue o rádio.\n2. Conecte o cabo ao jack MIC/SP.\n"
        "3. Pressione e segure [FW] ao ligar o rádio para entrar no "
        "modo CLONE.\n4. Pressione OK no prompt do chirp.\n"
        "5. <b>Após clicar em OK</b>, pressione o botão [DWN] no rádio "
        "para enviar a imagem. O rádio dirá CLN OUT durante o "
        "download.\n",
    "1. Turn radio off.\n2. Connect cable to MIC/SP jack.\n"
    "3. Press and hold [FW] while turning radio on to put into CLONE "
    "mode.\n4. Press [UP] button on radio. The radio will say CLN IN.\n"
    "5. <b>After radio says CLN IN</b>, press OK on chirp prompt to "
    "upload.\n":
        "1. Desligue o rádio.\n2. Conecte o cabo ao jack MIC/SP.\n"
        "3. Pressione e segure [FW] ao ligar o rádio para entrar no "
        "modo CLONE.\n4. Pressione o botão [UP] no rádio. O rádio dirá "
        "CLN IN.\n5. <b>Após o rádio dizer CLN IN</b>, pressione OK no "
        "prompt do chirp para enviar.\n",
    "1. Turn radio off.\n2. Connect clone cable to the MIC/SP jack.\n"
    "3. Press and hold [PTT] and [Lamp] while turning the radio on.\n"
    "4. Rotate the dial to select \"CLONE\", then press [F].\n"
    "     (\"CLONE\" will appear on the display)\n"
    "5. <b>After clicking OK</b>, hold [PTT] briefly to transmit.\n"
    "     (\"SENDING\" will appear on the display)\n":
        "1. Desligue o rádio.\n2. Conecte o cabo clone ao jack MIC/SP.\n"
        "3. Pressione e segure [PTT] e [Lamp] ao ligar o rádio.\n"
        "4. Gire o dial para selecionar \"CLONE\" e pressione [F].\n"
        "     (\"CLONE\" aparecerá no display)\n"
        "5. <b>Após clicar em OK</b>, segure [PTT] brevemente para "
        "transmitir.\n     (\"SENDING\" aparecerá no display)\n",
    "1. Turn radio off.\n2. Connect clone cable to the MIC/SP jack.\n"
    "3. Press and hold [PTT] and [Lamp] while turning the radio on.\n"
    "4. Rotate the dial to select \"CLONE\", then press [F].\n"
    "     (\"CLONE\" will appear on the display)\n"
    "5. Press [MONI] to receive.\n"
    "     (\"SAVING\" will appear on the display)\n":
        "1. Desligue o rádio.\n2. Conecte o cabo clone ao jack MIC/SP.\n"
        "3. Pressione e segure [PTT] e [Lamp] ao ligar o rádio.\n"
        "4. Gire o dial para selecionar \"CLONE\" e pressione [F].\n"
        "     (\"CLONE\" aparecerá no display)\n"
        "5. Pressione [MONI] para receber.\n"
        "     (\"SAVING\" aparecerá no display)\n",
})

# --- settings dos rádios (h777, uv5r/BOM-5701, uv17Pro) ---
TRANSLATIONS.update({
    "A Channel Display Type": "Tipo de exibição do canal A",
    "Alarm": "Alarme",
    "Allows or blocks use of the 65-108 MHz broadcast FM receiver from the radio's CALL button.": "Permite ou bloqueia o uso do receptor FM de radiodifusão 65-108 MHz pelo botão CALL do rádio.",
    "Announces the channel number and other operations out loud as you use the radio. It can be intrusive in quiet surroundings.": "Anuncia o número do canal e outras operações em voz alta conforme você usa o rádio. Pode ser intrusivo em ambientes silenciosos.",
    "Auto Key Lock": "Trava automática de teclas",
    "Automatic Key Lock": "Trava automática de teclas",
    "Automatically locks the keypad to prevent accidental changes. Hold the # key to unlock the keypad.": "Trava o teclado automaticamente para evitar alterações acidentais. Segure a tecla # para destravar o teclado.",
    "B Channel Display Type": "Tipo de exibição do canal B",
    "Backlight": "Luz de fundo",
    "Backlight Timer": "Temporizador da luz de fundo",
    "Bandwidth": "Largura de banda",
    "Bank name 1": "Nome do banco 1",
    "Bank name 10": "Nome do banco 10",
    "Bank name 2": "Nome do banco 2",
    "Bank name 3": "Nome do banco 3",
    "Bank name 4": "Nome do banco 4",
    "Bank name 5": "Nome do banco 5",
    "Bank name 6": "Nome do banco 6",
    "Bank name 7": "Nome do banco 7",
    "Bank name 8": "Nome do banco 8",
    "Bank name 9": "Nome do banco 9",
    "Battery Save Mode": "Modo de economia de bateria",
    "Battery saver": "Economia de bateria",
    "Beep Tone": "Tom do beep",
    "Bluetooth": "Bluetooth",
    "Boot Screen 1": "Tela de inicialização 1",
    "Boot Screen 2": "Tela de inicialização 2",
    "Boot Screen Mode": "Modo da tela de inicialização",
    "Broadcast FM Radio": "Rádio FM de radiodifusão",
    "Broadcast FM radio receiver. The radio cannot scan while this is active": "Receptor de rádio FM de radiodifusão. O rádio não pode fazer varredura enquanto isso estiver ativo",
    "Busy Channel Lockout": "Bloqueio de canal ocupado",
    "CTCSS Tail Revert": "Reversão de cauda CTCSS",
    "Channel A display type": "Tipo de exibição do canal A",
    "Channel A work mode": "Modo de trabalho do canal A",
    "Channel B display type": "Tipo de exibição do canal B",
    "Channel B work mode": "Modo de trabalho do canal B",
    "Chooses how the alarm function operates when the CALL button is held: Site, Tone, or Code.": "Escolhe como a função de alarme opera quando o botão CALL é segurado: Site, Tom ou Código.",
    "Controls access to the full front-panel menu. Disabling it can prevent users from changing programmed settings on the radio.": "Controla o acesso ao menu completo do painel frontal. Desativá-lo pode impedir usuários de alterar configurações programadas no rádio.",
    "Controls what scanning does after finding a signal. TO resumes after a preset time, CO resumes after the signal disappears, and SE stops scanning on the detected frequency or channel.": "Controla o que a varredura faz após encontrar um sinal. TO retoma após um tempo predefinido, CO retoma após o sinal desaparecer, e SE para a varredura na frequência ou canal detectado.",
    "Controls whether the VFO/MR button can switch between frequency and memory-channel modes.": "Controla se o botão VFO/MR pode alternar entre modos de frequência e canal de memória.",
    "Controls whether the radio's front-panel RESET menu is available. This does not reset the radio by itself.": "Controla se o menu RESET do painel frontal do rádio está disponível. Isso não reinicia o rádio por si só.",
    "Cuts standby power consumption by switching the receiver off and on in a repeating cycle once no signal has been received for a few seconds. It considerably extends battery life, at the cost of occasionally clipping the first moment of an incoming transmission.": "Reduz o consumo de energia em espera desligando e ligando o receptor em um ciclo repetido quando nenhum sinal foi recebido por alguns segundos. Aumenta consideravelmente a vida útil da bateria, com o custo de ocasionalmente cortar o primeiro momento de uma transmissão recebida.",
    "DTMF Sidetone": "Tom lateral DTMF",
    "DTMF Speed (off)": "Velocidade DTMF (desligado)",
    "DTMF Speed (on)": "Velocidade DTMF (ligado)",
    "Delay Time (ms)": "Tempo de atraso (ms)",
    "Digit Duration (ms)": "Duração do dígito (ms)",
    "Digit Interval Duration (ms)": "Duração do intervalo entre dígitos (ms)",
    "Disable FM radio": "Desativar rádio FM",
    "Display ANI": "Exibir ANI",
    "Display Mode": "Modo de exibição",
    "Display Mode (A)": "Modo de exibição (A)",
    "Display Mode (B)": "Modo de exibição (B)",
    "Dual Standby": "Dupla espera",
    "Dual Watch TX Priority": "Prioridade TX do Dual Watch",
    "Emergency alarm triggered by the side key. Depending on the model this either sounds a local siren or also alerts other radios on the channel": "Alarme de emergência acionado pela tecla lateral. Dependendo do modelo, isso soa uma sirene local ou também alerta outros rádios no canal.",
    "Enable FM radio": "Ativar rádio FM",
    "Enable Menu Rst": "Ativar Reset do Menu",
    "Enable Voice": "Ativar voz",
    "Enables or disables the alarm sound.": "Ativa ou desativa o som do alarme.",
    "Entry 1": "Entrada 1",
    "Entry 10": "Entrada 10",
    "Entry 11": "Entrada 11",
    "Entry 12": "Entrada 12",
    "Entry 13": "Entrada 13",
    "Entry 14": "Entrada 14",
    "Entry 15": "Entrada 15",
    "Entry 2": "Entrada 2",
    "Entry 3": "Entrada 3",
    "Entry 4": "Entrada 4",
    "Entry 5": "Entrada 5",
    "Entry 6": "Entrada 6",
    "Entry 7": "Entrada 7",
    "Entry 8": "Entrada 8",
    "Entry 9": "Entrada 9",
    "FM function": "Função FM",
    "GPS Mode": "Modo GPS",
    "GPS On": "GPS Ligado",
    "GPS Speed Units": "Unidades de velocidade GPS",
    "GPS Timezone": "Fuso horário GPS",
    "Hang-up time": "Tempo de espera",
    "High voltage inhibit transmit": "Inibir transmissão em alta tensão",
    "In channel mode, chooses whether display line A shows the memory channel number, its programmed name, or its frequency.": "No modo canal, escolhe se a linha A do display mostra o número do canal de memória, seu nome programado ou sua frequência.",
    "In channel mode, chooses whether display line B shows the memory channel number, its programmed name, or its frequency.": "No modo canal, escolhe se a linha B do display mostra o número do canal de memória, seu nome programado ou sua frequência.",
    "Inhibit VOX on receive": "Inibir VOX na recepção",
    "Input DTMF": "DTMF de entrada",
    "Key Auto Lock": "Trava automática de teclas",
    "Key Lock": "Trava de teclas",
    "Limits how long a single transmission may last. When the time runs out the radio stops transmitting until PTT is released, which prevents overheating and stops a stuck PTT from blocking the channel for everyone else.": "Limita quanto tempo uma única transmissão pode durar. Quando o tempo acaba o rádio para de transmitir até que o PTT seja solto, o que previne superaquecimento e impede que um PTT travado bloqueie o canal para todos os outros.",
    "Low voltage inhibit transmit": "Inibir transmissão em baixa tensão",
    "Makes the dual PTT controls operate as a single PTT.": "Faz os controles de PTT duplo operarem como um único PTT.",
    "Menu Quit Timer": "Temporizador de saída do menu",
    "Offset (0.0-999.999)": "Offset (0.0-999.999)",
    "PTT Press Send": "Enviar ao pressionar PTT",
    "PTT Release Send": "Enviar ao soltar PTT",
    "Periodically checks both the A and B displayed frequencies. When either receives a signal, the radio stays on it until that signal disappears.": "Verifica periodicamente as frequências A e B exibidas. Quando uma delas recebe um sinal, o rádio permanece nela até que o sinal desapareça.",
    "Pilot Tone": "Tom piloto",
    "Power On Display Type": "Tipo de exibição ao ligar",
    "Power On Time": "Tempo ao ligar",
    "Power On Tone": "Tom ao ligar",
    "Prevents transmitting on a channel that is already in use. Pressing PTT on a busy channel sounds an alert tone instead of keying the transmitter.": "Impede a transmissão em um canal já em uso. Pressionar PTT em um canal ocupado emite um tom de alerta em vez de acionar o transmissor.",
    "QT Save Mode": "Modo de economia QT",
    "RESET Menu": "Menu RESET",
    "RX LED Color": "Cor do LED RX",
    "Radio ID": "ID do rádio",
    "Range Override Parameter": "Parâmetro de sobrescrita de alcance",
    "Read Password": "Senha de leitura",
    "Read Protect": "Proteção de leitura",
    "Repeater Tail Delay (ms)": "Atraso de cauda do repetidor (ms)",
    "Repeater Tail Revert (ms)": "Reversão de cauda do repetidor (ms)",
    "Roger": "Roger",
    "Roger Beep": "Beep Roger",
    "Roger Beep (RX)": "Beep Roger (RX)",
    "Roger Beep (TX)": "Beep Roger (TX)",
    "Rpt Tail Clear": "Limpar cauda do repetidor",
    "Rpt Tail Delay": "Atraso de cauda do repetidor",
    "STE Repeater Delay": "Atraso do repetidor STE",
    "Save Mode": "Modo de economia",
    "Scan": "Varredura",
    "Scan Mode": "Modo de varredura",
    "Scan mode": "Modo de varredura",
    "Selects the display backlight color used while receiving, or turns receive illumination off.": "Seleciona a cor da luz de fundo do display usada durante a recepção, ou desliga a iluminação de recepção.",
    "Selects the display backlight color used while transmitting, or turns transmit illumination off.": "Seleciona a cor da luz de fundo do display usada durante a transmissão, ou desliga a iluminação de transmissão.",
    "Selects the display backlight color while the radio is in standby, or turns that standby illumination off.": "Seleciona a cor da luz de fundo do display enquanto o rádio está em espera, ou desliga essa iluminação de espera.",
    "Selects the language for spoken radio-operation prompts, or disables those prompts.": "Seleciona o idioma para avisos falados de operação do rádio, ou desativa esses avisos.",
    "Selects the language the spoken voice prompts use. It has no effect unless Voice prompts are enabled.": "Seleciona o idioma que os avisos de voz falados usam. Não tem efeito a menos que os avisos de voz estejam ativados.",
    "Selects the memory channel monitored by the Dual Watch function.": "Seleciona o canal de memória monitorado pela função Dual Watch.",
    "Selects the squelch-tail elimination setting used for communication through a compatible repeater. Use OFF when the repeater does not support this feature.": "Seleciona a configuração de eliminação de cauda de squelch usada para comunicação através de um repetidor compatível. Use DESLIGADO quando o repetidor não suporta este recurso.",
    "Selects the tone-burst frequency sent for repeater access.": "Seleciona a frequência de burst de tom enviada para acesso ao repetidor.",
    "Selects whether the radio sounds an end-of-reception tone for the A or B display, or disables it.": "Seleciona se o rádio emite um tom de fim de recepção para o display A ou B, ou desativa-o.",
    "Selects which side has transmit priority while Dual Watch is enabled.": "Seleciona qual lado tem prioridade de transmissão enquanto o Dual Watch está ativado.",
    "Send ID Delay": "Atraso de envio de ID",
    "Sends a short tone at the end of each transmission so other stations can hear that you released PTT.": "Emite um tom curto no fim de cada transmissão para que outras estações ouçam que você soltou o PTT.",
    "Service override for supported-frequency checks during upload. Leave this at Default unless you fully understand the radio's hardware limits and the legal limits for your location.": "Sobrescrita de serviço para verificações de frequência suportada durante o upload. Deixe em Padrão a menos que você compreenda totalmente os limites de hardware do rádio e os limites legais para sua localização.",
    "Set the channel selector to channel 16 to scan channels 1-15. Scanning stops when a signal is detected and resumes once it clears. At least two channels are required, and scanning is unavailable while the FM radio function is active": "Defina o seletor de canal para o canal 16 para varrer canais 1-15. A varredura para quando um sinal é detectado e retoma quando ele desaparece. Pelo menos dois canais são necessários, e a varredura não está disponível enquanto a função de rádio FM está ativa.",
    "Sets how many seconds the display backlight remains on after a key press or radio activity. 0 disables the automatic backlight.": "Define quantos segundos a luz de fundo do display permanece acesa após uma tecla ser pressionada ou atividade do rádio. 0 desativa a luz de fundo automática.",
    "Sets how strong a received signal must be before the speaker unmutes. 0 leaves the squelch open so you hear noise all the time, higher values reject more weak signals and noise. Raise this value if the speaker keeps unmuting on interference, lower it if distant stations are being cut off.": "Define a força que um sinal recebido deve ter antes de o alto-falante desmutar. 0 deixa o squelch aberto para que você ouça ruído o tempo todo, valores mais altos rejeitam mais sinais fracos e ruído. Aumente este valor se o alto-falante continuar desmutando em interferência, diminua se estações distantes estão sendo cortadas.",
    "Sets the VOX sensitivity. Too sensitive a setting keys the transmitter on the noise around the radio, too insensitive a setting fails to pick up your voice.": "Define a sensibilidade do VOX. Uma configuração muito sensível aciona o transmissor com o ruído ao redor do rádio, uma configuração muito insensível falha em captar sua voz.",
    "Sets the delay before repeater squelch-tail elimination is applied. Match this timing to the repeater; use OFF when the feature is not required.": "Define o atraso antes da eliminação de cauda de squelch do repetidor ser aplicada. Ajuste este tempo ao repetidor; use DESLIGADO quando o recurso não é necessário.",
    "Shift": "Deslocamento",
    "Side Tone": "Tom lateral",
    "Side key function": "Função da tecla lateral",
    "Signal Code": "Código de sinal",
    "Signal Code 1": "Código de sinal 1",
    "Signal Code 1 Name": "Nome do código de sinal 1",
    "Signal Code 10": "Código de sinal 10",
    "Signal Code 10 Name": "Nome do código de sinal 10",
    "Signal Code 11": "Código de sinal 11",
    "Signal Code 11 Name": "Nome do código de sinal 11",
    "Signal Code 12": "Código de sinal 12",
    "Signal Code 12 Name": "Nome do código de sinal 12",
    "Signal Code 13": "Código de sinal 13",
    "Signal Code 13 Name": "Nome do código de sinal 13",
    "Signal Code 14": "Código de sinal 14",
    "Signal Code 14 Name": "Nome do código de sinal 14",
    "Signal Code 15": "Código de sinal 15",
    "Signal Code 15 Name": "Nome do código de sinal 15",
    "Signal Code 16": "Código de sinal 16",
    "Signal Code 16 Name": "Nome do código de sinal 16",
    "Signal Code 17": "Código de sinal 17",
    "Signal Code 17 Name": "Nome do código de sinal 17",
    "Signal Code 18": "Código de sinal 18",
    "Signal Code 18 Name": "Nome do código de sinal 18",
    "Signal Code 19": "Código de sinal 19",
    "Signal Code 19 Name": "Nome do código de sinal 19",
    "Signal Code 2": "Código de sinal 2",
    "Signal Code 2 Name": "Nome do código de sinal 2",
    "Signal Code 20": "Código de sinal 20",
    "Signal Code 20 Name": "Nome do código de sinal 20",
    "Signal Code 3": "Código de sinal 3",
    "Signal Code 3 Name": "Nome do código de sinal 3",
    "Signal Code 4": "Código de sinal 4",
    "Signal Code 4 Name": "Nome do código de sinal 4",
    "Signal Code 5": "Código de sinal 5",
    "Signal Code 5 Name": "Nome do código de sinal 5",
    "Signal Code 6": "Código de sinal 6",
    "Signal Code 6 Name": "Nome do código de sinal 6",
    "Signal Code 7": "Código de sinal 7",
    "Signal Code 7 Name": "Nome do código de sinal 7",
    "Signal Code 8": "Código de sinal 8",
    "Signal Code 8 Name": "Nome do código de sinal 8",
    "Signal Code 9": "Código de sinal 9",
    "Signal Code 9 Name": "Nome do código de sinal 9",
    "Single PTT (BTech UV-82HP only)": "PTT único (apenas BTech UV-82HP)",
    "Single PTT (UV-82C only)": "PTT único (apenas UV-82C)",
    "Skey2 Short": "Skey2 curto",
    "Sound Alarm": "Soar alarme",
    "Sounds a short confirmation tone as you operate the radio. Turn it off when the radio has to be used discreetly.": "Emite um tom curto de confirmação conforme você opera o rádio. Desligue quando o rádio precisar ser usado discretamente.",
    "Squelch": "Squelch",
    "Squelch Level": "Nível de squelch",
    "Squelch Tail Eliminate (HT to HT)": "Eliminação de cauda de squelch (HT para HT)",
    "Squelch Tail Eliminate (repeater)": "Eliminação de cauda de squelch (repetidor)",
    "Squelch level": "Nível de squelch",
    "Standby LED Color": "Cor do LED em espera",
    "TX LED Color": "Cor do LED TX",
    "Tail Clear": "Limpar cauda",
    "Timeout (s)": "Tempo limite (s)",
    "Timeout Timer Alarm": "Alarme do temporizador de tempo limite",
    "Timeout timer": "Temporizador de tempo limite",
    "Tone Burst Frequency (BTech UV-82HP only)": "Frequência de burst de tom (apenas BTech UV-82HP)",
    "Transmits a special end-of-transmission signal intended to reduce the squelch burst heard by another compatible handheld. The manual recommends disabling this for repeater operation.": "Transmite um sinal especial de fim de transmissão destinado a reduzir o burst de squelch ouvido por outro portátil compatível. O manual recomenda desativar isso para operação em repetidor.",
    "VFO A": "VFO A",
    "VFO B": "VFO B",
    "VFO/MR Button": "Botão VFO/MR",
    "VFO/MR Switching (BTech UV-82HP only)": "Comutação VFO/MR (apenas BTech UV-82HP)",
    "VFO/MR Switching (UV-82C only)": "Comutação VFO/MR (apenas UV-82C)",
    "VOX": "VOX",
    "VOX level": "Nível VOX",
    "Voice": "Voz",
    "Voice Alert": "Alerta de voz",
    "Voice language": "Idioma da voz",
    "Voice operated transmit. The radio starts transmitting when you speak towards the microphone, so hands-free conversation is possible without pressing PTT.": "Transmissão operada por voz. O rádio começa a transmitir quando você fala em direção ao microfone, permitindo conversa com as mãos livres sem pressionar o PTT.",
    "Voice prompt": "Aviso de voz",
    "Vox": "Vox",
    "Vox Delay Time": "Tempo de atraso do Vox",
    "Vox Level": "Nível do Vox",
    "Vox Switch": "Chave do Vox",
    "When to send ANI ID": "Quando enviar ID ANI",
    "Write Password": "Senha de gravação",
    "Write Protect": "Proteção de gravação",
})


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
        else:
            if e.obsolete:
                # Reativa entrada marcada como obsoleta (#~): sem isso a
                # tradução é gravada mas NÃO entra no .mo compilado.
                e.obsolete = False
            if not e.msgstr or e.msgstr != pt:
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
