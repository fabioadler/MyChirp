# MyChirp

Fork moderno do __[CHIRP](https://www.chirpmyradio.com)__ — programador de
rádios amadores com interface **PySide6 (Qt)** 100% responsiva e temas
claro/escuro consistentes em todos os componentes.

Créditos do projeto original: CHIRP Project (Dan Smith e contribuidores),
GPLv3. Esta versão: **Feita/modificada por Fábio Adler de Luna Gomes**.

> **Plataformas**: **Linux** é a plataforma de referência (Debian 13,
> validada em hardware). O MyChirp roda também em **Windows 10/11**
> (interface Qt + pyserial multiplataforma) — instruções de instalação
> e uso abaixo.

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

## Instalação (Windows 10/11)

### 1. Python

Baixe o **Python 3.10 ou superior** em <https://www.python.org/downloads/>
e instale **marcando a opção "Add python.exe to PATH"** na primeira tela
do instalador. Confirme no PowerShell:

```powershell
py -3 --version
```

### 2. Preparar a pasta do projeto

Abra o PowerShell na pasta do MyChirp (ex.: botão direito → "Abrir no
Terminal") e crie o ambiente virtual:

```powershell
py -3 -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.txt
```

> Se o PowerShell reclamar de execução de scripts ao usar
> `Activate.ps1`, rode antes:
> `Set-ExecutionPolicy -Scope Process RemoteSigned`
> (vale só para a janela atual).

### 3. Executar

```powershell
venv\Scripts\mychirp.exe
```

Os comandos de terminal seguem o mesmo padrão: `venv\Scripts\mychirpc.exe`
e `venv\Scripts\mychirp-fw.exe` (veja os exemplos abaixo trocando
`venv/bin/...` por `venv\Scripts\...exe`).

### 4. Driver do cabo de programação

A maioria dos cabos Baofeng/similares usa o chip **CH340/CH341**:

- No **Windows 10/11** o driver normalmente é instalado sozinho pelo
  Windows Update na primeira vez que o cabo é conectado.
- Se não aparecer nenhuma porta, abra o **Gerenciador de Dispositivos**
  (Win+X → Gerenciador de Dispositivos) → seção **"Portas (COM e LPT)"**:
  um item "USB-SERIAL CH340 (COM**x**)" indica o número da porta
  (ex.: `COM3`). Se houver um alerta amarelo, clique com o botão
  direito → **Atualizar driver** → "Procurar automaticamente".

Use esse `COMx` no lugar de `/dev/ttyUSB0` em todos os comandos e na
caixa **Porta** da interface gráfica.

> Se o rádio falhar ao iniciar a clonagem logo após conectar, desconecte
> e reconecte o cabo e aguarde 2–3 s (a porta CH340 precisa se
> reestabilizar — o mesmo vale no Linux).

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

No **Windows** (PowerShell, porta `COM3` como exemplo):

```powershell
venv\Scripts\mychirpc.exe --serial=COM3 --radio=BOMVINK_BOM-5701 `
    --download-mmap --mmap=backup.img
venv\Scripts\mychirpc.exe --mmap=backup.img --list-mem
venv\Scripts\mychirpc.exe --serial=COM3 --radio=BOMVINK_BOM-5701 `
    --upload-mmap --mmap=backup.img
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
venv/bin/mychirp-fw --map dump.bin                     # análise semântica
```

- `--backup` salva também em `~/.chirp/fw-backups/` (nome assinado pelo
  sha256), junto do YAML de metadados (modelo, porta, baud, data, hash).
  No Windows: `C:\Users\<seu_usuário>\.chirp\fw-backups\`.
- O `--diff` compara dois dumps byte a byte (resumo por faixa).
- O `--map` dá o resumo semântico de um dump (driver resolvido pelo
  YAML sidecar ou `--radio`): canais usados, settings por grupo e
  regiões com dados reais — destacando as que ficam FORA das structs
  do driver (candidatas a engenharia reversa).
- Exemplos no Windows (PowerShell):

```powershell
venv\Scripts\mychirp-fw.exe --list-radios --vendor=baofeng
venv\Scripts\mychirp-fw.exe --serial=COM3 --radio=BAOFENG_BF-777S
venv\Scripts\mychirp-fw.exe --diff antigo.bin novo.bin
venv\Scripts\mychirp-fw.exe --map dump.bin
```

- Formatos documentados: [família H777](docs/dump-format-h777.md) e
  [família UV-5R](docs/dump-format-uv5r.md).

## Notas do BOM-5701

- Aguarde **~20 s entre sessões** de clonagem (o rádio reinicia após
  cada sessão, inclusive falhas).
- O driver cuida automaticamente das particularidades do protocolo
  (ordem aux-antes-do-main e retry pós-NACK).
- Backups automáticos em `~/.chirp/backups/` — mantenha sempre um antes
  de gravar.

Documentação completa e histórico do projeto: [PLAN.md](PLAN.md)
