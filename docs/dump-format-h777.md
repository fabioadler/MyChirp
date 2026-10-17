# Formato de dump — família H777 (BF-777S / RC 3002 G2)

> Fonte de verdade (schema): `mychirp/drivers/h777.py` (`MEM_FORMAT`).
> Dados validados em hardware real: 2 unidades, dumps byte-idênticos por
> unidade (_sessão 2026-10-16_, sha256 `4d8db228…` BF-777S e
> `1fa31046…` RC 3002 G2, 992 B, 9600 8N1, ident `P3107`).
> Ferramenta: `mychirp-fw --map <dump.bin>` reproduz o resumo abaixo.

## 1. Mapa de regiões (992 B = 0x03E0)

| Offset | Tamanho | Conteúdo | Estado real nos dumps |
|---|---|---|---|
| `0x0000-0x0010` | 16 B | **ident/Área 0** — nunca lida pelo driver | `FF` (BF) / `00` (RC) |
| `0x0010-0x0110` | 256 B | **memory[16]** — 16 canais × 16 B | programados de fábrica |
| `0x0110-0x02B0` | 416 B | **sem mapeamento no driver** (RE) | BF: `FF` / RC: `00` + curvas de calibração |
| `0x02B0-0x02C0` | 16 B | **settings** — 10 campos + padding | valores de fábrica, idênticos entre marcas |
| `0x02C0-0x0380` | 192 B | **sem mapeamento no driver** (RE) | padrões de `0x55` a cada 17 B |
| `0x0380-0x03E0` | 96 B | área de upload (inclui **settings2** `0x03C0`) | `settings2` em `0x03C0-0x03C8` |

Nota: o rádio preenche áreas não usadas com `00` (RC 3002 G2) ou `FF`
(BF-777S) conforme a marca — "vazio" não é único; o driver considera
canal vazio apenas `rxfreq == 0`.

Regiões RE observadas no `--map` (BF-777S):

```
Regiões mapeadas:      0x0010-0x0110, 0x02B0-0x02C0, 0x03C0-0x03C8, 0x03D0-0x03D8
Regiões NÃO-MAPEADAS:  0x0200-0x0268, 0x0270-0x0290, 0x0300-0x0338
```

## 2. Structs "limpas" (equivalente C das definições bitwise)

### 2.1 memory[16] — `0x0010`, 16 B por registro

```c
struct channel {          // @0x0010 + 16*i
    uint8_t rxfreq[4];    // lbcd (BCD LE): b0,b1,b2,b3 -> val = b3|b2|b1|b0 (dígitos) ×10 Hz
    uint8_t txfreq[4];    // idem; == rxfreq => simplex
    uint8_t rxtone[2];    // lbcd CTCSS/DCS RX (0xFFF/0x0 = off)
    uint8_t txtone[2];    // lbcd CTCSS/DCS TX
    uint8_t flags;        // bits: bcl | beatshift | narrow | highpower | skip | unknown1..3
    uint8_t unknown4[3];
};
```

| Campo | Semântica |
|---|---|
| `rxfreq`/`txfreq` | BCD little-endian, dígitos em pares por byte: bytes `00 25 21 46` = `46|21|25|00` = 46212500 → **462.125000 MHz** |
| `flags.bcl` | busy channel lockout |
| `flags.narrow` | 1 = FM estreito (12,5 kHz) |
| `flags.highpower` | 0 = potência baixa / 1 = potência alta |
| `flags.skip` | excluir do scan |
| `unknown4[3]` | **desconhecido** (RE) — zero nos dumps |

### 2.2 settings — `0x02B0` (10 B + padding até 0x02C0)

```c
struct settings {         // @0x02B0
    uint8_t voiceprompt;      // 0/1
    uint8_t voicelanguage;    // 0=English 1=Chinese
    uint8_t scan;             // 0/1
    uint8_t vox;              // 0/1
    uint8_t voxlevel;         // 1..5
    uint8_t voxinhibitonrx;   // 0/1
    uint8_t lowvolinhibittx;  // 0/1
    uint8_t highvolinhibittx; // 0/1
    uint8_t alarm;            // 0/1
    uint8_t fmradio;          // 0/1
};
```

### 2.3 settings2 — `0x03C0` (H777: 8 B; variante BF1900 muda a ordem)

```c
struct settings2 {        // @0x03C0 (H777Radio)
    uint8_t flags0;         // bits: beep(bit0) | batterysaver(bit1)
    uint8_t squelchlevel;   // 0..9
    uint8_t sidekeyfunction;// 0=Monitor 1=M.lua/Alarm 2=Scan 3=Lamp (ver VOICE/SIDEKEY no driver)
    uint8_t timeouttimer;   // índice em TIMEOUTTIMERLIST (ex. 0x03="180 seconds")
    uint8_t unused2[3];
    uint8_t flags1;         // bit7: scanmode (0=TO "Time" / 1=CO "Carrier")
};
// Variante BF1900_SETTINGS2 (@0x03C0): flags0 igual, depois
// squelchlevel, scanmode (byte inteiro), timeouttimer, unused2[4].
```

### 2.4 Enumerações usadas pelos docs/CLI

- `voicelanguage`: `0=English`, `1=Chinese` (`VOICE_LIST`)
- `sidekeyfunction`: `0=Monitor`, demais em `SIDEKEY_LIST` (Alarm/Scan/Lamp)
- `scanmode` (H777 bit): `0=TO (Time)`, `1=CO (Carrier)`

## 3. Valores de fábrica medidos (hardware real)

### 3.1 Canais — BF-777S (dígitos de fábrica originais)

| CH | Freq RX (MHz) | Tônica |
|---|---|---|
| 01 | 462.125000 | TSQL 88.5 |
| 02-08 | 462.225-462.825 (passo 100 kHz) | 02/03 off; 04-08 TSQL (103.5/114.8/127.3/136.5/162.2) |
| 09-11 | 462.925-463.125 | DTCS 025/051/125 N |
| 12-13 | 463.225/463.525 | DTCS 155/465 R |
| 14 | 450.225000 | DTCS 023 N |
| 15 | 460.325000 | off |
| 16 | 469.950000 | TSQL 203.5 |

### 3.2 Settings — idênticos nas duas marcas

```
voiceprompt=on  voicelanguage=English  scan=off  vox=off  voxlevel=2
voxinhibitonrx=on  lowvolinhibittx=on  highvolinhibittx=on
alarm=off  fmradio=on  beep=on  batterysaver=on  squelchlevel=3
sidekeyfunction=Monitor  timeouttimer="180 seconds"  scanmode="Time"
```

## 4. Análise BF-777S × RC 3002 G2 (83 faixas do `--diff`)

| Região | Diferença | Interpretação |
|---|---|---|
| `0x0010-0x0110` (canais) | **16/16 canais diferentes** | programação de fábrica distinta por marca (RC usa `00` como filler, BF usa `FF`) |
| `settings` + `settings2` | **zero diferenças** | derive de um schema comum: mesmos valores default |
| `0x0110-0x01FF` | BF `FF` × RC `00` | filler; sem dados nos dois |
| `0x0200-0x0268` | pares `0x1C,0x37→0x29,0x3D`, rampa monotônica decrescente | **curva de calibração** (candidata: точки de RSSI/volt/bateria — RE) |
| `0x0270-0x0290` | rampa `0x3E→0x13` | segunda curva de calibração (RE) |
| `0x0290-0x02AF`, `0x02C0-0x02FF`, `0x0338-0x037F` | BF `FF` × RC `00` com `0x55` a cada 17 B (`0x0299,0x02AA,0x02CC,0x02DD,0x02EE,0x02FF…`) | registros de 16 B + marcador `0x55` (RE) |
| `0x0300-0x032F` | rampa `0x38,0x3A,0x3C…(+2)` | terceira tabela de calibração (RE) |

Canais RC (resumo): CH01 `462.5625`, CH02-15 `462.575-462.7125`
(passo irregular ~10,6 kHz), CH14-16 sobre `467.5625-467.5875`,
DTCS 023 predominante.

## 5. Mapa estendido por serial (sessão 2026-10-17, RC 3002 G2)

> Fonte: `tools/probe_serial_fw.py` + `tools/dump_full_map.py`
> (commit `9c8a3562`), dump validado cross-check com o clone oficial.

### 5.1 O que o cabo expõe além do clone

- **Mapa endereçável**: responde até **0x8000** (32 KB solicitados);
  dump completo `Intelbras_RC_3002_G2_MAPFULL_8B.bin`, 32 768 B,
  0 endereços ruins, 111 s (só blocos de 8 B).
- **Máscara de endereço = `0x3FFF`**: o conteúdo **repete** com período
  `0x4000` — endereços ≥0x4000 são alias do primeiro bloco de 16 KB;
  endereços ≥0x8000 respondem `FF` (fora do decode do handler).
- **Zonas reais** (dentro dos 16 KB):
  | Faixa | Conteúdo |
  |---|---|
  | `0x0000-0x07FF` | codeplug + calibração + settings (o clone 992 B) |
  | `0x0800-0x0FFF` | zeros |
  | `0x1000-0x17FF` | **cópia byte-a-byte da zona 0x0000-0x07FF** — zona-mirror REAL de fábrica (design dual-zone de recuperação; não é alias: 0x2000+ = zeros) |
  | `0x1800-0x3FFF` | zeros (10 KB livres) |

### 5.2 Regras do protocolo (validated em hardware)

- **Leitura**: só blocos de **8 B são confiáveis**. Tamanhos `0x40/80/C0`
  são aceitos (echo correto) mas **dados corrompidos** — handler só
  refresca as páginas de 8 B; `0xFF` falha.
- **Saindo de comandos**: `E` responde `0x46` ('F'); demais comandos
  desconhecidos (`V?IF`, 0xA5) = timeout. **Não há modo boot via
  serial** nesta família (0xA5 não acorda nada).
- **Ident não distingue marcas**: BF-777S e RC 3002 G2 = mesmo
  `P3107` (`50 33 31 30 37 f7 00 00`).
- **Firmware e vozes NÃO estão no espaço serial** — a voz PT do RC é
  propriedade do flash interno do MCU (manual Intelbras: "anúncios em
  português"; manual BF-888S: CHI/ENG apenas). Extração: cirurgia de
  hardware (§ do diário, adiada a pedido do usuário).
- **Valor de resgate**: a zona-mirror `0x1000-0x17FF` é um backup
  natural do codeplug; o dump 8-B é o registro fiel para restore.

## 6. Protocolo de escrita (restore) — validado em hardware W1

> Fonte: `tools/roundtrip_noop.py` — round-trip no-op no BF-777S real
> (2026-10-17, unidade sha `4d8db228…`) e no RC 3002 G2. Backend:
> `mychirp/fwtool.py` (`restore_h777_image`) · CLI `mychirp-fw
> --restore` · GUI `Radio > Firmware restore...` (Ctrl+Shift+W).

### 6.1 Frame de gravação

```c
struct write_frame {       // 12 bytes TX (4 header + 8 data)
    uint8_t  cmd;          // 'W' (0x57)
    uint16_t addr;         // BE; janela clone 0x0000-0x03D8
    uint8_t  count;        // sempre 8
    uint8_t  data[8];      // bytes a gravar
};
// RX do rádio: 1 byte apenas — 0x06 (ACK) em até ~0,31 s.
// NÃO há eco de endereço (diferente da leitura, que ecoa 'W'+addr+count).
```

- **Janela clone = 992 B (0x03E0)**: 124 blocos de 8 B, offsets
  `0x0000 … 0x03D8`. A imagem do clone (download padrão) escreve
  **1:1 na memória** (sem prefixo de ident, ao contrário do UV-5R).
- **Sessão única viva**: igual ao download, gravar exige entrar
  (0x02 + `PROGRAM` → 0x06) e já sair gravando. **Pré-leitura de
  992 B na MESMA sessão causa NACK no 1º bloco** (comportamento
  observado em hardware; causa-raiz da 1ª falha de escrita às 14:00
  do diário). O dump/verify pré e pós são sessões SEPARADAS.
- **Fechamento**: 'E' → 0x46 ('F'), igual à leitura.
- **Aborto no meio**: rádio fica num estado que exige religar
  fisicamente (observado; não há forma de recuperação conhecida via
  cabo — trate como regra de operação: aborto = religar o rádio).

### 6.2 Rails de segurança do restore (`fwtool.restore_h777_image`)

1. **Imagem deve ter exatamente 992 B** — erro claro caso contrário.
2. **Sessão 1 (read-only)**: entra, lê os 992 B, salva
   `<driver>_RESTORE_<data>_pre_<sha8>.bin` (e .yaml sidecar) em
   `~/.chirp/fw-backups/` antes de qualquer escrita.
3. **Sessão 2 (write)**: entra e grava; **cada bloco AGUARDA o ACK
   0x06**. Qualquer NACK/timeout → ABORTA imediatamente (resto dos
   blocos NÃO é enviado); reporta `aborted=<endereço>`.
4. **Sessão 3 (verify)**: re-entra, re-lê 992 B, salva
   `_post_<sha8>.bin`, calcula diff por byte. Com gravação completa:
   `diffs=[]` esperado se a imagem = conteúdo da unidade (no-op) ou
   se a gravação foi fiável; com aborto: `diffs=None` (sem diff
   confiável).
5. **Dupla confirmação humana**: GUI em 2 modais (QMessageBox.question
   + input da palavra exata "GRAVAR"); CLI em 2 fases de stdin
   (sim/NÃO + digitar GRAVAR — impossível sem TTY interativo).
6. **Família restrita**: só drivers com `PROGRAM_CMD == b"PROGRAM"` —
   família h777 (BF-777S, RC 3002 G2, BF-888S). GUI e CLI recusam os
   demais com mensagem explícita.

### 6.3 Dicionário reportado por restore (RestoreReport)

```python
{
  "ok": bool            # True somente com gravação completa e diffs=[]
  "aborted": addr|None  # endereço do primeiro NACK/timeout (se any)
  "sha_old": hex        # sha256 do dump prévio (sessão 1)
  "sha_new": hex        # sha256 da re-leitura pós-escrita (sessão 3)
  "diffs": [offsets]    # bytes divergentes pós-escrita (None se abort)
  "pre_path": path      # backup prévio .bin (e .yaml lado a lado)
  "post_path": path     # re-leitura pós-escrita .bin (e .yaml)
}
```

## 7. Pontos abertos (RE futura)

1. `unknown4[3]` de cada canal e os 3 bits superiores de `flags`.
2. Curvas de calibração em `0x0200-0x02FF`/`0x0300-0x032F` — mapear
   unidades (RSSI? tensão de bateria? pontos de squelch).
3. Blocos com marcador `0x55` de stride 17 B (exatamente um por bloco
   de preenchimento) — cadência constante em RC, ausente em BF.
4. Área `0x0000-0x0010` não lida pelo driver (ident no protocolo).
5. Bytes `0x0300-0x031E` incluem valor `0x0305: E0→2D`, e texto ASCII
   detectável em `0x030E-0x0315` (`"2/…"` dígito-dígito) — pode ser
   serial/calibração gravada.
6. **Escrita fora da janela clone**: em RC (§5) o handler serial lê
   até 0x8000 — falta testar se o frame `W` aceita endereços além de
   0x03D8 (janela clone), para o restore do mapa estendido (as
   zonas-mirror e a área livre podem ser graváveis → mais resgate
   útil).
7. **Perfis de escrita BC vs brand**: BF e RC divergem só em 1 byte
   (fmradio @0x02B9) no estado não-programado — mapear se a unidade
   responde diferente ao frame `W` por marca (perfil forense por
   unidade).
