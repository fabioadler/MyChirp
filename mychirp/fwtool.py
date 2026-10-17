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
