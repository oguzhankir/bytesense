from __future__ import annotations

import pytest

from bytesense._rust import is_rust_available

pytestmark = pytest.mark.skipif(
    not is_rust_available(),
    reason="Rust extension not compiled",
)


def test_rust_available() -> None:
    assert is_rust_available() is True


def test_rust_histogram_length() -> None:
    from bytesense._rust_core import byte_histogram  # type: ignore[import-untyped]

    h = byte_histogram(b"hello world")
    assert len(h) == 256


def test_rust_histogram_counts() -> None:
    from bytesense._rust_core import byte_histogram  # type: ignore[import-untyped]

    h = byte_histogram(b"aab")
    assert h[ord("a")] == 2
    assert h[ord("b")] == 1


def test_rust_utf8_check_valid() -> None:
    from bytesense._rust_core import utf8_check  # type: ignore[import-untyped]

    valid, conf = utf8_check("héllo".encode())
    assert valid is True
    assert conf == pytest.approx(1.0)


def test_rust_utf8_check_invalid() -> None:
    from bytesense._rust_core import utf8_check  # type: ignore[import-untyped]

    valid, conf = utf8_check(b"\xff\xfe\x00hello")
    assert valid is False
    assert 0.0 <= conf <= 1.0


def test_native_histogram_matches_independent_python_implementation() -> None:
    from bytesense._rust_core import byte_histogram as rust_hist

    from bytesense.fingerprint import _byte_histogram_pure

    for data in (b"", bytes(range(256)) * 400, b"x" * 100003):
        assert rust_hist(data) == list(_byte_histogram_pure(data))
