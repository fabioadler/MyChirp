# Formato de dump — família UV-5R (BOMVINK BOM-5701)

> Fonte de verdade (schema): `mychirp/drivers/uv5r.py` (`MEM_FORMAT`).
> Classe específica: `mychirp/drivers/bom5701.py` (`UV5RAuxFirstClone`).
> Dados validados em hardware real: 2 dumps byte-idênticos
> (_sessão 2026-10-16_, sha256 `6efa912e…`, 6472 B @9600, ~20 s de
> pausa entre sessões de clone — o rádio reinicia).
> Ferramenta: `mychirp-fw --map <dump.bin>`.

## 1. Layout da imagem (6472 B)

O driver BOM-5701 é **aux-block-first**: o rádio só entra no modo
programação se o download pedir primeiro o bloco auxiliar; a imagem do
dump é montada como:

```
[0x0000 .. 0x1808)  bloco principal (6152 B, _memsize do UV-5R)
[0x1808 .. 0x1948)  bloco auxiliar anexado (320 B)
```

Por isso um dump tem 6472 B, enquanto a classe base declara
`_memsize = 0x1808` (6152) — o `--map` emite warning e continua.

## 2. Mapa de regiões (bloco principal)

| Offset | Tamanho | Conteúdo | Estado real no dump |
|---|---|---|---|
| `0x0008` | 128×16 B | **memory[128]** — 128 canais | 23 usados (CH000-126; bounds do driver) |
| `0x0B08` | 15×16 B | **pttid[15]** — códigos PTT-ID (5 B + 11 B unused) | `FF` |
| `0x0C88` | ~120 B | **ani** — códigos DTMF (222… 555… 60606, 70707 etc.) | `FF` |
| `0x0E28` | 67 B | **settings** — grupo Basic/Advanced | valores de fábrica |
| `0x0E7E` | 2 B | **wmchannel** (mrcha/mrchb) | CH 0 |
| `0x0F10` | 32 B | **vfoa** — VFO A | 146.520 etc. |
| `0x0F30` | 32 B | **vfob** | `FF` parcialmente |
| `0x0F56` | 2 B | fm_presets (u16) | — || `0x1008` | 128×16 B | **names[128]** — nome 7 char + 9 B | nomes em minúsculas reais (`Coz.`, `Artu.`) |
| `0x1818` | 14 B | sixpoweron_msg (2×7 char) | vazio |
| `0x1828` | 14 B | poweron_msg| `Welcome` / `Fabio A` (unidade do usuário) |
| `0x1838` | 14 B | firmware_msg | vazio |
| `0x18A8` | 64 B | squelch_new (vhf/uhf sql0-sql9) | — |
| `0x18E8` | 32 B | squelch_old | — |
| `0x1908` | 64 B | limits_new (enable/bbcd lower/upper ×vhf/uhf) | 128-176 / 384-524 MHz |
| `0x1948` | fim | — | — |

## 3. Structs "limpas"

### 3.1 memory[128] — `0x0008`, 16 B por registro

```c
struct channel {          // @0x0008 + 16*i
    uint8_t rxfreq[4];    // lbcd ×10 Hz
    uint8_t txfreq[4];
    uint16_t rxtone;      // ul16 le
    uint16_t txtone;
    uint8_t sflags;       // unused1:3 | isuhf:1 | scode:4
    uint8_t txtoneicon;   // bit0 (unknown1:7)
    uint8_t lowpower:2;   // resto: mailicon:3 | unknown2:3
    uint8_t pttid:2;      // bcl:1 | scan:1 | unknown4 | wide | unknown3
};
```

- `rxfreq == 0` ⇒ canal vazio (unidades reais costumam preencher com
  `FF` ou `00`).
- `scode` = índice PTT-ID/tone-code do canal; `lowpower`: 0=high,
  1=low, 3=? (ver `POWER_LEVELS` do driver).

### 3.2 settings — `0x0E28` (67 B, bitfields por byte)

Campos nomeados (sequência): `squelch, step, unknown1, save, vox,
unknown2, abr, tdr, beep, timeout, unknown3[4], voice, unknown4,
dtmfst, unknown5, screv[:2], pttid, pttlt, mdfa, mdfb, bcl, autolk,
sftd, unknown6[3], wtled, rxled, txled, almod, band, tdrab, ste,
rpste, rptrl, ponmsg, roger, rogerrx, tdrch, displayab|fmradio|alarm|
reset|menu (bits), singleptt|vfomrlock (bits), workmode, keylock`.

### 3.3 vfoa/vfob — `0x0F10`/`0x0F30` (32 B cada)

```c
struct vfo {
    uint8_t freq[8];      // ASCII decimal Hz ("146520000")
    uint8_t offset[6];
    uint16_t rxtone, txtone;
    uint8_t band:1;       // unused1:7
    uint8_t unknown3;
    uint8_t scode:4;      // sftd:2, unused2:2
    uint8_t step:3;       // unused4:4, unused3:1
    uint8_t txpower3:2;   // widenarr:1, txpower:1, unknown5:4
};
```

### 3.4 limits_new — `0x1908`

```c
struct limit { uint8_t enable; uint8_t lower[2]; uint8_t upper[2]; };
struct { struct limit vhf; struct limit uhf; } limits_new; // bbcd: BE
```

Unidades BOM podem ter a área `0xFF` (blank) — o driver faz clamp
(`_clamp_limit_memobj`) antes de expor no menu: out-of-range vira
default de hardware (VHF 128-176, UHF 384-524).

## 4. Valores de fábrica / da unidade (dump `6efa912e`)

- **23 canais usados de 127** — CH000 `SOS 1` (146.520), CH001 `SOS 2`
  (439.000), CH002-016 `BF Cx` na banda 462-470 MHz (esquema de
  fábrica, idêntico ao BF-777S), CH018-022 com nomes do usuário
  (`Coz.`, `Artu.`, `DEP.`, `HORT.` 467.6375, `S/L/C` 462.700 —
  provavelmente gravados pelo proprietário anterior).
- Settings principais: `squelch=1, save=1:4, abr=10, beep=off,
  timeout=600s, mdfa/mdfb=Name, roger=on, tdr=on, voice=English,
  fmradio=on, ste=on, allrange=Default`, LED
  wtled=purple/rxled=blue/txled=orange, `ponmsg=Message`,
  VFO limits 128-176 / 384-524 (enable=on).
- 60+ itens de Work Mode Settings além dos 40 mostrados pelo `--map`
  (truncamento configurável).

## 5. Pontos abertos (RE futura)

1. Semântica de `scode`/`pttid` quando os blocos `0x0B08`/`0x0C88`
   estão `FF` (PTT-ID sempre ausente? Reset apaga?).
2. Bloco auxiliar (320 B anexados): está fora do namespace de structs
   do driver — mapa próprio pendente (RE).
3. `unknown3[4]`/`unknown5..9` dentro de `settings` (0x0E28).
4. FM presets em `0x0F56` — sem parser dedicado no driver.

---

Ver também: `docs/dump-format-h777.md` (família H777 — 2ª família) e
`rethink/uv17m-descobertas.md` (3ª família: 115200, pendência P1).
