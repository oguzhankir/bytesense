from __future__ import annotations

import os

import pytest

from bytesense._rust import is_rust_available

pytestmark = pytest.mark.skipif(
    not is_rust_available(),
    reason="Rust extension not compiled — run: maturin develop --release",
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


def test_rust_is_faster_than_python() -> None:
    """Rust histogram must be at least 5x faster than pure Python on 100KB data."""
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        pytest.skip("Performance assertions are too noisy on shared CI runners")

    import time

    from bytesense._rust_core import byte_histogram as rust_hist  # type: ignore[import-untyped]

    from bytesense.fingerprint import byte_histogram as py_hist

    data = bytes(range(256)) * 400  # 102 400 bytes

    # Warmup
    for _ in range(10):
        rust_hist(data)
        py_hist(data)

    n = 200

    t0 = time.perf_counter()
    for _ in range(n):
        rust_hist(data)
    rust_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(n):
        py_hist(data)
    py_time = time.perf_counter() - t0

    speedup = py_time / rust_time
    min_speedup = 5.0
    assert speedup >= min_speedup, f"Expected >={min_speedup}x speedup, got {speedup:.1f}x"
