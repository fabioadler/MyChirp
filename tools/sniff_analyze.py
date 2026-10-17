#!/usr/bin/env python3
"""sniff_analyze.py — resumo de uma captura do serialsniff (console.txt).

Sumariza as transações por lado (A=wine/CPS, B=rádio real), membros
write/read agrupados por transação (grupos separados por silêncio) e
os pedidos de leitura "R <addr_hi> <addr_lo> <size>" / "S..." do
protocolo de clone — imprimindo o mapa do que a CPS de fato lê/escreve.

Uso: tools/sniff_analyze.py tools/cps/cap/console.txt [--raw A.bin]
"""
import re
import sys

HEXHDR = re.compile(r"^(A|B) (\d+):")
HEXBYTE = re.compile(r"[0-9a-fA-F]{2}")


def load_text(path):
    """Chunks (side, bytes) — agrupa as linhas de hexdump sob cada header
    'A N:'/'B N:'; pad acima do fim usa '--' e é ignorado."""
    chunks = []
    side, expect = None, 0
    buf = bytearray()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            m = HEXHDR.match(line)
            if m:
                if side is not None and buf:
                    chunks.append((side, bytes(buf)))
                side, expect = m.group(1), int(m.group(2))
                buf = bytearray()
                continue
            if side is None:
                continue
            # linha de hexdump: pares hex separados por espaço a cada 4
            hexs = re.sub(r"(?i)^(?!\-|-)", "", line.strip())
            toks = [t for t in re.split(r"\s+", line) if t]
            for t in toks:
                if "--" in t:
                    continue
                for b in HEXBYTE.findall(t):
                    buf.append(int(b, 16))
    if side is not None and buf:
        chunks.append((side, bytes(buf)))
    return chunks


def describe(data):
    """Classifica frame de clone h777/uv5r: R/S/X/W/exercício/crack."""
    if not data:
        return "empty"
    b0 = data[0]
    printable = all(32 <= b < 127 for b in data)
    if printable and len(data) >= 4:
        return "ascii %r" % data[:24].decode()
    if b0 == ord("R") and len(data) == 4:
        return "READ  addr=0x%04X size=0x%X" % (
            (data[1] << 8) | data[2], data[3])
    if b0 == ord("S") and len(data) == 4:
        return "REQ   addr=0x%04X size=0x%X" % (
            (data[1] << 8) | data[2], data[3])
    if b0 == ord("X") and len(data) >= 4:
        return "DATA  addr=0x%04X size=0x%X" % (
            (data[1] << 8) | data[2], data[3])
    if b0 == ord("W") and len(data) >= 4:
        return "WRcmd addr=0x%04X size=0x%X" % (
            (data[1] << 8) | data[2], data[3])
    if b0 == 0x06 and len(data) == 1:
        return "ACK"
    if b0 == 0x15:
        return "NAK"
    if b0 == 0x02:
        return "DIR cute ident trigger 0x02"
    return "raw %s (%d)" % (data[:8].hex(), len(data))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    chunks = load_text(path)
    if not chunks:
        print("Sem dados parseáveis em %s" % path)
        return 1

    counts = {"A": 0, "B": 0}
    bytes_side = {"A": 0, "B": 0}
    for side, data in chunks:
        counts[side] += 1
        bytes_side[side] += len(data)
    print("Chunks: A=%d (%d B)  B=%d (%d B)" % (
        counts["A"], bytes_side["A"], counts["B"], bytes_side["B"]))

    # grupo de transação: quebra quando o lado muda
    last = None
    shown = {"A": 0, "B": 0}
    for side, data in chunks:
        if side != last:
            shown = {"A": 0, "B": 0}
            print("\n[%s]" % ("CPS(wine)" if side == "A" else "RÁDIO"))
            last = side
        shown[side] += 1
        if shown[side] <= 40:
            print("  %s" % describe(data))
        elif shown[side] == 41:
            print("  ... (+%d no lado %s)" % (counts[side] - 40, side))
    return 0


if __name__ == "__main__":
    sys.exit(main())
