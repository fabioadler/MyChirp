"""Testes do restore de firmware (escrita validada W1) na janela clone.

Serial simulada combinada com tools/roundtrip_noop.py — o script
validado em hardware no BF-777S em 2026-10-17 (sha 4d8db228: 124
blocos ACK + re-leitura idêntica). O fake implementa/exige o MESMO
protocolo: enter PROGRAM → ident → ACK → blocos `W` com ACK 0x06 →
re-leitura → 'E' fecha (responde 'F' / 0x46).
"""

import struct

import pytest

from mychirp import fwtool
from mychirp.fwtool import (
    H777_PROGRAM_CMD,
    H777_WINDOW_END,
    restore_h777_image,
)

BLOCK = 8


class FakeH777:
    """Serial simulada com o protocolo h777 (leitura por 8 B e escrita
    'W' com ACK). Memória simulada de 992 B com padrão sintético."""

    IDENT = b"P3107\xf7\x00\x00"

    def __init__(self, initial_bytes=None, fail_write_at=None):
        self.mem = bytearray(H777_WINDOW_END)
        for i in range(H777_WINDOW_END):
            # padrão de fábrica sintético: zonas identificáveis
            self.mem[i] = i % 0x100 if i < 0x0110 else 0xFF
        if initial_bytes is not None:
            self.mem[:len(initial_bytes)] = initial_bytes
        self.fail_write_at = fail_write_at
        self.writes_done = []
        self.enters = 0
        self.in_program = False
        self.addr = 0  # cursor da última leitura/escrita por 8 B
        self._rx = b""
        self._await_ping = False  # 1º 0x02 antes do PROGRAM
        self._await_ident = False  # 2º 0x02 pós-ACK

    # ----- serial API (subset) -----
    timeout = 0.25

    def write(self, data):
        if data == b"\x02":
            if self.in_program:
                # 2º ping de dentro da sessão (ident/echo)
                self._await_ident = True  # ou responder ident
                self._rx = self.IDENT
                return len(data)
            self._await_ping = True
            self._rx = b""
            return len(data)
        if data == H777_PROGRAM_CMD and self._await_ping:
            self.in_program = True
            self.enters += 1
            self._rx = b"\x06"
            self._await_ping = False
            return len(data)
        if self.in_program and len(data) == 1:
            op = data
            if op == b"\x06":
                # ACK do cliente após leitura/ident → limpa
                self._rx = b""
                return 1
            if op == b"E":
                self.in_program = False
                self._rx = b"F"  # 0x46, como no hardware real
                return 1
        if self.in_program and len(data) == 4 and data[:1] == b"R":
            addr = struct.unpack(">H", data[1:3])[0]
            count = data[3]
            self._rx = b"W" + data[1:3] + bytes([count]) + \
                bytes(self.mem[addr:addr + count])
            return len(data)
        if self.in_program and data[:1] == b"W" and len(data) == 4 + 8:
            addr = struct.unpack(">H", data[1:3])[0]
            count = data[3]
            payload = data[4:4 + count]
            if self.fail_write_at is not None and \
                    addr >= self.fail_write_at:
                self._rx = b"\x15"  # NACK
                return len(data)
            self.mem[addr:addr + count] = payload
            self.writes_done.append(addr)
            self._rx = b"\x06"
            return len(data)
        self._rx = b""
        return len(data)

    def read(self, n=1):
        out, self._rx = self._rx[:n], self._rx[n:]
        return out

    def close(self):
        pass


def fake_serial_factory(fail_write_at=None, initial=None):
    fake = FakeH777(initial_bytes=initial, fail_write_at=fail_write_at)

    class _Factory:
        def __call__(self, port, rclass):
            return fake

        def __enter__(self):
            return fake

        def __exit__(self, *a):
            return False

    return _Factory(), fake


@pytest.fixture
def patch_open_serial(monkeypatch):
    def _install(fail_write_at=None, initial=None):
        factory, fake = fake_serial_factory(fail_write_at, initial)
        monkeypatch.setattr("mychirp.serial_link.open_serial",
                            lambda port, rclass: fake)
        return fake
    return _install


def test_rejeita_tamanho_errado(patch_open_serial):
    with pytest.raises(fwtool.FwDumpError) as e:
        restore_h777_image("Baofeng_BF-777S", "/dev/FAKE", b"\x00" * 991)
    assert "992" in str(e.value)


def test_roundtrip_noop_dif_zero(patch_open_serial):
    """Escrita dos MESMOS bytes lidos → 124 blocos ACK + diff vazio
    (o cenário W1 validado em hardware @4d8db228)."""
    fake = patch_open_serial()
    image = bytes(fake.mem)
    assert len(image) == H777_WINDOW_END
    rep = restore_h777_image("Baofeng_BF-777S", "/dev/FAKE", image)
    assert rep["ok"] is True
    assert rep["diffs"] == []
    assert rep["aborted"] is None
    assert len(fake.writes_done) == 124
    assert rep["sha_old"] == rep["sha_new"]
    assert rep["pre_path"].startswith(
        fwtool.fw_backup_dir())
    assert rep["post_path"].startswith(
        fwtool.fw_backup_dir())


def test_write_real_mem_changed(patch_open_serial):
    """Escrita de imagem DIFERENTE: memória simulada passa a ter os
    bytes da imagem (100% ACK) e a re-leitura reflete a mudança."""
    fake = patch_open_serial()
    image = bytes((0xAA if i % 2 else 0x55
                   for i in range(H777_WINDOW_END)))
    rep = restore_h777_image("Baofeng_BF-777S", "/dev/FAKE", image)
    assert rep["ok"] is True and rep["diffs"] == []
    assert fake.mem == bytearray(image)  # escrita efetiva na memória
    assert rep["sha_old"] != rep["sha_new"]  # mudou algo de fato


def test_aborto_nack_em_meio(patch_open_serial, tmp_path):  # noqa: ARG001
    """NACK no meio da escrita: report aborted e NÂO faz diff (o
    comportamento do hardware real exige religar o rádio)."""
    fake = patch_open_serial(fail_write_at=0x0200)
    image = bytes((i % 251 for i in range(H777_WINDOW_END)))
    rep = restore_h777_image("Baofeng_BF-777S", "/dev/FAKE", image)
    assert rep["ok"] is False
    assert rep["aborted"] == 0x0200
    assert rep["diffs"] is None  # sem diff confiável quando aborta
    # blocos antes do NACK foram gravados, depois NÃO
    assert 0x0100 in fake.writes_done
    assert 0x0208 not in fake.writes_done


def test_non_h777_driver_recusado(patch_open_serial):
    """Driver de outra família (sem PROGRAM_CMD == b'PROGRAM') não é
    aceito pelo restore."""
    from mychirp import directory
    directory.import_drivers()
    plain = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if getattr(r, "PROGRAM_CMD", None) != H777_PROGRAM_CMD),
        None)
    if plain is None:
        pytest.skip("sem driver de outra família registrado")
    other_id = None
    for k, v in directory.DRV_TO_RADIO.items():
        if v is plain:
            other_id = k
            break
    fake = patch_open_serial()
    with pytest.raises(Exception):
        restore_h777_image(other_id, "/dev/FAKE", b"\x00" * 992)
