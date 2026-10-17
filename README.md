# MyChirp

Fork moderno do __[CHIRP](https://www.chirpmyradio.com)__ — programador de
rádios amadores com interface **PySide6 (Qt)** 100% responsiva e temas
claro/escuro consistentes em todos os componentes.

Créditos do projeto original: CHIRP Project (Dan Smith e contribuidores),
GPLv3. Esta versão: **Feita/modificada por Fábio Adler de Luna Gomes**.

> **Plataformas suportadas**: atualmente **apenas Linux** (testado em
> Debian 13). Não há suporte oficial para Windows/macOS nesta versão.

## Esta versão

Mantém **todos os modelos do CHIRP original** e substitui a interface wxUI
por uma interface nova (`mychirp/pysideui`):

- **Rádios adicionados nativamente**: Baofeng **UV-16** (legado), Baofeng
  **UV-16 Plus** (2024/25, driver criado por engenharia reversa — ver
  `mychirp/drivers/baofeng_uv16.py`) e Baofeng **UV-17M** (tela colorida +
  GPS, 999 canais, round-trip validado em hardware — ver
  `mychirp/drivers/baofeng_uv17Pro.py`)

- **Temas claro/escuro/sistema** aplicados de verdade em todos os
  componentes — abas, tabelas, navegação lateral, formulários, diálogos,
  barra de status — inclusive após download do rádio e troca de abas
- **Bem-vindo** — logo centralizada (≤400px) que segue o tema ativo
- **Memórias** — grade paginada com filtro, ocultar vazios e edição de
  canal com controles tipados (frequência, tons CTCSS, DTCS, duplex...)
- **Configurações** — navegação lateral responsiva (NavRail → Dropdown em
  telas estreitas) com formulários por grupo e aplicação em lote
- **Clonagem** — download/upload com seleção fabricante → modelo → porta
  e barra de progresso
- **Sobre** — créditos ao CHIRP original, desenvolvedor da versão e logo
  da empresa

## Instalação (Linux)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/mychirp
```

> O diálogo de arquivos usa o `zenity` do sistema
> (`sudo apt install zenity` no Debian/Ubuntu).

## Interface gráfica

- **Ctrl+O** — abrir imagem/CSV · **Arquivo** — recentes, salvar (Ctrl+S),
  salvar como, fechar aba (Ctrl+W)
- **Rádio → Baixar do rádio** (Ctrl+D) / **Carregar no rádio** (Ctrl+U)
- **Ver → Tema** claro/escuro · **F5** — recarregar dados
- **Ajuda → Sobre** — créditos e versão

## Uso pelo terminal (mychirpc)

```bash
venv/bin/mychirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --download-mmap --mmap=backup.img      # baixar
venv/bin/mychirpc --mmap=backup.img --list-mem                # ver canais
venv/bin/mychirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --upload-mmap --mmap=backup.img       # gravar (protocolo validado)
```

## Dump de memória (mychirp-fw)

Ferramenta read-only: baixa a **imagem completa de memória** de
qualquer rádio do catálogo (a partir de um driver de clone — os 59
Baofeng incluídos), sem nunca gravar nada no rádio:

```bash
venv/bin/mychirp-fw --list-radios --vendor=baofeng     # catálogo
venv/bin/mychirp-fw --serial=/dev/ttyUSB0 \
    --radio=BAOFENG_BF-777S                            # dump .bin + .yaml
venv/bin/mychirp-fw --serial=COM3 --radio=BAOFENG_UV-5R --backup
venv/bin/mychirp-fw --diff antigo.bin novo.bin         # diff byte-level
```

- `--backup` salva também em `~/.chirp/fw-backups/` (nome assinado pelo
  sha256), junto do YAML de metadados (modelo, porta, baud, data, hash).
- O `--diff` compara dois dumps byte a byte (resumo por faixa).

## Notas do BOM-5701

- Aguarde **~20 s entre sessões** de clonagem (o rádio reinicia após
  cada sessão, inclusive falhas).
- O driver cuida automaticamente das particularidades do protocolo
  (ordem aux-antes-do-main e retry pós-NACK).
- Backups automáticos em `~/.chirp/backups/` — mantenha sempre um antes
  de gravar.

Documentação completa e histórico do projeto: [PLAN.md](PLAN.md)
