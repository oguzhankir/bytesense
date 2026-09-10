"""Compact character-pair evidence; optional native scoring has identical semantics."""

from __future__ import annotations

import gzip
import json
import unicodedata
from collections import Counter
from functools import lru_cache
from importlib.resources import files
from typing import Any

from ._rust import is_rust_available


@lru_cache(maxsize=1)
def _model() -> tuple[frozenset[str], dict[str, float], Any]:
    payload = json.loads(
        gzip.decompress(files("bytesense.data").joinpath("language.json.gz").read_bytes())
    )
    letters, pairs = frozenset(payload["letters"]), payload["pairs"]
    if any(not 0.0 <= weight <= 1.0 for weight in pairs.values()):
        raise ValueError("model pair support must be between zero and one")
    native = None
    if is_rust_available():
        from ._rust_core import NgramModel  # type: ignore[import-not-found]

        native = NgramModel(payload["letters"], list(payload["pairs"].items()))
    return letters, pairs, native


def _prepare(text: str) -> tuple[str, float, float]:
    if not text:
        return "", 0.0, 0.0
    counts = Counter(text)
    bad = sum(n for c, n in counts.items() if not c.isprintable() and c not in "\n\r\t") / len(text)
    symbols = sum(
        n
        for c, n in counts.items()
        if c in "\\^`{|}~#"
        or (
            ord(c) >= 128
            and not c.isalpha()
            and not c.isspace()
            and unicodedata.category(c)[0] not in "PNM"
        )
    ) / len(text)
    lower = text.lower()
    table = {ord(c): c if c.isalpha() else " " for c in set(lower)}
    return lower.translate(table), bad, symbols


def _score_pure(
    text: str, bad: float, symbols: float, letters: frozenset[str], pairs: dict[str, float]
) -> float:
    counts = Counter(text)
    total_letters = sum(n for c, n in counts.items() if c != " ")
    known_letters = sum(n for c, n in counts.items() if c != " " and c in letters)
    total = 0
    known = 0.0
    for (a, b), n in Counter(zip(text, text[1:])).items():
        if a == b == " ":
            continue
        weight = n * (1 if (a + b).isascii() else 4)
        total += weight
        if a + b in pairs:
            known += weight * pairs[a + b]
    return (
        0.25 * known_letters / max(1, total_letters)
        + 0.75 * known / max(1, total)
        - bad * 5
        - symbols * 3
    )


def _classify(chars: str) -> list[tuple[bool, bool, bool]]:
    """Unicode scalar properties from this Python version; no document state."""
    return [
        (
            c.isalpha(),
            not c.isprintable() and c not in "\n\r\t",
            c in "\\^`{|}~#"
            or (
                ord(c) >= 128
                and not c.isalpha()
                and not c.isspace()
                and unicodedata.category(c)[0] not in "PNM"
            ),
        )
        for c in chars
    ]


def _quality(text: str, minimum: float | None) -> tuple[float, float] | None:
    # Canonically equivalent spellings must provide the same evidence. In
    # particular, Vietnamese legacy text often stores combining tone marks.
    # This only normalizes scoring input; returned text/bytes are never changed.
    text = unicodedata.normalize("NFC", text)
    letters, pairs, native = _model()
    if native:
        result = native.quality(text, text.lower(), _classify, minimum)
        if result is None:
            return None
        score, bad = result
    else:
        normalized, bad, symbols = _prepare(text)
        # All model supports are in [0, 1]. This bound cannot prune an
        # acceptable candidate, even before scoring its character pairs.
        if minimum is not None and 1.0 - 5 * bad - 3 * symbols + 1e-9 < minimum:
            return None
        score = _score_pure(normalized, bad, symbols, letters, pairs)
    return round(score, 10), bad


def text_quality(text: str) -> tuple[float, float]:
    """Return exact linguistic support and control ratio, not a probability."""
    result = _quality(text, None)
    assert result is not None
    return result


def quality_if_supported(text: str, minimum: float = 0.25) -> tuple[float, float] | None:
    """Skip pair scoring only when an upper bound proves insufficient support."""
    return _quality(text, minimum)
