"""
Mess / chaos detector.

Scores how "garbled" a decoded string is.
0.0 = clean human-readable text.
1.0 = completely garbled (wrong encoding).

Improvements over charset-normalizer:
- Weighted multi-component score (not a single heuristic)
- Bigram validity check for Latin scripts
- Word-length plausibility check
- Sliding-window approach for large texts
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple

from .constant import BIGRAM_FREQUENCIES


def _cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff") / len(text)


def _hangul_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if "\uac00" <= c <= "\ud7a3") / len(text)


def _skip_latin_mess_heuristics(text: str) -> bool:
    """Ideographic / Hangul text: Latin bigram/word-length heuristics are misleading."""
    if not text:
        return False
    return _cjk_ratio(text) > 0.18 or _hangul_ratio(text) > 0.18


@lru_cache(maxsize=16_384)
def _is_printable(char: str) -> bool:
    return char.isprintable()


def _latin_extended_fraction(text: str) -> float:
    """Share of Latin letters that use Latin Extended-A/B (Polish, Baltic, etc.)."""
    latin = [c for c in text if c.isalpha() and ord(c) < 0x300]
    if len(latin) < 4:
        return 0.0
    ext = sum(1 for c in latin if 0x100 <= ord(c) <= 0x024F)
    return ext / len(latin)


def _bigram_mess(text: str, language_hint: Optional[str] = None) -> float:
    """
    Fraction of Latin bigrams that are NOT in the valid set for any language.
    Lower = cleaner text.
    """
    # Build combined valid bigram set
    if language_hint and language_hint in BIGRAM_FREQUENCIES:
        valid: set[str] = set(BIGRAM_FREQUENCIES[language_hint])
    else:
        valid = set()
        for bg_list in BIGRAM_FREQUENCIES.values():
            valid.update(bg_list)

    if not valid:
        return 0.0

    if _skip_latin_mess_heuristics(text):
        return 0.0

    # Latin Extended: English-centric bigrams falsely flag Polish/Czech/Baltic as noise.
    if _latin_extended_fraction(text) > 0.22:
        return 0.0

    latin = [c.lower() for c in text if c.isalpha() and ord(c) < 0x250]
    if len(latin) < 8:
        return 0.0

    total = len(latin) - 1
    invalid = sum(1 for i in range(total) if latin[i] + latin[i + 1] not in valid)
    return invalid / total if total > 0 else 0.0


def _unprintable_ratio(text: str) -> float:
    n = len(text)
    if n == 0:
        return 0.0
    bad = sum(
        1 for c in text if not _is_printable(c) and c not in ("\n", "\r", "\t")
    )
    return bad / n


def _suspicious_ratio(text: str) -> float:
    n = len(text)
    if n == 0:
        return 0.0
    suspicious = sum(
        1
        for c in text
        if (0xFFFD <= ord(c) <= 0xFFFD)  # replacement char
        or (0xE000 <= ord(c) <= 0xF8FF)  # private use area
    )
    return min(suspicious / n, 1.0)


def _word_length_mess(text: str) -> float:
    if _skip_latin_mess_heuristics(text):
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    avg = sum(len(w) for w in words) / len(words)
    # Penalise: average word length > 25 characters suggests garbled text
    return min(max(avg - 25.0, 0.0) / 25.0, 1.0)


def mess_ratio(
    decoded: str,
    threshold: float = 0.2,
    language_hint: Optional[str] = None,
) -> float:
    """
    Compute chaos ratio for a decoded string chunk.

    Components (weighted sum):
      0.45 — unprintable character ratio
      0.25 — suspicious Unicode range ratio
      0.20 — bigram invalidity ratio  (Latin text only)
      0.10 — word length plausibility
    """
    if not decoded:
        return 0.0

    ratio = (
        _unprintable_ratio(decoded) * 0.45
        + _suspicious_ratio(decoded) * 0.25
        + _bigram_mess(decoded, language_hint) * 0.20
        + _word_length_mess(decoded) * 0.10
    )
    return min(ratio, 1.0)


def sliding_window_mess(
    decoded: str,
    window_size: int = 512,
    threshold: float = 0.2,
    language_hint: Optional[str] = None,
) -> Tuple[float, bool]:
    """
    Compute mess ratio with a sliding window.
    More accurate than a single pass on large or mixed-content strings.

    Returns:
        (mean_mess_ratio, exceeded_threshold_early)
    """
    if len(decoded) <= window_size:
        r = mess_ratio(decoded, threshold, language_hint)
        return r, r >= threshold

    step = window_size // 2
    ratios = []
    exceeded = 0

    for i in range(0, len(decoded) - window_size + 1, step):
        r = mess_ratio(decoded[i : i + window_size], threshold, language_hint)
        ratios.append(r)
        if r >= threshold:
            exceeded += 1
        # Early exit: more than half the windows already exceed threshold
        if exceeded > max(2, len(ratios) // 2):
            return sum(ratios) / len(ratios), True

    mean = sum(ratios) / len(ratios) if ratios else 0.0
    return mean, mean >= threshold
