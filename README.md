# MyChirp

Fork moderno do __[CHIRP](https://www.chirpmyradio.com)__ — programador de
rádios amadores com interface **Flet** 100% responsiva e temas claro/escuro
consistentes em todos os componentes.

Créditos do projeto original: CHIRP Project (Dan Smith e contribuidores),
GPLv3. Esta versão: **Feita/modificada por Fábio Adler de Luna Gomes**.

## Esta versão

Mantém **todos os modelos do CHIRP original** e substitui a interface wxUI
por uma interface nova (`mychirp/fletui`):

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

## Notas do BOM-5701

- Aguarde **~20 s entre sessões** de clonagem (o rádio reinicia após
  cada sessão, inclusive falhas).
- O driver cuida automaticamente das particularidades do protocolo
  (ordem aux-antes-do-main e retry pós-NACK).
- Backups automáticos em `~/.chirp/backups/` — mantenha sempre um antes
  de gravar.

Documentação completa e histórico do projeto: [PLAN.md](PLAN.md)
