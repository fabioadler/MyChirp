# CHIRP Parity Roadmap — MyChirp (Flet UI)

> Derivado da auditoria `docs/CHIRP_PARITY_AUDIT.md` (commit `7e0c0ce5`).
> Estado: após implementação do **Batch A** (memória ops + CSV export + Banks tab).

---

## ✅ Implementado (Batch A — agora)

| # | Recurso | Situação | Testes |
|---|---|---|---|
| 1 | Exportar memórias para CSV | ✔ implementado | `test_export_reimport_roundtrip` |
| 2 | Copiar/colar memórias (mesmo rádio + cross-model) | ✔ implementado | `test_paste_same_radio`, `test_paste_cross_model` |
| 10 | Excluir memória (simples + bloco+shift / tudo+shift) | ✔ implementado | `test_delete_*` |
| 11 | Mover canal para cima/baixo | ✔ implementado | `test_move_up/down` |
| 14 | Ir para canal (Go to channel) | ✔ implementado | teste manual |
| 14 | Inserir linha acima (insert above) | ✔ implementado | `test_insert_above` |
| 22 | Exportar para CSV | ✔ implementado | `test_export_reimport_roundtrip` |
| 24 | Aba **Banks** (matriz memórias × bancos) | ✔ implementado | `TestBanksDataLayer` (data layer) + `BanksScreen` (UI) |

**Arquivos criados/modificados:**
- `mychirp/fletui/services/memory_ops.py` (novo)
- `mychirp/fletui/services/radio_service.py` (+ `run_memory_op`, `export_csv`)
- `mychirp/fletui/services/app_state.py` (+ `memory_clipboard`, `clear_recent_files`)
- `mychirp/fletui/screens/memories_screen.py` (toolbar ops + seleção de linha + handlers)
- `mychirp/fletui/screens/banks_screen.py` (novo — aba Banks)
- `mychirp/fletui/components/layout.py` (+ `BanksScreen`, botão Export CSV no menu File, `apply_theme` blindado)
- `mychirp/fletui/components/layout.py` (import `MyTabs.insert_tab`)
- `mychirp/fletui/dialogs/*` (API `page.open` → `page.show_dialog`/`pop_dialog`)
- `mychirp/fletui/services/radio_service.py` (novos métodos `run_memory_op`, `export_csv`)
- `mychirp/fletui/services/app_state.py` (`clear_recent_files`, `memory_clipboard`)
- `mychirp/fletui/screens/memories_screen.py` (toolbar, seleção, ops handlers)
- `mychirp/fletui/screens/banks_screen.py` (novo)
- `mychirp/fletui/services/memory_ops.py` (novo — operações puras)
- `tests/unit/test_fletui_memory_ops.py` (17 testes novos)
- `tests/unit/test_session_config.py` (persistência de sessão)

---

## 🚧 Roadmap — Prioridade média/baixa (próximos sprints)

| # | Recurso | Situação | Módulos | Prioridade | Esforço estimado |
|---|---|---|---|---|---|
| 1 | **Live radios** (edição assíncrona Kenwood, Yaesu, etc.) | ✖ ausente na UI | `radiothread.py` (removido c/ wxui) + `chirp_common.LiveRadio` | **Alta** | Grande (requer nova arquitetura assíncrona Flet) |
| 2 | **Consulta a fontes de repetidoras** (RepeaterBook, RadioReference, DMR-MARC, PRZ, mapy73, AMSAT, SatNOGS) | ✖ ausente na UI | `mychirp/sources/` (data layer pronto) | Média | Médio/Grande (diálogo + thread pool + cache) |
| 3 | **Rádios de rede** (`NetworkSourceRadio`) | ✖ ausente na UI | `sources/base.py` | Média | Médio (usa mesmo padrão dos live) |
| 4 | **Undo/Redo** (fila 50 itens estilo wxui) | ✖ ausente | data layer: `chirp_common` não tem; precisa infra nova | Média | Médio |
| 16 | Ordenar por coluna (sort visual) | ✖ ausente | wxui: `sort_via` | Média | Baixo (sort na view) |
| 16 | Ir para canal (Goto) | ✔ implementado (teste manual) | memedit_screen | — | — |
| 17 | Desfazer/refazer (undo/redo) | ✖ ausente | fila de operações | Média (roadmap) | Médio |
| 18 | Localizar próximo (Find Next com realce) | ◐ parcial (filtro instantâneo) | fletui filter | Baixa | Baixo |
| 19 | Exportar para formatos Kenwood/ITM/HMK | ◐ parcial (abre ok; export só CSV) | drivers `kenwood_itm/hmk` | Baixa | Baixo (mesmo driver de leitura) |
| 25 | Consultas repetidoras (UI) | ✖ ausente | `mychirp/sources/` | Média (roadmap) | Médio/Grande |
| 26 | Rádios de rede (NetworkSourceRadio) | ✖ ausente | `sources/base.py` | Média | Médio |
| 27 | Escolher plano de bandas | ✖ ausente | data layer `bandplan_*` | Baixa | Baixa |
| 28 | Edição automática (offset automático) | ✖ ausente | wxui `auto_edits` | Baixa | Baixa |
| 30 | Impressão / pré-visualização | ✖ ausente | `wxui/printing.py` | Baixa | Média (requer PDF/HTML render) |
| 32 | Seletor de idioma UI | ◐ parcial (catálogo pt_BR carregado; sem seletor) | `fletui/i18n.py` | Baixa | Baixa |
| 36 | Modo desenvolvedor (browser raw, dump, info) | ✖ ausente | wxui `developer.py` | Baixa | Média |
| 37 | Ferramenta de relato de bugs | ✖ ausente | wxui `bugreport.py` | Baixa | Baixa |
| 37 | Find Next (próxima ocorrência com realce) | ◐ parcial (filtro ok; sem "next") | `memories_screen` | Baixa | Baixa |
| 23 | Importar em rádio aberto (merge via `import_mem`) | ◐ parcial (abre como aba nova; merge no rádio atual pendente) | `import_logic` | Média | Baixo (usa mesma engine do paste) |
| 16 | Colunas "extra" (mem.extra no diálogo) | ◐ parcial (imutáveis desabilitadas; extras não mostrados) | `memories_screen` | Média | Média |

---

## Limitações conhecidas

| Item | Descrição |
|---|---|
| **Live radios** | Nenhuma UI assíncrona — requer reescrita do `radiothread` com `page.run_task` + websocket/serial thread + Flet async. Bloqueia uso de Kenwood/Yaesu live. |
| **Query sources (RepeaterBook, etc.)** | Data layer pronto; UI do diálogo + thread pool + cache de resultados é trabalho médio/grande. |
| **Undo/Redo** | Necessita infraestrutura de command pattern + fila limitada a 50 itens (igual CHIRP). |
| **Banks tab** | Implementado básico (toggles). Faltam: índice de banco por memória (BankIndexModel), edição de nomes de banco, import_bank (merge cross-model), ordenação de bancos. |
| **CSV export** | Implementado básico. Falta: exportar seleção, exportar todos os campos (mem.extra), filtro de export. |
| **Paste cross-model** | Funciona mas sem diálogo de seleção do rádio destino (sempre cola no rádio atual). |
| **Undo/Redo** | Ausente — requer infra de command + historical buffer. |
| **Live radio edit** | Ausente — precisa reimplementar `radiothread` em Flet (async + serial). |
| **Import merge (merge into open radio)** | Importa como aba nova; merge no rádio atual pendente (usa `import_mem`). |

---

## Compatibilidade e regressão

| Área | Estado |
|---|---|
| 561 drivers | ✔ todos carregados; suíte `test_drivers.py` executa 500+ simulações |
| 741 testes unitários | ✔ passam (13 skipped) |
| Compatibilidade `.img` + CSV | ✔ round-trip validado |
| Persistência tema + sessão | ✔ light↔dark + restore session |
| Diálogos flet 1.0 | `show_dialog`/`pop_dialog` migrados ✓ |
| Theme toggle fix | `page.update()` único → sem mixed-theme bug |

---

## Próximos passos sugeridos (ordem sugerida)

1. **Paste cross-model dialog** — permitir colar em rádio aberto diferente do atual.
2. **Banks tab enhancements** — renomear bancos, definir índices, import_bank.
3. **CSV export refinements** — exportar seleção, exportar todos os campos, filtro por faixa.
3. **Memory ops avançadas** — Undo/Redo básico (queue de 20), sort por coluna, Find Next.
4. **Live radio scaffold** — reativar `radiothread` via `page.run_task` + callbacks de progresso; habilitar para Kenwood/Yaesu.
5. **Query sources UI** — diálogo genérico "Consultar repetidoras" usando pool de threads + cache + aba de resultados (paginada).
5. **Auto-detect serial + detect_from_serial** — botão no CloneDialog + portwatch reativado.
6. **Diagnóstico/Serial trace UI** — painel estilo wxui `diagnostics.py`.

---

## Como contribuir / rodar localmente

```bash
python3 -m venv venv
source venv/bin/apt install python3-wxgtk4.0  # desnecessário p/ flet
venv/bin/pip install -r requirements-dev.txt
venv/bin/pip install -e .

# rodar app
venv/bin/mychirp

# testes
venv/bin/python -m pytest tests/unit -q
venv/bin/python -m pytest tests/unit/test_fletui_memory_ops.py -q
```

---

---

## 🔍 Auditoria Completa & Modernização (Novas Tarefas)

| # | Tarefa | Prioridade | Esforço estimado |
|---|--------|------------|------------------|
| 1 | Verificar todos os códigos incompletos ou com bugs | **Alta** | Grande |
| 1a | ✅ SettingsScreen: botão "Apply" não gravava (fields nunca populados), subgrupos recursivos, warnings, apply callbacks — **corrigido** (commit `0cab3ebd`) | — | — |
| 1b | ✅ MemoriesScreen: cabeçalhos de coluna vazios (header row nunca anexado) — **corrigido** (commit `6ba8762f`) | — | — |
| 1d | ✅ BOM-5701 driver separado (`mychirp/drivers/bom5701.py`), limites VHF 128-176 / UHF 384-524 clamped, settings inicializados — **validado em hardware real**: download + backup + upload + round-trip byte-idêntico (commit `dcc0d759`) | — | — |
| 1c | ✅ import_logic: `_()` usado sem importar gettext (NameError em import cross-model com freq fora de faixa) — **corrigido** (commit `5b2a73a5`) | — | — |
| 2a | ✅ Ordenar por coluna (clique no cabeçalho, asc/desc com seta) — **implementado** (commit `6ba8762f`) | — | — |
| 3a | ✅ Find Next (salta para próxima ocorrência do filtro) — **implementado** (commit `6ba8762f`) | — | — |
| 3b | ✅ Paste cross-model dialog (escolher rádio destino ao colar sem seleção) — **implementado** (commit `5b2a73a5`) | — | — |
| 4a | ✅ Undo/Redo fila de 50 (Ctrl+Z/Ctrl+Y) para delete/insert/move/paste — **implementado** (commit `830b8f5a`) | — | — |
| 7a | ✅ Warnings pytest 486 → 7 (config pytest; restantes são testes intencionais de caminhos deprecados) — **feito** (commit `8ce9d58a`) | — | — |
| 2 | Verificar paridade total de funções/recursos do CHIRP original | **Alta** | Grande |
| 3 | Inventariar funções/recursos faltantes e adicionar ao backlog | **Alta** | Médio |
| 4 | Auditar commits/histórico para identificar recursos perdidos/removidos | **Alta** | Médio |
| 5 | Implementar pendências + corrigir todos os bugs/defeitos | **Crítica** | Muito Grande |
| 6 | Modernizar layout UI + terminal (design premium, paleta da logo, ui-ux-pro-max-cli) | **Alta** | Grande |
| 7 | Varredura minuciosa: lógica, incompletos, botões sem função, warnings | **Crítica** | Grande |

---

> **Processo obrigatório:** Commit após cada etapa concluída → Atualizar este arquivo → `graphify update .` ao final.

---

**Última atualização:** 2026-10-11 (commit `ec6ea101`)