"""
Multi-encoding document detector.

Splits a byte sequence into segments and detects encoding per-segment.
Useful for legacy email with mixed encodings or multi-part documents.

"""

from __future__ import annotations

import codecs
import sys
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from .api import from_bytes
from .models import DetectionResult

_SLOTS_KW = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**_SLOTS_KW)
class DocumentSegment:
    """A contiguous segment of bytes with a detected encoding."""

    start: int
    end: int
    data: bytes
    detection: DetectionResult

    @property
    def encoding(self) -> Optional[str]:
        return self.detection.encoding

    @property
    def text(self) -> str:
        if self.encoding is None:
            raise UnicodeError("segment encoding is unknown; choose an explicit decoding policy")
        return self.data.decode(self.encoding, errors="strict")

    def to_dict(self) -> Dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "length": self.end - self.start,
            "encoding": self.encoding,
            "confidence": self.detection.confidence,
            "language": self.detection.language,
        }


@dataclass(**_SLOTS_KW)
class MultiEncodingResult:
    """Result of multi-encoding document analysis."""

    segments: List[DocumentSegment]
    is_uniform: bool  # True if all segments have the same encoding
    dominant: Optional[str]  # Most common encoding by byte weight

    @property
    def full_text(self) -> str:
        """Concatenate all segments decoded with their respective encodings."""
        return "".join(seg.text for seg in self.segments)

    def to_dict(self) -> Dict[str, object]:
        return {
            "is_uniform": self.is_uniform,
            "dominant": self.dominant,
            "segment_count": len(self.segments),
            "segments": [s.to_dict() for s in self.segments],
        }


def detect_multi(
    data: bytes,
    segment_size: int = 4096,
    min_segment_bytes: int = 128,
    merge_threshold: float = 0.85,
) -> MultiEncodingResult:
    """
    Detect encoding(s) in a potentially mixed-encoding document.

    Algorithm:
    1. Split `data` into contiguous segments near `segment_size` bytes.
    2. Detect encoding for each segment independently.
    3. Merge adjacent segments with the same encoding.
    4. Return the segment list.

    Args:
        data:               Byte sequence to analyse.
        segment_size:       Initial segment size in bytes.
        min_segment_bytes:  Minimum bytes per segment (smaller segments are merged).
        merge_threshold:    Confidence threshold to merge adjacent same-encoding segments.

    Returns:
        :class:`MultiEncodingResult`
    """
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if not isinstance(segment_size, int) or isinstance(segment_size, bool) or segment_size <= 0:
        raise ValueError("segment_size must be a positive integer")
    if (
        not isinstance(min_segment_bytes, int)
        or isinstance(min_segment_bytes, bool)
        or min_segment_bytes <= 0
    ):
        raise ValueError("min_segment_bytes must be a positive integer")
    if not 0.0 <= merge_threshold <= 1.0:
        raise ValueError("merge_threshold must be between 0 and 1")
    whole = from_bytes(data)
    # A fully validated Unicode/stateful stream must not be cut into arbitrary
    # byte windows; those windows can start inside a code unit or shift state.
    uniform = whole.encoding is not None and (
        whole.encoding.startswith("utf_")
        or (whole.encoding.startswith("iso2022_") or whole.encoding == "hz")
    )
    if len(data) <= segment_size or uniform:
        # Single-segment case — fast path
        result = whole
        seg = DocumentSegment(start=0, end=len(data), data=data, detection=result)
        return MultiEncodingResult(
            segments=[seg],
            is_uniform=True,
            dominant=result.encoding,
        )

    # Detect per-segment
    raw_segments: list[tuple[int, int, DetectionResult]] = []
    pos = 0
    while pos < len(data):
        end = min(pos + segment_size, len(data))
        if 0 < len(data) - end < min_segment_bytes:
            end = len(data)
        # When a full-file candidate is available, avoid cutting a complete
        # multibyte character at the right edge. Internal decode failures are
        # left to segment detection; no bytes are discarded.
        if whole.encoding and end < len(data):
            try:
                decoder = codecs.getincrementaldecoder(whole.encoding)()
                decoder.decode(data[pos:end], final=False)
                for _ in range(8):
                    pending = decoder.getstate()[0]
                    if not pending or end == len(data):
                        break
                    decoder.decode(data[end : end + 1], final=False)
                    end += 1
            except (UnicodeError, LookupError, TypeError):
                pass
        chunk = data[pos:end]
        r = from_bytes(chunk)
        raw_segments.append((pos, end, r))
        pos = end

    # Merge adjacent segments with same encoding
    merged: list[DocumentSegment] = []
    if raw_segments:
        cur_start, cur_end, cur_result = raw_segments[0]
        for start, end, result in raw_segments[1:]:
            if (
                result.encoding == cur_result.encoding
                and result.confidence >= merge_threshold
                and cur_result.confidence >= merge_threshold
            ):
                cur_end = end
                merged_len = cur_end - cur_start
                cur_result = replace(
                    cur_result,
                    byte_count=merged_len,
                    bytes_validated=merged_len if cur_result.encoding else 0,
                    bytes_examined=cur_result.bytes_examined + result.bytes_examined,
                    confidence=min(cur_result.confidence, result.confidence),
                )
            else:
                merged.append(
                    DocumentSegment(
                        start=cur_start,
                        end=cur_end,
                        data=data[cur_start:cur_end],
                        detection=cur_result,
                    )
                )
                cur_start, cur_end, cur_result = start, end, result
        merged.append(
            DocumentSegment(
                start=cur_start,
                end=cur_end,
                data=data[cur_start:cur_end],
                detection=cur_result,
            )
        )

    if not merged and data:
        r = from_bytes(data)
        merged = [DocumentSegment(start=0, end=len(data), data=data, detection=r)]

    # Determine dominant encoding by byte weight
    enc_weights: dict[str, int] = {}
    for seg in merged:
        enc = seg.encoding or "unknown"
        enc_weights[enc] = enc_weights.get(enc, 0) + (seg.end - seg.start)
    dominant = max(enc_weights, key=lambda k: enc_weights[k]) if enc_weights else None

    is_uniform = len({s.encoding for s in merged}) <= 1

    return MultiEncodingResult(
        segments=merged,
        is_uniform=is_uniform,
        dominant=dominant,
    )
