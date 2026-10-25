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
