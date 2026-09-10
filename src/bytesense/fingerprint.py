"""
Byte-distribution fingerprinting engine.

The central insight: every encoding has a characteristic byte-frequency
"signature". By computing the cosine similarity between the observed
byte histogram and pre-computed encoding fingerprints, we can shortlist
likely encodings in O(n) time without any decoding.
"""

from __future__ import annotations

import array
from collections import Counter
from functools import lru_cache
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Core histogram (may be replaced by Rust at module load time — see _rust.py)
# ---------------------------------------------------------------------------


def _byte_histogram_pure(data: bytes) -> array.array:
    """Pure-Python byte histogram (also used when the Rust extension is absent)."""
    hist: array.array = array.array("Q", [0] * 256)
    for value, count in Counter(data).items():
        hist[value] = count
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


def _utf8_continuation_score_pure(data: bytes) -> float:
    """
    Pure-Python UTF-8 continuation scoring (also used when Rust is absent).
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

    sample = data[:512]
    # Distinguish byte lanes, including non-Latin UTF-16 and supplementary UTF-32.
    lanes = [sample[i::4] for i in range(4)]
    zero = [lane.count(0) / len(lane) for lane in lanes]
    if zero[0] > 0.8 and zero[1] > 0.8 and zero[3] < 0.5:
        return "utf_32_be"
    if zero[2] > 0.8 and zero[3] > 0.8 and zero[0] < 0.5:
        return "utf_32_le"
    even, odd = sample[0::2], sample[1::2]
    ze, zo = even.count(0) / len(even), odd.count(0) / len(odd)
    if ze >= 0.08 and zo < ze * 0.1:
        return "utf_16_be"
    if zo >= 0.08 and ze < zo * 0.1:
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
    scores = list(_scores_for_hist(hist).items())

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


@lru_cache(maxsize=1)
def _fingerprint_groups() -> list[tuple[list[str], tuple[float, ...]]]:
    from .data.fingerprints import ENCODING_FINGERPRINTS

    groups: dict[tuple[float, ...], list[str]] = {}
    for encoding, raw_vector in ENCODING_FINGERPRINTS.items():
        groups.setdefault(tuple(raw_vector), []).append(encoding)
    result = []
    for vector, names in groups.items():
        norm = sum(v * v for v in vector) ** 0.5
        result.append((names, tuple(v / norm if norm else 0.0 for v in vector)))
    return result


# Static profiles only: identical vectors share one dot product.


def _scores_for_hist(hist: array.array) -> dict[str, float]:
    norm = sum(n * n for n in hist) ** 0.5
    if not norm:
        return {name: 0.0 for names, _ in _fingerprint_groups() for name in names}
    observed = [(i, n / norm) for i, n in enumerate(hist) if n]
    scores: dict[str, float] = {}
    for names, vector in _fingerprint_groups():
        score = sum(n * vector[i] for i, n in observed)
        scores.update((name, score) for name in names)
    # Restore table order to preserve stable ties.
    from .data.fingerprints import ENCODING_FINGERPRINTS

    return {name: scores[name] for name in ENCODING_FINGERPRINTS}


def fingerprint_scores(data: bytes) -> dict[str, float]:
    """Score distinct static profiles from one sparse byte histogram."""
    return _scores_for_hist(byte_histogram(data))


from ._rust import (  # noqa: E402 — intentional late import
    _RUST_AVAILABLE,
    rust_byte_histogram,
    rust_utf8_continuation_score,
)


def byte_histogram(data: bytes) -> array.array:
    """
    Compute byte frequency histogram.
    Returns a 256-element ``array.array("Q", ...)`` of occurrence counts.
    O(n), single pass. Uses Rust when available.
    """
    if _RUST_AVAILABLE:
        return rust_byte_histogram(data)
    return _byte_histogram_pure(data)


def utf8_continuation_score(data: bytes) -> float:
    """
    Score how well `data` fits UTF-8 multibyte sequence structure.
    Returns 0.0 (no evidence) to 1.0 (strong UTF-8 multibyte pattern).
    Works even when the data is not fully valid UTF-8. Uses Rust when available.
    """
    if _RUST_AVAILABLE:
        return rust_utf8_continuation_score(data)
    return _utf8_continuation_score_pure(data)
