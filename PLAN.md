# PLANO DE TRABALHO — Suporte ao BOMVINK BOM-5701 + Modernização da Interface

> Branch: `feature/bomvink-bom5701` (base: `origin/master`)
> Instalação original (AppImage next-20260911): **intocada**. Toda a execução é feita a partir deste repositório em um venv.
> Regra de segurança: **nenhuma gravação (upload) no rádio físico**. `sync_out` do BOM-5701 fica bloqueado até a leitura ser validada em hardware real e houver autorização explícita.

---

## 1. Objetivo

1. Adicionar suporte de **leitura** ao rádio **BOMVINK BOM-5701** no CHIRP (driver baseado no protocolo UV-5R, com ordem de leitura adaptada à evidência coletada).
2. Modernizar a interface wxui (tema claro/escuro, janela principal, grid de canais, diálogos de clonagem, painel de diagnóstico), preservando 100% das funcionalidades existentes.

## 2. Diagnóstico da falha original (evidências reais)

Erro relatado pelo usuário com o driver "Baofeng UV-5R": `Radio refused to send second block 0x1EC0`.

Evidências coletadas (registros locais, somente leitura do rádio):

- `~/.chirp/debug.log`, `/home/f/chirp-debug.log` e **rastreio serial completo** `/home/f/chirp-trace.txt` (814 linhas, bytes TX/RX).
- Issue pública idêntica: https://chirpmyradio.com/issues/12332 (BOMVINK BOM-5701; autor relata que o rádio **reinicia** após a falha; aberta, sem correção).

Sequência observada no rastreio:

| Etapa | Comportamento | Resultado |
|---|---|---|
| Magic `50 BB FF 20 12 07 25` (e também `50 BB FF 01 25 98 4D` em outra sessão) | ACK `06` → `02` → ident `aa 30 76 04 00 05 20 dd` | OK |
| Versão: `S 0x1E80` (1º comando, sem ACK) → dados; `S 0x1EC0` → ACK + 64 bytes `0xFF` (versão em branco); `S 0x1FC0` → ACK + dados reais (byte[15]=0x00 → sem "dropped byte") | Leituras auxiliares **antes** do bloco principal funcionam | OK |
| Bloco principal: 96 blocos `0x0000–0x1800`, todos ACK + dados reais (canais decodificam como memórias UV-5R, ex. 146.520 MHz) | OK | OK |
| Aux: `S 0x1EC0 0x40` após o main | **`R # timeout` (1.002 s) — silêncio absoluto; sem ACK, sem header X** | FALHA |

**Causa raiz (hipótese forte):** o firmware do BOM-5701 encerra a sessão de clone quando o bloco principal completa (estilo UV-5R antigo pré-BFB291) e o rádio sai do modo de programação. Leituras da área auxiliar são atendidas **antes** do bloco principal.

**Correção proposta:** baixar o bloco auxiliar **antes** do principal (flag `_aux_first` na classe nova; padrão `False` preserva todos os modelos existentes) e montar a imagem na ordem padrão UV-5R (ident 8 + main 0x1800 + aux 0x140 = 0x1948 bytes).

**Não confirmado até teste real:** a ordem "aux primeiro" funcionar no rádio físico. Testes simulados provam apenas a lógica do código.

## 3. Observações técnicas

- Módulo interno `E220-400722D` = EByte E220-400T22D (LoRa UART, LLCC68, 410–493 MHz) — componente de dados sem fio, **sem relação** com o protocolo de clonagem via conector de 2 pinos.
- String de versão do rádio em branco (`0xFF`×14) → `match_model` padrão não reabre imagens salvas; a classe nova terá `match_model` próprio (tamanho 0x1948 + versão em branco).
- Cabo: CH340 (1A86:7523) em `/dev/ttyUSB0`, permissões OK.

## 4. Fases e status

- [x] **Fase 0** — Repositório: remote/fetch/branch, PLAN.md, .gitignore, graphify build inicial
- [x] **Fase 1** — Driver `chirp/drivers/uv5r.py`: helper `_download_aux()`, flag `_aux_first` (default off), classe `BOMVINKBOM5701` (VENDOR=BOMVINK, MODEL=BOM-5701, `match_model` próprio, `sync_out` bloqueado, `get_prompts` experimental)
- [x] **Fase 1b** — Testes `tests/unit/test_bomvink_bom5701.py` (serial simulado roteado pelo rastreio real) + suíte de regressão completa
- [x] **Fase 2** — Design: `uipro init` + registro de decisões (`docs/ui-redesign.md`)
- [x] **Fase 3** — `chirp/wxui/theme.py`: tema claro/escuro, detecção do sistema, estilização central, persistência
- [x] **Fase 4** — Janela principal (`chirp/wxui/main.py`): status de conexão, indicador de alterações, hierarquia (funcionalidades preservadas)
- [ ] **Fase 5** — Grid de canais (`chirp/wxui/memedit.py`): estética, destaque de pendências, validação clara (lógica intacta)
- [ ] **Fase 6** — `chirp/wxui/clone.py` (leitura × gravação inequívocos) + erros em duas camadas + `chirp/wxui/diagnostics.py`
- [ ] **Fase 7** — Testes UI (smoke headless via Xvfb se disponível), screenshots antes/depois, instruções do teste real de leitura
- [ ] **Fase 8** — Relatório final PT-BR (diffs, resultados reais, limitações, reversão)

## 5. Ritual por alteração (criteriosidade)

1. Implementar (mínima e isolada)
2. Testes da área + não-regressão (baseline capturado antes de qualquer mudança)
3. Lint nos arquivos tocados (`python ./tools/cpep8.py <arquivos>`)
4. Atualizar este PLAN.md
5. `graphify . --update` (incremental)
6. `git add <arquivos específicos> && git commit` (sem push)

## 6. Log de progresso

| Data | Fase | Commit | Resumo |
|---|---|---|---|
| 2026-10-10 | 0 | 5dcaf759 | Repositório obtido do upstream (kk7ds/chirp master 33d2528c), branch `feature/bomvink-bom5701`, PLAN.md, .gitignore (graphify-out/), venv (Python 3.13 + wx 4.2.3 do sistema), baseline: tests/unit 720 passed/13 skipped; driver UV5R 140 passed/28 skipped/4 xfailed/4 xpassed; graphify build inicial (10810 nós, 600 comunidades) |
| 2026-10-10 | 1 | cf950d80 | `uv5r.py`: helper `_download_aux()`, caminho `_aux_first` no `_do_download` (aux lido ANTES do main e anexado depois — imagem idêntica 0x1948), classe `BOMVINKBOM5701` com `match_model` (0x1948 + versão em branco 0xFF) e `sync_out` bloqueado; regressão: unit 720 passed, driver UV5R 140 passed (idêntico ao baseline) |
| 2026-10-10 | 1b | 07f16196 | `tests/unit/test_bomvink_bom5701.py`: 9 testes com FakeBOM5701Serial fiel ao rastreio (magics UV-5R, ident `aa 30 76 04...`, sem ACK no 1º comando S, ACK nos demais, silêncio após o bloco main). Cobertura: ordem aux→main e imagem 0x1948, variante dropped-byte, decodificação de memórias (146.520/462.125 MHz do rastreio), UV-5R genérico ainda falha em 0x1EC0, upload bloqueado sem novos comandos, silêncio no meio do main → erro, sem contato → erro, match_model (aceita versão em branco, rejeita BFB297/tamanhos errados), detecção via directory. Suíte: 729 passed/13 skipped |
| 2026-10-10 | 2 | 34d63ca5 | `uipro init -a opencode` instalou a skill UI/UX Pro Max 2.15.0 em `.opencode/skills/` (não rastreada pelo git, já coberta pelo .gitignore upstream). Decisões de design registradas em `docs/ui-redesign.md`: tokens em 3 camadas adaptados ao wxPython, paleta semântica clara/escura com contraste AA, escala 4px, verde=Ler/laranja=Gravar, erros em duas camadas, widgets nativos preservados |
| 2026-10-10 | 3 | 3da757e6 | `chirp/wxui/theme.py`: infraestrutura de tema (paletas LIGHT/DARK por papéis semânticos, detecção do sistema via wx.SystemSettings, modo persistido no config 'state', register/apply que estiliza janelas recursivamente sem pintar widgets nativos, escala de espaçamento 4px) + `tests/unit/test_theme.py` (6 testes: papéis consistentes, resolução nos dois modos, modo system com mock, papéis/valores inválidos, acentos Ler≠Gravar) |
| 2026-10-10 | 4 | 7ce399fb | `main.py`: tema registrado na janela principal (register/apply), submenu Ver→Tema (Sistema/Claro/Escuro, itens radio persistidos via theme.set_mode), barra de status com 3 campos (mensagens · rádio conectado · "Alterações não salvas"), tema aplicado às novas abas em add_editorset. Smoke de inicialização da versão dev OK (wx 4.2.3/Python 3.13; sem exceções; observação: .mo de tradução não compilado na árvore dev → UI dev em inglês) |
| 2026-10-10 | 5 | 6603edf6 | `memedit.py`: linhas alternadas com `BG_GRID_ALT` do tema, células imutáveis com novo papel `BG_IMMUTABLE` (substitui a detecção manual de darkmode do sistema), `set_row_pending` pinta a linha inteira com `BG_PENDING` enquanto a escrita está em andamento, restripe completo ao trocar o tema (`theme.on_mode_change`). Cor base do grid passa a vir do tema (`BG_PANEL`). Smoke com rádio CSV real OK, sem exceções |
| 2026-10-10 | 6 | (pendente) | `clone.py`: banner de direção ("Read from radio (download)" verde / "Write to radio (upload)" laranja, negrito) + `LAST_CLONE_RESULT` registrado em `complete()`/`fail()`. `common.py`: `error_hints()` (mapeia padrões conhecidos → mensagem simplificada + sugestões; padrões desconhecidos → sem camada simplificada, nada inventado) e `ChirpErrorDialog` com detalhes técnicos ocultáveis + botão More Info preservado. Novo `diagnostics.py`: painel Help→Radio diagnostics (portas detectadas com VID/PID, modelo selecionado + baud, resultado da última comunicação com erro técnico original, sugestões, acesso ao debug log). `main.py`: item de menu. Testes: `test_errorhints.py` (5) |

## 7. Ambiente de desenvolvimento (Linux/Debian 13)

```
python3 -m venv --system-site-packages .venv   # wx 4.2.3 vem do pacote apt python3-wxgtk4.0
.venv/bin/pip install -e . --no-deps           # se --no-deps: instalar pyserial requests yattag lark suds* manualmente
.venv/bin/pip install -r test-requirements.txt
.venv/bin/chirp                                 # versão de desenvolvimento
.venv/bin/pytest tests/unit -v                  # testes unitários
```

## 8. Reversão

- Por fase: `git revert <commit>` (commits atômicos por alteração)
- Total: `git reset --hard origin/master && git clean -fd` (remove também graphify-out/, .venv/ e PLAN.md não commitado)

## 9. Teste real com o rádio (após Fases 1–1b)

1. Rádio **desligado** → conectar o cabo de 2 pinos → ligar o rádio (volume 100%).
2. Executar a versão de desenvolvimento e escolher **Radio → Download From Radio**.
3. Modelo: **BOMVINK BOM-5701** · Porta: `/dev/ttyUSB0`.
4. Ao concluir, **salvar imediatamente** um arquivo `.img` de backup.
5. Conferir coerência: número de canais e frequências exibidas no rádio vs. tabela do CHIRP.
6. **NUNCA** usar Upload To Radio nesta fase. Se falhar: coletar `~/.chirp/debug.log` + rastreio serial e registrar aqui.
