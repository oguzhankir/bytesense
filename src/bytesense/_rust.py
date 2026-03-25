"""
Optional Rust extension loader.

Replaces pure-Python implementations with compiled Rust equivalents
when the extension module is available.  The public API is identical
regardless of whether Rust is loaded.
"""
from __future__ import annotations

_RUST_AVAILABLE: bool = False

try:
    import bytesense._rust_core  # noqa: F401 — extension probe

    _RUST_AVAILABLE = True
except ImportError:
    pass


def is_rust_available() -> bool:
    """Return ``True`` if the compiled Rust extension is loaded."""
    return _RUST_AVAILABLE
