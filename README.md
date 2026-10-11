# CHIRP Project

This is the official git repository for the
__[CHIRP](https://www.chirpmyradio.com)__ project.

When submitting PRs, please see [this file](.github/pull_request_template.md)
for rules and guidelines.

## Como usar esta versão (português)

Esta é uma versão modificada do CHIRP (branch `feature/bomvink-bom5701`).
Ela mantém **todos os 558 modelos do CHIRP original** e adiciona:

- **BOMVINK BOM-5701** — protocolo UV-5R com particularidades descobertas
  e validadas em hardware real (leitura e gravação completas);
- **Baofeng BF-777S** e **Intelbras RC 3002 G2** — protocolo BF-888,
  verificados pelo proprietário (leitura e gravação).

### Interface gráfica

```bash
python3 -m venv --system-site-packages .venv        # uma vez
.venv/bin/pip install -e . --no-deps                # uma vez
.venv/bin/pip install pyserial requests yattag lark suds
.venv/bin/chirp
```

- **Rádio → Baixar do rádio** / **Carregar no rádio**: escolha
  fabricante/modelo e porta. O cabo é reconhecido automaticamente ao
  plugar. A gravação exige **dupla confirmação** (instruções + caixa
  "Eu entendo que sobrescreve") e mostra aviso permanente de
  sobrescrita.
- **Ver → Tema**: sistema / claro / escuro.
- **Ver → Idioma**: Português (Brasil) (padrão), Inglês, Chinês,
  Japonês. Requer reiniciar o CHIRP.
- **Ajuda → Diagnóstico de rádio**: portas detectadas, cabos
  conhecidos, modelo/baud, última comunicação com erro técnico e
  sugestões, testes de conexão (porta e identificação somente
  leitura), rastreio serial e backups.
- **Arquivo → Exportar dump bruto de memória** (modo desenvolvedor):
  exporta a imagem de canais em `.bin` + hexdump com CRC32
  (não é firmware).
- Ativação do modo desenvolvedor: **Ajuda → Developer Mode**.

### Terminal (chirpc)

```bash
# Baixar (leitura) do rádio
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --download-mmap --mmap=backup.img

# Listar canais de uma imagem salva
.venv/bin/chirpc --mmap=backup.img --list-mem

# Carregar (gravação) no rádio — o mesmo protocolo validado da GUI
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --upload-mmap --mmap=backup.img

# Outros modelos desta versão
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio=Baofeng_BF-777S \
    --download-mmap --mmap=backup.img
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio='Intelbras_RC 3002 G2' \
    --download-mmap --mmap=backup.img
```

### Particularidades do BOM-5701 (descobertas e validadas)

1. O rádio **encerra a sessão de clonagem** quando o bloco principal
   completa; por isso o driver lê/grava o bloco auxiliar **antes** do
   principal.
2. Após cada escrita aceita, o rádio **recusa (NACK) a escrita
   imediata seguinte** (janela de commit) e aceita no retry — o
   driver faz isso automaticamente.
3. O rádio precisa de **alguns segundos de intervalo entre sessões**
   de clonagem (inclusive após falhas). Se um clone acabou de rodar,
   aguarde antes de iniciar outro.
4. Mantenha sempre um backup: os backups automáticos ficam em
   `~/.chirp/backups/`.

A gravação de **firmware** não é suportada (o protocolo de clonagem
não expõe a memória de programa; gravá-la sem validação pode danificar
o rádio permanentemente).
