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


def test_log_on_unopened_port_does_not_raise():
    pipe = SerialPipe(port=None)
    pipe.log("should not crash")


def test_open_serial_uses_serial_pipe(monkeypatch):
    from mychirp.pysideui.services import radio_service

    opened = {}

    class FakePipe:
        def __init__(self, **kwargs):
            opened.update(kwargs)
            self.rts = None
            self.dtr = None

        def open(self):
            opened["opened"] = True

    monkeypatch.setattr("mychirp.serial_pipe.SerialPipe", FakePipe)

    class DummyRadio:
        BAUD_RATE = 9600
        HARDWARE_FLOW = False
        WANTS_RTS = True
        WANTS_DTR = True

    pipe = radio_service.open_serial("/dev/null", DummyRadio)
    assert opened["opened"] is True
    assert pipe.port == "/dev/null"
    assert pipe.rts is True and pipe.dtr is True
    assert isinstance(pipe, FakePipe)
