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
import time

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
    """Callback de progresso do sync_in(): linha única com percentual.

    Aceita dois formatos de chamada:
      - objeto com atributos .cur/.max (./.msg opcional) — usado por
        sync_in() do driver (dump_clone);
      - int com o endereço atual — usado por download_full_window()
        do driver UV-5R (janela de 0x2000 B).
    """
    last_line = [""]

    def _status(status):
        if isinstance(status, int):
            cur = status
            maxv = 0x2000  # janela completa UV-5R/BOM-5701 (8 KiB)
            msg = "Cloning"
        else:
            maxv = getattr(status, "max", 0) or 0
            cur = getattr(status, "cur", 0)
            msg = getattr(status, "msg", "") or "Cloning"
        pct = 100 * cur // maxv if maxv else 0
        line = "%s: %3d%%" % (msg, pct)
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


def dump_full_window(radio_id, port, out=None, backup=False):
    """Dump da janela completa cabelada (radio 0x0000-0x1FFF, 8 KiB).

    Somente drivers com ``download_full_window`` (quirk aux-primeiro,
    p. ex. BOMVINK BOM-5701): inclui a área de calibração de fábrica
    0x1800-0x1EC0 que o clone padrão (0x1948) NÃO cobre. Read-only do
    começo ao fim; a ordem de leitura é a ordem da sessão validada em
    hardware (warm-up → calibração → aux → main por último, que fecha
    a sessão). Salva .bin + YAML sidecar igual ao dump_clone.
    """
    if not port:
        raise FwDumpError("Informe a porta serial com --serial=/dev/ttyUSB0")
    rclass = resolve_rclass(radio_id)
    if not hasattr(rclass, "download_full_window"):
        raise FwDumpError(
            "driver %s não expõe download_full_window" % radio_id)
    baud = getattr(rclass, "BAUD_RATE", 9600)
    LOG.info("Dump janela completa %s @%s (baud %i)", radio_id, port, baud)

    from mychirp.serial_link import open_serial
    pipe = open_serial(port, rclass)
    try:
        radio = rclass(pipe)
        data = radio.download_full_window(status_fn=_progress_printer())
    finally:
        print()
        try:
            pipe.close()
        except Exception:
            pass

    timestamp = datetime.datetime.now()
    stamp = timestamp.strftime("%Y%m%d-%H%M%S")
    radio_id2 = directory.get_driver(rclass)
    if backup and not out:
        os.makedirs(fw_backup_dir(), exist_ok=True)
        bin_path = os.path.join(
            fw_backup_dir(),
            "%s_FULLWINDOW_8K_%s_%s.bin" % (
                radio_id2, sha256_hex(data)[:8], stamp))
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".",
                    exist_ok=True)
        bin_path = out
    os.makedirs(os.path.dirname(bin_path) or ".", exist_ok=True)
    with open(bin_path, "wb") as f:
        f.write(data)

    meta = _dump_info(rclass, port, data, timestamp)
    meta["note"] = ("janela completa 8 KiB (0x0000-0x1FFF) via "
                    "download_full_window; inclui calibração de fábrica "
                    "0x1800-0x1EC0 fora da imagem padrão")
    yaml_path = _write_sidecar(meta, bin_path)
    print("Dumper: {vendor} {model} ({driver})".format(**meta))
    print("Imagem: %s (%d bytes)" % (bin_path, len(data)))
    print("sha256: %s" % meta["sha256"])
    print("Meta  : %s" % yaml_path)
    return bin_path


# ---------------------------------------------------------------------------
# Escrita/restore (gravação validada W1 — round-trip no-op em hardware
# 2026-10-17, BF-777S, sha 4d8db228: 124 blocos ACK, re-leitura idêntica)
# ---------------------------------------------------------------------------

H777_PROGRAM_CMD = b"PROGRAM"
H777_WINDOW_END = 0x03E0  # 992 B (janela do clone padrão h777)

RestoreReport = dict  # {image, sha_old, sha_new, pre_path, post_path,
#                        diffs, ok, aborted}


def _h777_enter(serial):
    import time
    from mychirp import errors
    import struct
    serial.write(b"\x02")
    time.sleep(0.1)
    serial.write(H777_PROGRAM_CMD)
    ack = serial.read(1)
    if ack != b"\x06":
        raise errors.RadioNoResponse()
    serial.write(b"\x02")
    ident = serial.read(8)
    if not ident:
        raise errors.RadioNoResponse()
    serial.write(b"\x06")
    serial.read(1)
    return ident


def _h777_read8(serial, addr):
    import struct
    cmd = struct.pack(">cHb", b"R", addr, 8)
    serial.write(cmd)
    serial.timeout = 0.25
    resp = serial.read(4 + 8)
    if resp[:1] != b"W" or resp[1:4] != cmd[1:4] or len(resp) != 4 + 8:
        return None
    serial.write(b"\x06")
    serial.read(1)
    return resp[4:]


def _h777_write8(serial, addr, data):
    import struct
    cmd = struct.pack(">cHb", b"W", addr, 8)
    serial.write(cmd + data)
    serial.timeout = 0.5  # gravação pode levar até ~0,31 s (obs. driver)
    return serial.read(1) == b"\x06"


def _h777_read_window(serial):
    out = bytearray()
    for addr in range(0, H777_WINDOW_END, 8):
        d = _h777_read8(serial, addr)
        if d is None:
            return None
        out += d
    return bytes(out)


def restore_h777_image(radio_id, port, image, backup=True):
    """Restore da janela clone h777 (992 B) com rails de segurança.

    @image: bytes de exatamente 992 B (dump do MESMO modelo/família).
    Fluxo validado em hardware (ver tools/roundtrip_noop.py e diário §12):
      sessão 1: enter → ler janela → salvar .pre + sha_old → exit
      sessão 2: enter → gravar image bloco a bloco (ACK por bloco,
                ABORTAR em qualquer NACK/timeout) → exit
      sessão 3: enter → re-ler janela → salvar .post + sha_new → exit
    Gravação só funciona no padrão do driver (entrar e escrever logo
    depois, sem pré-leitura na mesma sessão).
    """
    import datetime
    import hashlib
    import os as _os
    import struct
    log = print
    if len(image) != H777_WINDOW_END:
        raise FwDumpError("imagem deve ter %d B (tem %d)"
                         % (H777_WINDOW_END, len(image)))
    rclass = resolve_rclass(radio_id)
    from mychirp.serial_link import open_serial
    serial = open_serial(port, rclass)
    try:
        ident = _h777_enter(serial)
        pre = _h777_read_window(serial)
        if pre is None:
            serial.write(b"E")
            raise FwDumpError("leitura prévia falhou")
        sha_old = hashlib.sha256(pre).hexdigest()
        serial.write(b"E")
        time.sleep(1.0)
        serial.read(4096)
        log("dump prévio: sha256=%s (%s)" % (sha_old[:16], ident.hex()))

        # sessão de gravação: entra e escreve logo (padrão do_upload)
        ident = _h777_enter(serial)
        aborted = None
        for addr in range(0, H777_WINDOW_END, 8):
            if not _h777_write8(serial, addr, image[addr:addr + 8]):
                aborted = addr
                break
        serial.write(b"E")
        if aborted is not None:
            log("ABORTADO: NACK/timeout em 0x%04X" % aborted)
        time.sleep(1.0)
        serial.read(4096)

        # sessão de verificação
        ident = _h777_enter(serial)
        post = _h777_read_window(serial)
        serial.write(b"E")
        if post is None:
            raise FwDumpError("re-leitura pós-gravação falhou")
        sha_new = hashlib.sha256(post).hexdigest()
        if aborted is None:
            diffs = [i for i in range(H777_WINDOW_END)
                     if post[i] != image[i]]
        else:
            diffs = None  # gravação incompleta: sem diff confiável

        # backups automáticos (pré e pós)
        paths = [None, None]
        if backup:
            fw_backup_dir_impl = fw_backup_dir()
            _os.makedirs(fw_backup_dir_impl, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            name = "%s_RESTORE_%s_%s.bin" % (
                directory.get_driver(rclass), stamp,
                sha_new[:8])
            base = _os.path.join(fw_backup_dir_impl, name)
            paths[0] = base.replace(".bin", "_pre_%s.bin" % sha_old[:8])
            paths[1] = base.replace(".bin", "_post_%s.bin" % sha_new[:8])
            with open(paths[0], "wb") as f:
                f.write(pre)
            with open(paths[1], "wb") as f:
                f.write(post)
            meta = _dump_info(rclass, port, pre, datetime.datetime.now())
            meta["note"] = "dump ANTES de restore_h777_image"
            _write_sidecar(meta, paths[0])
            meta["note"] = "dump DEPOIS de restore_h777_image "
            meta["sha256"] = sha_new
            meta["size"] = len(post)
            _write_sidecar(meta, paths[1])
        return RestoreReport(
            ok=aborted is None and diffs == [], aborted=aborted,
            sha_old=sha_old, sha_new=sha_new, diffs=diffs,
            pre_path=paths[0], post_path=paths[1])
    finally:
        try:
            serial.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Escrita/restore família UV-5R aux-first (BOM-5701) — sessão 3 estágios,
# reutilizando a maquinaria do driver (ident + X-frame 16 B com retry,
# validados em hardware 2026-10-10/11, issue #12332).
# ---------------------------------------------------------------------------

UV5R_AUX_FIRST_IMAGE_END = 0x1948  # ident 8 + main 0x1800 + aux 0x140
UV5R_AUX_FIRST_COOLDOWN = 8.0  # s entre sessões (o rádio reinicia e
# demora a ficar pronto: 2 s NÃO bastam — falha W4 1ª rodada, nenhuma
# gravação ocorreu porque a sessão de escrita nem entrou em PROGRAM)
UV5R_AUX_FIRST_WRITE_RETRIES = 1  # retries da sessão de escrita após
# ident/NACK fatal; re-gravar os mesmos blocos é idempotente

# Faixas da IMAGEM que o upload do driver NÃO grava (gaps clássicos de
# proteção do UV-5R: _ranges_main_default pula i = 0x0CF8-0x0D08 e
# 0x0DF8-0x0E08 = chunks image[i..i+16) ⇒ bytes de imagem 0x0CF8-0x0D08
# e 0x0DF8-0x0E08, que correspondem a wire 0x0CF0-0x0D00 e 0x0DF0-0x0E00).
# O verify do restore EXCLUI essas faixas do diff (o conteúdo lá
# permanece o da unidade — byte a byte, preservado do pre-dump).
UV5R_UPLOAD_SKIP_IMAGE_OFFSETS = [(0x0CF8, 0x0D08), (0x0DF8, 0x0E08)]


def _uv5r_auxfirst_dump(rclass, port):
    """Sessão de download do driver: imagem 0x1948 B da unidade.

    Mesmo caminho do dump_clone (sync_in, quirk aux-primeiro incluído);
    validação de tamanho no fim.
    """
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
    data = radio.get_mmap().get_byte_compatible().get_packed()
    if len(data) != UV5R_AUX_FIRST_IMAGE_END:
        raise FwDumpError(
            "download retornou %d B; esperado %d (BOM-5701)"
            % (len(data), UV5R_AUX_FIRST_IMAGE_END))
    return data


def _uv5r_auxfirst_write(rclass, port, image):
    """Sessão de gravação pela maquinaria do driver.

    Constrói o radio a partir da imagem-alvo (MemoryMapBytes +
    process_mmap) e roda sync_out() — que faz ident, grava o bloco
    AUX primeiro (0x1EC0-0x2000 em 20× 16 B) e depois o MAIN (382×
    16 B: a faixa wire completa tem 384 blocos, mas o driver pula os
    chunks dos gaps de proteção do UV-5R nas offsets de imagem
    0x0CF8 e 0x0DF8), com retry de 6× 0,15 s por bloco (janela de
    commit). Em ident/NACK fatal do rádio, repete a sessão inteira
    até UV5R_AUX_FIRST_WRITE_RETRIES vezes (com cooldown entre
    tentativas — re-gravar os mesmos blocos é idempotente).
    Retorna (aborted, addr): aborted False em sucesso; True se as
    tentativas se esgotaram; addr do bloco recusado (ou None quando
    a falha é de ident — o rádio nem entra em programação).
    """
    import re
    from mychirp import memmap
    from mychirp.serial_link import open_serial

    aborted, ab_addr = False, None
    for attempt in range(UV5R_AUX_FIRST_WRITE_RETRIES + 1):
        pipe = open_serial(port, rclass)
        radio = None
        try:
            radio = rclass(memmap.MemoryMapBytes(bytes(image)))
            radio.process_mmap()
            radio.pipe = pipe
            try:
                radio.sync_out()
                return False, None
            except Exception as e:
                aborted = True
                m = re.search(r"0x[0-9A-Fa-f]{3,4}", str(e))
                ab_addr = int(m.group(0), 16) if m else None
        finally:
            radio.pipe = None
            try:
                pipe.close()
            except Exception:
                pass
        if attempt < UV5R_AUX_FIRST_WRITE_RETRIES:
            time.sleep(UV5R_AUX_FIRST_COOLDOWN)
    return aborted, ab_addr


def restore_bom5701_image(radio_id, port, image, backup=True):
    """Restore na janela clone UV-5R aux-first (BOM-5701): 3 sessões.

    DIFERE do restore_h777_image porque a família UV-5R-aux-first
    (BOM-5701) tem protocolo de escrita próprio (validado em HW,
    2026-10-10/11): frame `X` de 16 B com retry (janela de commit do
    EEPROM), ordem AUX→MAIN e remap de endereço (wire = imagem − 8 na
    main; aux remap 0x1808..0x1948 → 0x1EC0..0x2000). Sessões:

      1) download (driver read path) → sha_old + .pre
      2) gravação (driver write path: ident + aux-first + retry)
      3) re-download → sha_new + .post + diff byte-a-byte (a partir
         do offset 8; os 8 B iniciais são ident de handshake, NÃO
         graváveis via serial)
    """
    log = print
    if len(image) != UV5R_AUX_FIRST_IMAGE_END:
        raise FwDumpError(
            "imagem deve ter %d B (6.472; tem %d)"
            % (UV5R_AUX_FIRST_IMAGE_END, len(image)))
    rclass = resolve_rclass(radio_id)

    # 1) dump prévio
    pre = _uv5r_auxfirst_dump(rclass, port)
    sha_old = sha256_hex(pre)
    log("dump prévio: sha256=%s" % sha_old[:16])
    time.sleep(UV5R_AUX_FIRST_COOLDOWN)

    # 2) gravação pela maquinaria do driver
    aborted, ab_addr = _uv5r_auxfirst_write(rclass, port, image)
    if aborted:
        log("ABORTADO: NACK após retries em/wire 0x%04X" % (ab_addr or 0))
    time.sleep(UV5R_AUX_FIRST_COOLDOWN)

    # 3) re-download de verificação
    post = _uv5r_auxfirst_dump(rclass, port)
    sha_new = sha256_hex(post)
    if aborted:
        diffs = None  # gravação incompleta: sem diff confiável
        preserve_diffs = None
    else:
        diffs = [i for i in range(8, UV5R_AUX_FIRST_IMAGE_END)
                 if post[i] != image[i]
                 and not any(lo <= i < hi for lo, hi in
                             UV5R_UPLOAD_SKIP_IMAGE_OFFSETS)]
        # divergências nas faixas "preserve" (não gravadas pelo driver,
        # ex.: gaps de proteção) — informativo, não falha o restore
        preserve_diffs = [
            (lo, hi) for lo, hi in UV5R_UPLOAD_SKIP_IMAGE_OFFSETS
            if post[lo:hi] != image[lo:hi]]
        if post[:8] != pre[:8]:
            log("AVISO: ident pós-gravação difere do prévio (anômalo)")

    paths = [None, None]
    if backup:
        fw_backup_dir_impl = fw_backup_dir()
        os.makedirs(fw_backup_dir_impl, exist_ok=True)
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = "%s_RESTORE_%s.bin" % (directory.get_driver(rclass), stamp)
        base = os.path.join(fw_backup_dir_impl, name)
        paths[0] = base.replace(".bin", "_pre_%s.bin" % sha_old[:8])
        paths[1] = base.replace(".bin", "_post_%s.bin" % sha_new[:8])
        with open(paths[0], "wb") as f:
            f.write(pre)
        with open(paths[1], "wb") as f:
            f.write(post)
        meta = _dump_info(rclass, port, pre, datetime.datetime.now())
        meta["note"] = "dump ANTES de restore_bom5701_image"
        _write_sidecar(meta, paths[0])
        meta["note"] = "dump DEPOIS de restore_bom5701_image"
        meta["sha256"] = sha_new
        meta["size"] = len(post)
        _write_sidecar(meta, paths[1])

    return RestoreReport(
        ok=not aborted and diffs == [], aborted=aborted,
        aborted_addr=ab_addr, sha_old=sha_old, sha_new=sha_new,
        diffs=diffs, preserve_diffs=preserve_diffs,
        pre_path=paths[0], post_path=paths[1])


def restore_image(radio_id, port, image, backup=True):
    """Dispatch de restore pela família de protocolo de @radio_id.

    h777 (PROGRAM_CMD == b'PROGRAM'): restore_h777_image (janela 992 B
    1:1). UV-5R-aux-first (_aux_first + _aux_block, ex. BOM-5701):
    restore_bom5701_image (0x1948, X-frame 16 B, aux→main). Demais
    famílias: recusa clara (escrita ainda não validada).
    """
    rclass = resolve_rclass(radio_id)
    if getattr(rclass, "PROGRAM_CMD", None) == H777_PROGRAM_CMD:
        return restore_h777_image(radio_id, port, image, backup=backup)
    if getattr(rclass, "_aux_first", False) and \
            getattr(rclass, "_aux_block", False):
        return restore_bom5701_image(radio_id, port, image, backup=backup)
    raise FwDumpError(
        "família de protocolo do driver %s não tem escrita validada "
        "(famílias suportadas: h777, UV-5R-aux-first/BOM-5701; "
        "escrita nova = fase de RE própria)" % radio_id)


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
