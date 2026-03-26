"""
bytesense — Fast, accurate charset/encoding detection.

Zero ML. Zero dependencies. Optional Rust acceleration.
Author: Oğuzhan Kır
"""
from __future__ import annotations

import logging

from .api import from_bytes, from_fp, from_path, is_binary
from .hints import best_hint, hint_from_content, hint_from_http_headers
from .legacy import detect
from .models import DetectionResult, EncodingAlternative
from .multi import DocumentSegment, MultiEncodingResult, detect_multi
from .repair import RepairResult, is_mojibake, repair, repair_bytes
from .streaming import StreamDetector, detect_stream
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
    "detect_stream",
    "repair",
    "repair_bytes",
    "is_mojibake",
    "RepairResult",
    "hint_from_http_headers",
    "hint_from_content",
    "best_hint",
    "detect_multi",
    "MultiEncodingResult",
    "DocumentSegment",
    "__version__",
    "VERSION",
]

__author__ = "Oğuzhan Kır"

logging.getLogger("bytesense").addHandler(logging.NullHandler())
