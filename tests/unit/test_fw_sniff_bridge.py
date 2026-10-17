"""F3: ponte serialsniff (pty↔pty) validada sem hardware.

Sobepõe o serialsniff real (compilado na hora, se houver gcc) entre
duas ptys sintéticas e fecha o proxy nos dois sentidos — é o mesmo
encanamento do fw-sniff.sh (wine COM1 → sniffer → rádio), com as
pontas de rádio e CPS simuladas no próprio teste.
"""

import os
import pty
import select
import subprocess
import shutil
import tempfile
import termios
import time

import pytest

SNIFF_SRC = "tools/serialsniff.c"


def _compile_sniff():
    if shutil.which("gcc") is None:
        pytest.skip("gcc indisponível")
    out = os.path.join(tempfile.mkdtemp(prefix="sniff_"), "serialsniff")
    r = subprocess.run(["gcc", "-O2", "-std=gnu89", "-D_DEFAULT_SOURCE",
                        "-o", out, SNIFF_SRC], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("compilação do serialsniff falhou: %s" % r.stderr[:200])
    return out


def _raw_slave(slave_path):
    """Coloca o terminal do slave em modo raw — é o que a CPS real faz
    sobre o tty; sem isso (ICANON) as ptys retêm bytes sem '\n'."""
    fd = os.open(slave_path, os.O_RDWR | os.O_NOCTTY)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] = 0  # lflag: sem ICANON/ECHO/ISIG/...
        attrs[1] = 0  # oflag
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    finally:
        os.close(fd)


@pytest.fixture
def bridge(tmp_path):
    sniff = _compile_sniff()
    logA = os.path.join(tmp_path, "A.bin")
    logB = os.path.join(tmp_path, "B.bin")
    masterA, ma = pty.openpty()
    masterB, mb = pty.openpty()
    # raw nos terminals do lado do sniffer (slaves)
    _raw_slave(os.ttyname(ma))
    _raw_slave(os.ttyname(mb))
    # NÃO usar O_NONBLOCK: o saferead() do sniffer dá timeout de 50ms e
    # um read() em pty com master fechado retorna 0 (EOF) → loop de
    # "Timeout" vazio. Manter masters abertos durante todo o teste.
    p = subprocess.Popen(
        [sniff, "-A", os.ttyname(ma), "--logA", logA,
         "-B", os.ttyname(mb), "--logB", logB,
         "-q", "-d", "16"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(0.3)  # dá tempo do sniffer abrir os lados
    try:
        yield masterA, masterB, p, logA, logB
    finally:
        p.terminate()
        p.wait(timeout=5)
        for fd in (masterA, masterB):
            os.close(fd)


def _read(master, n, timeout=2.0):
    """Leitura com select (mestres ficam bloqueantes; select evita hang)."""
    end = time.time() + timeout
    data = b""
    while time.time() < end and len(data) < n:
        r, _, _ = select.select([master], [], [], 0.1)
        if r:
            data += os.read(master, n - len(data))
            if data.endswith(b"R\x00\x10\x02") or \
                    data.endswith(b"X\x00\x10\x02ab"):
                break
    return data


def test_ponte_bidirecional_e_rawlog(bridge):
    masterA, masterB, proc, logA, logB = bridge
    assert proc.poll() is None, "serialsniff morreu no boot"

    # CPS->RÁDIO: escreve lado A, sai no lado B
    os.write(masterA, b"R\x00\x10\x02")
    assert _read(masterB, 4, 2.0) == b"R\x00\x10\x02"

    # RÁDIO->CPS: resposta volta pelo caminho inverso
    os.write(masterB, b"X\x00\x10\x02ab")
    assert _read(masterA, 6, 2.0) == b"X\x00\x10\x02ab"

    # rawlogs: cada lado registra o que o sniffer LÊ dele (não espelha)
    dataA = open(logA, "rb").read()
    dataB = open(logB, "rb").read()
    assert b"R\x00\x10\x02" in dataA, "frame CPS não logado no lado A"
    assert b"X\x00\x10\x02ab" in dataB, "resposta não logada no lado B"
