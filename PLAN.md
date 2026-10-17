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

1. **Gravação de janela clone (992 B) família h777 — RESTORE AUTORIZADO
   e validado** em hardware real (2026-10-17, round-trip no-op BF-777S
   sha `4d8db228`: 124 blocos ACK + re-leitura byte-idêntica). Guias:
   `Radio > Firmware restore...` (GUI, dupla confirmação modal +
   backups automáticos .pre/.post em `~/.chirp/fw-backups/`) e
   `mychirp-fw --restore` (CLI, dupla confirmação no terminal;
   impossível sem TTY). Restaura só a MESMA unidade via backup
   sha-assinado. Outras famílias (UV-5R, BOM-5701, RC via própria
   janela estendida) recusadas com mensagem clara até validação
   (senão, entrar no fluxo do P1/análogo do BF-777S).
2. **Firmware de nível binário (flash do MCU) NÃO existe por cabo**:
   apenas codeplug/EEPROM é endereçável (código do MCU via biopsia de
   hardware, adiada — ver diário forense).
3. **Dupla confirmação obrigatória para upload/restore** ( ações
   destrutivas — marca uma exceção validada acima).
4. **Backups automáticos** em `~/.chirp/backups/` (codeplug GUI) e
   `~/.chirp/fw-backups/` (dump/restore fwtool) antes de gravar.
5. **Versão do sistema (`CHIRP_VERSION`)**: só muda por ordem explícita
   do mantenedor (Fábio). Nenhuma alteração/commit deve tocar na
   versão por iniciativa própria.

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
  **Validado em hardware real (2026-10-16)**: BF-777S @/dev/ttyUSB0,
  2 dumps byte-idênticos (sha256 `4d8db228…`, 992 B @9600), ident
  `P3107 f7 00 00`; diff entre dumps = 0 faixas. Também
  **Intelbras RC 3002 G2** (outro driver da família H777, 0 linhas
  novas): 2 dumps byte-idênticos (sha256 `1fa31046…`); prova de D2:
  BF-777S × RC3002G2 = 83 faixas diferentes atribuídas campo a campo
  (16/16 canais com programação de fábrica distinta; settings
  idênticos; curvas de calibração/blocos `0x55` fora das structs —
  ver `docs/dump-format-h777.md`).
  Também **BOMVINK BOM-5701** (3ª família de protocolo, UV-5R schema
  com quirk aux-primeiro): 2 dumps byte-idênticos (sha256 `6efa912e…`,
  6472 B @9600, ~20 s entre sessões respeitado).
- [ ] **D2** — Comparação de dumps entre versões de firmware (diff byte-level). _(implementado: `mychirp-fw --diff a.bin b.bin`)_
- [ ] **D3** — Extração de firmware de fábrica para backup antes de customização. _(implementado: `--backup` + YAML sidecar; falta validar em HW)_
- [x] **D4 — RE dos dumps (`--map` + docs de formato)** — `mychirp-fw
  --map <dump.bin>`: análise semântica (canais usados, settings por
  grupo e regiões reais classificadas mapeadas × não-mapeadas), driver
  resolvido pelo YAML sidecar. Formatos das 3 famílias de protocolo
  documentados com structs "limpas" e valores de fábrica:
  `docs/dump-format-h777.md`, `docs/dump-format-uv5r.md`
  (UV-17M/115200 fica para o P1).

#### Pendências do mychirp-fw (pós-sessão 2026-10-17)

Sessões 2026-10-17 (tarde): **3 unidades varridas** (BF-777S,
RC 3002 G2, BOM-5701 - rádios reconectados na bancada). Feitos:

- [x] **Mapa estendido H777 por serial** (`9c8a3562`): RC 3002 G2
  responde até 0x8000; máscara `0x3FFF` (período 0x4000); zonas reais
  = codeplug 0x0000-0x07FF + **zona-mirror 0x1000-0x17FF** (cópia
  byte-a-byte); 8-B único tamanho confiável; `E`→`0x46`; sem boot por
  serial (0xA5 não acorda). `docs/dump-format-h777.md` §5.
- [x] **Janela completa 8 KiB BOM-5701** (`d15dc044`): calibração de
  fábrica 0x1800-0x1900 preservada 1ª vez (curvas TX VHF/UHF); byte
  `0x1FCE` volátil entre sessões (0x16→0x13), estável em sessão;
  ident igual ao UV-16 Plus (não único por modelo).
  `docs/dump-format-uv5r.md` §5.
- [x] **GUI: `Radio > Firmware dump...`** (read-only): diálogo com
  vendor/model/porta preenchído do rádio aberto, opção "janela
  completa" só p/ drivers suportados, job em thread, save
  `~/.chirp/fw-backups/` + YAML sidecar assinado por sha;
  `fwtool.dump_full_window` + `RadioService.fw_dump`;
  `tests/unit/test_pysideui_fw_dump.py`.
- [x] **W1 — escrita/restore de firmware (BF-777S primeiro)**:
  round-trip no-op **validado em hardware** (2026-10-17, sha
  `4d8db228`, 124 blocos ACK + re-leitura byte-idêntica; script
  `tools/roundtrip_noop.py`). Backend `fwtool.restore_h777_image`
  (janela 992 B, 3 sessões: dump prévio + escrita com ACK por bloco +
  re-leitura diff; ABORT em NACK/timeout; backups .pre/.post
  automáticos sha-assinados). Entregues: CLI `mychirp-fw --restore`
  (dupla confirmação no terminal; ideal sem TTY cancela) + GUI
  `Radio > Firmware restore...` (Ctrl+Shift+W; dupla confirmação
  modal: QMessageBox.question + digitar "GRAVAR"; diff pré/pós no
  fim). Alcance do cabo = imagem de EEPROM apenas (código do MCU
  exige biopsia §8.7).
- [x] **W2 — restore real (não no-op) em hardware** (18:49): backup
  da própria unidade `4d8db228…` restaurado na MESMA unidade com
  dupla confirmação pela frente ("Tente restaurar agora" +
  "Pode gravar") — `fwtool.restore_h777_image` end-to-end: sha_old
  == sha_new == `4d8db228…`, diffs == [] (124 blocos W-frame,
  contíguo, gaps de `_ranges` também gravados — padrão W1).
  Sidecars `.pre_…`/`.post_…` salvos em `~/.chirp/fw-backups/`.
  **W2-B validado em sequência na 2ª unidade da família**: RC
  3002 G2 (`1fa31046…`, 18:54, mesmo protocolo, diffs=[]).
  **Pendência sequencial**: mais unidades da família h777 conforme
  chegarem (dupla confirmação por unidade). Família BOM-5701/UV-5R:
  escrita validada em hardware no BOM-5701 (W4 abaixo, 19:54).
- [x] **GUI: `Radio > Firmware restore...`** (escrita): diálogo com
  vend/model/port preenchidos, picker de .bin (default em
  `~/.chirp/fw-backups/`) validando tamanho 992 B, apenas família
  h777 habilitada (recusa de driver fora com explicação), dupla
  confirmação (modal + palavra "GRAVAR"), verify pós-escrita com
  diff e paths .pre/.post exibidos. `RadioService.fw_restore` +
  `fwtool.restore_h777_image` em thread; testes
  `tests/unit/test_pysideui_fw_restore.py` e
  `tests/unit/test_fwtool_restore.py`.
- [x] **W3 — escrita/restore família UV-5R-aux-first (BOM-5701):
  backend + CLI/GUI** (`3bf4596a`, `b342bcd4`):
  `fwtool.restore_bom5701_image` — 3 sessões: pre-dump read-only
  (sha_old + `.pre`) → gravação pela maquinaria do PRÓPRIO driver
  (`sync_out`: ident + frame `X` 16 B com `_send_block_retry`,
  ordem AUX→MAIN = 402 blocos ACK: 20 aux + 382 main) → re-download
  de verify (sha_new + `.post` + diff). Gaps de proteção do UV-5R
  (image `0x0CF8-0x0D08`/`0x0DF8-0x0E08`) NÃO graváveis: excluídos
  do diff e reportados como `preserve_diffs`; aborto por NACK
  persistente reporta o wire addr do bloco recusado. Dispatcher
  `fwtool.restore_image` por família (h777 × aux-first × recusa
  clara); CLI `--restore` e diálogo GUI com gate/tamanho por
  família e nota de faixas preservadas. Docs:
  `docs/dump-format-uv5r.md` §6. Testes fake-serial (6, com modelo
  de memória compartilhado entre as sessões) + 2 GUI + 2 CLI.
- [x] **W4 — W3 validado em hardware**: round-trip no-op na
  unidade BOM-5701 (`bccd9a99…` restaurado nela mesma, 402 blocos
  escrevendo AUX + MAIN com ACK/retry, re-leitura idêntica em
  `20261017-195404`, sha_old == sha_new == `bccd9a99`, diffs=[])
  com dupla confirmação realizada. Backups pre/post salvos.
- [ ] **P1 — Família 115200**: dump real do **UV-17M** (imagem
  33,6 KB = codeplug 0x8380 da família UV-17Pro confirmado em
  `radio_tool`; XOR "CO 7" = chave 1 da tabela de 20). Dados de RE em
  `rethink/uv17m-descobertas.md`.
- [ ] **P2 — D1-boot (família UV-17Pro/5RM/UV21)**: validar a hipótese
  do boot mode silencioso (descobertas §22) — enviar 0xA5 e SEGUIR a
  sequência; primeiro teste com CMD_READFLASH (leitura). Base:
  `mychirp/boot_image.py` (B1). Testar também o sniffing do
  `Import Picture tools.exe` via wine+socat antes, se possível.
- [ ] **P3 — D2 com dumps de firmware de nível diferente**: diff entre
  versões de firmware quando houver dumps de unidades com builds
  distintos (hoje o D2 já provado entre codeplugs de unidades).
- [ ] **P4 — Demais unidades que chegarem**: cada rádio novo = 1 dump
  (2x byte-idêntico) + nota aqui; catálogo genérico pronto (59 drivers
  Baofeng + todos os demais vendors).

## 8. Ambiente (Linux/Debian 13)

Python 3.13 · PySide6 6.12 · pytest 8.4.2
· pytest-qt (GUI offscreen) · venv em `./venv`. App em
`venv/bin/mychirp` (PySide6).

## 9. Reversão

O histórico git preserva o wxui completo (último commit com interface
antiga: `67e69033`). Reverter restauraria a interface legada se urgente.
