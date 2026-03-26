"""
Optional Rust extension loader.

Exports accelerated implementations when the compiled extension is available.
Falls back to pure-Python equivalents in higher layers (see fingerprint.py).
"""
from __future__ import annotations

import array

_RUST_AVAILABLE: bool = False

try:
    from bytesense._rust_core import (  # type: ignore[import-untyped]
        byte_histogram as _core_byte_histogram,
    )
    from bytesense._rust_core import (
        utf8_check as _core_utf8_check,
    )
    from bytesense._rust_core import (
        utf8_continuation_score as _core_utf8_continuation_score,
    )

    _RUST_AVAILABLE = True
except ImportError:
    pass


def is_rust_available() -> bool:
    """Return ``True`` if the compiled Rust extension is loaded."""
    return _RUST_AVAILABLE


if _RUST_AVAILABLE:

    def rust_byte_histogram(data: bytes) -> array.array:
        return array.array("L", _core_byte_histogram(data))  # type: ignore[misc]

    def rust_utf8_continuation_score(data: bytes) -> float:
        return _core_utf8_continuation_score(data)  # type: ignore[misc]

    def rust_utf8_check(data: bytes) -> tuple[bool, float]:
        return _core_utf8_check(data)  # type: ignore[misc]

else:

    def rust_byte_histogram(data: bytes) -> array.array:  # type: ignore[misc]
        raise RuntimeError("Rust extension not available")

    def rust_utf8_continuation_score(data: bytes) -> float:  # type: ignore[misc]
        raise RuntimeError("Rust extension not available")

    def rust_utf8_check(data: bytes) -> tuple[bool, float]:  # type: ignore[misc]
        raise RuntimeError("Rust extension not available")
