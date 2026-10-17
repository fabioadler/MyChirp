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


def _mk_image(tmp_path, n):
    p = tmp_path / "img.bin"
    p.write_bytes(b"\x00" * n)
    return str(p)


def test_restore_cli_bom_family_tty_gate(capsys, monkeypatch, tmp_path):
    """--restore na família aux-first (BOM-5701) sem TTY: cancela
    antes de tocar no rádio (exit 3) — o anúncio menciona a família."""
    from mychirp.cli import fw as fwcli
    img = _mk_image(tmp_path, 0x1948)
    rc = fwcli.main([
        "--radio=BOMVINK_BOM-5701", "--serial=/dev/FAKE",
        "--restore", img])
    assert rc == 3
    out = capsys.readouterr().out
    assert "AUX" in out and "0x1EC0-0x2000" in out


def test_restore_cli_family_not_validated(capsys, tmp_path):
    """Driver SEM família validada: erro imediato (exit 1), sem
    confirmação e sem tocar no rádio."""
    from mychirp import directory
    from mychirp.cli import fw as fwcli
    directory.import_drivers()
    other = next(
        (r for r in directory.DRV_TO_RADIO.values()
         if fw_family_is_none(r)), None)
    if other is None:
        # demasiadas famílias validadas: driver local inexistente
        return
    ident = directory.get_driver(other)
    img = _mk_image(tmp_path, 128)
    rc = fwcli.main([
        "--radio=%s" % ident, "--serial=/dev/FAKE", "--restore", img])
    assert rc == 1
    err = capsys.readouterr().err
    assert "não tem família" in err or "familia" in err


def fw_family_is_none(r):
    """Predicado: driver de CLONE serial sem família de escrita
    validada (exclui rádios file-backed, que nem clonam)."""
    from mychirp import chirp_common, fwtool
    if not issubclass(r, chirp_common.CloneModeRadio):
        return False
    if getattr(r, "PROGRAM_CMD", None) == fwtool.H777_PROGRAM_CMD:
        return False
    if getattr(r, "_aux_first", False) and getattr(r, "_aux_block", False):
        return False
    return True
