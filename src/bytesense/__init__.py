"""
bytesense — Fast, accurate charset/encoding detection.

Zero ML. Zero dependencies. Optional Rust acceleration.
Author: Oğuzhan Kır
"""
from __future__ import annotations

import logging

from .api import from_bytes, from_fp, from_path, is_binary
from .legacy import detect
from .models import DetectionResult, EncodingAlternative
from .streaming import StreamDetector
from .version import VERSION, __version__

__all__ = [
    "from_bytes",
    "from_fp",
    "from_path",
    "is_binary",
    "detect",
    "DetectionResult",
    "EncodingAlternative",
    "StreamDetector",
    "__version__",
    "VERSION",
]

__author__ = "Oğuzhan Kır"

logging.getLogger("bytesense").addHandler(logging.NullHandler())
