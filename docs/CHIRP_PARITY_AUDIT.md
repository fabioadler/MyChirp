# Auditoria de Paridade — MyChirp vs CHIRP-next

> Referência: repositório oficial kk7ds/chirp (build **next**, wxui).
> Base de comparação: o MyChirp é um **fork direto do CHIRP-next** — a camada
> de dados (drivers, protocolos, `chirp_common`, `bitwise`, `directory`,
> `settings`, `import_logic`, fontes de rede) é a mesma árvore do upstream.
> A interface atual é `mychirp/pysideui` (PySide6), que sucedeu wxui e a
> Flet UI intermediária. Paths `fletui/` na tabela abaixo são históricos
> (da auditoria de 2026-10-11); os módulos correspondentes hoje estão em
> `pysideui/` (ex.: `fletui/dialogs/clone_dialog.py` →
> `pysideui/dialogs/clone.py`).
>
> Legenda de situação: ✔ completo · ◐ parcial · ✖ ausente · ⚠ com defeito ·
> (?) não verificado.
> Auditoria realizada em 2026-10-11, commit de referência `7e0c0ce5`.

## Sumário executivo

- **Drivers/rádios: paridade total** (561 classes de rádio, 65 fabricantes,
  idênticos ao upstream — evidência: `directory.import_drivers()` e a suíte
  de testes de drivers herdada `tests/test_drivers.py`).
- O **gap real está na camada de interface**: recursos que a wxui expunha e
  que a fletui ainda não expõe. A camada de dados de todos eles **já existe**
  no pacote — nada precisa ser reescrito no protocolo/drivers.

## Tabela de recursos

| # | Recurso CHIRP-next | Situação | Módulos envolvidos | Evidência | Alteração necessária | Prioridade |
|---|---|---|---|---|---|---|
| 1 | Drivers de rádios (561 modelos) | ✔ completo | `mychirp/drivers/` (225 arqs) | `directory.import_drivers()` → 561 classes; `tests/test_drivers.py` executa os 561 com imagens simuladas | Nenhuma | — |
| 2 | Leitura/gravação clone (sync_in/sync_out) | ✔ completo (CloneModeRadio) | `fletui/dialogs/clone_dialog.py`, `fletui/services/radio_service.py` | `download_radio/upload_radio` com `status_fn` → ProgressBar; validado com imagem UV-5R | Nenhuma | — |
| 3 | Rádios "live" (Kenwood etc., edição sem clone) | ✖ ausente na UI | data layer ✔ (`chirp_common.LiveRadio`, 55 drivers live); wxui usava `radiothread` (removido) | grep wxui histórico: `ChirpLiveEditorSet` | Editor assíncrono na fletui (grande) | Alta (roadmap) |
| 4 | Detecção de porta serial passiva (cabo plugado) | ◐ parcial | wxui: `portwatch.py` (removido); fletui: lista simples `serial.tools.list_ports` no CloneDialog | CloneDialog só lista portas | Monitor de portas + aviso na statusbar | Média |
| 5 | Detecção do rádio pela serial (`detect_from_serial`) | ◐ parcial (data layer ✔, UI não usa) | `chirp_common.CloneModeRadio.detect_from_serial` | tests/test_detect.py cobre o data layer | Botão "Detectar" no CloneDialog | Média |
| 6 | Edição de memória por canal (freq, tons CTCSS/DCS, duplex, offset, potência, modo, tstep, skip, comentário) | ✔ completo | `fletui/screens/memories_screen.py` | `_make_field()` deriva opções de `get_features()`; smoke test UV-5R: 128 canais carregados | Nenhuma | — |
| 7 | Colunas derivadas de features (ocultar inválidas) | ✔ completo | `memories_screen._visible_columns()` | UV-5R renderiza apenas colunas suportadas | Nenhuma | — |
| 8 | Campos "extra" por rádio (mem.extra) | ◐ parcial | data layer ✔ (`settings.RadioSettingGroup` em mem.extra); UI desabilita imutáveis mas não renderiza extras no diálogo | `_build_fields` cobre colunas do grid apenas | Renderizar mem.extra no dialog de edição | Média |
| 9 | Inserir linha acima | ✖ ausente | wxui: `_insert_row_above`; data layer suporta via shift | grep histórico wxui | Implementar (shift-down) | **Alta (agora)** |
| 10 | Excluir memória (simples / bloco / bloco+shift) | ✖ ausente | wxui: `_delete_memories_at(rows, shift_up)`; data layer ✔ | algoritmo completo no histórico wxui (linhas 2118–2175) | Implementar (single + shift) | **Alta (agora)** |
| 11 | Mover canal para cima/baixo | ✖ ausente | wxui: `_move_up/_move_dn`; data layer = swap de `set_memory` | histórico wxui | Implementar | **Alta (agora)** |
| 12 | Copiar/colar memória (inclusive entre modelos) | ✖ ausente na UI | data layer ✔✔ `import_logic.import_mem()` + `import_bank()` (motor de compatibilidade cross-model do CHIRP) | `mychirp/import_logic.py:245` | Implementar clipboard + paste com import_mem | **Alta (agora)** |
| 13 | Ordenar por coluna (visão) | ✖ ausente | wxui: `sort_via` na tabela | histórico wxui | Implementar sort de visão | Média |
| 14 | Ir para canal (Goto) | ✖ ausente | wxui: `_goto` | histórico | Implementar (salto de página) | **Alta (agora)** |
| 15 | Desfazer/refazer (undo/redo) | ✖ ausente | wxui: fila de undo (50 itens) | histórico | Fila de operações inversíveis | Média (roadmap) |
| 16 | Localizar/localizar próximo | ◐ parcial | fletui: filtro de busca equivalente (aplica instantâneo); wxui: find+next com realce | `search_field` no memories_screen | Find next com realce é refinamento | Baixa |
| 17 | Ocultar vazios / fixar fonte / fonte grande | ◐ parcial | "Ocultar vazios" ✔ (`hide_empty_switch`); fontes fixas ✖ | memories_screen | Fonte mono opcional | Baixa |
| 18 | Configurações por rádio (básicas/avançadas/DTMF/workmode) | ✔ completo | `fletui/screens/settings_screen.py` | UV-5R: 5 grupos carregados e aplicáveis (`radio.set_settings`) | Nenhuma | — |
| 19 | Validação por rádio (limites de banda, passos, tons válidos) | ✔ herdado do data layer | `chirp_common.RadioFeatures`, `RadioSettingValue*.set_value` | exceções `InvalidValueError`/`RadioError` voltam ao status/dialog | Nenhuma | — |
| 20 | Abrir/salvar `.img` (+ metadados) | ✔ completo | `radio_service.open_file/save_radio`; `_strip_metadata` | sessão restaurada de `Baofeng_UV-5R.img` validada em teste | Nenhuma | — |
| 21 | Abrir CSV/ITM/HMK (drivers file-backed) | ✔ completo | `directory.get_radio_by_image` aceita csv; drivers `generic_csv`, `kenwood_itm/hmk` presentes | open_file já aceita `.csv` (FilePicker extensions) | Nenhuma | — |
| 22 | Exportar memórias para CSV | ✖ ausente | data layer ✔ `generic_csv.CSVRadio`; wxui `_export_to_file` (histórico) | algoritmo no histórico (CSVRadio + erase_memory(0)) | Implementar menu Exportar | **Alta (agora)** |
| 23 | Importar de arquivo para rádio aberto (merge) | ◐ parcial (abre como aba nova; wxui tinha "importar no rádio atual" com `import_mem`) | `import_logic.import_mem` ✔ | histórico wxui `memedit_import_all` | Merge pós-implementação do paste (mesma engine) | Média |
| 24 | Bancos de canais (Icom etc.) | ✖ ausente na UI | data layer ✔✔ `chirp_common.BankModel` (add/remove_memory_to_mapping, get_mappings…); `import_bank` ✔ | `Icom_IC-2820H.img`: `has_bank=True`; wxui `bankedit` no histórico | Aba "Banks" no RadioTabsView | **Média-alta (agora)** |
| 25 | Consultas de repetidoras (RepeaterBook, RadioReference, DMR-MARC, Przemienniki, mapy73, AMSAT, SatNOGS) | ✖ ausente na UI | data layer ✔ `mychirp/sources/` (9 módulos com `get_memories()`); wxui `query_sources.py` (histórico) | `sources/repeaterbook.py` funcional | Diálogo de consulta + aba de resultados | Média (roadmap) |
| 26 | Rádios de rede (NetworkSourceRadio) | ✖ ausente na UI | data layer ✔ (`chirp_common.NetworkSourceRadio`) | sources/base.py | Junto com #25 | Média |
| 27 | Escolher plano de bandas | ✖ ausente | data layer ✔ `bandplan_*` | wxui menu "Select bandplan" | Menu View | Baixa |
| 28 | Edição automática (duplex/offset auto) | ✖ ausente | wxui `auto_edits` | histórico | Opcional | Baixa |
| 29 | Trace serial / diagnóstico de comunicação | ◐ parcial | logger ✔ (debug.log com níveis); UI de trace ✖ | `mychirp/logger.py` | Painel de diagnóstico | Média (roadmap) |
| 30 | Mensagens de erro amigáveis | ✔ completo | diálogos de erro temáticos em layout/memories/settings | testes de fluxo | Nenhuma | — |
| 31 | Impressão / pré-visualização | ✖ ausente | wxui `printing.py` (histórico) | — | Roadmap | Baixa |
| 32 | Idiomas (catálogos gettext) | ◐ parcial | `fletui/i18n.py` carrega catálogo (pt_BR validado em teste); wxui tinha seletor | log: "Loaded locale catalog for pt_BR" | Seletor de idioma no menu View | Baixa |
| 33 | Tema claro/escuro | ✔ completo (evolução: central, persistido, alternável a quente sem perder foco — corrigido em `7e0c0ce5`) | `fletui/theme/`, `app_state.set_theme_mode` | teste B: 20 toggles consistentes; confirmação do usuário | Nenhuma | — |
| 34 | Arquivos recentes + restaurar sessão | ✔ completo (evolução: aba Recentes com cards, limpar histórico, auto-restore na inicialização) | `recent_screen.py`, `app_state.restore_session` | teste: restaurou 1 rádio ao iniciar | Nenhuma | — |
| 35 | Sobre/créditos | ✔ completo | `dialogs/about_dialog.py` | créditos CHIRP original + dev + empresa | Nenhuma | — |
| 36 | Modo desenvolvedor (browser raw, dump, info) | ✖ ausente | wxui `developer.py` (histórico) | — | Roadmap | Baixa |
| 37 | Testes automatizados | ✔ completo (724 unit ✔ + suíte de drivers herdada; novos testes de sessão/clear) | `tests/` | `pytest tests/unit -q` → 724 passed | Nenhuma | — |

## Conclusões da auditoria

1. **Não há gap na camada de drivers/protocolo** — o MyChirp carrega a
   mesma árvore de drivers do CHIRP-next (561 rádios) e a suíte de testes
   de drivers do upstream roda sem alterações.
2. **Todo o gap é de exposição na UI** e se concentra em:
   operações de grade (#9–#14), exportação CSV (#22), bancos (#24),
   fontes de repetidoras (#25/#26) e rádios live (#3).
3. O motor de **compatibilidade cross-model** (`import_logic.import_mem`)
   já existe e é a mesma engine que o CHIRP usa para colar entre modelos
   distintos — a UI só precisa consumi-lo.
