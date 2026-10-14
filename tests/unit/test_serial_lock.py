"""Trava de porta serial ocupada (serial_pipe acquire/release).

A trava usa flock não-bloqueante em arquivo sidecar por porta: se outro
processo/operação já estiver usando a porta, o usuário recebe um aviso
dizendo quem está usando, para fechar e tentar novamente.
"""

import json
import os
import subprocess
import sys
import time

import pytest

fcntl = pytest.importorskip("fcntl")

from mychirp.serial_pipe import (  # noqa: E402
    PortBusyError,
    acquire_port_lock,
    is_busy_osa_error,
    port_lock_path,
    release_port_lock,
)


@pytest.fixture
def pty_port():
    """Par PTY; o slave é usado como 'porta serial' de teste."""
    master, slave = os.openpty()
    name = os.ttyname(slave)
    yield name
    os.close(master)
    os.close(slave)


@pytest.fixture(autouse=True)
def clean_lock(pty_port):
    yield
    try:
        os.unlink(port_lock_path(pty_port))
    except OSError:
        pass


def test_acquire_release_cycle(pty_port):
    lockfile = acquire_port_lock(pty_port)
    assert lockfile is not None
    # conteúdo do arquivo de trava identifica o dono
    info = json.load(open(port_lock_path(pty_port)))
    assert info["pid"] == os.getpid()
    release_port_lock(lockfile)
    # liberou: arquivo removido e re-aquisição funciona
    assert not os.path.exists(port_lock_path(pty_port))
    lockfile2 = acquire_port_lock(pty_port)
    release_port_lock(lockfile2)


def test_busy_lock_reports_holder(pty_port):
    lockfile = acquire_port_lock(pty_port)
    try:
        with pytest.raises(PortBusyError) as exc:
            acquire_port_lock(pty_port)
        msg = str(exc.value)
        # aviso fala de porta ocupada e aponta o dono (nós mesmos,
        # pois a trava está no mesmo processo -> "outra operação")
        assert "ocupada" in msg
        assert str(os.getpid()) in msg
    finally:
        release_port_lock(lockfile)


def test_busy_lock_cross_process(pty_port):
    """Outro processo (como outro MyChirp) segurando a trava: o aviso
    aponta o PID dele."""
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import fcntl, json, os, sys, time\n"
         "f = open(sys.argv[1], 'a+')\n"
         "f.write(json.dumps({'pid': os.getpid(), 'name': 'outro-mychirp'}))\n"
         "f.flush()\n"
         "fcntl.flock(f, fcntl.LOCK_EX)\n"
         "print('locked', flush=True)\n"
         "time.sleep(5)\n",
         port_lock_path(pty_port)],
        stdout=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 5
        line = None
        while time.time() < deadline:
            line = child.stdout.readline()
            if line:
                break
            if child.poll() is not None:
                pytest.fail("processo filho morreu: %s" % child.returncode)
            time.sleep(0.05)
        assert line and "locked" in line

        with pytest.raises(PortBusyError) as exc:
            acquire_port_lock(pty_port)
        msg = str(exc.value)
        assert "ocupada" in msg
        assert "outro-mychirp" in msg
        assert str(child.pid) in msg
    finally:
        child.kill()
        child.wait()


def test_serialpipe_releases_lock_on_close(pty_port):
    from mychirp.serial_pipe import SerialPipe

    lockfile = acquire_port_lock(pty_port)
    pipe = SerialPipe(port=pty_port, baudrate=9600, timeout=0.1)
    pipe.attach_port_lock(lockfile)
    pipe.close()
    # close() liberou a trava: re-aquisição imediata funciona
    lockfile2 = acquire_port_lock(pty_port)
    release_port_lock(lockfile2)


def test_open_serial_ebusy_becomes_friendly(pty_port, monkeypatch):
    """open() com EBUSY (TIOCEXCL de outro processo) vira o aviso
    amigável e não vaza a trava."""
    import errno as _errno
    from mychirp.pysideui.services import radio_service
    from mychirp.serial_pipe import SerialPipe

    def fake_open(self):
        raise OSError(_errno.EBUSY, "Device or resource busy")

    monkeypatch.setattr(SerialPipe, "open", fake_open)
    rclass = type("R", (), {"BAUD_RATE": 9600})
    with pytest.raises(PortBusyError) as exc:
        radio_service.open_serial(pty_port, rclass)
    assert "ocupada" in str(exc.value)
    # trava foi liberada antes de subir o erro
    lockfile = acquire_port_lock(pty_port)
    release_port_lock(lockfile)


def test_is_busy_osa_error():
    import serial as pyserial
    assert is_busy_osa_error(OSError(16, "Device or resource busy"))
    assert is_busy_osa_error(pyserial.SerialException(
        "could not open port /dev/ttyUSB0: [Errno 16] Device busy"))
    assert not is_busy_osa_error(ValueError("x"))
    assert not is_busy_osa_error(OSError(2, "No such file"))
