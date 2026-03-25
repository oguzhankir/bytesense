"""
Ground-truth samples tuned for **realistic stress**: paragraph-sized buffers
(~400+ encoded bytes) so detectors see enough signal; still hard because of
near-ambiguous encodings (KOI8 vs cp1251, SJIS vs EUC-JP, Big5 vs cp949),
UTF-16 without BOM, ISO-2022-JP, and mixed-script UTF-8.

Used only by benchmarks/test_hard_scenarios.py — not merged into the main
DATASET (which enforces len >= 16 for stable fingerprinting).
"""
from __future__ import annotations

from typing import List, Tuple

# Target minimum encoded size (bytes) — simulates a real log line / paragraph.
_STRESS_MIN_BYTES = 400

# (scenario_id, unicode_text seed, canonical_encoding_name matching bytesense)
_RAW: List[Tuple[str, str, str]] = [
    # --- SBCS: same seed repeated to paragraph length ---
    (
        "ru_cp1251_sms",
        "\u041f\u0440\u0438\u0432\u0435\u0442! \u041a\u0430\u043a \u0434\u0435\u043b\u0430? ",
        "cp1251",
    ),
    (
        "ru_koi8r_sms",
        "\u041f\u0440\u0438\u0432\u0435\u0442! \u041a\u0430\u043a \u0434\u0435\u043b\u0430? ",
        "koi8_r",
    ),
    (
        "ru_cp866_dos",
        "\u041f\u0440\u0438\u0432\u0435\u0442, \u043c\u0438\u0440! ",
        "cp866",
    ),
    (
        "he_cp1255_snippet",
        "\u05e9\u05dc\u05d5\u05dd! \u05d4\u05d9\u05d5\u05dd \u05d9\u05e4\u05d4 \u05d9\u05d5\u05dd \u05d7\u05dd. ",
        "cp1255",
    ),
    (
        "he_iso8859_8_snippet",
        "\u05e9\u05dc\u05d5\u05dd! \u05d4\u05d9\u05d5\u05dd \u05d9\u05e4\u05d4 \u05d9\u05d5\u05dd \u05d7\u05dd. ",
        "iso8859_8",
    ),
    (
        "el_cp1253_snippet",
        "\u039a\u03b1\u03bb\u03b7\u03bc\u03ad\u03c1\u03b1! \u03a0\u03ce\u03c2 \u03b5\u03af\u03c3\u03b1\u03b9; ",
        "cp1253",
    ),
    (
        "el_iso8859_7_snippet",
        "\u039a\u03b1\u03bb\u03b7\u03bc\u03ad\u03c1\u03b1! \u03a0\u03ce\u03c2 \u03b5\u03af\u03c3\u03b1\u03b9; ",
        "iso8859_7",
    ),
    (
        "tr_cp1254_id",
        "\u0130stanbul'da h\u0131zl\u0131 kahve. \u015e\u00fckran. ",
        "cp1254",
    ),
    (
        "pl_cp1250_snippet",
        "Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144 w \u0142\u00f3\u017cu. ",
        "cp1250",
    ),
    (
        "ar_cp1256_snippet",
        "\u0645\u0631\u062d\u0628\u0627\u064b \u0628\u0643 \u0641\u064a \u0627\u0644\u0642\u0627\u0647\u0631\u0629. ",
        "cp1256",
    ),
    (
        "lt_cp1257_snippet",
        "Labas rytas, Lietuva! \u0105\u010d\u0119\u0117\u012f\u0161\u0173\u016b\u017e ",
        "cp1257",
    ),
    (
        "th_tis620_snippet",
        "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35 \u0e01\u0e23\u0e38\u0e07\u0e40\u0e17\u0e1e \u0e21\u0e2b\u0e32\u0e19\u0e04\u0e23 ",
        "tis_620",
    ),
    (
        "vi_cp1258_snippet",
        "Ti\u1ebfng Vi\u1ec7t c\u00f3 d\u1ea5u. Th\u00e0nh ph\u1ed1 H\u00e0 N\u1ed9i. ",
        "cp1258",
    ),
    # --- CJK: SJIS vs EUC vs ISO-2022 ---
    (
        "jp_shift_jis_tweet",
        "\u6771\u4eac\u30bf\u30ef\u30fc\u3067\u30c6\u30b9\u30c8\u3002\u3042\u3044\u3046\u3048\u304a",
        "shift_jis",
    ),
    (
        "jp_euc_jp_tweet",
        "\u6771\u4eac\u30bf\u30ef\u30fc\u3067\u30c6\u30b9\u30c8\u3002\u3042\u3044\u3046\u3048\u304a",
        "euc_jp",
    ),
    (
        "jp_iso2022jp_line",
        "\u6771\u4eac\u3067\u4f1a\u8b70\u3002\u8cc7\u6599\u3092\u9001\u308a\u307e\u3059\u3002",
        "iso2022_jp",
    ),
    (
        "kr_euc_kr_chat",
        "\uc548\ub155\ud558\uc138\uc694! \uc624\ub298 \ub0a0\uc528\uac00 \uc88b\uc544\uc694. ",
        "euc_kr",
    ),
    (
        "kr_cp949_chat",
        "\uc548\ub155\ud558\uc138\uc694! \uc624\ub298 \ub0a0\uc528\uac00 \uc88b\uc544\uc694. ",
        "cp949",
    ),
    (
        "cn_big5_headline",
        "\u6e2f\u5cf6\u65b0\u805e\u5831\u982d\u689d\u6e2c\u8a66\u3002",
        "big5",
    ),
    (
        "cn_gb18030_line",
        "\u5317\u4eac\u5e02\u653f\u5e9c\u901a\u544a\u6e2c\u8bd5\u6587\u672c\u3002",
        "gb18030",
    ),
    # --- UTF-8 edge: emoji / ZWJ sequences ---
    (
        "utf8_emoji_mixed",
        "OK \u2603 \u2192 caf\u00e9 \U0001f64f repeat ",
        "utf_8",
    ),
    (
        "utf8_zwj_emoji",
        "\U0001f468\u200d\U0001f469\u200d\U0001f466 family ",
        "utf_8",
    ),
    # --- Windows Latin with € / smart punctuation ---
    (
        "cp1252_invoice",
        "Price: \u20ac1.234,56 \u2014 \u201cnett\u201d \u00a9 2025. ",
        "cp1252",
    ),
    # --- UTF-16: NUL-heavy; often confused with UTF-8 or binary ---
    (
        "utf16_le_ascii_bulk",
        "Status: OK\r\nLine2\r\nLine3\r\n",
        "utf_16_le",
    ),
    (
        "utf16_le_mixed_script",
        "ID: ABC-9 \u4e2d\u6587\u6d4b\u8bd5 \u041f\u0440\u0438\u0432\u0435\u0442\r\n",
        "utf_16_le",
    ),
]


def _codec_py(enc: str) -> str:
    if enc == "utf_8_sig":
        return "utf-8-sig"
    return enc.replace("_", "-")


def _repeat_to_min(text: str, enc: str, min_bytes: int) -> str:
    """Repeat `text` until `len(text.encode(enc)) >= min_bytes` (cap iterations)."""
    codec = _codec_py(enc)
    t = text
    for _ in range(500):
        if len(t.encode(codec)) >= min_bytes:
            return t
        t += text
    return t


def build_hard_scenarios() -> List[Tuple[str, bytes, str]]:
    out: List[Tuple[str, bytes, str]] = []
    for sid, text, enc in _RAW:
        try:
            long_text = _repeat_to_min(text, enc, _STRESS_MIN_BYTES)
            data = long_text.encode(_codec_py(enc), errors="strict")
        except (LookupError, UnicodeEncodeError, ValueError):
            continue
        if len(data) < 12:
            continue
        out.append((sid, data, enc))
    return out


HARD_SCENARIOS: List[Tuple[str, bytes, str]] = build_hard_scenarios()
