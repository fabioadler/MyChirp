"""Serial-port probing helpers for the PySide6 UI.

Keeps the wrong-port detection logic out of the dialogs: ``probe_port``
opens the device exactly like the real clone does and converts low-level
pyserial/OS errors into a single friendly ``PortProbeError`` so callers
show a clean message instead of a stack trace. ``is_programmer_device``
classifies USB-serial adapters for hotplug auto-detect.
"""

import logging
import os

from mychirp.pysideui.i18n import _

LOG = logging.getLogger(__name__)

NO_RADIO_MESSAGE = _(
    "No radio detected on this port. "
    "Check the cable and try another port.")


class PortProbeError(Exception):
    """Raised when a port cannot be opened or the radio does not ACK."""


def is_serial_error(exc):
    """True for pyserial SerialException / OSError from serial code."""
    try:
        import serial
        kinds = (serial.SerialException, OSError)
    except Exception:
        kinds = (OSError,)
    return isinstance(exc, kinds)


def probe_port(port, rclass, timeout=2.0):
    """Open @port like the clone would; raise PortProbeError on failure.

    On success the pipe is closed and None is returned. Radio-level
    ident/ACK failure is also mapped to PortProbeError when the driver
    cannot be contacted within @timeout seconds.
    """
    from mychirp.pysideui.services.radio_service import open_serial
    from mychirp.serial_pipe import PortBusyError

    pipe = None
    try:
        pipe = open_serial(port, rclass)
    except PortBusyError as e:
        # Motivo específico (porta ocupada) vai direto ao usuário
        raise PortProbeError(str(e)) from e
    except Exception as e:
        if is_serial_error(e):
            raise PortProbeError(NO_RADIO_MESSAGE) from e
        raise
    try:
        pipe.timeout = timeout
        ack_timeout = getattr(rclass, "IDENT_ACK_TIMEOUT", 0)
        if ack_timeout:
            pipe.timeout = min(timeout, float(ack_timeout))
            data = pipe.read(1)
            if not data:
                raise PortProbeError(NO_RADIO_MESSAGE)
    except PortProbeError:
        raise
    except Exception as e:
        if is_serial_error(e):
            raise PortProbeError(NO_RADIO_MESSAGE) from e
        LOG.debug("Non-fatal probe read failure on %s: %s", port, e)
    finally:
        try:
            pipe and pipe.close()
        except Exception:
            pass
    return None


def is_programmer_device(device):
    """Heuristics: does @device look like a USB programming cable?"""
    if not device:
        return False
    base = os.path.basename(device)
    if base.startswith(("ttyUSB", "ttyACM")):
        return True
    try:
        import serial.tools.list_ports
        for info in serial.tools.list_ports.comports():
            if info.device != device:
                continue
            if info.vid and info.pid:
                return True
            driver = (getattr(info, "driver", None) or "").lower()
            if "usb" in driver:
                return True
            sysdir = os.path.join("/sys/class/tty", base, "device", "driver")
            if os.path.exists(sysdir) and "usb" in os.path.realpath(sysdir).lower():
                return True
    except Exception:
        LOG.debug("USB detection failed for %s", device)
    return False
