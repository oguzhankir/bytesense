"""
Raw-byte priors for candidate ordering (no external detectors).

Heuristic ranges are approximate; they only reorder the existing shortlist so
likely encodings are tried earlier before decode+mess ranking.
"""
from __future__ import annotations

from typing import List, Optional


def _bump_to_front(candidates: List[str], *want: str) -> List[str]:
    seen: set[str] = set()
    front: List[str] = []
    for e in want:
        if e in candidates and e not in seen:
            front.append(e)
            seen.add(e)
    rest = [c for c in candidates if c not in seen]
    return front + rest


def hebrew_sbcs_likelihood(data: bytes) -> float:
    """Share of high bytes in typical Windows-1255 Hebrew letter range (0xE0–0xFA)."""
    if len(data) < 8:
        return 0.0
    hi = sum(1 for b in data if b >= 0x80)
    if hi < 8:
        return 0.0
    heb = sum(1 for b in data if 0xE0 <= b <= 0xFA)
    return heb / hi


def thai_tis620_likelihood(data: bytes) -> float:
    """
    Share of high bytes in the lower TIS-620 Thai band (0xA1–0xDF).

    Excludes 0xE0–0xFA, which overlaps Windows-1255 Hebrew and inflates false Thai scores.
    """
    if len(data) < 8:
        return 0.0
    hi = sum(1 for b in data if b >= 0x80)
    if hi < 8:
        return 0.0
    th = sum(1 for b in data if 0xA1 <= b <= 0xDF)
    return th / hi


def koi8_byte_hint(data: bytes) -> bool:
    """KOI8-R Cyrillic uses many high bytes in 0xC0–0xFF — avoid false Hebrew reorder."""
    hi = [b for b in data if b >= 0x80]
    if len(hi) < 24:
        return False
    block = sum(1 for b in hi if 0xC0 <= b <= 0xFF)
    return block / len(hi) >= 0.58


def cp866_vs_cp1251_hint(data: bytes) -> Optional[str]:
    """DOS (cp866) block 0x80–0xAF vs Windows (cp1251) 0xC0–0xFF — rough split."""
    hi = [b for b in data if b >= 0x80]
    if len(hi) < 20:
        return None
    b866 = sum(1 for b in hi if 0x80 <= b <= 0xAF)
    b1251 = sum(1 for b in hi if 0xC0 <= b <= 0xFF)
    t = len(hi)
    if b866 / t >= 0.40 and b1251 / t <= 0.42:
        return "cp866"
    if b1251 / t >= 0.40 and b866 / t <= 0.38:
        return "cp1251"
    return None


def japanese_mbcs_bias(data: bytes) -> Optional[str]:
    """Rough Shift_JIS vs EUC-JP from multi-byte pair patterns."""
    if len(data) < 24:
        return None
    sj = 0
    ej = 0
    for i in range(len(data) - 1):
        b1, b2 = data[i], data[i + 1]
        if 0x81 <= b1 <= 0x9F or 0xE0 <= b1 <= 0xFC:
            if 0x40 <= b2 <= 0xFC and b2 != 0x7F:
                sj += 1
        if 0xA1 <= b1 <= 0xFE and 0xA1 <= b2 <= 0xFE:
            ej += 1
        if b1 == 0x8E and 0xA1 <= b2 <= 0xDF:
            ej += 2
    if sj + ej < 14:
        return None
    # CP866 Cyrillic: moderate EUC-like pair counts without true JIS dominance — not Japanese.
    hint = cp866_vs_cp1251_hint(data)
    if hint == "cp866":
        if ej > sj * 5.0:
            return "euc_jp"
        if sj > ej * 1.4 and sj >= 40:
            return "shift_jis"
        return None
    if sj > ej * 1.2:
        return "shift_jis"
    if ej > sj * 1.2:
        return "euc_jp"
    return None


def chinese_big5_vs_gb_hint(data: bytes) -> Optional[str]:
    """
    GB18030 can use 4-byte sequences; Big5 is overwhelmingly two-byte pairs.
    Very rough — ranking still validates via decode+mess.
    """
    if len(data) < 32:
        return None
    quadish = 0
    for i in range(len(data) - 3):
        if 0x81 <= data[i] <= 0xFE and 0x30 <= data[i + 1] <= 0x39:
            quadish += 1
    if quadish >= max(4, len(data) // 400):
        return "gb18030"
    pairs = 0
    for i in range(len(data) - 1):
        b1, b2 = data[i], data[i + 1]
        if 0xA1 <= b1 <= 0xFE and 0x40 <= b2 <= 0xFE:
            pairs += 1
    if pairs >= len(data) // 6:
        return "big5"
    return None


def reorder_candidates(data: bytes, candidates: List[str]) -> List[str]:
    """Apply raw-byte hints by moving likely encodings earlier."""
    out = list(candidates)

    if (
        hebrew_sbcs_likelihood(data) >= 0.50
        and cp866_vs_cp1251_hint(data) is None
        and not koi8_byte_hint(data)
    ):
        out = _bump_to_front(out, "cp1255", "iso8859_8")

    if thai_tis620_likelihood(data) >= 0.52 and hebrew_sbcs_likelihood(data) < 0.55:
        out = _bump_to_front(out, "tis_620", "iso8859_11")

    hint = cp866_vs_cp1251_hint(data)
    if hint == "cp866":
        out = _bump_to_front(out, "cp866", "koi8_r", "cp1251")
    elif hint == "cp1251":
        out = _bump_to_front(out, "cp1251", "koi8_r", "cp866")

    jb = japanese_mbcs_bias(data)
    if jb == "shift_jis":
        out = _bump_to_front(out, "shift_jis", "cp932", "euc_jp", "iso2022_jp")
    elif jb == "euc_jp":
        out = _bump_to_front(out, "euc_jp", "iso2022_jp", "shift_jis", "cp932")

    if jb is None:
        ch = chinese_big5_vs_gb_hint(data)
        if ch == "gb18030":
            out = _bump_to_front(out, "gb18030", "gbk", "gb2312", "big5", "big5hkscs")
        elif ch == "big5":
            out = _bump_to_front(out, "big5", "big5hkscs", "gb18030", "gbk", "gb2312")

    return out
