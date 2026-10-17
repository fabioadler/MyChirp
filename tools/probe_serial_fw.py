#!/usr/bin/env python3
"""Sondador read-only do protocolo serial de rádios legacy (h777 family).

Descobre se o firmware do rádio responde a comandos além do clone
oficial (EEPROM 992 B), sem escrever NADA:

  1. ident (PROGRAM handshake)
  2. leituras R além do fim da EEPROM (0x3E0..0x7000) — se o firmware
     mapear mais memória, essas leituras respondem W-frame
  3. tamanhos de bloco maiores (16/32/64) em 0x0000
  4. comandos desconhecidos (1 byte + strings) — captura respostas
  5. tentativa de boot-mode 0xA5 (família UV-5R/UV-17 — improvável aqui)

Uso: venv/bin/python tools/probe_serial_fw.py /dev/ttyUSB0 "Intelbras_RC_3002_G2"
Saída: relatório no stdout + raw hexdump no ~/.chirp/debug.log.
"""
import struct
import sys
import time

sys.path.insert(0, ".")
from mychirp import serial_link  # noqa: E402
from mychirp.drivers import h777  # noqa: E402
from mychirp import directory  # noqa: E402

CMD_ACK = b"\x06"


def _rx(serial, n, timeout=0.4):
    serial.timeout = timeout
    return serial.read(n)


def describe(resp):
    if not resp:
        return "timeout/vazio"
    if resp == CMD_ACK:
        return "ACK 0x06"
    if resp[:1] == b"W" and len(resp) >= 4:
        addr, size = struct.unpack(">Hb", resp[1:4])
        return "W-frame addr=0x%04X size=0x%X (%d B dados)" % (
            addr, size, len(resp) - 4)
    return "%d B: %s" % (len(resp), resp[:16].hex())


def enter_prog(serial, rclass):
    serial.timeout = 0.5
    serial.write(b"\x02")
    time.sleep(0.05)
    serial.write(rclass.PROGRAM_CMD)
    ack = _rx(serial, 1, 0.5)
    if ack != CMD_ACK:
        return None
    serial.write(b"\x02")
    ident = _rx(serial, 8, 0.7)
    if not ident:
        return None
    serial.write(CMD_ACK)
    _rx(serial, 1, 0.5)
    return ident


def try_read(serial, addr, size=8):
    cmd = struct.pack(">cHb", b"R", addr, size)
    serial.write(cmd)
    resp = _rx(serial, 4 + size, 0.4)
    ok = resp and resp[:1] == b"W" and resp[1:4] == cmd[1:] and \
        len(resp) == 4 + size
    if ok:
        serial.write(CMD_ACK)
        _rx(serial, 1, 0.3)
    return resp, bool(ok)


def main():
    port, radio_id = sys.argv[1], sys.argv[2]
    rclass = directory.get_radio(radio_id)
    if not hasattr(rclass, "PROGRAM_CMD"):
        rclass = rclass.__class__

    serial = serial_link.open_serial(port, rclass)
    print("== sondagem %s em %s" % (radio_id, port))

    ident = enter_prog(serial, rclass)
    print("1. ident:", describe(ident) if ident else "FALHOU (tentativa 2 de programa)")

    # sanity: bloco conhecido
    resp, ok = try_read(serial, 0x0000)
    print("2. sanity 0x0000/8:", describe(resp), "OK" if ok else "FALHOU")

    # além do fim da EEPROM
    probes = list(range(0x3E0, 0x840, 8))
    probes += list(range(0x1000, 0x7100, 0x200))
    hits = []
    for addr in probes:
        resp, ok = try_read(serial, addr)
        if ok:
            hits.append((addr, resp))
    if hits:
        print("3. LEITURAS além de 0x3E0 que responderam:",
              [(hex(a), r[:12].hex()) for a, r in hits])
    else:
        print("3. 64+ sondas além de 0x3E0: nenhuma resposta (EOF do mapa)")

    # tamanhos maiores no bloco 0 (comporta read-loop do firmware)
    for size in (0x10, 0x20, 0x40):
        resp, ok = try_read(serial, 0x0000, size)
        print("4. leitura 0x0000 size=0x%X:" % size, describe(resp))

    # comandos desconhecidos (nunca 'W': é escrita!)
    for cmd in (b"E", b"V", b"?", b"I", b"F", b"\xA5", b"U`\x00\xff",
                b"F\x00\x00\x08", b"R\x00\x00\x18"):
        serial.write(cmd)
        print("5. comando %r:" % cmd, describe(_rx(serial, 12, 0.35)))

    # sair limpo
    serial.write(b"E")
    time.sleep(0.2)
    print("6. exit 'E' enviado")
    serial.close()


if __name__ == "__main__":
    main()
