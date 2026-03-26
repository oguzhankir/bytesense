"""
Shared benchmark fixtures.

Builds an in-memory dataset of (data: bytes, expected_encoding: str) tuples.
Both libraries are tested on exactly the same data.

1) Synthetic samples (encoded in-process).
2) Official charset-normalizer `data/` files (same ground truth as their
   tests/test_full_detection.py), fetched via scripts/fetch_cn_benchmark_samples.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import pytest

_BENCH_ROOT = Path(__file__).resolve().parent
_CN_DIR = _BENCH_ROOT / "data" / "cn_official"
_CN_MANIFEST = _BENCH_ROOT / "cn_official_manifest.json"

# ---------------------------------------------------------------------------
# Ground-truth dataset
# Each entry: (description, text, encoding)
# ---------------------------------------------------------------------------
_RAW: List[Tuple[str, str | bytes, str]] = [
    # --- UTF-8 (should be trivial for both) ---
    # One non-ASCII UTF-8 byte so detection is utf_8 (not ascii-only fast path)
    (
        "utf8_ascii_only",
        "Hello World! Simple ASCII text for benchmarking purposes.\u00a0",
        "utf_8",
    ),
    (
        "utf8_english_unicode",
        "The caf\u00e9 is on the boulevard. Na\u00efve r\u00e9sum\u00e9.",
        "utf_8",
    ),
    (
        "utf8_french_long",
        ("Bonjour le monde! J\u2019aime les \u00e9toiles. " "Le fran\u00e7ais est magnifique. " * 20),
        "utf_8",
    ),
    (
        "utf8_german",
        ("Sch\u00f6nen Gru\u00df aus Deutschland! " "\u00dcber die \u00e4sthetischen Werte. " * 15),
        "utf_8",
    ),
    (
        "utf8_spanish",
        ("El r\u00e1pido zorro marr\u00f3n salta sobre el perro perezoso. "
         "La ciudad de M\u00e9xico. " * 15),
        "utf_8",
    ),
    (
        "utf8_russian",
        ("\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440! "
         "\u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u044f\u0437\u044b\u043a. " * 20),
        "utf_8",
    ),
    (
        "utf8_chinese",
        "\u4e2d\u6587\u6d4b\u8bd5\u6587\u672c\uff0c\u7528\u4e8e\u7f16\u7801\u68c0\u6d4b\u3002" * 30,
        "utf_8",
    ),
    (
        "utf8_japanese",
        "\u65e5\u672c\u8a9e\u306e\u30c6\u30b9\u30c8\u30c6\u30ad\u30b9\u30c8\u3002" * 30,
        "utf_8",
    ),
    (
        "utf8_arabic",
        "\u0627\u0644\u0644\u063a\u0629 \u0627\u0644\u0639\u0631\u0628\u064a\u0629 \u062c\u0645\u064a\u0644\u0629." * 20,
        "utf_8",
    ),
    (
        "utf8_bom",
        "Hello with BOM! UTF-8 text with byte order mark.",
        "utf_8",
    ),
    # --- Extra UTF-8 variety (legacy SBCS cases are ambiguous across detectors) ---
    (
        "utf8_portuguese",
        "A raposa marrom r\u00e1pida salta sobre o c\u00e3o pregui\u00e7oso. " * 25,
        "utf_8",
    ),
    (
        "utf8_polish",
        "Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144. " * 30,
        "utf_8",
    ),
    (
        "utf8_turkish",
        "H\u0131zl\u0131 kahverengi tilki tembel k\u00f6pe\u011fin \u00fczerinden atlar. " * 20,
        "utf_8",
    ),
    (
        "utf8_greek",
        "\u0397 \u03b3\u03c1\u03ae\u03b3\u03bf\u03c1\u03b7 \u03ba\u03b1\u03c6\u03ad \u03ba\u03b1\u03c4\u03b1\u03ba\u03bb\u03cd\u03b6\u03b5\u03b9 \u03c4\u03bf\u03bd \u03c4\u03b5\u03bc\u03bd\u03cc \u03c3\u03ba\u03cd\u03bb\u03bf. " * 18,
        "utf_8",
    ),
    (
        "utf8_hebrew",
        "\u05d4\u05e9\u05d5\u05e2\u05dc \u05d4\u05d7\u05d5\u05dd \u05e7\u05d5\u05e4\u05e5 \u05de\u05e2\u05dc \u05d4\u05db\u05dc\u05d1 \u05d4\u05e2\u05e6\u05dc. " * 22,
        "utf_8",
    ),
    # --- Cyrillic ---
    (
        "cp1251_russian",
        ("\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440! "
         "\u042d\u0442\u043e \u0442\u0435\u043a\u0441\u0442. " * 20),
        "cp1251",
    ),
    # --- CJK (encoded) ---
    ("shift_jis_japanese", ("\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8\u3002" * 30), "shift_jis"),
    ("euc_jp_japanese", ("\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8\u3002" * 30), "euc_jp"),
    (
        "utf8_korean",
        "\uc774 \ube60\ub978 \ub2ec\ucf64 \uac1c\ub294 \uac8c\uc73c\ub978 \uac1c \uc704\ub97c \ub6f0\uc5b4\ub118\uc2b5\ub2c8\ub2e4. " * 25,
        "utf_8",
    ),
    # --- UTF-16 ---
    ("utf16_le", "Hello UTF-16 LE encoding test! " * 10, "utf_16_le"),
    # --- Large file (non-ASCII tail so detector expects UTF-8, not ASCII) ---
    (
        "large_utf8_1mb",
        ("The quick brown fox jumps over the lazy dog. " * 5000) + "café",
        "utf_8",
    ),
]


def _build_dataset() -> List[Tuple[str, bytes, str]]:
    """
    Convert _RAW entries to (name, bytes, expected_encoding) tuples.
    Entries where `text` is already bytes are used directly.
    """
    dataset = []
    for name, text, enc in _RAW:
        if isinstance(text, bytes):
            data = text
        else:
            try:
                if name == "utf8_bom":
                    data = text.encode("utf-8-sig")
                elif enc == "utf_16_le":
                    data = text.encode("utf-16-le")
                else:
                    codec = enc.replace("_", "-") if enc != "utf_8_sig" else "utf-8-sig"
                    data = text.encode(codec, errors="ignore")
            except (LookupError, UnicodeEncodeError):
                continue
        if len(data) >= 16:
            dataset.append((name, data, enc))
    return dataset


def _load_charset_normalizer_official_files() -> List[Tuple[str, bytes, str]]:
    """
    Load bytes + expected encoding from charset-normalizer's published samples.

    Requires: python scripts/fetch_cn_benchmark_samples.py
    """
    if not _CN_MANIFEST.is_file():
        return []
    spec = json.loads(_CN_MANIFEST.read_text(encoding="utf-8"))
    out: List[Tuple[str, bytes, str]] = []
    for entry in spec.get("files", []):
        fname = entry["file"]
        enc = entry["encoding"]
        path = _CN_DIR / fname
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) < 16:
            continue
        safe = fname.replace(".", "_")
        out.append((f"cn_official_{safe}", data, enc))
    return out


def _merge_datasets() -> List[Tuple[str, bytes, str]]:
    merged = _build_dataset() + _load_charset_normalizer_official_files()
    seen: set[str] = set()
    unique: List[Tuple[str, bytes, str]] = []
    for name, data, enc in merged:
        if name in seen:
            continue
        seen.add(name)
        unique.append((name, data, enc))
    return unique


DATASET: List[Tuple[str, bytes, str]] = _merge_datasets()
DATASET_IDS = [name for name, _, _ in DATASET]


@pytest.fixture(scope="session")
def benchmark_dataset() -> List[Tuple[str, bytes, str]]:
    return DATASET
