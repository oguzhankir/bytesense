from __future__ import annotations

import pytest

from bytesense import detect


def test_returns_dict() -> None:
    r = detect(b"Hello world")
    assert isinstance(r, dict)
    assert "encoding" in r
    assert "confidence" in r
    assert "language" in r


def test_encoding_is_str_or_none() -> None:
    r = detect(b"Hello world")
    assert r["encoding"] is None or isinstance(r["encoding"], str)


def test_confidence_is_float_or_none() -> None:
    r = detect(b"Hello world")
    if r["confidence"] is not None:
        assert 0.0 <= r["confidence"] <= 1.0


def test_utf8_detected() -> None:
    data = "Héllo wörld üñîcödé".encode()
    r = detect(data)
    enc = (r["encoding"] or "").replace("-", "_").lower()
    assert "utf" in enc and "8" in enc


def test_wrong_type_raises() -> None:
    with pytest.raises(TypeError):
        detect("not bytes")  # type: ignore[arg-type]


def test_empty_bytes() -> None:
    r = detect(b"")
    assert r["encoding"] is not None  # returns utf_8 fallback
