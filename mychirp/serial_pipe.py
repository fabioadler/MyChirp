"""SerialPipe: pyserial Serial com anotações de log integradas.

Alguns drivers (h777, ga510, baofeng_uv17/uv17Pro, tdm11, thd74,
tk8180, radtel_rt900, retevis_rt18) chamam ``pipe.log(msg)`` para
anotar a comunicação (leitura de bloco, envio de endereço etc.). O
pipe é aberto com esta classe para que essas anotações entrem no
sistema de log já existente (mychirp/logger.py): console quando
verbose/CHIRP_DEBUG, ``debug.log`` ou ``CHIRP_LOG`` no disco.
"""

import logging

import serial

LOG = logging.getLogger("mychirp.serial")


class SerialPipe(serial.Serial):
    """serial.Serial + método log() para anotações dos drivers."""

    def log(self, message):
        """Registra uma anotação de protocolo no sistema de log atual."""
        LOG.debug("%s: %s", self.port, message)
