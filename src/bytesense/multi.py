"""
Multi-encoding document detector.

Splits a byte sequence into segments and detects encoding per-segment.
Useful for legacy email with mixed encodings or multi-part documents.

"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .api import from_bytes
from .models import DetectionResult


@dataclass
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
            return self.data.decode("utf_8", errors="replace")
        return self.data.decode(self.encoding, errors="replace")

    def to_dict(self) -> Dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "length": self.end - self.start,
            "encoding": self.encoding,
            "confidence": self.detection.confidence,
            "language": self.detection.language,
        }


@dataclass
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
    1. Split `data` into overlapping segments of `segment_size` bytes.
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
    if len(data) <= segment_size:
        # Single-segment case — fast path
        result = from_bytes(data)
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
        chunk = data[pos:end]
        if len(chunk) >= min_segment_bytes:
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
                # Extend current segment
                cur_end = end
                # Re-detect on the merged range for a better result
                cur_result = from_bytes(data[cur_start:cur_end])
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
