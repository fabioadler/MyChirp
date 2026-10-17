#!/usr/bin/env python3
"""Round-trip no-op (família h777/BF-777S): grava de volta EXATAMENTE os
bytes lidos — valida a via de escrita sem alterar nada funcionalmente.

PROTOCOLO de gravação idêntico ao driver validado (`_h777_write_block`):
frame `W` (b'W' + addr u16 BE + size i8) + 8 bytes de dados; espera
ACK 0x06. Qualquer NACK/timeout = ABORTO imediato, sem retry agressivo,
seguido de `E` (exit).

Fluxo: enter → ler 0x0000-0x03E0 (passo 8) → sha → gravar os MESMOS
bytes → exit → re-enter → re-ler → diff byte a byte → relatório.

Uso (só com DUMPLA confirmação humana!):
    python tools/roundtrip_noop.py /dev/ttyUSB0
"""
import hashlib
import struct
import sys
import time

sys.path.insert(0, ".")
import serial as _ser  # noqa: E402

CMD_ACK = b"\x06"
BLOCK = 8
END = 0x03E0  # janela do clone padrão h777 (992 B)


def enter(serial):
    """Handshake PROGRAM da família h777 (igual _h777_enter_programming_mode)."""
    serial.write(b"\x02")
    time.sleep(0.1)
    serial.write(b"PROGRAM")
    ack = serial.read(1)
    if ack != CMD_ACK:
        raise RuntimeError("PROGRAM ack=%r" % (ack,))
    serial.write(b"\x02")
    ident = serial.read(8)
    if not ident:
        raise RuntimeError("ident vazio")
    serial.write(CMD_ACK)
    serial.read(1)
    return ident


def rd8(serial, addr):
    cmd = struct.pack(">cHb", b"R", addr, BLOCK)
    serial.write(cmd)
    serial.timeout = 0.25
    resp = serial.read(4 + BLOCK)
    if resp[:1] != b"W" or resp[1:4] != cmd[1:4] or len(resp) != 4 + BLOCK:
        return None
    serial.write(CMD_ACK)
    serial.read(1)
    return resp[4:]


def wr8(serial, addr, data):
    """Frame de escrita idêntico ao _h777_write_block validado."""
    cmd = struct.pack(">cHb", b"W", addr, BLOCK)
    serial.write(cmd + data)
    serial.timeout = 0.5  # gravação pode levar até ~0,31 s (obs. do driver)
    ack = serial.read(1)
    return ack == CMD_ACK


def read_all(serial):
    out = bytearray()
    for addr in range(0, END, BLOCK):
        d = rd8(serial, addr)
        if d is None:
            return None, addr
        out += d
    return bytes(out), None


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    image = None
    if len(sys.argv) > 2 and sys.argv[2] != "-":
        # modo "write-only": grava o arquivo lido recentemente do MESMO
        # rádio (replica do_upload do driver: entra e escreve, sem pré-
        # leitura na mesma sessão)
        image = open(sys.argv[2], "rb").read()
        assert len(image) == END, "arquivo deve ter %d B" % END
        print("modo write-only de:", sys.argv[2])

    serial = _ser.Serial(port, 9600, timeout=0.5)
    serial.setDTR(True)
    serial.setRTS(True)
    serial.read(4096)  # drain

    ident = enter(serial)
    if image is None:
        # leitura fresca (backup vivo na própria sessão)
        image, fail = read_all(serial)
        if image is None:
            serial.write(b"E")
            raise SystemExit("ABORTADO na leitura em 0x%04X" % fail)
        print("sessão de leitura concluída; re-entrando…")
        serial.write(b"E")
        time.sleep(1.0)
        serial.read(4096)
        ident = enter(serial)
    sha = hashlib.sha256(image).hexdigest()
    print("ident:", ident.hex())
    print("alvo a gravar: %d B sha256: %s" % (len(image), sha[:16]))

    # 2) gravação dos MESMOS bytes (no-op)
    print("gravação no-op iniciada…")
    falhas = []
    for addr in range(0, END, BLOCK):
        data = image[addr:addr + BLOCK]
        if not wr8(serial, addr, data):
            falhas.append(addr)
            print("ABORTADO: NACK/timeout em 0x%04X" % addr)
            serial.write(b"E")
            raise SystemExit(2)
        if (addr % 0x100) == 0:
            print("  gravado até 0x%04X" % (addr + BLOCK))
    serial.write(b"E")
    time.sleep(0.3)
    print("gravação concluída: %d blocos" % (END // BLOCK))

    # 3) re-entrada + re-leitura completa para validação
    serial.read(4096)
    time.sleep(0.3)
    ident2 = enter(serial)
    check, fail = read_all(serial)
    serial.write(b"E")
    if check is None:
        raise SystemExit("re-leitura falhou em 0x%04X" % fail)
    sha2 = hashlib.sha256(check).hexdigest()
    iguais = check == image
    print("re-ler: sha256:", sha2[:16], "| idêntico:", iguais)
    if not iguais:  # não deve ACONTECER: escrevemos os mesmos bytes
        diffs = [i for i in range(END) if image[i] != check[i]]
        print("!!! divergências encontradas: primeira 0x%04X" % diffs[0])
        for i in diffs[:10]:
            print("   0x%04X: gravado=%02X agora=%02X" % (
                i, image[i], check[i]))
    print("\nRESULTADO:", "ROUND-TRIP OK (0 divergências)" if iguais
          else "ROUND-TRIP FALHOU")


if __name__ == "__main__":
    main()
