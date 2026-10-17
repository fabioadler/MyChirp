# PLANO DE TRABALHO — MyChirp (BOM-5701 + Interface PySide6)

> Regra de segurança: gravação no BOM-5701 foi **validada em hardware
> real** (round-trip byte-idêntico, commit `dcc0d759`). Backup salvo em
> `~/.chirp/backups/` antes de cada sessão de upload.

---

## 1. Objetivo

1. Suporte de **leitura** ao rádio **BOMVINK BOM-5701** (driver baseado no
   protocolo UV-5R) — **concluído e validado em hardware**.
2. Interface gráfica moderna em **PySide6** (direção
   CHIRP-next com design tokens compartilhados) — **concluída**.
3. Estrutura de projeto limpa: pacote único `mychirp`, backend neutro
   (`mychirp/theme.py`, `mychirp/memory_ops.py`), UI em
   `mychirp/pysideui/`.

## 2. Arquitetura atual (2026-10-12, migração PySide6)

```
mychirp/
├── pysideui/          # Interface principal (PySide6/QSS)
│   ├── main.py        # entry point (mychirp=pysideui:run)
│   ├── theme.py       # QSS paleta/escuro gerado de mychirp/theme.py
│   ├── i18n.py        # gettext lazy (compat com pt_BR)
│   ├── widgets/       # MainWindow (QMenuBar + QTabWidget closable)
│   ├── tabs/          # Welcome, Recent, Memories (QTableView),
│   │                  # Settings (lado-esq. QFormLayout), Banks
│   ├── dialogs/       # CloneDialog (download/upload), About
│   └── services/      # AppState (QObject), RadioService
│   │                  # (QThreadPool + progress/finished signals)
├── theme.py           # Tokens de cores/espaçamento compartilhados
├── memory_ops.py      # Operações de memória (backend puro, UndoStack)
├── config.py          # configuração persistente (ex-wxui/config.py)
├── drivers/           # todos os drivers do CHIRP original +
│   │                  # bom5701.py (driver separado do BOM-5701)
├── share/             # assets: mychirp-logo.png,
│                      # mychirp_logo_transparente.png, logo_empresa.png
└── (núcleo: chirp_common, bitwise, directory, settings, platform...)

Comandos: mychirp (GUI PySide6) · mychirpc (CLI) · experttune
```

**Tokens de design:** `mychirp/theme.py` exporta
`AppColors`/`Palette`/`SPACING`, fonte única das cores do tema
mapeadas em QPalette + QSS por `pysideui/theme.py`.

## 3. Interface PySide6 — componentes e temas

- **Temas claro/escuro/sistema** persistidos em `chirp.config`
  (seção `state`, chave `theme_mode`) — mesmos tokens do design
  (docs/ui-redesign.md) mapeados em `mychirp/theme.py` (Light/Dark),
  gerados como QPalette + QSS por `pysideui/theme.py`.
- **MainWindow**: QMenuBar (File/Edit/View/Radio/Help espelhando o
  wxui) + QTabWidget movível/fechável por aba (implementado com
  QTabBar/QToolButton) + QStatusBar de 3 campos.
- **WelcomeTab**: logo ≤300px centralizada, segue o tema (sem fundo
  hardcoded).
- **MemoriesTab**: QTableView + QAbstractTableModel paginado (50/
  página), filtro instantâneo, "Find next", Hide empty, edição por canal
  (MemoryEditDialog tipado), sort por coluna clicável, toolbar de ops
  (Copy/Paste/Insert/Delete×3/Move/Goto/Undo/Redo/Export CSV).
- **SettingsTab**: NavigationRail → QListWidget lateral +
  QFormLayout à direita (estilo Treebook CHIRP-next), controles tipados
  por RadioSettingValue (QCheckBox/QComboBox/QSpinBox/QDoubleSpinBox/
  QLineEdit), warnings exibidos e Apply/Revert.
- **BanksTab**: matriz memórias × bancos com checkboxes (QTableView +
  QAbstractTableModel).
- **CloneDialog**: QComboBox vendedor→modelo→porta + QProgressBar;
  download assíncrono via RadioService (sinais → GUI thread).
- **AboutDialog**: logo MyChirp, créditos CHIRP original (GPLv3),
  "Desenvolvido por Fábio Adler de Luna Gomes", logo da empresa.

## 4. Políticas de segurança vigentes

1. **Gravação de firmware NÃO existe** (impossível pelo protocolo de
   clone; risco de brick permanente).
2. **Dupla confirmação obrigatória para upload** (ação destrutiva).
3. **BOM-5701**: upload permanece bloqueado até autorização explícita.
4. **Backups automáticos** em `~/.chirp/backups/` antes de gravar.
5. **Versão do sistema (`CHIRP_VERSION`)**: só muda por ordem explícita
   do mantenedor (Fábio). Nenhuma alteração/commit deve tocar na versão
   por iniciativa própria.

## 5. Diagnóstico do BOM-5701 (histórico validado em hardware)

Erro original com driver "Baofeng UV-5R": `Radio refused to send second
block 0x1EC0`. Rastreio serial completo (814 linhas TX/RX) mostrou que o
firmware encerra a sessão de clone quando o bloco principal completa;
leituras auxiliares só são atendidas **antes** do bloco principal.

**Correção implementada** (`_aux_first` na classe `BOMVINKBOM5701`):
baixar bloco auxiliar antes do principal; imagem montada na ordem padrão
UV-5R (ident 8 + main 0x1800 + aux 0x140 = 0x1948 bytes). `match_model`
próprio (tamanho 0x1948 + versão em branco `0xFF`).

**Validação em hardware real (2026-10-10/11): leitura e escrita
completas comprovadas** — ver histórico git (seção 7 do plano anterior)
e `tests/unit/test_bomvink_bom5701.py` (serial simulado roteado pelo
rastreio real).

Observações técnicas: módulo interno E220-400722D (LoRa) sem relação
com o clone via conector de 2 pinos; cabo CH340 em `/dev/ttyUSB0`.

## 5b. Diagnóstico do Baofeng UV-16 Plus (2026-10-13, validado em hardware)

Modelo 2024/25 (10W no rótulo, display estilo UV-5R), sem suporte no CHIRP
upstream — protocolo descoberto por engenharia reversa com o rádio físico:

- **Protocolo**: clone clássico UV-5R a 9600 baud (cabo CH340/K1)
- **Magic aceito**: `UV5R_MODEL_291` (`50 BB FF 20 12 07 25`) — recusado
  com DTR/RTS baixos; aceito após reconexão do cabo (quirk do CH340)
- **Ident/fingerprint**: `aa 30 76 04 00 05 20 dd` (termina em `\xDD`)
- **Firmware** (aux 0x1EF0): `HN5RV01` — base do `BASETYPE_UV16PLUS`
- **Memória**: layout idêntico ao UV-5R — ident(8) + main 0x0000-0x1800 +
  aux 0x1EC0-0x2000 = 0x1948 bytes; 128 canais (0-127) validados contra o
  display (ch0=144.725 VHF, ch127=435.725 UHF)
- **Tri-power**: High/Med/Low (10/5/2W rotulados)
- **Driver**: `mychirp/drivers/baofeng_uv16.py` herda de
  `BaofengBFF8HPRadio` com power levels próprias re-mapeadas por label
- **Distinção UV-16 legado** (2022, mesmo protocolo do BF-F8HP): classe
  `BaofengUV16Radio` em `uv5r.py`; alias `UV-16 Pro`/`UV-16 Pro Mate`

## 6. Fases e status

- [x] **F0** — Repositório, branch, PLAN.md, graphify
- [x] **F1** — Driver `mychirp/drivers/uv5r.py`: `_download_aux()`,
  `_aux_first`, classe `BOMVINKBOM5701` + testes de regressão
- [x] **F2** — Renome do pacote `chirp` → `mychirp` (imports, setup.py,
  MANIFEST, tox, mypy, egg-info)
- [x] **F3** — About com créditos (CHIRP original, desenvolvedor,
  logo da empresa)
- [x] **F4** — Correções de DeprecationWarning (seekto redundante,
  `wx.NewId` → `wx.ID_ANY`, `LOG.warn` → `LOG.warning`, pytest 8.x)
- [x] **F5** — Interface Flet (`mychirp/fletui`): tema centralizado,
  Welcome, Memories, Settings, CloneDialog, About, StatusBar temática,
  atalhos de teclado (Ctrl+O/S/D/U/W, F5), FilePicker como serviço
- [x] **F6** — Limpeza: remoção do wxui + testes legados, config →
  `mychirp/config.py`, assets únicos em share, scripts raiz removidos,
  README/PLAN reescritos
- [x] **M0** — Migração PySide6: dependência instalada (PySide6 6.12,
  pytest-qt), branch `feature/pyside6-migration`
- [x] **M1** — Adaptadores Qt: `services/radio_service.py`
  (QThreadPool + signals, mesmas assinaturas),
  `services/app_state.py` (QObject AppState), `i18n.py`
- [x] **M2** — Interface completa: `widgets/main_window.py`,
  `tabs/`, `dialogs/`, `theme.py` (QSS light/dark)
- [x] **M3** — Entry points: `mychirp=pysideui:run`, smoke tests
  offscreen (test_pysideui_smoke.py, 3 testes)
- [x] **M4** — Remoção do Flet: pacote `fletui/` removido, dependência
  desinstalada, `mychirp-flet` removido; backend e testes preservados
  (test_move_ops -> test_memory_ops/imports atualizados). Suíte: 744
  testes passam, 13 skipped.
- [x] **V1** — Suporte ao Baofeng UV-16 legado (2022): classe
  `BaofengUV16Radio` em `uv5r.py` (plataforma BF-F8HP) + aliases
  UV-16 Pro/Pro Mate
- [x] **V2** — Suporte oficial ao Baofeng UV-16 Plus: driver dedicado
  `baofeng_uv16.py` (engenharia reversa, ver §5b) + imagem de teste
  clonada do rádio real (35 testes do driver passando)
- [x] **V3** — Suporte oficial ao Baofeng UV-17M (tela colorida + GPS,
  firmware V0.04/H01): classe `UV17M` em `baofeng_uv17Pro.py` herda de
  `UV17RPlus` (magic `PROGRAMBFNORMALU`), 999 canais, GPS settings,
  6 settings adicionais descobertos na imagem real (Power On Tone/Time,
  Display ANI, Input DTMF, Single Watch, GPS Speed Units), round-trip
  byte-idêntico validado 2x, imagem de teste real. Boot display: só
  LOGO ou tensão (sem mensagem de texto — confirmado no menu do rádio).

## 5c. Diagnóstico do Baofeng UV-17M (2026-10-15/16, validado em hardware)

Modelo 2024/25 (tela colorida, GPS, airband AM), firmware V0.04,
hardware V01. Driver `UV17M` em `baofeng_uv17Pro.py`:

- **Protocolo**: idêntico ao UV-17R-Plus (família NORMALU): magic
  `PROGRAMBFNORMALU`, fingerprint `0x06`, handshake 0x46(16)/0x4D(15),
  imagem 0x8380, XOR "CO 7", 115200 baud. O magic COLOR é recusado.
- **Round-trip**: upload→download byte-idêntico (sha256, 2x).
- **Canais**: 999 (o rádio navega 1-999); slot 1000 preservado no struct.
- **GPS**: gpsw/gpsmode/gpstimezone mapeados; gpstimezone 0xFF de
  fábrica fica oculto (regra de fora-de-faixa da família).
- **Boot display**: apenas LOGO (byte 0) ou tensão da bateria
  (byte != 0). Não suporta mensagem de texto (confirmado no hardware).
- **EEPROM 64 KiB**: mapa completo via sonda de leitura; sem bitmap de
  logo (logo vive na flash do firmware, fora do protocolo de clone).
- **Quirk CH340**: primeira abertura da porta pode ecoar o 1º byte do
  magic; probe open/close antes da sessão resolve (como UV-16 Plus).
- Ver `rethink/uv17m-descobertas.md` para o diário completo de RE.

## 7. Correções pós-migração Flet (ordem de entrada)

### F7 — Lista de recentes era reconstruída após restart
- **Sintoma**: "quando clicamos em limpar os arquivos recentes, ele não
  limpa todos sempre fica um" — após limpar e reiniciar, um item voltava.
- **Causa raiz**: `restore_session()` chamava `shell.open_file()` que
  empurrava os arquivos auto-restaurados para a lista de recentes.
- **Correção**: novo parâmetro `record_recent` em `open_file()`, o
  restore passa `record_recent=False`. Teste `test_clear_restart.py`
  valida que a lista fica vazia após clear + restart simulado.

### F8 — Download do rádio terminava com pipe string
- **Sintoma**: `'NoneType' object has no attribute 'timeout'` no
  `sync_in()` — `RadioJob` passava a string da porta como `pipe`.
- **Causa raiz**: `download_radio()` fazia `rclass(port)` ao invés de
  `rclass(open_serial(port, rclass))`.
- **Correção**: nova função `open_serial(port, rclass)` em
  `radio_service.py` configurando `serial.Serial` com ba/RTS/DTR/
  timeout, idêntica ao `open_serial` do CHIRP original.

### F9 — Memórias/Settings não carregam após download (bug crítico)
- **Sintoma**: após download concluído, a aba abre mas a grade e os
  settings ficam vazios.
- **Causa raiz**: `add_radio_tab()` só criava a view; ninguém chamava
  `refresh_data()`/ `load_settings()` depois de adicionar a aba.
- **Correção**: `add_radio_tab()` agora chama `view.refresh_data()`
  (memórias + bancos encadeados) e `view.settings.load_settings()` se
  existir. Validado com FakeUV17 e rádios de teste reais.

### F10 — Tabelas não ocupavam a largura total da seção
- **Sintoma**: tabela de canais/configurações encolhia ao conteúdo ao
  invés de preencher o painel.
- **Correção**: `ft.ResponsiveRow(expand=True, controls=[table])` com
  `col=12` na DataTable + `horizontal_alignment=STRETCH` na coluna de
  settings para garantir fundo completo nas linhas.

### F11 — Atalhos de teclado do CHIRP original (paridade)
- **Objetivo**: manter os mesmos atalhos da interface anterior.
- **Implementados**: Ctrl+N (novo arquivo CSV), Ctrl+O/S/E/W, Ctrl+D/U,
  Ctrl+X/C/V/G, Ctrl+A (select all), Ctrl+Shift+T (restore), Ctrl+Backspace
  (delete channel), F5 (refresh em qualquer aba).

## 8. Ritual por alteração

1. Alteração mínima, testes (`venv/bin/python -m pytest tests/unit -q`).
2. App abre sem erros (`: > ~/.chirp/debug.log; venv/bin/mychirp`,
   verificar log).
3. Commit imediato por unidade lógica; `/graphify update` ao final de
   lotes grandes.

## 7b. Boot Image / Firmware Access — plano de implementação

> Descoberto por engenharia reversa do `Import Picture tools.exe` v1.1
> (CPS oficial Baofeng UV-5RM Plus). Ver `rethink/uv17m-boot-image-protocol.md`
> para a especificação completa do protocolo.

### Fases

- [ ] **B1** — Protocolo de boot mode: implementado (`mychirp/boot_image.py`),
  mas **NÃO VALIDADO em hardware**. O UV-17M V0.04 não responde ao
  0xA5 (boot mode). Ver seção 20-22 de `rethink/uv17m-descobertas.md`.
  - **PRÓXIMO TESTE**: hipótese do boot mode silencioso — enviar 0xA5
    e SEGUIR a sequência completa sem esperar ACK. Se CMD_READFLASH
    retornar dados, o protocolo funciona sem ACK explícito.
  - **ALTERNATIVA**: sniffing do Import Picture tools.exe com wine +
    socat (serial virtual) para capturar a sequência EXATA.
- [ ] **B2** — Ferramenta de boot image (CLI): converter BMP 160×128
  → formato do rádio → upload via protocolo B1. Validar em hardware.
- [ ] **B3** — Integração no MyChirp (UI): menu Radio > Boot Image
  com preview, seleção de arquivo BMP e progress bar.
- [ ] **B4** — Firmware dump/read: CMD_READFLASH para dump completo
  da flash (≥1MB) e comparação entre versões de firmware.
- [ ] **B5** — Extensão para outros rádios da família UV-17Pro:
  UV-17, UV-17Pro, UV-17ProGPS, 5RM, K6, UV-32, UV-28, BF-F8HP-PRO
  (mesmo protocolo, endereços podem variar).
- [ ] **B6** — Segurança: confirmação dupla para gravação de flash,
  dump obrigatório antes de upload, aviso de risco de brick.

### Rádios que suportam boot image (família UV-17Pro, tela colorida)

| Modelo | Flash addr | Dimensão BMP | Confirmado |
|---|---|---|---|
| UV-17M | 0xC0000 (assumido, grupo UV17-20) | 160×128 | testar em HW |
| UV-17, UV-18, UV-19, UV-20 | 0xC0000 | 150×128/160×128/128×160 | sim (video ref) |
| UV-21 | 0x100000 | mesma | sim (tool v1.1) |
| 5RM/5RM Plus/T6UV | 0xC0000 | mesma | sim (tool incluído) |
| UV-32 GPS/28 Pro GPS | 0xC0000 | mesma | sim (CPS chama tool) |

### Rádios sem boot image (família UV-5R, tela mono)

UV-5R, UV-82, BF-888S, BF-T1, BF-T8: protocolo clone apenas (EEPROM 8KB),
sem modo boot, sem tela colorida — boot image não se aplica.

### Ferramenta de diagnóstico (paralelo)

- [x] **D1 (parte clone)** — `mychirp-fw` CLI (`mychirp/cli/fw.py` +
  `mychirp/fwtool.py`): dump de memória via `sync_in()` do driver
  (**genérico** — qualquer CloneModeRadio do directory, incl. os 59
  drivers Baofeng; abertura serial compartilhada em
  `mychirp/serial_link.py`). Salva `.bin` + YAML de metadados
  (sha256/porta/baud) e `~/.chirp/fw-backups/` com `--backup`. Read-only
  (nunca grava no rádio). D1a/D1b validados com rádio simulado H777
  (BF-777S) — testes em `tests/unit/test_fw_cli.py`.
  **Teste de hardware pendente (CHECK: avisar mantenedor antes).**
- [ ] **D2** — Comparação de dumps entre versões de firmware (diff byte-level). _(implementado: `mychirp-fw --diff a.bin b.bin`)_
- [ ] **D3** — Extração de firmware de fábrica para backup antes de customização. _(implementado: `--backup` + YAML sidecar; falta validar em HW)_

## 8. Ambiente (Linux/Debian 13)

Python 3.13 · PySide6 6.12 · pytest 8.4.2
· pytest-qt (GUI offscreen) · venv em `./venv`. App em
`venv/bin/mychirp` (PySide6).

## 9. Reversão

O histórico git preserva o wxui completo (último commit com interface
antiga: `67e69033`). Reverter restauraria a interface legada se urgente.
