"""sniff-analyze (F3): parser do console do serialsniff."""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import sniff_analyze as sa  # noqa: E402


def _write(tmp_path, text):
    p = tmp_path / "console.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_load_chunks_multiline(tmp_path):
    text = (
        "serialsniff - Version 1.02\n"
        "/dev/pts/5\n"
        "A 8:\n"
        " 5051 4246 5c2c 2020\n"
        "B 2:\n"
        " 5006\n"
    )
    chunks = sa.load_text(_write(tmp_path, text))
    assert chunks == [("A", bytes.fromhex("5051424 65c2c2020".replace(" ", ""))),
                      ("B", b"\x50\x06")]


def test_describe_frames():
    assert "READ" in sa.describe(b"R\x00\x10\x08")
    assert "REQ" in sa.describe(b"S\x0e\x40\x40")
    assert "ACK" in sa.describe(b"\x06")
    assert "raw" in sa.describe(b"\x50\xbb\xff")
    data_x = b"X\x00\x10\x08abcdefgh"
    assert "DATA  addr=0x0010 size=0x8" in sa.describe(data_x)


def test_main_runs_on_synthetic(tmp_path, capsys, monkeypatch):
    text = (
        "A 4:\n 5200 1002\n"
        "B 12:\n 5800 1041 4142 4344 4546\n"
        "A 1:\n 06\n"
        "--\n"
    )
    path = _write(tmp_path, text)
    monkeypatch.setattr(sys, "argv", ["sniff_analyze.py", path])
    rc = sa.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "READ  addr=0x0010 size=0x2" in out
    # DATA = resposta X-echoed: addr conferida; size vem do byte de payload
    assert "DATA  addr=0x0010 size=0x41" in out
    assert "ACK" in out
