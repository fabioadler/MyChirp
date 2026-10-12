"""Radio I/O operations isolated from the UI.

All blocking operations (image detection, clone, memory reads) run in
worker threads; progress is delivered back to the UI thread via
``page.run_task`` scheduled callbacks.
"""

import logging
import os
import threading
import weakref

import flet as ft

from mychirp import chirp_common
from mychirp import directory
from mychirp import errors as chirp_errors
from mychirp import config

LOG = logging.getLogger(__name__)

_services: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def open_serial(port, rclass):
    """Create and open the serial pipe for @rclass at @port.

    Same setup as the CHIRP-next clone dialog: pyserial Serial with the
    radio's BAUD_RATE, hardware flow, RTS/DTR pin configuration and a
    short timeout so the clone protocol retries work.
    """
    import serial

    pipe = serial.Serial(
        baudrate=getattr(rclass, "BAUD_RATE", 9600),
        rtscts=getattr(rclass, "HARDWARE_FLOW", False),
        timeout=0.25,
    )
    pipe.rts = getattr(rclass, "WANTS_RTS", True)
    pipe.dtr = getattr(rclass, "WANTS_DTR", True)
    pipe.port = port
    pipe.open()
    LOG.debug('Serial opened: %s (rts=%s dtr=%s br=%s)',
              pipe, pipe.rts, pipe.dtr, getattr(rclass, 'BAUD_RATE', None))
    return pipe


# keep public API
__all__ = ["RadioService", "get_service", "list_serial_ports",
           "list_vendors", "list_models", "model_label_to_class",
           "RadioJob", "open_serial"]


def list_serial_ports():
    """Return a list of available serial port device paths."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return sorted(p.device for p in ports)
    except Exception:
        return []


def list_vendors() -> list[str]:
    directory.import_drivers()
    vendors = sorted({
        rclass.VENDOR for rclass in directory.DRV_TO_RADIO.values()
        if getattr(rclass, "VENDOR", None)
    })
    return vendors


def list_models(vendor: str) -> list[str]:
    directory.import_drivers()
    models = []
    seen = set()
    for rclass in directory.DRV_TO_RADIO.values():
        if rclass.VENDOR == vendor:
            label = "%s %s" % (rclass.MODEL, rclass.VARIANT or "")
            label = label.strip()
            if label not in seen:
                seen.add(label)
                models.append(label)
    return sorted(models)


def model_label_to_class(vendor: str, label: str):
    directory.import_drivers()
    for rclass in directory.DRV_TO_RADIO.values():
        if rclass.VENDOR != vendor:
            continue
        cand = "%s %s" % (rclass.MODEL, rclass.VARIANT or "")
        if cand.strip() == label:
            return rclass
    return None


def open_serial(port, rclass):
    """Create and open the serial pipe for @rclass at @port.

    Same setup as the CHIRP-next clone dialog: pyserial Serial with the
    radio's BAUD_RATE, hardware flow, RTS/DTR pin configuration and a
    short timeout so the clone protocol retries work.
    """
    import serial

    pipe = serial.Serial(
        baudrate=getattr(rclass, "BAUD_RATE", 9600),
        rtscts=getattr(rclass, "HARDWARE_FLOW", False),
        timeout=0.25,
    )
    pipe.rts = getattr(rclass, "WANTS_RTS", True)
    pipe.dtr = getattr(rclass, "WANTS_DTR", True)
    pipe.port = port
    pipe.open()
    LOG.debug('Serial opened: %s (rts=%s dtr=%s br=%s)',
              pipe, pipe.rts, pipe.dtr, getattr(rclass, 'BAUD_RATE', None))
    return pipe


class RadioJob:
    """Result of an operation executed in a worker thread."""

    def __init__(self, fn, radio=None, *args, **kwargs):
        self.fn = fn
        # Target radio kept SEPARATE from fn args: the closures already
        # capture what they need; ``radio`` only feeds progress_cb
        self.radio = radio
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            LOG.exception("RadioJob failed")
            self.error = e


class RadioService:
    """Runs radio operations on threads and reports back to the page."""

    def __init__(self, page: ft.Page):
        self.page = page

    # ----- helpers -----
    def _run_async(self, job, on_done, progress_cb=None):
        """Run ``job`` in a thread; call ``on_done(job)`` on the UI loop.

        ``progress_cb`` (if given) is installed as the job radio's
        ``status_fn`` while the job runs.
        """

        def worker():
            if progress_cb and job.radio is not None:
                try:
                    job.radio.status_fn = progress_cb
                except Exception:
                    pass
            job.run()
            self.page.run_task(self._deliver, job, on_done)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    async def _deliver(self, job, on_done):
        try:
            on_done(job)
        except Exception:
            LOG.exception("Failed delivering radio job result")

    # ----- operations -----
    def open_file(self, filename, on_done):
        """Open an image/csv file, returning the radio instance."""

        def _open():
            # get_radio_by_image returns an instantiated radio
            return directory.get_radio_by_image(filename)

        job = RadioJob(_open)
        self._run_async(job, on_done)

    def download_radio(self, rclass, port, on_done, on_progress=None):
        """Clone from a physical radio into memory."""

        def _download():
            pipe = open_serial(port, rclass)
            radio = rclass(pipe)
            radio.status_fn = (
                lambda status: self.page.run_task(
                    self._emit_progress, on_progress, status)
                if on_progress else None)
            radio.sync_in()
            # Detach the pipe so the in-memory radio can be edited/saved
            try:
                radio.pipe.close()
            except Exception:
                pass
            radio.pipe = None
            return radio

        job = RadioJob(_download)
        self._run_async(job, on_done)

    async def _emit_progress(self, on_progress, status):
        try:
            on_progress(status)
        except Exception:
            LOG.exception("progress emit failed")

    def upload_radio(self, radio, port, on_done, on_progress=None):
        """Write the current radio contents back to the device."""

        def _upload():
            pipe = open_serial(port, type(radio))
            radio.pipe = pipe
            radio.status_fn = (
                lambda status: self.page.run_task(
                    self._emit_progress, on_progress, status)
                if on_progress else None)
            radio.sync_out()

        job = RadioJob(_upload, radio=radio)
        self._run_async(job, on_done)

    def save_radio(self, radio, filename, on_done):
        def _save():
            radio.save(filename)
            return filename

        job = RadioJob(_save, radio=radio)
        self._run_async(job, on_done)

    def load_memories(self, radio, on_done, progress=None):
        """Read every memory of the radio into a dict {number: Memory}."""

        def _load():
            features = radio.get_features()
            result = {}
            lo, hi = features.memory_bounds
            for number in range(lo, hi + 1):
                try:
                    mem = radio.get_memory(number)
                except Exception as e:
                    LOG.warning("Failed to read memory %s: %s", number, e)
                    continue
                result[number] = mem
            for name in features.valid_special_chans:
                try:
                    result[name] = radio.get_memory(name)
                except Exception as e:
                    LOG.warning("Failed special channel %s: %s", name, e)
            return result

        job = RadioJob(_load, radio=radio)
        self._run_async(job, on_done)

    def set_memory(self, radio, memory, on_done):
        def _set():
            radio.set_memory(memory)
            return memory

        job = RadioJob(_set, radio=radio)
        self._run_async(job, on_done)

    # ----- memory grid operations (see services/memory_ops.py) -----
    def run_memory_op(self, fn, radio, *args, on_done=None):
        """Run a pure memory operation in a worker thread."""
        def _run():
            return fn(radio, *args)

        job = RadioJob(_run, radio=radio)
        self._run_async(job, on_done or (lambda job: None))

    def run_callable(self, radio, fn, on_done=None):
        """Run an arbitrary callable (already bound) in a thread."""

        def _run():
            fn()

        job = RadioJob(_run, radio=radio)
        self._run_async(job, on_done or (lambda job: None))

    def export_csv(self, radio, filename, on_done):
        def _export():
            from mychirp.fletui.services import memory_ops
            return memory_ops.export_csv(radio, filename)

        job = RadioJob(_export, radio=radio)
        self._run_async(job, on_done)

    def load_settings(self, radio, on_done):
        def _load():
            return radio.get_settings()

        job = RadioJob(_load, radio=radio)
        self._run_async(job, on_done)

    def save_settings(self, radio, settings, on_done):
        def _save():
            radio.set_settings(settings)
            return True

        job = RadioJob(_save, radio=radio)
        self._run_async(job, on_done)


def get_service(page: ft.Page) -> RadioService:
    service = _services.get(page)
    if service is None:
        service = RadioService(page)
        _services[page] = service
    return service
