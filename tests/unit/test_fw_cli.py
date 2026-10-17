"""mychirp-fw: testes do dump de memória (fwtool + CLI).

Estratégia: serial falsa implementando a sessão de clone de um rádio da
família H777/BF-888S (ident do BF-777S), com o driver REAL
BaofengBF777SRadio — cobra o caminho completo resolve_rclass -> sync_in
-> .bin + YAML sidecar, sem hardware.
"""

import os
import struct

import pytest

import builtins

builtins._ = lambda s: s  # noqa — drivers usam _() carregado pelo CLI

from mychirp import chirp_common, directory, fwtool  # noqa: E402

F777_ID = "BAOFENG_BF-777S"

# Imagem crua simulada (0x3E0 = memsize do H777Radio), padrão tipado
FAKE_IMAGE = (
    bytes(range(256)) * 4 +          # 0x0000-0x03FFish — dados variados
    b"\xff" * 1024)[:0x3E0]


class FakeH777Serial:
    """Serial falsa que responde o protocolo h777 (BF-777S, 9600 bd)."""

    def __init__(self, image=FAKE_IMAGE):
        self.image = image
        self.timeout = 0.25
        self.rts = True
        self.dtr = True
        self._rx = b""
        self._ident_pending = False
        self.closed = False

    def log(self, message):
        pass

    def flush(self):
        pass

    def open(self):
        pass

    def close(self):
        self.closed = True

    def _queue(self, data):
        self._rx += data

    def write(self, data):
        if data == b"\x02":
            if self._ident_pending:
                # segunda injeção de 0x02: o rádio responde o ident (8 B)
                self._queue(b"P3107\xff\x00\x00")
                self._ident_pending = False
        elif data == b"PROGRAM":
            # CMD_PROGRAM -> ACK p/ ser consumido no read(1) seguinte
            self._queue(b"\x06")
            self._ident_pending = True
        elif data == b"E":
            pass  # exit programming mode
        elif data[:1] == b"R":
            addr, size = struct.unpack(">Hb", data[1:4])
            self._queue(b"W" + data[1:] + self.image[addr:addr + size])
        elif data == b"\x06":
            self._queue(b"\x06")  # ACK eco (sentinel do protocolo)
        else:  # pragma: no cover
            raise AssertionError("unexpected write %r" % data)
        return len(data)

    def read(self, count=1):
        data, self._rx = self._rx[:count], self._rx[count:]
        return data


@pytest.fixture
def bf777s_serial(monkeypatch):
    """open_serial da serial_link devolve nossa serial falsa."""
    fake = FakeH777Serial()

    def fake_open_serial(port, rclass):
        return fake

    monkeypatch.setattr("mychirp.serial_link.open_serial", fake_open_serial)
    return fake


def test_all_baofeng_registered_are_clonable():
    """F0: TODO rádio Baofeng do directory é CloneModeRadio e, portanto,
    dumpável pelo mychirp-fw; catalog lines >= 50 (evita regressão
    silenciosa na contagem de drivers)."""
    directory.import_drivers()
    baofeng = [(ident, rclass) for ident, rclass in directory.DRV_TO_RADIO.items()
               if rclass.VENDOR == "Baofeng"]
    assert len(baofeng) >= 50, "catálogo Baofeng encolheu?"
    for ident, rclass in baofeng:
        assert issubclass(rclass, chirp_common.CloneModeRadio), \
            "%s não é CloneModeRadio" % ident


def test_resolve_rclass_case_insensitive():
    assert fwtool.resolve_rclass(F777_ID) is not None
    lower = fwtool.resolve_rclass("baofeng_bf-777s")
    assert lower.__name__ == "BaofengBF777SRadio"


def test_resolve_unknown_raises():
    with pytest.raises(fwtool.FwDumpError):
        fwtool.resolve_rclass("BAOFENG_NAOEXISTE")


def test_dump_clone_writes_bin_and_yaml(bf777s_serial, tmp_path, monkeypatch):
    out = str(tmp_path / "dump.bin")
    path = fwtool.dump_clone(F777_ID, "/dev/fake",
                             out=out, backup=False)
    assert path == out
    with open(path, "rb") as f:
        data = f.read()
    assert data == FAKE_IMAGE
    assert len(data) == 0x3E0
    # serial fechada pelo dump
    assert bf777s_serial.closed
    yaml_path = out[:-4] + ".yaml"
    assert os.path.exists(yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        meta = f.read()
    assert "sha256" in meta
    assert fwtool.sha256_hex(FAKE_IMAGE) in meta
    assert "BF-777S" in meta
    assert "9600" in meta


def test_dump_clone_backup_dir(bf777s_serial, tmp_path, monkeypatch):
    bdir = str(tmp_path / "fw-backups")
    monkeypatch.setattr(fwtool, "DEFAULT_BACKUP_DIR", bdir)
    path = fwtool.dump_clone(F777_ID, "/dev/fake", backup=True)
    assert os.path.dirname(path) == bdir
    base = os.path.basename(path)
    # nome assinado: BAOFENG_BF-777S_<sha8>_<data>.bin
    assert base.startswith("Baofeng_BF-777S_")
    assert fwtool.sha256_hex(FAKE_IMAGE)[:8] in base
    assert base.endswith(".bin")


def test_dump_clone_requires_serial():
    with pytest.raises(fwtool.FwDumpError):
        fwtool.dump_clone(F777_ID, None)


def test_diff_files_identical(tmp_path):
    a_path = str(tmp_path / "a.bin")
    b_path = str(tmp_path / "b.bin")
    with open(a_path, "wb") as f:
        f.write(FAKE_IMAGE)
    with open(b_path, "wb") as f:
        f.write(FAKE_IMAGE)
    _, _, ranges = fwtool.diff_files(a_path, b_path)
    assert ranges == []
    text = fwtool.format_diff(ranges, len(FAKE_IMAGE), len(FAKE_IMAGE))
    assert "idênticos" in text.lower()


def test_diff_files_detect_changes(tmp_path):
    a = bytearray(FAKE_IMAGE)
    a[0x10] ^= 0xFF
    a[0x210] ^= 0xFF
    a[0x211] ^= 0xFF
    a_path = str(tmp_path / "a.bin")
    b_path = str(tmp_path / "b.bin")
    with open(a_path, "wb") as f:
        f.write(bytes(a))
    with open(b_path, "wb") as f:
        f.write(FAKE_IMAGE)
    _, _, ranges = fwtool.diff_files(a_path, b_path)
    starts = [r[0] for r in ranges]
    assert 0x10 in starts
    assert 0x210 in starts
    # de 0x210 a 0x212 é uma faixa contínua (2 bytes)
    assert [r for r in ranges if r[0] == 0x210][0][2] is not None
    text = fwtool.format_diff(ranges, len(a), len(FAKE_IMAGE))
    assert "0x000010" in text or "0x000010" in text


def test_diff_files_size_mismatch(tmp_path):
    a_path = str(tmp_path / "a.bin")
    b_path = str(tmp_path / "b.bin")
    with open(a_path, "wb") as f:
        f.write(FAKE_IMAGE)
    with open(b_path, "wb") as f:
        f.write(FAKE_IMAGE[:100])
    _, _, ranges = fwtool.diff_files(a_path, b_path)
    assert any(r[2] is None for r in ranges)  # marcador de tamanho
