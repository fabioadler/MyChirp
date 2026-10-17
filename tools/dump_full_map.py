#!/usr/bin/env python3
"""Varre TODO o espaço endereçável que o firmware responder (R-frames),
dobrando o mapa do clone oficial (992 B → +0x8000+).

Read-only: usa apenas R + ACK, como o driver h777. Salva binário + meta
e imprime o mapa de regiões não-uniformes (candidatas a dados de voz/
tabelas de fábrica), com checagem cruzada contra o dump oficial.
"""
import struct
import sys
import time
import hashlib
import yaml  # noqa: F401  (meta igual fwtool)

sys.path.insert(0, ".")
from mychirp import serial_link  # noqa: E402
from mychirp import fwtool  # noqa: E402

CMD_ACK = b"\x06"


def _rx(serial, n, timeout=0.25):
    serial.timeout = timeout
    return serial.read(n)


def enter_prog(serial, rclass):
    serial.timeout = 0.5
    serial.write(b"\x02")
    time.sleep(0.05)
    serial.write(rclass.PROGRAM_CMD)
    ack = _rx(serial, 1, 0.5)
    if ack != CMD_ACK:
        raise RuntimeError("radio não entrou em PROGRAM (ack %r)" % ack)
    serial.write(b"\x02")
    ident = _rx(serial, 8, 0.7)
    serial.write(CMD_ACK)
    _rx(serial, 1, 0.5)
    return ident


def read_block(serial, addr, size=0x40, tries=2):
    cmd = struct.pack(">cHB", b"R", addr, size)
    for attempt in range(tries):
        serial.write(cmd)
        # 9600 bps: ~1 ms/byte (10 bits/B) + margem de processamento
        serial.timeout = 0.15 + size * 0.002 + attempt * 0.2
        resp = serial.read(4 + size)
        if resp[:1] == b"W" and resp[1:4] == cmd[1:] and len(resp) == 4 + size:
            serial.write(CMD_ACK)
            _rx(serial, 1, 0.15)
            return resp[4:]
    return None


def main():
    port, radio_id = sys.argv[1], sys.argv[2]
    rclass = fwtool.resolve_rclass(radio_id)
    if not hasattr(rclass, "PROGRAM_CMD"):
        rclass = rclass.__class__

    serial = serial_link.open_serial(port, rclass)
    ident = enter_prog(serial, rclass)
    print("ident:", ident.hex())

    # sanity + tamanho máximo aceito (JÁ validado: 8-B é o único seguro;
    # 0xC0+ returna lixo no handler — ver rethink 8.4/8.6)
    block = 8
    print("usando size=0x02XX: bloqueio 8-B (seguro, validado)")

    out = bytearray()
    fmt = lambda a: "0x%04X" % a
    t0 = time.time()
    addr = 0
    bad = []
    TOP = 0x8000
    while addr < TOP:
        data = read_block(serial, addr, block, tries=2)
        if data is None:
            # resync: drena restos de W-frame antigo e refaz bloco em 8 B
            serial.timeout = 0.05
            serial.read(4096)
            time.sleep(0.1)
            bad.append(fmt(addr))
            out += b"\x00" * block
        else:
            out += data
        addr += block
        if (addr % 0x400) == 0:
            el = time.time() - t0
            print("  %s ok (%.1fs, %d ruins)" % (
                fmt(addr), el, len(bad)))

    # probe do topo: 0x8000..0x10000 (8 B) — para HÁ Malha entre nós quem
    top_hits = []
    for addr in range(0x8000, 0x10000, 0x400):
        d = read_block(serial, addr, 8, tries=1)
        if d is not None:
            top_hits.append((fmt(addr), d.hex()))
    print("topo (>0x8000):", top_hits if top_hits else "nada responde")

    serial.write(b"E")
    time.sleep(0.2)
    serial.close()

    out = bytes(out)
    path = "/home/f/.chirp/fw-backups/%s_MAPFULL_8B.bin" % radio_id
    open(path, "wb").write(out)
    sha = hashlib.sha256(out).hexdigest()
    print("salvo:", path, len(out), "B sha256:", sha)
    print("endereços ruins:", bad[:20], "… total", len(bad))

    # mapa de regiões por uniformidade
    def kind(b):
        if all(x == 0x00 for x in b):
            return "00"
        if all(x == 0xFF for x in b):
            return "FF"
        return "data"
    prev = None
    start = 0
    print("\n-- mapa de regiões:")
    regions = []
    for i in range(0, len(out), 0x800):
        k = kind(out[i:i + 0x800])
        if prev is None:
            prev, start = k, i
        elif k != prev:
            regions.append((start, i, prev))
            prev, start = k, i
    regions.append((start, len(out), prev))
    for s, e, k in regions:
        print("  %s-%s: %s" % (fmt(s), fmt(e), k))

    # verificação cruzada: bytes 0x0000-0x3E0 vs dump oficial (se existir)
    try:
        ref = open(sys.argv[3], "rb").read()
        same = all(out[i] == ref[i] for i in range(min(len(ref), 0x3E0)))
        print("cross-check com %s: %s" % (sys.argv[3],
              "IDÊNTICO" if same else "DIFERE!"))
    except (IndexError, OSError):
        pass


if __name__ == "__main__":
    main()
