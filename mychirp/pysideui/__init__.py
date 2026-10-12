"""MyChirp PySide6 UI: Qt6 interface reusing the backend services."""

__all__ = ["run"]


def run():
    from mychirp.pysideui.main import run as _run
    return _run()
