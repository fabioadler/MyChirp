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
"""

import logging
import os
import time

import serial

from mychirp import util

LOG = logging.getLogger("mychirp.serial")


class SerialPipe(serial.Serial):
    """serial.Serial + log()/dump TX-RX opcional para drivers."""

    def __init__(self, *args, **kwargs):
        self._trace = bool(
            os.getenv("CHIRP_SERIAL_TRACE") or os.getenv("CHIRP_DEBUG"))
        self._started = time.monotonic()
        super().__init__(*args, **kwargs)
        if self._trace:
            LOG.debug("serial trace ativado (%s)", self.port)

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
