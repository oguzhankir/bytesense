"""
chardet / charset-normalizer drop-in compatibility layer.

Migration:
    # Before
    from chardet import detect
    # or
    from charset_normalizer import detect

    # After
    from bytesense import detect   # identical interface
"""
from __future__ import annotations

from typing import Dict, Optional, Union

from .api import from_bytes


def detect(byte_str: Union[bytes, bytearray]) -> Dict[str, Optional[object]]:
    """
    Drop-in replacement for ``chardet.detect()`` and
    ``charset_normalizer.detect()``.

    Args:
        byte_str: The byte sequence to examine.

    Returns:
        ``{"encoding": str|None, "confidence": float|None, "language": str}``
    """
    if not isinstance(byte_str, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(byte_str).__name__!r}")
    result = from_bytes(bytes(byte_str))
    return {
        "encoding": result.encoding,
        "confidence": result.confidence if result.encoding else None,
        "language": result.language,
    }
