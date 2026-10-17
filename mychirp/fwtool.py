"""Dump de memória de rádio (imagem de clone) — backend do mychirp-fw.

Invólucro genérico: para QUALQUER CloneModeRadio registrado no
directory (todos os rádios Baofeng e demais fabricantes), resolve o
driver pela identificação ``VENDOR_MODEL`` (mesmo padrão do mychirpc),
abre a serial pela abertura compartilhada (mychirp.serial_link), roda
``sync_in()`` do driver (mesmo protocolo do download da GUI) e salva:

- a imagem RAW (``.bin``) — útil para diff entre rádios/versões; e
- um YAML de metadados (``.yaml``) junto do binário: modelo, porta,
  baud, data, sha256, tamanho e versão do MyChirp.

Read-only: este módulo NUNCA grava no rádio (sem erase/write/upload —
política de segurança do PLAN.md §4). Upload continua existindo apenas
no mychirpc/UI com dupla confirmação.

Estrutura dos backups (``--backup``): ``~/.chirp/fw-backups/`` com nome
``<vendor>_<model>_<sha8>_<data>.bin`` — o mesmo espírito do diretório
``~/.chirp/backups/`` usado pela GUI.
"""

import datetime
import hashlib
import logging
import os

from mychirp import directory
from mychirp import chirp_common

class FwDumpError(Exception):
    """Erro claro de uso do dump (driver inexistente ou não-clonável)."""


LOG = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = os.path.join(os.path.expanduser("~"), ".chirp",
                                  "fw-backups")


def sha256_hex(data):
    """Hash sha256 hex da @data (identificação dos dumps)."""
    return hashlib.sha256(data).hexdigest()


def fw_backup_dir():
    """Diretório padrão dos backups de dump (~/.chirp/fw-backups)."""
    return DEFAULT_BACKUP_DIR


def _progress_printer():
    """Callback de progresso do sync_in(): linha única com percentual."""
    last_line = [""]

    def _status(status):
        if status.max:
            pct = 100 * status.cur // status.max
        else:
            pct = 0
        cur = getattr(status, "msg", "") or "Cloning"
        line = "%s: %3d%%" % (cur, pct)
        if line != last_line[0]:
            print("\r" + line + "    ", end="", flush=True)
            last_line[0] = line

    return _status


def resolve_rclass(radio_id):
    """Classe do driver pela identificação do directory (ex.: Baofeng_BF-777S).

    Erro claro quando o driver não existe; erro claro quando o driver
    aceita só arquivos (sem clonagem serial, ex.: CSV/file-backed).
    """
    directory.import_drivers()
    try:
        rclass = directory.get_radio(radio_id)
    except Exception:
        rclass = None
    if rclass is None:
        # Tolerância de caixa: BAOFENG_BF-777S == Baofeng_BF-777S
        low = radio_id.replace(" ", "_").lower()
        for ident, cand in directory.DRV_TO_RADIO.items():
            if ident.lower() == low:
                rclass = cand
                break
    if rclass is None:
        raise FwDumpError(
            "Driver \"%s\" não encontrado. Veja as identificações com "
            "mychirp-fw --list-radios (filtro --vendor=Baofeng)." % radio_id)
    if not issubclass(rclass, chirp_common.CloneModeRadio):
        raise FwDumpError(
            "Driver \"%s\" não clona via serial (radio file-backed); "
            "dump de memória não se aplica." % radio_id)
    return rclass


def _out_path(out, rclass, packed, timestamp):
    """Caminho de saída: --out, ou nome automático com ident + sha8."""
    if out:
        return out
    radio_id = directory.get_driver(rclass)
    h = sha256_hex(packed)[:8]
    stamp = timestamp.strftime("%Y%m%d-%H%M%S")
    return "%s_%s_%s.bin" % (radio_id, stamp, h)


def _dump_info(rclass, port, packed, timestamp):
    """Dict de metadados do dump (YAML sidecar)."""
    from mychirp import CHIRP_VERSION
    return {
        "tool": "mychirp-fw",
        "version": CHIRP_VERSION,
        "driver": directory.get_driver(rclass),
        "vendor": rclass.VENDOR,
        "model": rclass.MODEL,
        "variant": rclass.VARIANT or "",
        "port": port,
        "baud": getattr(rclass, "BAUD_RATE", 9600),
        "date": timestamp.isoformat(timespec="seconds"),
        "size": len(packed),
        "sha256": sha256_hex(packed),
    }


def _write_sidecar(meta, bin_path):
    yaml_path = os.path.splitext(bin_path)[0] + ".yaml"
    import yaml
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(meta, f, allow_unicode=True, sort_keys=False)
    return yaml_path


def dump_clone(radio_id, port, out=None, backup=False):
    """Dump completo da memória (imagem de clone) de @radio_id via @port.

    Malha completa do driver: rclass(pipe) -> sync_in() (o MESMO
    download da GUI, com o protocolo específico do driver) -> imagem RAW
    .bin + YAML sidecar. Com backup=True escreve também em
    ~/.chirp/fw-backups/ com nome assinado pelo sha256.

    Retorna o caminho do .bin escrito. Nenhum comando de escrita é
    enviado ao rádio em nenhum ponto.
    """
    if not port:
        raise FwDumpError("Informe a porta serial com --serial=/dev/ttyUSB0")
    rclass = resolve_rclass(radio_id)
    b = getattr(rclass, "BAUD_RATE", 9600)
    LOG.info("Dump %s @%s (baud %i)", radio_id, port, b)

    from mychirp.serial_link import open_serial
    pipe = open_serial(port, rclass)
    try:
        radio = rclass(pipe)
        radio.status_fn = _progress_printer()
        radio.sync_in()
    finally:
        print()
        try:
            pipe.close()
        except Exception:
            pass
    packed = radio.get_mmap().get_byte_compatible().get_packed()

    timestamp = datetime.datetime.now()
    bin_path = _out_path(out, rclass, packed, timestamp)
    if backup and not out:
        os.makedirs(fw_backup_dir(), exist_ok=True)
        radio_id2 = directory.get_driver(rclass)
        bin_path = os.path.join(
            fw_backup_dir(),
            "%s_%s_%s.bin" % (radio_id2, sha256_hex(packed)[:8],
                              timestamp.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(os.path.dirname(bin_path) or ".", exist_ok=True)
    with open(bin_path, "wb") as f:
        f.write(packed)

    meta = _dump_info(rclass, port, packed, timestamp)
    yaml_path = _write_sidecar(meta, bin_path)
    print("Dumper: {vendor} {model} ({driver})".format(**meta))
    print("Imagem: %s (%d bytes)" % (bin_path, len(packed)))
    print("sha256: %s" % meta["sha256"])
    print("Meta  : %s" % yaml_path)
    return bin_path


def diff_files(a_path, b_path):
    """Diff byte-level entre dois dumps; retorna (a, b, faixas).

    faixas = lista de (offset_inicio, offset_fim, diferenças) onde
    diferenças destaca os primeiros bytes conflitantes da faixa.
    """
    with open(a_path, "rb") as f:
        a = f.read()
    with open(b_path, "rb") as f:
        b = f.read()

    ranges = []
    n = min(len(a), len(b))
    i = 0
    while i < n:
        if a[i] != b[i]:
            start = i
            diffbytes = []
            while i < n and a[i] != b[i]:
                diffbytes.append((i, a[i], b[i]))
                i += 1
            ranges.append((start, i, diffbytes))
        else:
            i += 1
    if len(a) != len(b):
        ranges.append((n, max(len(a), len(b)), None))
    return a, b, ranges


def load_meta(bin_path):
    """YAML sidecar de um dump do mychirp-fw; {} se não houver."""
    yaml_path = os.path.splitext(bin_path)[0] + ".yaml"
    if not os.path.exists(yaml_path):
        return {}
    import yaml
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def driver_from_meta(bin_path):
    """(driver_id, meta) do yaml sidecar; (None, {}) sem sidecar."""
    meta = load_meta(bin_path)
    return meta.get("driver"), meta


def _desc_value(value):
    """String compacta de um RadioSettingValue* para o --map."""
    from mychirp.settings import (
        RadioSettingValueBoolean, RadioSettingValueInteger,
        RadioSettingValueString, RadioSettingValueList,
        RadioSettingValueFloat, RadioSettingValueInvertedBoolean)
    val = value.get_value()
    if isinstance(value, (RadioSettingValueBoolean,
                          RadioSettingValueInvertedBoolean)):
        return "on" if val else "off"
    if isinstance(value, RadioSettingValueList):
        if isinstance(val, int):
            opts = value.get_options()
            val = opts[val] if 0 <= val < len(opts) else str(val)
        return str(val)
    return str(val)


def _collect_settings(root, out, prefix=""):
    from mychirp.settings import RadioSetting, RadioSettingGroup
    from mychirp import chirp_common
    for el in root:
        if isinstance(el, RadioSetting):
            name = prefix + el.get_name()
            try:
                # RadioSetting.value -> RadioSettingValue (via __getattr__)
                value = el.value
                if isinstance(value, list):
                    # setting-array: mostra um por item
                    for i, sub in enumerate(value):
                        out.append(("%s[%d]" % (name, i),
                                    _desc_value(sub)))
                else:
                    out.append((name, _desc_value(value)))
            except Exception as e:
                out.append((name, "<erro: %s>" % type(e).__name__))
        elif isinstance(el, RadioSettingGroup):
            _collect_settings(el, out, prefix + el.get_shortname() + ": ")


def _data_regions(data, width=8):
    """Regiões contíguas com bytes != 0xFF: [(start, end), ...]."""
    regions = []
    cur = None
    for off in range(0, len(data), width):
        isdata = any(b != 0xFF for b in data[off:off + width])
        if isdata and cur is None:
            cur = off
        elif not isdata and cur is not None:
            regions.append((cur, off))
            cur = None
    if cur is not None:
        regions.append((cur, len(data)))
    return regions


def analyze_dump(bin_path, rclass=None, max_channels=None,
                 max_settings=40):
    """Análise semântica de um dump (--map).

    Resolve o driver pelo yaml sidecar do mychirp-fw (ou @rclass
    explícito), carrega a imagem numa instância real do driver e
    produz: canais usados, resumo de settings, e as regiões com dados
    reais classificadas como mapeadas (dentro dos _ranges do driver)
    ou não-mapeadas (candidatas a RE).
    """
    from mychirp import memmap

    with open(bin_path, "rb") as f:
        data = f.read()
    if rclass is None:
        ident, meta = driver_from_meta(bin_path)
        if ident:
            rclass = resolve_rclass(ident)
    if rclass is None:
        raise FwDumpError(
            "Driver não identificável para %s — passe --radio (o yaml "
            "sidecar do mychirp-fw também resolve o driver)."
            % os.path.basename(bin_path))
    if len(data) != getattr(rclass, "_memsize", 0):
        LOG.warning("Dump %s tem %d bytes; driver espera %d",
                    os.path.basename(bin_path), len(data),
                    getattr(rclass, "_memsize", 0))

    radio = rclass(memmap.MemoryMapBytes(bytes(data)))

    # ----- canais -----
    lo, hi = radio.get_features().memory_bounds
    channels, empty = [], 0
    for number in range(lo, hi + 1):
        try:
            mem = radio.get_memory(number)
        except Exception:
            continue
        if mem.empty:
            empty += 1
            continue
        tone = ""
        if mem.tmode == "Tone":
            tone = "T%d" % mem.rtone
        elif mem.tmode == "TSQL":
            tone = "TSQ%d" % mem.rtone
        elif mem.tmode == "DTCS":
            tone = "D%d%s" % (mem.dtcs, mem.dtcs_polarity)
        elif mem.tmode == "Cross":
            tone = mem.cross_mode
        from mychirp import chirp_common
        offset = ""
        if mem.duplex not in ("", "off"):
            offset = chirp_common.format_freq(mem.offset)
        channels.append({
            "number": number,
            "freq": chirp_common.format_freq(mem.freq),
            "duplex": mem.duplex or "",
            "offset": offset,
            "tone": tone,
            "name": (mem.name or "").strip(),
        })

    # ----- settings -----
    settings, trunc = [], 0
    try:
        _collect_settings(radio.get_settings(), settings)
        trunc = max(0, len(settings) - max_settings)
        settings = settings[:max_settings]
    except Exception as e:
        LOG.debug("get_settings indisponível: %s", e)

    # ----- regiões -----
    ranges = getattr(radio, "_ranges", None) or         getattr(type(radio), "_ranges", None)
    mapped, unmapped = [], []
    for s, e in _data_regions(data):
        if not ranges or any(s >= rs and e <= re for rs, re in ranges):
            mapped.append((s, e))
        else:
            unmapped.append((s, e))

    return {
        "path": bin_path,
        "size": len(data),
        "sha256": sha256_hex(data),
        "driver": directory.get_driver(rclass),
        "vendor": rclass.VENDOR,
        "model": rclass.MODEL,
        "memory_bounds": (lo, hi),
        "channels": channels,
        "empty": empty,
        "total_slots": len(channels) + empty,
        "settings": settings,
        "settings_truncated": trunc,
        "mapped_regions": mapped,
        "unmapped_regions": unmapped,
    }


def format_map(an, max_channels=30):
    """Resumo legível de analyze_dump() para o CLI (--map)."""
    out = []
    out.append("Dumper: %s %s (%s)" % (an["vendor"], an["model"],
                                       an["driver"]))
    out.append("Imagem: %s" % an["path"])
    out.append("Tamanho: %d bytes (0x%X)" % (an["size"], an["size"]))
    out.append("sha256: %s" % an["sha256"])

    lo, hi = an["memory_bounds"]
    ch = an["channels"]
    out.append("Canais: %d usados de %d (%d vazios) [%d..%d]"
               % (len(ch), an["total_slots"], an["empty"], lo, hi))
    for c in ch[:max_channels]:
        out.append("  #%3d  %-12s MHz  %-12s %s" % (
            c["number"], c["freq"], c["tone"] or "-", c["name"]))
    if len(ch) > max_channels:
        out.append("  ... +%d canais" % (len(ch) - max_channels))

    if an["settings"]:
        out.append("Settings (%d):" % len(an["settings"]))
        for k, v in an["settings"]:
            out.append("  %-36s = %s" % (k, v))
        if an["settings_truncated"]:
            out.append("  ... +%d itens truncados"
                       % an["settings_truncated"])

    if an["mapped_regions"]:
        out.append("Regiões mapeadas (dentro dos ranges do driver):")
        for s, e in an["mapped_regions"]:
            out.append("  0x%04X-0x%04X (%d B)" % (s, e, e - s))
    if an["unmapped_regions"]:
        out.append("Regiões NÃO-MAPEADAS (fora dos ranges do driver — "
                   "candidatas a RE):")
        for s, e in an["unmapped_regions"]:
            out.append("  0x%04X-0x%04X (%d B)" % (s, e, e - s))
    return "\n".join(out)


def format_diff(ranges, a_size, b_size, max_examples=8):
    """Representação textual do diff (resumo por faixa)."""
    lines = []
    if not ranges:
        lines.append("Dumps idênticos (byte a byte).")
        return "\n".join(lines)
    lines.append("Tamanhos: A=%d B=%d" % (a_size, b_size))
    lines.append("Faixas com diferença: %d" % len(ranges))
    for start, end, diffbytes in ranges[:max_examples]:
        if diffbytes is None:
            lines.append("  0x%06X-0x%06X (tamanhos diferentes)"
                         % (start, end))
            continue
        samples = ", ".join(
            "0x%06X: %02X->%02X" % (off, x, y)
            for off, x, y in diffbytes[:4])
        lines.append("  0x%06X-0x%06X (%d B)  %s%s"
                     % (start, end, end - start, samples,
                        " ..." if len(diffbytes) > 4 else ""))
    if len(ranges) > max_examples:
        lines.append("  ... mais %d faixa(s)" % (len(ranges) - max_examples))
    return "\n".join(lines)
