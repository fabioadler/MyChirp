# CHIRP Project

Fork oficial do repositório __[CHIRP](https://www.chirpmyradio.com)__ (PRs upstream: ver [pull_request_template.md](.github/pull_request_template.md)).

## Esta versão

Mantém **todos os modelos do CHIRP original** e adiciona suporte validado a:

- **BOMVINK BOM-5701** — protocolo UV-5R, leitura e gravação completas comprovadas em hardware
- **Baofeng BF-777S** e **Intelbras RC 3002 G2** — protocolo BF-888, verificados pelo proprietário

## Instalação (Linux)

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-dev.txt   # CHIRP + testes + pyusb
.venv/bin/chirp
```

> Requer `python3-wxgtk4.0` do sistema (o venv o aproveita via
> `--system-site-packages`).

## Uso pela interface gráfica

- **Rádio → Baixar / Carregar no rádio** — o cabo é detectado ao plugar;
  a gravação exige dupla confirmação e mantém aviso de sobrescrita.
- **Ver → Tema** (claro/escuro/sistema) · **Ver → Idioma**
  (pt-BR padrão, inglês, chinês, japonês).
- **Ajuda → Diagnóstico de rádio** — portas, cabos, testes de conexão
  (porta e identificação, somente leitura), rastreio serial e backups.
- Modo desenvolvedor (**Ajuda → Developer Mode**) libera:
  - **Arquivo → Exportar dump bruto de memória** — imagem de canais em
    `.bin` + hexdump com CRC32;
  - **Arquivo → Exportar memória completa visível pelo cabo** — os 8 KiB
    que o cabo enxerga, incluindo a área de calibração (0x1800–0x1EC0);
    é tudo que existe: firmware não é acessível pelo cabo;
  - **Arquivo → Ler chip com a programadora CH341A** — leitura de
    EEPROMs I2C (24Cxx) e flash SPI (25xx) com identificação JEDEC;
    somente leitura, nada é gravado no chip.

## Uso pelo terminal (chirpc)

```bash
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --download-mmap --mmap=backup.img      # baixar
.venv/bin/chirpc --mmap=backup.img --list-mem                # ver canais
.venv/bin/chirpc --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 \
    --upload-mmap --mmap=backup.img       # gravar (protocolo validado)
```

Outros modelos: `--radio=Baofeng_BF-777S` · `--radio='Intelbras_RC 3002 G2'`

## Notas do BOM-5701

- Aguarde **~20 s entre sessões** de clonagem (o rádio reinicia após
  cada sessão, inclusive falhas).
- O driver cuida automaticamente das particularidades do protocolo
  (ordem aux-antes-do-main e retry pós-NACK).
- Backups automáticos em `~/.chirp/backups/` — mantenha sempre um antes
  de gravar.
- Gravação de **firmware** não existe: o protocolo de clone não expõe a
  memória de programa.

Documentação completa (diagnóstico, evidências, testes):
[PLAN.md](PLAN.md)
