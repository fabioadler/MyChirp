import logging

import serial

from mychirp.serial_pipe import SerialPipe


def test_is_serial_subclass():
    assert issubclass(SerialPipe, serial.Serial)


def test_log_annotates_current_logging_system(caplog):
    pipe = SerialPipe(port=None)
    with caplog.at_level(logging.DEBUG, logger="mychirp.serial"):
        pipe.log("Reading 64 block at 0000")
    assert not pipe.is_open
    assert "Reading 64 block at 0000" in caplog.text
    pipe.close()


def test_trace_off_by_default():
    pipe = SerialPipe(port=None)
    assert not pipe.trace_enabled


def test_trace_enabled_by_env(monkeypatch):
    monkeypatch.setenv("CHIRP_SERIAL_TRACE", "1")
    pipe = SerialPipe(port=None)
    assert pipe.trace_enabled


def test_dump_emits_hexdump_only_when_enabled(caplog):
    pipe = SerialPipe(port=None)
    with caplog.at_level(logging.DEBUG, logger="mychirp.serial"):
        pipe._dump("W", b"\x01\x02\xfe")
    assert "01 02 fe" not in caplog.text.replace("01 02 fe", "01 02 fe")

    pipe.trace_enabled = True
    with caplog.at_level(logging.DEBUG, logger="mychirp.serial"):
        pipe._dump("W", b"\x01\x02\xfe")
        pipe._dump("R", b"")
    assert "01 02 fe" in caplog.text
    assert "W" in caplog.text
    assert "# timeout" in caplog.text
    pipe.close()


def test_log_on_unopened_port_does_not_raise():
    pipe = SerialPipe(port=None)
    pipe.log("should not crash")


def test_open_serial_uses_serial_pipe(monkeypatch, tmp_path):
    from mychirp.pysideui.services import radio_service
    from mychirp.serial_pipe import release_port_lock

    lockdir = tmp_path / "port-locks"
    monkeypatch.setattr("mychirp.serial_pipe.port_lock_dir",
                        lambda: str(lockdir))

    opened = {}

    class FakePipe:
        def __init__(self, **kwargs):
            opened.update(kwargs)
            self.rts = None
            self.dtr = None
            self._port_lock = None

        def open(self):
            opened["opened"] = True

        def attach_port_lock(self, lockfile):
            self._port_lock = lockfile

        def fileno(self):
            raise OSError("no real fd")

    monkeypatch.setattr("mychirp.serial_pipe.SerialPipe", FakePipe)

    class DummyRadio:
        BAUD_RATE = 9600
        HARDWARE_FLOW = False
        WANTS_RTS = True
        WANTS_DTR = True

    pipe = radio_service.open_serial("/dev/null", DummyRadio)
    try:
        assert opened["opened"] is True
        assert pipe.port == "/dev/null"
        assert pipe.rts is True and pipe.dtr is True
        assert isinstance(pipe, FakePipe)
        # a trava da porta foi adquirida e anexada ao pipe
        assert pipe._port_lock is not None
        assert (lockdir / "_dev_null.lock").exists()
    finally:
        release_port_lock(pipe._port_lock)
