"""
Public detection API.

All public functions live here.  The internal pipeline:

  1. Validate input type
  2. BOM/SIG detection          → instant, certainty = 1.0
  3. ASCII-only check           → O(n), certainty = 1.0
  4. UTF-8 validity check       → O(n), high certainty
  5. Null-pattern (UTF-16/32)   → O(n)
  6. Byte fingerprint shortlist → O(n + k)
  7. Decode → mess → coherence  → only for ≤40 candidates (see CandidateSelector cap)
  8. Rank and return
"""
from __future__ import annotations

import logging
from os import PathLike
from typing import Any, BinaryIO, List, Optional

from .candidate import CandidateSelector
from .coherence import detect_language
from .constant import LANGUAGE_ENCODINGS, OPTIMAL_SAMPLE, SIMILAR_ENCODINGS, TOO_LARGE
from .fingerprint import (
    cp1252_zone_ratio,
    detect_null_pattern,
    fingerprint_cosine_for_encoding,
)
from .heuristics import (
    cp866_vs_cp1251_hint,
    hebrew_sbcs_likelihood,
    japanese_mbcs_bias,
)
from .mess import sliding_window_mess
from .models import DetectionResult, EncodingAlternative

logger = logging.getLogger("bytesense")


def _language_encoding_alignment(language: str, encoding: str) -> float:
    """Return 1.0 if `encoding` is typical for detected `language`, else 0.0."""
    if not language:
        return 0.0
    encs = LANGUAGE_ENCODINGS.get(language, [])
    return 1.0 if encoding in encs else 0.0


def _latin_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if c.isalpha() and ord(c) < 0x0300) / n


def _cyrillic_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u0400" <= c <= "\u04ff" or "\u0500" <= c <= "\u052f") / n


def _arabic_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u0600" <= c <= "\u06ff" or "\u0750" <= c <= "\u077f") / n


def _greek_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u0370" <= c <= "\u03ff") / n


def _cjk_ideographs_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u4e00" <= c <= "\u9fff") / n


def _hangul_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\uac00" <= c <= "\ud7a3") / n


def _hebrew_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u0590" <= c <= "\u05ff") / n


def _thai_letters_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u0e00" <= c <= "\u0e7f") / n


def _kana_ratio(decoded: str) -> float:
    n = len(decoded)
    if n == 0:
        return 0.0
    return sum(1 for c in decoded if "\u3040" <= c <= "\u30ff" or "\u31f0" <= c <= "\u31ff") / n


def _turkish_unicode_score(decoded: str) -> float:
    """İ/ı/ş/ğ etc. after a correct Turkish Windows decode — not present in cp1250 mojibake."""
    if not decoded:
        return 0.0
    hits = sum(
        1
        for c in decoded
        if c in "\u0130\u0131\u011e\u011f\u015e\u015f\u00dc\u00fc\u00d6\u00f6\u00c7\u00e7"
    )
    return hits / min(len(decoded), 2000)


def _baltic_latin_score(decoded: str) -> float:
    """ą č ę ė į š ų ū ž — typical in Lithuanian cp1257 text."""
    if not decoded:
        return 0.0
    hits = sum(
        1
        for c in decoded
        if c in "\u0105\u010d\u0119\u0117\u012f\u0161\u0173\u016b\u017e\u010c\u012e\u0160\u017d"
    )
    return hits / min(len(decoded), 2000)


def _emoji_zwj_rich_text(text: str) -> bool:
    """Valid UTF-8 with ZWJ / emoji clusters can trip Latin-centric mess heuristics."""
    if not text:
        return False
    if "\u200d" in text:
        return True
    ext = sum(1 for c in text if ord(c) >= 0x1F300)
    return ext / max(len(text), 1) >= 0.02


def _maybe_promote_korean_mbcs(
    rows: List[tuple[str, float, float, str, int, str, float]],
    sample_data: bytes,
) -> List[tuple[str, float, float, str, int, str, float]]:
    """
    If a Windows/Latin/Cyrillic SBCS wins but decodes to no Hangul while
    cp949/euc_kr decodes the same bytes to strong Hangul text, prefer the
    Korean multibyte path.
    """
    if not rows:
        return rows
    _, _, _, _, _, text0, _ = rows[0]
    if _hangul_ratio(text0) > 0.12:
        return rows
    for row in rows:
        enc, _, _, _, _, _, _ = row
        if enc not in ("cp949", "euc_kr", "johab"):
            continue
        try:
            alt = sample_data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if _hangul_ratio(alt) > 0.35:
            return [row] + [r for r in rows if r is not row]
    return rows


def _maybe_promote_hebrew_sbcs(
    rows: List[tuple[str, float, float, str, int, str, float]],
    sample_data: bytes,
) -> List[tuple[str, float, float, str, int, str, float]]:
    from .heuristics import cp866_vs_cp1251_hint, koi8_byte_hint

    if cp866_vs_cp1251_hint(sample_data) is not None or koi8_byte_hint(sample_data):
        return rows
    if not rows:
        return rows
    enc0, _, _, _, _, t0, _ = rows[0]
    if enc0 in ("cp1255", "iso8859_8"):
        return rows
    if _hebrew_letters_ratio(t0) > 0.12:
        return rows
    best: Optional[tuple[str, float, float, str, int, str, float]] = None
    best_h = -1.0
    for row in rows:
        enc = row[0]
        if enc not in ("cp1255", "iso8859_8"):
            continue
        try:
            alt = sample_data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        h = _hebrew_letters_ratio(alt)
        if h > best_h:
            best_h = h
            best = row
    if best is None or best_h < 0.20:
        return rows
    if best_h > _hebrew_letters_ratio(t0) + 0.10:
        return [best] + [r for r in rows if r is not best]
    return rows


def _maybe_promote_thai_mbcs(
    rows: List[tuple[str, float, float, str, int, str, float]],
    sample_data: bytes,
) -> List[tuple[str, float, float, str, int, str, float]]:
    from .heuristics import thai_tis620_likelihood

    if not rows:
        return rows
    if thai_tis620_likelihood(sample_data) < 0.92:
        return rows
    if hebrew_sbcs_likelihood(sample_data) >= 0.55:
        return rows
    _, _, _, _, _, t0, _ = rows[0]
    if _thai_letters_ratio(t0) > 0.12:
        return rows
    best: Optional[tuple[str, float, float, str, int, str, float]] = None
    best_th = -1.0
    for row in rows:
        enc = row[0]
        if enc not in ("tis_620", "iso8859_11"):
            continue
        try:
            alt = sample_data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        th = _thai_letters_ratio(alt)
        if th > best_th:
            best_th = th
            best = row
    if best is None or best_th < 0.35:
        return rows
    if best_th > _thai_letters_ratio(t0) + 0.10:
        return [best] + [r for r in rows if r is not best]
    return rows


def _maybe_promote_japanese_mbcs(
    rows: List[tuple[str, float, float, str, int, str, float]],
    sample_data: bytes,
) -> List[tuple[str, float, float, str, int, str, float]]:
    jb = japanese_mbcs_bias(sample_data)
    if jb is None or not rows:
        return rows
    # Hangul-heavy bytes decode as plausible EUC-JP but are Korean — only when jb says euc_jp.
    if jb == "euc_jp":
        try:
            hang_cp949 = _hangul_ratio(sample_data.decode("cp949"))
        except (UnicodeDecodeError, LookupError):
            hang_cp949 = 0.0
        try:
            hang_ej = _hangul_ratio(sample_data.decode("euc_jp"))
        except (UnicodeDecodeError, LookupError):
            hang_ej = 0.0
        if hang_cp949 > 0.38 and hang_ej < 0.06:
            return rows
    enc0, _, _, _, _, t0, _ = rows[0]
    if enc0 in ("shift_jis", "euc_jp", "cp932", "iso2022_jp", "iso2022_jp_1", "iso2022_jp_2"):
        return rows
    want = ("shift_jis", "cp932") if jb == "shift_jis" else ("euc_jp", "iso2022_jp")
    best: Optional[tuple[str, float, float, str, int, str, float]] = None
    best_j = -1.0
    for row in rows:
        enc = row[0]
        if enc not in want:
            continue
        try:
            alt = sample_data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        j = _kana_ratio(alt) + _cjk_ideographs_ratio(alt)
        if j > best_j:
            best_j = j
            best = row
    if best is None or best_j < 0.08:
        return rows
    lead_j = _kana_ratio(t0) + _cjk_ideographs_ratio(t0)
    if lead_j > best_j + 0.10:
        return rows
    return [best] + [r for r in rows if r is not best]


def _maybe_promote_cjk_over_cp949(
    rows: List[tuple[str, float, float, str, int, str, float]],
    sample_data: bytes,
) -> List[tuple[str, float, float, str, int, str, float]]:
    """
    Chinese Big5 / GB18030 bytes often decode as pure Hangul under cp949; prefer Han decodes.
    """
    if not rows or rows[0][0] != "cp949":
        return rows
    try:
        t949 = sample_data.decode("cp949")
    except (UnicodeDecodeError, LookupError):
        return rows
    hang9 = _hangul_ratio(t949)
    cjk9 = _cjk_ideographs_ratio(t949)
    if hang9 > 0.88 and cjk9 < 0.07:
        try:
            cjk5 = _cjk_ideographs_ratio(sample_data.decode("big5"))
        except (UnicodeDecodeError, LookupError):
            cjk5 = 0.0
        if cjk5 > 0.42:
            row_big5 = next((r for r in rows if r[0] == "big5"), None)
            if row_big5 is not None:
                return [row_big5] + [r for r in rows if r is not row_big5]
    try:
        sample_data.decode("big5")
        big5_ok = True
    except (UnicodeDecodeError, LookupError):
        big5_ok = False
    if not big5_ok:
        try:
            cjk18 = _cjk_ideographs_ratio(sample_data.decode("gb18030"))
        except (UnicodeDecodeError, LookupError):
            return rows
        if cjk18 > 0.42 and hang9 > 0.35 and cjk9 > 0.18:
            row_gb = next((r for r in rows if r[0] == "gb18030"), None)
            if row_gb is not None:
                return [row_gb] + [r for r in rows if r is not row_gb]
    return rows


def _looks_like_iso2022(data: bytes) -> bool:
    """
    7-bit ISO-2022 (JP/KR) uses ESC sequences; without this, pure-ASCII+ESC
    payloads are misclassified as plain ASCII.
    """
    if b"\x1b" not in data:
        return False
    # Common ISO-2022 lead-ins (JP: ESC $ B / ESC ( B, etc.)
    return (
        b"\x1b\x24" in data
        or b"\x1b\x28" in data
        or b"\x1b\x29" in data
        or b"\x1b\x2e" in data
    )


def _encoding_script_bonus(encoding: str, decoded: str) -> float:
    """
    Score how well the decoded Unicode matches scripts typically produced by `encoding`.
    Used to break ties (e.g. cp1252 vs cp1251 on Latin text, mac_cyrillic vs iso8859_7 on Russian).
    Rough range about -0.5 .. +1.0.
    """
    cyr = _cyrillic_letters_ratio(decoded)
    lat = _latin_letters_ratio(decoded)
    arab = _arabic_letters_ratio(decoded)
    gre = _greek_letters_ratio(decoded)
    cjk = _cjk_ideographs_ratio(decoded)
    hang = _hangul_ratio(decoded)
    heb = _hebrew_letters_ratio(decoded)
    thai = _thai_letters_ratio(decoded)

    score = 0.0

    if encoding in ("cp1251", "koi8_r", "koi8_u", "cp866", "mac_cyrillic", "iso8859_5", "ptcp154", "kz1048"):
        score += min(1.0, cyr * 1.1)
        if lat > 0.2 and cyr < 0.06:
            score -= 0.55
        kn = _kana_ratio(decoded)
        if (kn > 0.045 or cjk > 0.14) and cyr < 0.38:
            score -= 0.95
    if encoding == "mac_cyrillic" and cyr < 0.12 and lat > 0.22:
        score -= 0.72
    if encoding == "mac_cyrillic" and thai > 0.14 and cyr < 0.15:
        score -= 0.88
    if encoding in ("cp1252", "cp1250", "cp1254", "cp1258", "latin_1", "iso8859_15", "iso8859_9"):
        score += min(0.9, lat * 0.45)
        if cyr > 0.12 and lat < 0.1:
            score -= 0.15
    tu = _turkish_unicode_score(decoded)
    if encoding in ("cp1254", "iso8859_9"):
        score += min(0.45, tu * 12.0)
    if encoding in ("cp1250", "cp1252", "latin_1") and tu > 0.004:
        score -= min(0.38, tu * 7.0)
    if encoding in ("cp1256", "iso8859_6"):
        score += min(1.0, arab * 1.0)
        if arab < 0.08 and cyr > 0.05:
            score -= 0.35
    if encoding in ("tis_620", "iso8859_11"):
        score += min(1.0, thai * 1.05)
    if encoding in ("cp1257",):
        score += min(0.85, lat * 0.42)
        bal = _baltic_latin_score(decoded)
        if bal > 0.004:
            score += min(0.42, bal * 20.0)
    if encoding in ("cp1255", "iso8859_8"):
        score += min(1.0, heb * 1.05)
    if encoding in ("cp1253", "iso8859_7"):
        score += min(1.0, gre * 1.0)
        if cyr > 0.12 and gre < 0.12:
            score -= 0.55
    if encoding in ("big5", "big5hkscs", "gb2312", "gbk", "gb18030", "hz"):
        score += min(1.0, cjk * 0.85 + hang * 0.1)
    if encoding in ("cp949", "euc_kr", "johab", "iso2022_kr"):
        score += min(1.0, hang * 0.85 + cjk * 0.15)
        # GB/Big5 bytes mis-decoded as Hangul+Han (not typical pure Korean chat).
        if hang > 0.22 and cjk > 0.22:
            score -= 0.48
    if encoding in ("shift_jis", "euc_jp", "cp932", "iso2022_jp", "iso2022_jp_1", "iso2022_jp_2"):
        kana = sum(
            1 for c in decoded if "\u3040" <= c <= "\u30ff" or "\u31f0" <= c <= "\u31ff"
        ) / max(len(decoded), 1)
        score += min(1.0, kana * 0.5 + cjk * 0.35)
        if hang > 0.2 and kana < 0.12:
            score -= 0.55
        # Han text without kana is often Chinese/Korean mis-tagged as Japanese
        if cjk > 0.22 and kana < 0.06:
            score -= 0.52

    return max(-0.55, min(1.0, score))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _confidence(chaos: float, coherence: float, bom: bool) -> float:
    if bom:
        return 1.0
    base = 1.0 - chaos
    boost = coherence * 0.12
    return min(round(base + boost, 4), 1.0)


def _ci(conf: float) -> tuple[float, float]:
    uncertainty = (1.0 - conf) * 0.45
    return (
        round(max(0.0, conf - uncertainty), 4),
        round(min(1.0, conf + uncertainty), 4),
    )


def _make_result(
    encoding: Optional[str],
    chaos: float,
    coherence: float,
    language: str,
    bom_detected: bool,
    alternatives: List[EncodingAlternative],
    why: str,
    byte_count: int,
    confidence: Optional[float] = None,
) -> DetectionResult:
    conf = confidence if confidence is not None else _confidence(chaos, coherence, bom_detected)
    return DetectionResult(
        encoding=encoding,
        confidence=conf,
        confidence_interval=_ci(conf),
        language=language,
        alternatives=alternatives,
        bom_detected=bom_detected,
        chaos=round(chaos, 4),
        coherence=round(coherence, 4),
        why=why,
        byte_count=byte_count,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def from_bytes(
    data: bytes | bytearray,
    steps: int = 5,
    chunk_size: int = 512,
    threshold: float = 0.2,
    cp_isolation: Optional[List[str]] = None,
    cp_exclusion: Optional[List[str]] = None,
    language_threshold: float = 0.1,
    enable_fallback: bool = True,
) -> DetectionResult:
    """
    Detect the encoding of a byte sequence.

    Args:
        data:               Raw bytes to analyse.
        steps:              (legacy compat) Number of chunks for mess detection.
        chunk_size:         (legacy compat) Chunk size in bytes.
        threshold:          Maximum chaos ratio to accept an encoding (0.0–1.0).
        cp_isolation:       If set, only test these encodings.
        cp_exclusion:       If set, never test these encodings.
        language_threshold: Minimum coherence score for language reporting.
        enable_fallback:    Return utf_8 fallback instead of None when nothing works.

    Returns:
        :class:`DetectionResult`
    """
    del steps, chunk_size  # legacy compatibility — reserved for future use

    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError(f"Expected bytes or bytearray, got {type(data).__name__!r}")

    byte_count = len(data)

    # Empty input
    if byte_count == 0:
        return _make_result(
            "utf_8",
            0.0,
            0.0,
            "",
            False,
            [],
            "Empty input — defaulting to UTF-8.",
            0,
            confidence=0.5,
        )

    sel = CandidateSelector(data)

    # ── Fast path 1: BOM ─────────────────────────────────────────────────────
    bom_enc = sel.bom_encoding()
    if bom_enc:
        try:
            decoded = data.decode(bom_enc, errors="strict")
            sample = decoded[:4000]
            langs = detect_language(sample, threshold=language_threshold)
            lang = langs[0][0] if langs else ""
            coh = langs[0][1] if langs else 0.0
            # Report utf_8 for UTF-8 BOM (common benchmark / interchange label).
            report_enc = "utf_8" if bom_enc == "utf_8_sig" else bom_enc
            return _make_result(
                report_enc,
                0.0,
                coh,
                lang,
                True,
                [],
                f"BOM/SIG detected ({bom_enc!r}) — reporting as {report_enc!r}.",
                byte_count,
                confidence=1.0,
            )
        except (UnicodeDecodeError, LookupError):
            pass  # Misleading BOM — fall through

    # ── Fast path 2: Pure ASCII (but not 7-bit ISO-2022) ───────────────────────
    if sel.is_ascii_only() and not _looks_like_iso2022(data):
        return _make_result(
            "ascii",
            0.0,
            1.0,
            "English",
            False,
            [EncodingAlternative("utf_8", 1.0, "English")],
            "All bytes in 0x00–0x7F range — pure ASCII.",
            byte_count,
            confidence=1.0,
        )

    # ── Fast path 3: Valid UTF-8 ──────────────────────────────────────────────
    # UTF-16/32-stored ASCII can decode as UTF-8 (ASCII + NUL); prefer null-pattern path.
    null_pat = detect_null_pattern(data)
    utf16_or_32_shape = null_pat is not None and byte_count >= 8

    # 7-bit ISO-2022 is valid UTF-8 byte-for-byte but is not UTF-8 text.
    if (
        not utf16_or_32_shape
        and sel.is_utf8_valid()
        and not _looks_like_iso2022(data)
    ):
        decoded = data.decode("utf_8")
        sample = decoded[:4000]
        chaos, exceeded = sliding_window_mess(sample, threshold=threshold)
        if not exceeded or _emoji_zwj_rich_text(sample):
            langs = detect_language(sample, threshold=language_threshold)
            lang = langs[0][0] if langs else ""
            coh = langs[0][1] if langs else 0.0
            return _make_result(
                "utf_8",
                chaos,
                coh,
                lang,
                False,
                [],
                f"Valid UTF-8. Chaos {chaos:.1%}. Coherence {coh:.1%} ({lang}).",
                byte_count,
            )

    # ── Standard path ─────────────────────────────────────────────────────────
    candidates = sel.get_candidates()

    if cp_isolation:
        candidates = [c for c in candidates if c in cp_isolation]
    if cp_exclusion:
        candidates = [c for c in candidates if c not in cp_exclusion]
    if not candidates:
        candidates = ["utf_8"]

    # Sample large files
    sample_data = data[:OPTIMAL_SAMPLE] if byte_count > TOO_LARGE else data

    results: List[tuple[str, float, float, str, int, str, float]] = []
    failed_skip: set[str] = set()

    for cand_idx, encoding in enumerate(candidates):
        if encoding in failed_skip:
            logger.debug("Skipping %s (similar to failed encoding)", encoding)
            continue

        try:
            decoded = sample_data.decode(encoding, errors="strict")
        except (UnicodeDecodeError, LookupError):
            failed_skip.update(SIMILAR_ENCODINGS.get(encoding, []))
            continue

        chaos, exceeded = sliding_window_mess(decoded[:4000], threshold=threshold)
        if exceeded:
            logger.debug("%s rejected: chaos=%.3f", encoding, chaos)
            failed_skip.update(SIMILAR_ENCODINGS.get(encoding, []))
            continue

        sample_text = decoded[:4000]
        langs = detect_language(sample_text, threshold=language_threshold)
        lang = langs[0][0] if langs else ""
        coh = langs[0][1] if langs else 0.0
        fp_fit = fingerprint_cosine_for_encoding(sample_data, encoding)
        results.append((encoding, chaos, coh, lang, cand_idx, sample_text, fp_fit))
        logger.debug("%s accepted: chaos=%.3f coh=%.3f lang=%s", encoding, chaos, coh, lang)

    if not results:
        if enable_fallback:
            return _make_result(
                "utf_8",
                1.0,
                0.0,
                "",
                False,
                [],
                "No encoding passed detection. UTF-8 fallback returned.",
                byte_count,
                confidence=0.1,
            )
        return _make_result(
            None,
            1.0,
            0.0,
            "",
            False,
            [],
            "No encoding passed detection.",
            byte_count,
            confidence=0.0,
        )

    arab_cp1256_probe = 0.0
    try:
        arab_cp1256_probe = _arabic_letters_ratio(sample_data.decode("cp1256"))
    except (UnicodeDecodeError, LookupError):
        pass

    big5_cjk_probe = 0.0
    try:
        big5_cjk_probe = _cjk_ideographs_ratio(sample_data.decode("big5"))
    except (UnicodeDecodeError, LookupError):
        pass

    ej_kana_probe = 0.0
    try:
        _ejt = sample_data.decode("euc_jp")
        ej_kana_probe = _kana_ratio(_ejt) + _cjk_ideographs_ratio(_ejt)
    except (UnicodeDecodeError, LookupError):
        pass

    cyr_hint_for_rank = cp866_vs_cp1251_hint(sample_data)
    jb_for_rank = japanese_mbcs_bias(sample_data)

    def _rank_key(x: tuple[str, float, float, str, int, str, float]) -> tuple[float, int]:
        enc, chaos, coh, lang, idx, sample_text, fp_fit = x
        align = _language_encoding_alignment(lang, enc)
        script = _encoding_script_bonus(enc, sample_text)
        combined = coh + 0.28 * align + 0.42 * script
        # Chaos alone over-prefers a slightly lower mess when the encoding is wrong
        # (e.g. cp1251 vs cp1252 on Latin text). Blend chaos with coherence + priors.
        # Byte fingerprint cosine breaks ties when wrong decodings look clean (Big5→cp949).
        c1252_zone = cp1252_zone_ratio(sel.hist, len(sample_data))
        zone_adj = 0.0
        if enc == "latin_1" and c1252_zone > 0.0004:
            zone_adj += 0.28
        if enc in ("cp1252", "cp1250") and c1252_zone > 0.0004:
            zone_adj -= 0.05
        gre = _greek_letters_ratio(sample_text)
        heb = _hebrew_letters_ratio(sample_text)
        cyr_r = _cyrillic_letters_ratio(sample_text)
        win_iso = 0.0
        # Prefer Windows Greek/Hebrew over ISO-8859-* when both decode cleanly (CN corpus).
        if gre > 0.06 and cyr_r < 0.05:
            # Arabic bytes misread as Greek letters still yield high gre; cp1256 probe disambiguates.
            if arab_cp1256_probe > 0.65 and enc in ("cp1253", "iso8859_7") and gre > 0.35:
                win_iso += 0.16
            elif arab_cp1256_probe <= 0.65:
                if enc == "cp1253":
                    win_iso -= 0.11
                if enc == "iso8859_7":
                    win_iso += 0.11
        if heb > 0.06 and cyr_r < 0.05:
            if enc == "cp1255":
                win_iso -= 0.11
            if enc == "iso8859_8":
                win_iso += 0.11
        # Cyrillic DOS/Windows split — Hebrew gate avoids false Cyrillic tweaks on Hebrew bytes.
        if (
            cyr_hint_for_rank == "cp1251"
            and jb_for_rank is None
            and hebrew_sbcs_likelihood(sample_data) < 0.93
        ):
            if enc == "cp1251":
                win_iso -= 0.12
            if enc in ("cp1253", "iso8859_7"):
                win_iso += 0.16
        # Cyrillic bytes misread as Greek when Japanese pair heuristics fire on CP1251 streams;
        # cp1256 Arabic probe ~0.39 (Russian) vs ~0.49 (Greek CN) — split near 0.43.
        if (
            cyr_hint_for_rank == "cp1251"
            and jb_for_rank == "euc_jp"
            and enc == "cp1253"
            and gre > 0.5
            and arab_cp1256_probe < 0.43
            and hebrew_sbcs_likelihood(sample_data) < 0.93
        ):
            win_iso += 0.24
        if cyr_hint_for_rank == "cp866":
            if enc == "cp866":
                win_iso -= 0.18
            if enc == "cp1251":
                win_iso += 0.12
        if enc in ("big5", "big5hkscs") and ej_kana_probe > 0.55 and jb_for_rank == "euc_jp":
            win_iso += 0.19 if enc == "big5" else 0.17
        if enc == "cp949" and big5_cjk_probe > 0.38:
            h = _hangul_ratio(sample_text)
            cjk = _cjk_ideographs_ratio(sample_text)
            if h > 0.55 and cjk < 0.06:
                win_iso += 0.22
        score = chaos - 0.52 * combined - 0.26 * fp_fit + zone_adj + win_iso
        return (score, idx)

    results.sort(key=_rank_key)
    results = _maybe_promote_korean_mbcs(results, sample_data)
    results = _maybe_promote_hebrew_sbcs(results, sample_data)
    results = _maybe_promote_thai_mbcs(results, sample_data)
    results = _maybe_promote_japanese_mbcs(results, sample_data)
    results = _maybe_promote_cjk_over_cp949(results, sample_data)
    best_enc, best_chaos, best_coh, best_lang, _, _, _ = results[0]

    alts = [
        EncodingAlternative(enc, round(_confidence(c, h, False), 4), lg)
        for enc, c, h, lg, _, _, _ in results[1:6]
    ]

    why = (
        f"Selected {best_enc!r}. "
        f"Chaos: {best_chaos:.1%}. "
        + (f"Language: {best_lang} (coherence {best_coh:.1%}). " if best_coh > 0 else "")
        + (f"{len(results) - 1} alternative(s) considered." if len(results) > 1 else "")
    )

    return _make_result(best_enc, best_chaos, best_coh, best_lang, False, alts, why, byte_count)


def from_path(
    path: str | bytes | PathLike,  # type: ignore[type-arg]
    **kwargs: object,
) -> DetectionResult:
    """Detect encoding of a file. Accepts any path-like object."""
    with open(path, "rb") as fp:
        return from_fp(fp, **kwargs)


def from_fp(fp: BinaryIO, **kwargs: Any) -> DetectionResult:
    """Detect encoding from an open binary file pointer. Does not close it."""
    return from_bytes(fp.read(), **kwargs)


def is_binary(
    data: bytes | str | PathLike,  # type: ignore[type-arg]
    **kwargs: Any,
) -> bool:
    """Return ``True`` if `data` appears to be a binary (non-text) file."""
    kwargs.setdefault("enable_fallback", False)  # type: ignore[call-overload]
    if isinstance(data, (str, PathLike)):
        result = from_path(data, **kwargs)
    elif isinstance(data, (bytes, bytearray)):
        result = from_bytes(data, **kwargs)
    else:
        result = from_fp(data, **kwargs)
    return result.encoding is None
