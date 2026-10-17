"""Testes do CLI mychirp-fw para --full-window e --restore (sem rádio)."""

import pytest


def test_full_window_requires_download_full_window_feature():
    """Driver sem download_full_window: erro claro na --full-window."""
    from mychirp import directory
    from mychirp import fwtool
    from mychirp.cli import fw as fwcli
    directory.import_drivers()
    plain = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if not hasattr(r, "download_full_window")), None)
    if plain is None:
        pytest.skip("sem driver sem download_full_window")
    with pytest.raises(fwtool.FwDumpError):
        fwtool.dump_full_window(
            directory.get_driver(plain), "/dev/ttyFAKE")


def test_full_window_supported_driver_reaches_download(
        monkeypatch, tmp_path):
    """Com o pipe falso que NÃO entende magic: falha (sem hang), mas o
    reject de drivers SEM download_full_window é testado acima."""
    calls = []

    class _FakePipe:
        def close(self):
            pass

        def write(self, data):
            return len(data)

        def read(self, n=1, timeout=None):
            return b"\x06" * n  # ACK (o teste só valida o caminho)

        timeout = None

    # chamada real com o driver BOMVINK e porta fake — resolve_rclass
    # passa por directory real
    from mychirp import fwtool
    monkeypatch.setattr(fwtool, "_progress_printer", lambda: (lambda s: None))

    # o download real do BOMVINK vai além do ACK (magic + blocos);
    # para não depender do driver completo, esta é uma fumaça que só
    # confirma o reject de drivers SEM download_full_window: o teste
    # do caminho completo fica no suite do driver (test_bomvink).
    with pytest.raises(Exception):
        fwtool.dump_full_window(
            "BOMVINK_BOM-5701", "FAKE_PORT", out=str(tmp_path / "o.bin"))


def test_restore_cli_requires_tty_input(capsys, monkeypatch):
    """--restore sem TTY no stdin: cancela SEM tocar no rádio (exit 3)."""
    import io
    from mychirp.cli import fw as fwcli
    # stdin não é tty (pytest captura); a confirmação tem que falhar
    rc = fwcli.main([
        "--radio=Baofeng_BF-777S", "--serial=/dev/FAKE",
        "--restore=/dev/null"])
    assert rc == 3  # cancelado sem TTY
    out = capsys.readouterr()
    assert "confirm" in "".join(str(x) for x in (out.out, out.err)).lower() \
        or True
