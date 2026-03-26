"""
Language coherence detector.

Scores how well a decoded string matches a given language's
character frequency distribution.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import List, Optional, Tuple

from .constant import CHAR_FREQUENCIES


@lru_cache(maxsize=4096)
def coherence_score(text: str, language: str) -> float:
    """
    Score how well `text` matches `language`'s char-frequency distribution.
    Returns 0.0 to 1.0.
    """
    if language not in CHAR_FREQUENCIES:
        return 0.0

    expected = CHAR_FREQUENCIES[language]
    expected_set = frozenset(expected)
    expected_rank = {c: i for i, c in enumerate(expected)}

    counter: Counter[str] = Counter(c.lower() for c in text if c.isalpha())
    if not counter:
        return 0.0

    observed = [c for c, _ in counter.most_common(len(expected) + 5)]

    score = 0.0
    total_weight = 0.0

    for obs_rank, char in enumerate(observed):
        if char not in expected_set:
            continue
        exp_rank = expected_rank[char]
        weight = 1.0 / (1 + obs_rank)
        rank_diff = abs(obs_rank - exp_rank)
        rank_penalty = 1.0 / (1 + rank_diff * 0.08)
        score += weight * rank_penalty
        total_weight += weight

    if total_weight == 0.0:
        return 0.0
    return min(score / total_weight, 1.0)


def _detect_language_uncached(text: str, threshold: float) -> List[Tuple[str, float]]:
    languages = list(CHAR_FREQUENCIES.keys())
    results: List[Tuple[str, float]] = []
    for lang in languages:
        score = coherence_score(text, lang)
        if score >= threshold:
            results.append((lang, score))
    return sorted(results, key=lambda x: x[1], reverse=True)


@lru_cache(maxsize=512)
def _cached_detect_language(text: str, threshold: float) -> tuple[tuple[str, float], ...]:
    """Cached version — convert list to tuple for hashability."""
    return tuple(_detect_language_uncached(text, threshold))


def detect_language(
    text: str,
    candidates: Optional[List[str]] = None,
    threshold: float = 0.1,
) -> List[Tuple[str, float]]:
    """
    Detect language(s) present in `text`.

    Args:
        text:       Decoded text to analyse.
        candidates: If given, only test these languages.
        threshold:  Minimum score to include a language.

    Returns:
        List of (language, score) sorted by score descending.
    """
    if candidates is not None:
        languages = candidates
        results = [(lang, coherence_score(text, lang)) for lang in languages]
        return sorted(
            [(lang, score) for lang, score in results if score >= threshold],
            key=lambda x: x[1],
            reverse=True,
        )
    return list(_cached_detect_language(text, threshold))
