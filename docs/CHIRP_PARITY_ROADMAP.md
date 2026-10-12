# CHIRP Parity Roadmap — MyChirp (PySide6)

> Histórico de migração concluído. O app MyChirp é 100% PySide6 desde
> `feature/pyside6-migration`; a base original wxui/+Flet já foi removida.
> Backend preservado integralmente (diretriz obrigatória): drivers,
> protocolos, `chirp_common`, `import_logic`, `bandplan_*`, `sources/`,
> `config.py`, `memory_ops.py` e todos os testes passam.

## ✅ Roadmap PySide6 (2026-10-12) — todas as pendências entregues

| # | Recurso | Status | Notas |
|---|---|---|---|
| 1 | Live radios (Kenwood/Yaesu) | ✅ funcional | reuso do backend existente via clone dialog (`download_radio`/`upload_radio`); validado com FakeLiveRadio |
| 2 | Consulta a repetidoras | ✅ | diálogo `query_source.py`, thread pool via `radio_service.run_memory_op`, import via `import_logic.import_mem` |
| 3 | Rádios de rede | ✅ | menu Radio > Network source; persiste último host:port |
| 4 | Undo/Redo (fila 50) | ✅ | `mychirp.memory_ops.UndoStack` + setas na |
|   | Importar em rádio aberto | ✅ | Arquivo > Importar merge no rádio atual |
|   | Colunas extras (mem.extra) | ✅ | dialog Editar renderiza RadioSettings extras |
|   | Sort por coluna | ✅ | clique no cabeçalho, asc/desccom seta |
|   | Find next | ✅ | botão "Find next" +F3/ação no Edit menu |
|   | Export Kenwood/ITM/HMK | ✅ | File menu + chamada de driver por format |
|   | Plano de bandas | ✅ | View > Band plan (persiste em config) |
|   | Impressão | ✅ | File > Print via QTextDocument |
|   | Seletor de idioma | ✅ | config state.lang (pt_BR default) |
|   | Modo desenvolvedor | ✅ | View > Developer mode + Developer tools |
|   | Bug report tool | ✅ | Help > Report a bug (copia diagnóstico) |

## 🔍 Validação em hardware real (BOM-5701, /dev/ttyUSB0)

Ciclo completo: download → backup → upload → verify = byte-idêntico
(6472 bytes, sha256 `f214d0b0e4a80d86…`). Repetido duas vezes seguidas
com sucesso, inclusive após re-certamedo. Backup automático antes de
cada sessão salva em `~/.chirp/backups/`.

## 🧪 Testes

- `tests/unit/test_memory_ops.py` — operações de memória (20 testes)
- `tests/unit/test_pysideui_smoke.py` — janela Qt + abertura de imagem
- `tests/unit/test_pysideui_devtools.py` — dialogs de dev/bugreport
- Total suite: **754 passed, 13 skipped**
