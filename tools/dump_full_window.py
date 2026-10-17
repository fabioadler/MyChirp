#!/usr/bin/env python3
"""Dump da janela completa cabelada (radio addresses 0x0000-0x1FFF, 8 KiB)
do BOM-5701 (família UV-5R, quirk aux-primeiro).

DIFERENÇA para o clone oficial (0x1948): inclui a área de calibração de
fábrica 0x1800-0x1EC0, nunca coberta por CHIRP/CPS. Read-only; a ordem
respeita as regras da sessão (warm-up → gap → aux → main por último,
pois o main completo encerra a sessão — ver bom5701.py/uv5r.py).

Uso:
  python tools/dump_full_window.py /dev/ttyUSB0 ["BOMVINK BOM-5701"]
Salva em ~/.chirp/fw-backups/<driver>_FULLWINDOW_8K.bin + YAML sidecar.
"""
import datetime
import sys

sys.path.insert(0, ".")
from mychirp import directory, fwtool  # noqa: E402
from mychirp.serial_link import open_serial  # noqa: E402


def main():
    port = sys.argv[1]
    radio_id = sys.argv[2] if len(sys.argv) > 2 else "BOMVINK_BOM-5701"
    rclass = fwtool.resolve_rclass(radio_id)
    if not hasattr(rclass, "download_full_window"):
        raise SystemExit("driver %s não tem download_full_window" % radio_id)

    pipe = open_serial(port, rclass)
    try:
        radio = rclass(pipe)

        def status(addr):
            print("  lido até 0x%04X" % addr)

        print("identificando (aux-primeiro, sessão nova precisa de "
              "rádio religado; ~20 s de cooldown entre sessões)...")
        data = radio.download_full_window(status_fn=status)
    finally:
        try:
            pipe.close()
        except Exception:
            pass

    ts = datetime.datetime.now()
    name = directory.get_driver(rclass)
    path = "/home/f/.chirp/fw-backups/%s_FULLWINDOW_8K_%s.bin" % (
        name, ts.strftime("%Y%m%d-%H%M%S"))
    import hashlib
    open(path, "wb").write(data)
    meta = fwtool._dump_info(rclass, port, data, ts)
    meta["note"] = ("8 KiB janela completa (0x0000-0x1FFF) via "
                    "download_full_window; inclui calibração "
                    "0x1800-0x1EC0 fora da imagem padrão")
    yaml_path = fwtool._write_sidecar(meta, path)
    sha = hashlib.sha256(data).hexdigest()
    print("salvo:", path, len(data), "B sha256:", sha[:16], "…")
    print("Meta  :", yaml_path)

    # análise rápida inline: regiões por uniformidade
    def kind(b):
        if all(x == 0x00 for x in b):
            return "00"
        if all(x == 0xFF for x in b):
            return "FF"
        return "data"
    prev = None
    start = 0
    print("\n-- mapa de regiões (janela de 0x80):")
    for i in range(0, len(data), 0x80):
        k = kind(data[i:i + 0x80])
        if prev is None:
            prev, start = k, i
        elif k != prev:
            print("  0x%04X-0x%04X: %s" % (start, i, prev))
            prev, start = k, i
    print("  0x%04X-0x%04X: %s" % (start, len(data), prev))


if __name__ == "__main__":
    main()
