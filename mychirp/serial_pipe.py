"""SerialPipe: pyserial Serial com anotações de log integradas.

Alguns drivers (h777, ga510, baofeng_uv17/uv17Pro, tdm11, thd74,
tk8180, radtel_rt900, retevis_rt18) chamam ``pipe.log(msg)`` para
anotar a comunicação (leitura de bloco, envio de endereço etc.). O
pipe é aberto com esta classe para que essas anotações entrem no
sistema de log já existente (mychirp/logger.py): console quando
verbose/CHIRP_DEBUG, ``debug.log`` ou ``CHIRP_LOG`` no disco.

Dump opcional do tráfego TX/RX: definir a variável de ambiente
``CHIRP_SERIAL_TRACE`` (ou ``CHIRP_DEBUG``) faz ``read()``/``write()``
registrarem hexdumps timestamped no mesmo logger (nível DEBUG), útil
para depurar drivers novos. Desligado por padrão, sem custo.

Trava de porta ocupada: ``acquire_port_lock()`` toma um flock
não-bloqueante em um arquivo sidecar por porta; se outro processo
(ou outra operação deste mesmo app) já estiver usando a porta, o
usuário recebe um aviso imediato dizendo quem está usando, para
fechar e tentar novamente — sem falhas de leitura/escrita.
"""

import errno
import json
import logging
import os
import subprocess
import time

import serial

try:
    import fcntl
except ImportError:  # pragma: no cover (Windows)
    fcntl = None

from mychirp import errors, util

LOG = logging.getLogger("mychirp.serial")


class PortBusyError(errors.RadioError):
    """A porta serial está em uso por outro processo/operação."""


def port_lock_dir():
    """Diretório dos arquivos de trava (~/.chirp/port-locks)."""
    return os.path.join(os.path.expanduser("~"), ".chirp", "port-locks")


def port_lock_path(port):
    """Arquivo de trava sidecar da @port (sem tocar na tty)."""
    return os.path.join(port_lock_dir(),
                        "%s.lock" % str(port).replace(os.sep, "_"))


def _proc_name(pid):
    """Nome legível do processo (Linux /proc; fallback genérico)."""
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip() or "processo"
    except Exception:
        return "processo"


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _lock_holder(path):
    """(pid, nome) do processo segurando a trava, ou None."""
    try:
        with open(path) as f:
            info = json.load(f)
        pid = int(info.get("pid", 0))
    except Exception:
        return None
    if not pid or not _pid_alive(pid):
        return None
    return pid, info.get("name") or _proc_name(pid)


def _lsof_holder(port):
    """Quem tem a tty aberta (processo externo sem trava cooperativa)."""
    for cmd, extract in (
        (["lsof", "-t", "--", str(port)], lambda out: out.split()),
        (["fuser", str(port)], lambda out: [p.strip(": ")
                                            for p in out.split()]),
    ):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=3)
        except Exception:
            continue
        pids = []
        for tok in extract(res.stdout) or []:
            try:
                pids.append(int(tok))
            except ValueError:
                pass
        if pids:
            pid = pids[0]
            return pid, _proc_name(pid)
    return None


def _busy_message(port, holder, own_pid=False):
    if holder is None:
        return ("A porta %s está ocupada por outro processo. "
                "Feche o programa que está usando o rádio e tente "
                "novamente." % port)
    pid, name = holder
    if own_pid:
        return ("A porta %s está ocupada por outra operação deste "
                "mesmo programa (%s, PID %d). Aguarde a operação atual "
                "terminar e tente novamente." % (port, name, pid))
    return ("A porta %s está ocupada por: %s (PID %d). "
            "Feche o programa que está usando o rádio e tente "
            "novamente." % (port, name, pid))


def acquire_port_lock(port):
    """Tenta travar (flock não-bloqueante) a @port.

    Retorna o arquivo de trava — mantenha-o aberto enquanto a porta
    estiver em uso — ou levanta PortBusyError dizendo quem está com a
    porta, para o usuário fechar e tentar novamente.

    Plataformas sem fcntl (Windows): retorna None sem travar.
    """
    if fcntl is None:  # pragma: no cover (Windows)
        return None
    os.makedirs(port_lock_dir(), exist_ok=True)
    path = port_lock_path(port)
    lockfile = open(path, "a+")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lockfile.close()
        holder = _lock_holder(path)
        own = bool(holder and holder[0] == os.getpid())
        raise PortBusyError(_busy_message(port, holder, own_pid=own))
    lockfile.seek(0)
    lockfile.truncate()
    lockfile.write(json.dumps({"pid": os.getpid(),
                              "name": _proc_name(os.getpid())}))
    lockfile.flush()
    return lockfile


def release_port_lock(lockfile):
    """Libera a trava adquirida por acquire_port_lock()."""
    if lockfile is None:
        return
    path = None
    try:
        path = lockfile.name
    except Exception:
        pass
    try:
        fcntl.flock(lockfile, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        lockfile.close()
    except Exception:
        pass
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def busy_port_message(port):
    """Mensagem de porta ocupada identificando o dono via lsof/fuser
    (caso de processo externo segurando a tty, ex.: TIOCEXCL/EBUSY)."""
    return _busy_message(port, _lsof_holder(port))


def is_busy_osa_error(exc):
    """True quando a exceção de open() indica porta em uso (EBUSY)."""
    if isinstance(exc, OSError):
        if exc.errno in (errno.EBUSY, errno.EACCES, errno.EPERM):
            return True
    return "Errno 16" in str(exc) or "resource busy" in str(exc).lower()


class SerialPipe(serial.Serial):
    """serial.Serial + log()/dump TX-RX opcional para drivers."""

    def __init__(self, *args, **kwargs):
        self._trace = bool(
            os.getenv("CHIRP_SERIAL_TRACE") or os.getenv("CHIRP_DEBUG"))
        self._started = time.monotonic()
        # Trava de porta (attach_port_lock), liberada no close()
        self._port_lock = None
        super().__init__(*args, **kwargs)
        if self._trace:
            LOG.debug("serial trace ativado (%s)", self.port)

    def attach_port_lock(self, lockfile):
        """Associa a trava adquirida por acquire_port_lock(); ela é
        liberada automaticamente no close()."""
        self._port_lock = lockfile

    def close(self):
        try:
            super().close()
        finally:
            lockfile = self._port_lock
            self._port_lock = None
            if lockfile is not None:
                release_port_lock(lockfile)

    def log(self, message):
        """Registra uma anotação de protocolo no sistema de log atual."""
        LOG.debug("%s: %s", self.port, message)

    @property
    def trace_enabled(self):
        return self._trace

    @trace_enabled.setter
    def trace_enabled(self, value):
        self._trace = bool(value)

    def _dump(self, direction, data):
        """Hexdump timestamped de um trecho de tráfego (nível DEBUG)."""
        if not self._trace:
            return
        ts = time.monotonic() - self._started
        lines = util.hexprint(bytes(data), block_size=16).splitlines()
        if not lines and direction == "R":
            LOG.debug("%7.3f R # timeout", ts)
            return
        for line in lines:
            LOG.debug("%7.3f %s %s", ts, direction, line)

    def read(self, size=1):
        data = super().read(size)
        self._dump("R", data)
        return data

    def write(self, data):
        result = super().write(data)
        self._dump("W", data)
        return result
