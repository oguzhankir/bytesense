"""Language evidence from shared character statistics, without retaining user text."""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .constant import CHAR_FREQUENCIES

# Only static language metadata is retained globally. Document text is never cached.
_RANKS = {
    language: {c: i for i, c in enumerate(chars)} for language, chars in CHAR_FREQUENCIES.items()
}


def _score(
    counter: Counter[str],
    language: str,
    ordered: Optional[list[tuple[str, int]]] = None,
    total: Optional[int] = None,
) -> float:
    ranks = _RANKS.get(language)
    if not ranks or not counter:
        return 0.0
    score = weight_sum = 0.0
    total = sum(counter.values()) if total is None else total
    covered = 0
    for position, (char, count) in enumerate(
        (counter.most_common() if ordered is None else ordered)[: len(ranks) + 5]
    ):
        weight = 1.0 / (1 + position)
        weight_sum += weight
        if char in ranks:
            score += weight / (1 + abs(position - ranks[char]) * 0.08)
            covered += count
    # Unknown letters are evidence too. The old denominator ignored them and
    # reported perfect Arabic coherence for mostly Latin mojibake.
    return (score / weight_sum) * (covered / total) ** 0.5 if weight_sum else 0.0


def _letters(text: str) -> Counter[str]:
    counts = Counter(text.lower())
    return Counter({char: n for char, n in counts.items() if char.isalpha()})


def coherence_score(text: str, language: str) -> float:
    """Heuristic language support in [0, 1], not a probability."""
    return _score(_letters(text), language)


def detect_language(
    text: str,
    candidates: Optional[list[str]] = None,
    threshold: float = 0.1,
) -> list[tuple[str, float]]:
    """Rank languages using one character count for the entire candidate set."""
    counts = _letters(text)
    ordered = counts.most_common()
    total = sum(counts.values())
    result = [
        (language, _score(counts, language, ordered, total))
        for language in (_RANKS if candidates is None else candidates)
    ]
    return sorted(
        ((language, score) for language, score in result if score >= threshold),
        key=lambda item: item[1],
        reverse=True,
    )
