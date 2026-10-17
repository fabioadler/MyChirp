"""Serial de rádio como backend puro: abertura compartilhada por pipe.

Extraído de pysideui/services/radio_service.open_serial() para que a
GUI e as ferramentas CLI (mychirpc, mychirp-fw) usem a MESMA abertura:
pyserial/SerialPipe com BAUD_RATE do driver, fluxo de hardware
(rtscts), RTS/DTR conforme WANTS_RTS/WANTS_DTR, trava de porta
cooperativa (acquire_port_lock) e mensagem amigável de porta ocupada.

Sem dependência de toolkit GUI — importável por qualquer camada.
"""

import logging

from mychirp import serial_pipe as _sp

LOG = logging.getLogger(__name__)


def open_serial(port, rclass):
    """Create and open the serial pipe for @rclass at @port.

    Same setup as the CHIRP-next clone dialog: pyserial Serial with the
    radio's BAUD_RATE, hardware flow, RTS/DTR pin configuration and a
    short timeout so the clone protocol retries work.

    Porta ocupada (outro processo/operação): falha imediatamente com um
    aviso dizendo quem está usando a porta, para o usuário fechar e
    tentar novamente — em vez de falhas de leitura/escrita.

    Quirk CH340 (dobradiça do driver, ex.: UV-17M): a primeira abertura
    da porta pode ecoar/mudar; quem chama decide reabrir (probe) antes
    da sessão real quando o driver declara o quirk.

    Nota: os componentes vêm via mychirp.serial_pipe no momento da
    chamada (e não por import no topo) para respeitar monkeypatches dos
    testes (SerialPipe falso, port_lock_dir redirecionado).
    """
    lockfile = _sp.acquire_port_lock(port)
    try:
        pipe = _sp.SerialPipe(
            baudrate=getattr(rclass, "BAUD_RATE", 9600),
            rtscts=getattr(rclass, "HARDWARE_FLOW", False),
            timeout=0.25,
        )
        pipe.rts = getattr(rclass, "WANTS_RTS", True)
        pipe.dtr = getattr(rclass, "WANTS_DTR", True)
        pipe.port = port
        pipe.open()
    except Exception as e:
        _sp.release_port_lock(lockfile)
        if _sp.is_busy_osa_error(e):
            raise _sp.PortBusyError(_sp.busy_port_message(port)) from e
        raise
    pipe.attach_port_lock(lockfile)

    # Exclusividade dura: outros processos recebem EBUSY ao abrir a tty
    try:
        import fcntl
        import termios
        fcntl.ioctl(pipe.fileno(), termios.TIOCEXCL)
    except Exception as e:
        LOG.debug('TIOCEXCL indisponivel em %s: %s', port, e)

    LOG.debug('Serial opened: %s (rts=%s dtr=%s br=%s)',
              pipe, pipe.rts, pipe.dtr, getattr(rclass, 'BAUD_RATE', None))
    return pipe
