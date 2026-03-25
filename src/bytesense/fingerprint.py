"""
Byte-distribution fingerprinting engine.

The central insight: every encoding has a characteristic byte-frequency
"signature". By computing the cosine similarity between the observed
byte histogram and pre-computed encoding fingerprints, we can shortlist
likely encodings in O(n) time without any decoding.
"""
from __future__ import annotations

import array
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Core histogram (may be replaced by Rust at module load time — see _rust.py)
# ---------------------------------------------------------------------------


def byte_histogram(data: bytes) -> array.array:
    """
    Compute byte frequency histogram.
    Returns a 256-element ``array.array("L", ...)`` of occurrence counts.
    O(n), single pass.
    """
    hist: array.array = array.array("L", [0] * 256)
    # Process 8 bytes at a time to hint CPython for loop unrolling
    i = 0
    n = len(data)
    while i + 7 < n:
        hist[data[i]] += 1
        hist[data[i + 1]] += 1
        hist[data[i + 2]] += 1
        hist[data[i + 3]] += 1
        hist[data[i + 4]] += 1
        hist[data[i + 5]] += 1
        hist[data[i + 6]] += 1
        hist[data[i + 7]] += 1
        i += 8
    while i < n:
        hist[data[i]] += 1
        i += 1
    return hist


def histogram_to_ratios(hist: array.array, total: int) -> List[float]:
    """Convert raw counts to frequency ratios."""
    if total == 0:
        return [0.0] * 256
    inv = 1.0 / total
    return [c * inv for c in hist]


def high_byte_ratio(hist: array.array, total: int) -> float:
    """Fraction of bytes with value >= 0x80."""
    if total == 0:
        return 0.0
    return sum(hist[0x80:]) / total


def null_byte_ratio(hist: array.array, total: int) -> float:
    """Fraction of 0x00 bytes."""
    if total == 0:
        return 0.0
    return hist[0] / total


def cp1252_zone_ratio(hist: array.array, total: int) -> float:
    """
    Fraction of bytes in 0x80–0x9F.
    Non-zero → almost certainly cp1252 family, NOT latin_1
    (latin_1 treats 0x80-0x9F as C1 control codes; cp1252 maps them to printable chars).
    """
    if total == 0:
        return 0.0
    return sum(hist[0x80:0xA0]) / total


def utf8_continuation_score(data: bytes) -> float:
    """
    Score how well `data` fits UTF-8 multibyte sequence structure.
    Returns 0.0 (no evidence) to 1.0 (strong UTF-8 multibyte pattern).
    Works even when the data is not fully valid UTF-8.
    """
    if not data:
        return 0.0

    valid = 0
    invalid = 0
    i = 0
    n = len(data)

    while i < n:
        b = data[i]
        if b < 0x80:
            i += 1
            continue
        elif 0xC2 <= b <= 0xDF:
            seq_len = 2
        elif 0xE0 <= b <= 0xEF:
            seq_len = 3
        elif 0xF0 <= b <= 0xF4:
            seq_len = 4
        else:
            invalid += 1
            i += 1
            continue

        if i + seq_len > n:
            invalid += 1
            i += 1
            continue

        ok = all(0x80 <= data[i + j] <= 0xBF for j in range(1, seq_len))
        if ok:
            valid += 1
            i += seq_len
        else:
            invalid += 1
            i += 1

    total = valid + invalid
    return valid / total if total > 0 else 0.0


def detect_null_pattern(data: bytes) -> str | None:
    """
    Detect UTF-16/32 from null-byte distribution pattern.
    Returns encoding name or None.
    """
    if len(data) < 8:
        return None

    sample = data[: min(512, len(data))]
    n = len(sample)

    # UTF-32 BE: \x00\x00\x00X
    be32 = sum(
        1
        for i in range(0, n - 3, 4)
        if sample[i] == 0 and sample[i + 1] == 0 and sample[i + 2] == 0 and sample[i + 3] != 0
    )
    if be32 > n // 8:
        return "utf_32_be"

    # UTF-32 LE: X\x00\x00\x00
    le32 = sum(
        1
        for i in range(0, n - 3, 4)
        if sample[i] != 0 and sample[i + 1] == 0 and sample[i + 2] == 0 and sample[i + 3] == 0
    )
    if le32 > n // 8:
        return "utf_32_le"

    # UTF-16 BE: \x00X
    be16 = sum(1 for i in range(0, n - 1, 2) if sample[i] == 0 and sample[i + 1] != 0)
    if be16 > n // 4:
        return "utf_16_be"

    # UTF-16 LE: X\x00
    le16 = sum(1 for i in range(0, n - 1, 2) if sample[i] != 0 and sample[i + 1] == 0)
    if le16 > n // 4:
        return "utf_16_le"

    return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(y * y for y in b) ** 0.5
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def shortlist_encodings(
    hist: array.array,
    total: int,
    top_n: int = 12,
) -> List[Tuple[str, float]]:
    """
    Use the pre-computed fingerprint table to rank all encodings by
    byte-distribution similarity, returning the top_n most likely candidates.
    O(k) where k = number of fingerprints (~99).  No decoding performed.
    """
    try:
        from .data.fingerprints import ENCODING_FINGERPRINTS
    except ImportError:
        # Fingerprints not generated yet — return all encodings unranked
        from .constant import ALL_ENCODINGS

        return [(enc, 0.5) for enc in ALL_ENCODINGS[:top_n]]

    ratios = histogram_to_ratios(hist, total)
    scores: List[Tuple[str, float]] = [
        (enc, _cosine_similarity(ratios, fp)) for enc, fp in ENCODING_FINGERPRINTS.items()
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_n]


def fingerprint_cosine_for_encoding(data: bytes, encoding: str) -> float:
    """
    Cosine similarity (0..1) between `data`'s byte histogram and the
    precomputed fingerprint for `encoding`. Used to break ties when several
    decodings look linguistically plausible (e.g. Big5 bytes mis-read as cp949).
    """
    try:
        from .data.fingerprints import ENCODING_FINGERPRINTS
    except ImportError:
        return 0.0
    fp = ENCODING_FINGERPRINTS.get(encoding)
    if fp is None:
        return 0.0
    n = len(data)
    if n == 0:
        return 0.0
    hist = byte_histogram(data)
    ratios = histogram_to_ratios(hist, n)
    return _cosine_similarity(ratios, fp)


from ._rust import _RUST_AVAILABLE  # noqa: E402 — intentional late import

if _RUST_AVAILABLE:
    import array as _array

    from ._rust_core import (  # type: ignore[import]
        byte_histogram as _rust_bh,
    )
    from ._rust_core import (
        utf8_continuation_score as _rust_u8s,
    )

    def byte_histogram(data: bytes) -> _array.array:  # type: ignore[no-redef]
        return _array.array("L", _rust_bh(data))

    def utf8_continuation_score(data: bytes) -> float:  # type: ignore[no-redef]
        return _rust_u8s(data)
