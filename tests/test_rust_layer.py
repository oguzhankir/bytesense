"""Cover ``bytesense._rust`` wrappers and no-extension stubs (always runs)."""

from __future__ import annotations

import pytest

from bytesense._rust import (
    is_rust_available,
    rust_byte_histogram,
    rust_utf8_check,
    rust_utf8_continuation_score,
)


def test_rust_layer_branches() -> None:
    if is_rust_available():
        h = rust_byte_histogram(b"abc")
        assert len(h) == 256
        assert rust_utf8_continuation_score(b"\xc3\xa9") >= 0.0
        ok, conf = rust_utf8_check(b"hello")
        assert isinstance(ok, bool)
        assert 0.0 <= conf <= 1.0
    else:
        with pytest.raises(RuntimeError):
            rust_byte_histogram(b"x")
        with pytest.raises(RuntimeError):
            rust_utf8_continuation_score(b"x")
        with pytest.raises(RuntimeError):
            rust_utf8_check(b"x")
