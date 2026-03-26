"""
Mojibake repair engine.

Mojibake = text that was decoded with the wrong encoding and then
re-encoded or displayed as-is, producing garbled characters.

Classic pattern: UTF-8 bytes → decoded as Latin-1 → re-encoded → "Ã©tÃ©" instead of "été"

Strategy:
  1. Re-encode the garbled string back to bytes using the assumed wrong encoding.
  2. Try to decode those bytes with the correct encoding.
  3. Accept the result if mess_ratio improves significantly.

Supports:
  - Single-step mojibake   (utf-8 → latin-1 → utf-8)
  - Double-step mojibake   (utf-8 → latin-1 → utf-8 → latin-1 → utf-8)
  - Windows-1252 variant   (utf-8 → cp1252 → utf-8)
  - Detection-guided repair (auto-detect which transformation was applied)

"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .mess import mess_ratio

# Ordered list of (re-encode-as, then-decode-as) transformation chains to try.
# Most common patterns first.
_REPAIR_CHAINS: list[tuple[str, str]] = [
    ("latin_1", "utf_8"),  # UTF-8 read as Latin-1 (most common)
    ("cp1252", "utf_8"),  # UTF-8 read as Windows-1252
    ("latin_1", "cp1252"),  # cp1252 read as Latin-1
    ("latin_1", "cp1251"),  # Cyrillic UTF-8 read as Latin-1
    ("latin_1", "cp1253"),  # Greek UTF-8 read as Latin-1
    ("latin_1", "cp1256"),  # Arabic UTF-8 read as Latin-1
    ("latin_1", "iso8859_2"),  # Central European UTF-8 read as Latin-1
    ("utf_8", "latin_1"),  # Latin-1 re-encoded as UTF-8 (less common)
    ("cp1252", "latin_1"),  # Latin-1 mistaken for cp1252
]

# Maximum improvement in mess ratio to accept a repair
_MIN_IMPROVEMENT: float = 0.10


def _likely_utf8_mojibake(text: str) -> bool:
    """Heuristic markers when UTF-8 was misread as Latin-1 / cp1252 (mess may stay low)."""
    return any(m in text for m in ("Ã", "Â", "â", "Ä", "Å", "Æ", "Ç", "Ð", "Ñ", "Ø", "Ù"))


# UTF-8 read as Latin-1 / cp1252: only these chains are used for equal-mess tie-break
# (broader chains are still tried for strict mess improvement).
_TIE_BREAK_CHAINS: frozenset[tuple[str, str]] = frozenset(
    {
        ("latin_1", "utf_8"),
        ("cp1252", "utf_8"),
    }
)


@dataclass
class RepairResult:
    """Result of a mojibake repair attempt."""

    original: str
    repaired: str
    improved: bool
    chain: Optional[tuple[str, str]]  # (re_encode, decode) or None
    original_mess: float
    repaired_mess: float
    iterations: int  # Number of repair steps applied (1 = single, 2 = double)

    @property
    def improvement(self) -> float:
        return self.original_mess - self.repaired_mess

    def __str__(self) -> str:
        if not self.improved:
            return self.original
        return self.repaired

    def __repr__(self) -> str:
        return (
            f"RepairResult(improved={self.improved}, "
            f"chain={self.chain!r}, "
            f"improvement={self.improvement:.3f})"
        )


def _try_chain(text: str, re_encode: str, decode_as: str) -> Optional[str]:
    """
    Apply one transformation: re-encode text with `re_encode`, then decode as `decode_as`.
    Returns repaired string or None if transformation fails or produces worse text.
    """
    try:
        raw = text.encode(re_encode, errors="strict")
        return raw.decode(decode_as, errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
        return None


def repair(
    text: str,
    max_iterations: int = 2,
    chains: Optional[List[tuple[str, str]]] = None,
) -> RepairResult:
    """
    Attempt to repair mojibake in ``text``.

    Args:
        text:           Potentially garbled string to repair.
        max_iterations: Maximum repair cycles (1 = single chain, 2 = double).
        chains:         Override the default transformation chain list.

    Returns:
        :class:`RepairResult` — always contains the best available result.
        Check ``.improved`` to know if repair was applied.

    Example::

        from bytesense.repair import repair

        garbled = "Ã©tÃ©"
        result = repair(garbled)
        if result.improved:
            print(result.repaired)   # "été"
        else:
            print(result.original)   # unchanged
    """
    if not text:
        return RepairResult(
            original=text,
            repaired=text,
            improved=False,
            chain=None,
            original_mess=0.0,
            repaired_mess=0.0,
            iterations=0,
        )

    original_mess = mess_ratio(text)
    best_text = text
    best_mess = original_mess
    best_chain: Optional[tuple[str, str]] = None
    best_iters = 0

    effective_chains = chains if chains is not None else _REPAIR_CHAINS

    # Single-step: collect candidates, then pick lowest mess then preferred chain order.
    options: list[tuple[tuple[str, str], str, float, int]] = []
    for i, (re_encode, decode_as) in enumerate(effective_chains):
        candidate = _try_chain(text, re_encode, decode_as)
        if candidate is None or candidate == text:
            continue
        candidate_mess = mess_ratio(candidate)
        strong_improvement = (original_mess - candidate_mess) >= _MIN_IMPROVEMENT
        tie_utf8_mojibake = (
            _likely_utf8_mojibake(text)
            and (re_encode, decode_as) in _TIE_BREAK_CHAINS
            and candidate_mess <= original_mess + 1e-9
        )
        if strong_improvement or tie_utf8_mojibake:
            options.append(((re_encode, decode_as), candidate, candidate_mess, i))

    if options:
        options.sort(key=lambda x: (x[2], x[3]))
        best_chain, best_text, best_mess, _ = (
            options[0][0],
            options[0][1],
            options[0][2],
            options[0][3],
        )
        best_iters = 1

    # Double-step repair (only if single-step improved things)
    if max_iterations >= 2 and best_iters == 1 and best_mess > 0.05:
        opts2: list[tuple[tuple[str, str], str, float, int]] = []
        for i, (re_encode2, decode_as2) in enumerate(effective_chains):
            candidate2 = _try_chain(best_text, re_encode2, decode_as2)
            if candidate2 is None or candidate2 == best_text:
                continue
            candidate2_mess = mess_ratio(candidate2)
            strong_improvement = (original_mess - candidate2_mess) >= _MIN_IMPROVEMENT
            tie_utf8_mojibake = (
                _likely_utf8_mojibake(best_text)
                and (re_encode2, decode_as2) in _TIE_BREAK_CHAINS
                and candidate2_mess <= best_mess + 1e-9
            )
            if strong_improvement or tie_utf8_mojibake:
                opts2.append(((re_encode2, decode_as2), candidate2, candidate2_mess, i))
        if opts2:
            opts2.sort(key=lambda x: (x[2], x[3]))
            best_chain = opts2[0][0]
            best_text = opts2[0][1]
            best_mess = opts2[0][2]
            best_iters = 2

    improved = best_iters > 0 and (
        (original_mess - best_mess) >= _MIN_IMPROVEMENT
        or (best_text != text and _likely_utf8_mojibake(text) and best_mess <= original_mess + 1e-9)
    )

    return RepairResult(
        original=text,
        repaired=best_text if improved else text,
        improved=improved,
        chain=best_chain if improved else None,
        original_mess=original_mess,
        repaired_mess=best_mess if improved else original_mess,
        iterations=best_iters if improved else 0,
    )


def repair_bytes(
    data: bytes,
    encoding: Optional[str] = None,
    **kwargs: object,
) -> RepairResult:
    """
    Repair mojibake in a byte sequence.

    First decodes ``data`` with ``encoding`` (auto-detected if None),
    then applies text-level repair.

    Args:
        data:     Byte sequence to repair.
        encoding: Known encoding. If None, auto-detected via ``from_bytes``.
        **kwargs: Forwarded to ``repair()``.

    Returns:
        :class:`RepairResult`
    """
    if encoding is None:
        from .api import from_bytes as _fb

        r = _fb(data)
        enc = r.encoding or "utf_8"
    else:
        enc = encoding

    try:
        text = data.decode(enc, errors="replace")
    except LookupError:
        text = data.decode("utf_8", errors="replace")

    return repair(text, **kwargs)  # type: ignore[arg-type]


def is_mojibake(text: str, threshold: float = 0.15) -> bool:
    """
    Quick heuristic to determine if text looks like mojibake.

    Returns True if the text has high mess ratio AND attempting at least one
    repair chain produces a significantly cleaner result.

    Args:
        text:      String to check.
        threshold: Mess ratio above which we attempt repair and check.

    Returns:
        bool
    """
    if mess_ratio(text) < threshold and not _likely_utf8_mojibake(text):
        return False
    result = repair(text)
    return result.improved
