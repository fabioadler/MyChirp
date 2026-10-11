# PLANO DE TRABALHO — MyChirp (BOM-5701 + Interface Flet)

> Regra de segurança: **nenhuma gravação (upload) no rádio físico** sem
> validação e autorização explícita. `sync_out` do BOM-5701 segue bloqueado
> até nova ordem.

---

## 1. Objetivo

1. Suporte de **leitura** ao rádio **BOMVINK BOM-5701** (driver baseado no
   protocolo UV-5R) — **concluído e validado em hardware**.
2. Interface gráfica moderna com **Flet**, 100% responsiva, temas
   claro/escuro consistentes em todos os componentes — **concluído**.
3. Estrutura de projeto limpa: pacote único `mychirp`, interface única
   (`mychirp/fletui`), assets únicos em `mychirp/share`.

## 2. Arquitetura atual (2026-10-11)

```
mychirp/
├── fletui/            # Interface única (Flet 1.0)
│   ├── main.py        # entry point (mychirp=fletui:run)
│   ├── theme/         # tokens semânticos claro/escuro (colors/spacing)
│   ├── components/    # AppShell, MyTabs, StatusBar (todos temáticos)
│   ├── screens/       # Welcome, Memories (DataTable), Settings (NavRail)
│   ├── dialogs/       # Clone (download/upload), About (créditos+logos)
│   └── services/      # AppState (WeakKeyDictionary), RadioService (threads)
├── config.py          # configuração persistente (ex-wxui/config.py)
├── drivers/           # todos os drivers do CHIRP original
├── share/             # assets únicos: mychirp-logo.png (fundo preto),
│                      # mychirp_logo_transparente.png, logo_empresa.png,
│                      # model_alias_map.yaml
└── (núcleo: chirp_common, bitwise, directory, settings, platform...)

Comandos: mychirp (GUI Flet) · mychirpc (CLI) · experttune
```

**Removidos:** `mychirp/wxui/` (interface antiga, serviu de referência),
scripts raiz `chirpc`/`chirpwx.py`, dependência wxPython, testes da
interface antiga, imagens duplicadas em share.

## 3. Interface Flet — componentes e temas

- **Temas claro/escuro/sistema** persistidos em `chirp.config`
  (seção `state`, chave `theme_mode`) — mesmos tokens do design
  (docs/ui-redesign.md) mapeados em `theme/colors.py` (Light/Dark).
- **AppShell**: AppBar (logo + MenuBar + toggle de tema) → abas
  (MyTabs = TabBar/TabBarView) → StatusBar temática de 3 campos.
- **WelcomeScreen**: logo ≤400px centralizada, segue o tema (sem
  `_theme_exempt`, sem fundo hardcoded).
- **MemoriesScreen**: DataTable paginada (25/ página), filtro, ocultar
  vazios, edição por canal com controles tipados; colunas derivadas de
  `radio.get_features()`.
- **SettingsScreen**: NavigationRail responsivo (Dropdown < 900px),
  formulários por grupo (Switch/Dropdown/TextField por tipo de valor),
  aplicar em lote via `radio.set_settings()`.
- **CloneDialog**: fabricante → modelo → porta; `status_fn` alimenta
  ProgressBar; download abre aba nova, upload escreve no rádio aberto.
- **AboutDialog**: logo MyChirp, créditos CHIRP original (GPLv3),
  "Desenvolvido por Fábio Adler de Luna Gomes", logo da empresa.

## 4. Políticas de segurança vigentes

1. **Gravação de firmware NÃO existe** (impossível pelo protocolo de
   clone; risco de brick permanente).
2. **Dupla confirmação obrigatória para upload** (ação destrutiva).
3. **BOM-5701**: upload permanece bloqueado até autorização explícita.
4. **Backups automáticos** em `~/.chirp/backups/` antes de gravar.

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

## 7. Ritual por alteração

1. Alteração mínima, testes (`venv/bin/python -m pytest tests/unit -q`).
2. App abre sem erros (`: > ~/.chirp/debug.log; venv/bin/mychirp`,
   verificar log).
3. Commit imediato por unidade lógica; `/graphify update` ao final de
   lotes grandes.

## 8. Ambiente (Linux/Debian 13)

Python 3.13 · Flet 1.0.4 (GTK3/Flutter) · zenity (diálogos de arquivo) ·
pytest 8.4.2 · venv em `./venv`. App em `venv/bin/mychirp`.

## 9. Reversão

O histórico git preserva o wxui completo (último commit com interface
antiga: `67e69033`). Reverter restauraria a interface legada se urgente.
