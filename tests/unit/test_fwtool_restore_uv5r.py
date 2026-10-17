"""Testes do restore_bom5701_image (família UV-5R aux-first).

Fake serial no mesmo padrão do driver (test_bomvink_bom5701.py):
ident + frame X de 16 B com NACK na 1ª tentativa (janela de commit)
+ S-frame de leitura. O restore real usa a maquinaria DO PRÓPRIO
driver (sync_out), então o fake garante que o fluxo de 3 sessões do
fwtool conversa com o protocolo real (aux primeiro, remap endereços,
cooldown entre sessões).
"""

import struct

import pytest

from mychirp import fwtool
from mychirp.fwtool import (
    UV5R_AUX_FIRST_IMAGE_END,
    restore_bom5701_image,
    restore_image,
)

IDENT = b"\xaa\x30\x76\x04\x00\x05\x20\xdd"

MEM0 = (b"\x00\x20\x65\x14\x00\x20\x65\x14"
        b"\x00\x00\x00\x00\x00\x00\x00\x40")
MEM1 = (b"\x00\x25\x21\x46\x00\x25\x21\x46"
        b"\xb5\x02\xb5\x02\x00\x00\x00\x40")

BLOCK_1FC0 = (b"\xff" * 14 + b"\x00\x00\x1a\x00\x03\xc1\x01\x00\x01\xff"
              b"\x03\x6f\x03\xc1\x00\x00\x00\x00" + b"\x00" * 32)


def _build_main():
    main = bytearray(b"\xff" * 0x1800)
    main[0x0000:0x0010] = MEM0
    main[0x0010:0x0020] = MEM1
    return bytes(main)


def _build_aux():
    blocks = {
        0x1EC0: b"\xff" * 0x40,
        0x1F00: b"\xff" * 0x40,
        0x1F40: b"\xff" * 0x40,
        0x1F80: b"\xff" * 0x40,
        0x1FC0: BLOCK_1FC0,
    }
    aux = b""
    for addr in sorted(blocks):
        aux += blocks[addr]
    return aux


class _FakeBOM5701Core:
    """Serial fake (mesma lógica de test_bomvink_bom5701.FakeSerial,
    com gravação aplicada ao modelo de memória COMPARTILHADO entre
    as sessões (mutação no dict `model`) para o verify da sessão 3
    enxergar o que a sessão 2 gravou)."""

    def __init__(self, model, write_busy=True, reject_from=None):
        self.model = model
        self.write_busy = write_busy
        self.reject_from = reject_from  # wire addr a partir da qual NACK
        self.readbuf = b""
        self.wbuf = b""
        self.session_over = False
        self.first_s_command = True
        self.pending_secondack = False
        self.s_commands = []
        self.accepted_writes = []
        self.timeout = 1

    @property
    def main(self):
        return self.model["main"]

    @property
    def aux(self):
        return self.model["aux"]

    def _queue(self, data):
        self.readbuf += data

    def write(self, data):
        self.wbuf += data
        if self.wbuf == b"PROGRAM" or self.wbuf == \
                b"\x50\xBB\xFF\x20\x12\x07\x25":
            self.wbuf = b""
            if not self.session_over:
                self._queue(b"\x06")
            return
        if self.wbuf == b"\x02":
            self.wbuf = b""
            if not self.session_over:
                self._queue(IDENT)
                self.pending_secondack = True
            return
        if self.wbuf == b"\x06":
            self.wbuf = b""
            if self.pending_secondack and not self.session_over:
                self.pending_secondack = False
                self._queue(b"\x06")
            return
        if len(self.wbuf) >= 4 and self.wbuf[0:1] == b"X":
            _cmd, addr, size = struct.unpack(">BHB", self.wbuf[0:4])
            if len(self.wbuf) >= 4 + size:
                chunk = self.wbuf[4:4 + size]
                self.wbuf = b""
                if self.session_over:
                    return
                if self.reject_from is not None and addr < 0x1800 \
                        and addr >= self.reject_from:
                    self.reject_from = -1  # sempre NACK após esse
                    return
                if self.write_busy:
                    self.write_busy = False
                    return  # NACK de janela de commit
                self._queue(b"\x06")
                self.write_busy = True
                self.accepted_writes.append((addr, size, chunk))
                if addr < 0x1800:
                    self.model["main"] = \
                        self.model["main"][:addr] + chunk + \
                        self.model["main"][addr + size:]
                    if addr + size >= 0x1800:
                        self.session_over = True
                elif 0x1EC0 <= addr < 0x2000:
                    off = addr - 0x1EC0
                    self.model["aux"] = \
                        self.model["aux"][:off] + chunk + \
                        self.model["aux"][off + size:]
                return
        if len(self.wbuf) == 4 and self.wbuf[0:1] == b"S":
            _cmd, addr, size = struct.unpack(">BHB", self.wbuf)
            self.wbuf = b""
            self.s_commands.append((addr, size))
            if self.session_over:
                return
            if addr == 0x1E80:
                chunk = b"\xff" * size
            elif addr < 0x1800:
                chunk = self.model["main"][addr:addr + size]
                if addr + size >= 0x1800:
                    self.session_over = True
            elif addr >= 0x1EC0:
                chunk = self.model["aux"][addr - 0x1EC0:addr - 0x1EC0 + size]
            else:
                chunk = b"\xff" * size
            if not self.first_s_command:
                self._queue(b"\x06")
            self.first_s_command = False
            self._queue(b"X" + struct.pack(">HB", addr, size) + chunk)
            return

    def read(self, n):
        out, self.readbuf = self.readbuf[:n], self.readbuf[n:]
        return out

    def close(self):
        pass


@pytest.fixture
def patch_open_serial(monkeypatch):
    """Instala uma fábrica de pipes: CADA chamada de open_serial
    (sessão) recebe um fake NOVO com o mesmo modelo de memória."""
    def _install(drawn_model=None, **fake_kw):
        model = drawn_model or {"main": _build_main(),
                                "aux": _build_aux()}
        fakes = []

        def factory(port, rclass):
            fake = _FakeBOM5701Core(model, **fake_kw)
            fakes.append(fake)
            return fake

        monkeypatch.setattr("mychirp.serial_link.open_serial", factory)
        return model, fakes
    return _install


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # cooldown do fwtool + sleeps do driver ficam nulos no teste
    monkeypatch.setattr("mychirp.fwtool.time.sleep", lambda s: None)
    import mychirp.drivers.uv5r as _uv
    monkeypatch.setattr(_uv.time, "sleep", lambda s: None)


def test_rejeita_tamanho_errado(patch_open_serial):
    patch_open_serial()
    with pytest.raises(fwtool.FwDumpError) as e:
        restore_bom5701_image("BOMVINK_BOM-5701", "/dev/FAKE",
                              b"\x00" * 992)
    assert "6.472" in str(e.value) or "6472" in str(e.value)


def test_roundtrip_noop_dif_zero(patch_open_serial):
    """Restore da própria imagem lida: 402 blocos com ACK (20 aux +
    382 main; gaps de proteção do UV-5R pulados), 0 divergências."""
    model, fakes = patch_open_serial()
    image = IDENT + model["main"] + model["aux"]
    assert len(image) == UV5R_AUX_FIRST_IMAGE_END
    rep = restore_bom5701_image("BOMVINK_BOM-5701", "/dev/FAKE", image)
    assert rep["ok"] is True
    assert rep["diffs"] == []
    assert rep["preserve_diffs"] == []
    assert rep["aborted"] is False
    assert rep["sha_old"] == rep["sha_new"]
    # 3 sessões: apenas a sessão de gravação (índice 1) produz writes
    wf = fakes[1]
    assert len(wf.accepted_writes) == 402  # 20 aux + 382 main
    main_w = [a for a, s, c in wf.accepted_writes if a < 0x1800]
    aux_w = [a for a, s, c in wf.accepted_writes if a >= 0x1EC0]
    assert len(aux_w) == 20 and set(range(0x1EC0, 0x2000, 0x10)) == \
        set(aux_w)
    # todos os main writes são múltiplos de 16 e cobrem a faixa com gaps:
    assert all(a % 16 == 0 for a in main_w)
    assert len(main_w) == 382
    assert set(main_w) == set(range(0, 0x1800, 0x10)) - {0x0CF0, 0x0DF0}
    # gaps de proteção NÃO gravados (wire 0x0CF0-0x0D00 e 0x0DF0-0x0E00):
    assert 0x0CF0 not in main_w and 0x0D00 in main_w
    assert 0x0DF0 not in main_w and 0x0E00 in main_w
    # ordem: primeiro bloco aux (0x1EC0) antes do primeiro main
    assert wf.accepted_writes[0][0] == 0x1EC0
    assert rep["pre_path"] and rep["post_path"]
    assert rep["sha_old"] == rep["sha_new"]


def test_escrita_real_muda_memoria(patch_open_serial):
    """Imagem diferente: gravação efetiva e verify sem divergências."""
    model, fakes = patch_open_serial()
    image = bytearray(IDENT + model["main"] + model["aux"])
    # muda os 2 canais e 1 byte do aux (área de welcome, wire 0x1EC0)
    image[8 + 0x0000:8 + 0x0010] = MEM1
    image[0x1808:0x1809] = b"\xAA"
    rep = restore_bom5701_image("BOMVINK_BOM-5701", "/dev/FAKE",
                                bytes(image))
    assert rep["ok"] is True and rep["diffs"] == []
    assert rep["preserve_diffs"] == []
    assert rep["sha_old"] != rep["sha_new"]
    # memória simulada reflete a imagem alvo após as 3 sessões
    assert bytes(fakes[-1].model["main"]) == image[8:8 + 0x1800]
    assert bytes(fakes[-1].model["aux"]) == image[0x1808:0x1948]


def test_bytes_preservados_nao_falham_restore(patch_open_serial):
    """Imagem com mudanças SOMENTE nas faixas 'preserve' (chunks de
    imagem 0x0CF8-0x0D08 / 0x0DF8-0x0E08 = wire 0x0CF0-0x0D00 /
    0x0DF0-0x0E00): o resto é gravado, as faixas preservadas ficam
    com o conteúdo da unidade e o ok permanece True (preserve_diffs
    populado para transparência)."""
    model, fakes = patch_open_serial()
    orig_main = model["main"]
    image = bytearray(IDENT + model["main"] + model["aux"])
    # muda SOMENTE as faixas não-graváveis
    image[0x0CF8:0x0D08] = b"\x11" * 0x10
    image[0x0DF8:0x0E08] = b"\x22" * 0x10
    rep = restore_bom5701_image("BOMVINK_BOM-5701", "/dev/FAKE",
                                bytes(image))
    assert rep["ok"] is True
    assert rep["diffs"] == []
    assert rep["preserve_diffs"] == [(0x0CF8, 0x0D08), (0x0DF8, 0x0E08)]
    # rádio mantém os bytes preservados (não vieram da imagem alvo)
    assert fakes[-1].model["main"][0x0CF0:0x0D00] == orig_main[0x0CF0:0x0D00]
    assert fakes[-1].model["main"][0x0DF0:0x0E00] == orig_main[0x0DF0:0x0E00]


def test_aborto_nack_persistente(patch_open_serial):
    """NACK persistente a partir de um endereço de wire MAIN (depois
    do bloco aux normal): aborta, reporta addr e diffs=None."""
    model, fakes = patch_open_serial(reject_from=0x0200)
    image = IDENT + model["main"] + model["aux"]
    rep = restore_bom5701_image("BOMVINK_BOM-5701", "/dev/FAKE", image)
    assert rep["ok"] is False
    assert rep["aborted"] is True
    assert rep["aborted_addr"] == 0x0200
    assert rep["diffs"] is None
    assert rep["preserve_diffs"] is None
    # blocos ANTES do ponto de recusa foram aceitos (20 aux + 32 main)
    wf = fakes[1]
    assert len(wf.accepted_writes) == 20 + 32


def test_dispatcher_recente(patch_open_serial):
    """restore_image: dispatch BOM-5701 × h777 × família não suportada."""
    model, _ = patch_open_serial()
    image = IDENT + model["main"] + model["aux"]
    rep = restore_image("BOMVINK_BOM-5701", "/dev/FAKE", image)
    assert rep["ok"] is True

    with pytest.raises(fwtool.FwDumpError):
        restore_image("Driver_Inexistente", "/dev/FAKE", image)
