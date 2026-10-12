"""Radio I/O service for the PySide6 UI: thread pool + Qt signals.

Same operations as the flet radio_service (open_file, download,
upload, save, memories, settings) but instead of flet's page.run_task,
jobs run on QThreadPool and deliver results to the GUI thread via
queued signals.
"""

import logging
import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot, QThreadPool

from mychirp import directory
from mychirp import errors as chirp_errors

LOG = logging.getLogger(__name__)

__all__ = ["RadioService", "RadioJob", "get_service", "list_serial_ports",
           "list_vendors", "list_models", "model_label_to_class",
           "open_serial"]


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


class RadioJob:
    """Result of an operation executed in a worker thread."""

    def __init__(self, fn, radio=None, *args, **kwargs):
        self.fn = fn
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


class _WorkerSignals(QObject):
    finished = Signal(object)   # emits the RadioJob
    progress = Signal(object)   # emits a status object from the radio


class _Runnable(QRunnable):
    def __init__(self, job, signals):
        super().__init__()
        self.job = job
        self.signals = signals

    @Slot()
    def run(self):
        self.job.run()
        self.signals.finished.emit(self.job)


class RadioService(QObject):
    """Runs radio operations on the shared QThreadPool."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        # Keep signal objects alive while their job is running
        self._inflight: set[_WorkerSignals] = set()

    # ----- helpers -----
    def _run_async(self, job, on_done, progress_cb=None):
        """Run ``job`` in a worker; deliver results via Qt signals."""
        signals = _WorkerSignals(self)
        signals.finished.connect(
            lambda j, cb=on_done, sig=signals: self._deliver(
                j, cb, sig))
        if progress_cb:
            signals.progress.connect(
                progress_cb)  # queued to the GUI thread by default
        runnable = _Runnable(job, signals)
        if progress_cb and job.radio is not None:
            try:
                job.radio.status_fn = signals.progress.emit
            except Exception:
                pass
        self._inflight.add(signals)
        self._pool.start(runnable)

    def _deliver(self, job, on_done, signals):
        self._inflight.discard(signals)
        try:
            on_done(job)
        except Exception:
            LOG.exception("Failed delivering radio job result")

    # ----- operations -----
    def open_file(self, filename, on_done):
        def _open():
            return directory.get_radio_by_image(filename)

        job = RadioJob(_open)
        self._run_async(job, on_done)

    def download_radio(self, rclass, port, on_done, on_progress=None):
        """Clone from a physical radio into memory."""

        def _download():
            pipe = open_serial(port, rclass)
            radio = rclass(pipe)
            job.radio = radio
            if on_progress:
                signals = None
                # capture signals bound in _run_async
                def emit(status):
                    try:
                        job._signals.progress.emit(status)
                    except Exception:
                        pass
                radio.status_fn = emit
            radio.sync_in()
            try:
                radio.pipe.close()
            except Exception:
                pass
            radio.pipe = None
            return radio

        job = RadioJob(_download)
        job._signals = _WorkerSignals(self)
        if on_progress:
            job._signals.progress.connect(on_progress)
        self._inflight.add(job._signals)

        def wrapped_done(j):
            self._inflight.discard(job._signals)
            on_done(j)

        job._signals.finished.connect(wrapped_done)
        self._pool.start(_Runnable(job, job._signals))

    def upload_radio(self, radio, port, on_done, on_progress=None):
        """Write the current radio contents back to the device."""

        def _upload():
            pipe = open_serial(port, type(radio))
            radio.pipe = pipe
            if on_progress:
                def emit(status):
                    try:
                        job._signals.progress.emit(status)
                    except Exception:
                        pass
                radio.status_fn = emit
            radio.sync_out()

        job = RadioJob(_upload, radio=radio)
        job._signals = _WorkerSignals(self)
        if on_progress:
            job._signals.progress.connect(on_progress)
        self._inflight.add(job._signals)

        def wrapped_done(j):
            self._inflight.discard(job._signals)
            on_done(j)

        job._signals.finished.connect(wrapped_done)
        self._pool.start(_Runnable(job, job._signals))

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

    # ----- memory grid operations (see mychirp/memory_ops.py) -----
    def run_memory_op(self, fn, radio, *args, on_done=None):
        """Run a pure operation in a worker thread and call ``on_done``
        on the GUI thread with the populated RadioJob."""
        def _run():
            if not args:
                # Allow callers that close over everything (e.g. the
                # export path in the main window, which already holds
                # what it needs)
                return fn()
            return fn(radio, *args)

        job = RadioJob(_run, radio=radio)
        self._run_async(job, on_done or (lambda job: None))

    def export_csv(self, radio, filename, on_done):
        def _export():
            from mychirp import memory_ops
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


_service: RadioService | None = None


def get_service(parent=None) -> RadioService:
    """One RadioService per application (QObjects share one pool)."""
    global _service
    if _service is None:
        _service = RadioService(parent)
    return _service
