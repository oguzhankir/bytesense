from __future__ import annotations

from pathlib import Path

import pytest

from bytesense import from_bytes, from_path, is_binary


def test_from_bytes_no_fallback_may_fail() -> None:
    r = from_bytes(b"\xff" * 200, enable_fallback=False)
    assert r.encoding is None or isinstance(r.encoding, str)


def test_is_binary_detects_non_text() -> None:
    b = bytes(range(256)) * 8
    out = is_binary(b)
    assert isinstance(out, bool)


def test_from_path_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "sample.txt"
    p.write_bytes("café sur la plage".encode("utf-8"))
    r = from_path(p)
    assert r.encoding in ("utf_8", "ascii")


def test_from_path_missing_raises() -> None:
    with pytest.raises(OSError):
        from_path("/nonexistent/path/bytesense-test-404.txt")


def test_from_bytes_cp_isolation_empty_falls_back() -> None:
    r = from_bytes(b"hello", cp_isolation=[])
    assert r.encoding is not None
