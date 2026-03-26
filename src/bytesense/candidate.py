"""
Candidate encoding selector.

Reduces ~99 possible encodings to a short list before decode+mess,
using only byte-level evidence.
"""
from __future__ import annotations

import array
from typing import List, Optional

from .constant import ALL_ENCODINGS, BOM_MARKERS, SIMILAR_ENCODINGS
from .fingerprint import (
    byte_histogram,
    cp1252_zone_ratio,
    detect_null_pattern,
    high_byte_ratio,
    null_byte_ratio,
    shortlist_encodings,
    utf8_continuation_score,
)
from .heuristics import reorder_candidates


def _looks_like_iso2022_bytes(data: bytes) -> bool:
    """7-bit ISO-2022 uses ESC $ / ESC ( sequences — not plain ASCII text."""
    if b"\x1b" not in data:
        return False
    return (
        b"\x1b\x24" in data
        or b"\x1b\x28" in data
        or b"\x1b\x29" in data
        or b"\x1b\x2e" in data
    )


class CandidateSelector:
    """
    Select the most likely encoding candidates for a byte sequence
    without performing any full decode.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.length = len(data)
        self._hist: Optional[array.array] = None
        self._ascii_only: Optional[bool] = None
        self._utf8_valid: Optional[bool] = None

    @property
    def hist(self) -> array.array:
        if self._hist is None:
            self._hist = byte_histogram(self.data)
        return self._hist

    def bom_encoding(self) -> Optional[str]:
        """Return the encoding if a BOM/SIG prefix is detected, else None."""
        for encoding, bom in sorted(BOM_MARKERS.items(), key=lambda x: -len(x[1])):
            if self.data.startswith(bom):
                return encoding
        return None

    def is_ascii_only(self) -> bool:
        if self._ascii_only is None:
            n = self.length
            if n == 0:
                self._ascii_only = True
            else:
                no_high_byte = all(self.hist[i] == 0 for i in range(0x80, 0x100))
                # UTF-16 (even ASCII text) uses many 0x00 bytes — not "pure ASCII" bytes.
                nbr = null_byte_ratio(self.hist, n)
                self._ascii_only = no_high_byte and nbr < 0.12
        return self._ascii_only

    def is_utf8_valid(self) -> bool:
        if self._utf8_valid is None:
            try:
                self.data.decode("utf_8")
                self._utf8_valid = True
            except UnicodeDecodeError:
                self._utf8_valid = False
        return self._utf8_valid

    def get_candidates(self) -> List[str]:
        """
        Return ordered list of encoding candidates, most likely first.

        Decision tree:
          1. BOM  → single winner
          2. ASCII-only → [ascii, utf_8]
          3. Valid UTF-8 → [utf_8, …]
          4. Null byte pattern → UTF-16/32 variants
          5. Byte fingerprint cosine similarity → top 12
        """
        bom = self.bom_encoding()
        if bom:
            return [bom]

        if self.is_ascii_only() and not _looks_like_iso2022_bytes(self.data):
            return ["ascii", "utf_8"]

        # UTF-16/32 shape must come before valid-UTF-8: ASCII in UTF-16 is often valid UTF-8 (NUL bytes).
        null_pat = detect_null_pattern(self.data)
        if null_pat:
            if "32" in null_pat:
                return [null_pat, "utf_32", "utf_32_be", "utf_32_le"]
            return [null_pat, "utf_16", "utf_16_be", "utf_16_le"]

        if self.is_utf8_valid() and not _looks_like_iso2022_bytes(self.data):
            candidates = ["utf_8"]
            # Check for CJK 3-byte sequences (0xE2-0xE4 range is CJK in UTF-8)
            cjk_signal = sum(self.hist[i] for i in range(0xE2, 0xE5))
            if cjk_signal > self.length * 0.05:
                candidates += ["gb18030", "big5", "shift_jis"]
            return list(dict.fromkeys(candidates))

        hbr = high_byte_ratio(self.hist, self.length)
        nbr = null_byte_ratio(self.hist, self.length)
        c1252 = cp1252_zone_ratio(self.hist, self.length)
        u8s = utf8_continuation_score(self.data[:4096])

        # Heavy null presence → UTF-16/32 only
        if nbr > 0.15:
            return ["utf_16", "utf_16_le", "utf_16_be", "utf_32", "utf_32_le", "utf_32_be"]

        # Strong UTF-8 continuation but invalid → likely truncated or damaged UTF-8
        exclude: set[str] = set()
        if u8s > 0.8:
            exclude.update(["shift_jis", "euc_kr", "johab", "cp949"])

        # Fingerprint-based shortlist
        scored = shortlist_encodings(self.hist, self.length, top_n=20)
        candidates = [enc for enc, _ in scored if enc not in exclude]

        if _looks_like_iso2022_bytes(self.data):
            for enc in ("iso2022_jp", "iso2022_jp_2004", "euc_jp", "shift_jis", "cp932"):
                if enc in exclude:
                    continue
                if enc not in candidates:
                    candidates.insert(0, enc)

        # SBCS / common legacy encodings must be reachable even when fingerprints rank MBCS first.
        # Include big5/cp949/euc_kr — short cosine list often omits them for small files.
        if hbr > 0.02:
            preferred: List[str] = []
            for enc in (
                "latin_1",
                "cp1252",
                "cp1250",
                "cp1254",
                "cp1256",
                "cp1255",
                "cp1257",
                "cp1258",
                "iso8859_8",
                "cp1251",
                "koi8_r",
                "koi8_u",
                "cp866",
                "cp1253",
                "mac_cyrillic",
                "tis_620",
                "iso8859_11",
                "big5",
                "big5hkscs",
                "gb2312",
                "gbk",
                "gb18030",
                "shift_jis",
                "euc_jp",
                "iso2022_jp",
                "cp949",
                "euc_kr",
                "johab",
                "iso8859_7",
            ):
                if enc in exclude:
                    continue
                if enc not in preferred:
                    preferred.append(enc)
            candidates = preferred + [c for c in candidates if c not in preferred]

        # Ensure cp1252 is always tried for high-byte European content
        if hbr > 0.05 and c1252 >= 0.001 and "cp1252" not in candidates:
            candidates.insert(0, "cp1252")

        # Deduplicate while preserving order
        seen: set[str] = set()
        final: List[str] = []
        for enc in candidates:
            if enc not in seen:
                seen.add(enc)
                final.append(enc)

        final = reorder_candidates(self.data, final)

        return final[:40] if final else ALL_ENCODINGS[:40]

    def exclude_similar_to_failed(
        self,
        failed: str,
        remaining: List[str],
    ) -> List[str]:
        """Remove encodings too similar to `failed` from `remaining`."""
        similar = set(SIMILAR_ENCODINGS.get(failed, []))
        return [enc for enc in remaining if enc not in similar]
