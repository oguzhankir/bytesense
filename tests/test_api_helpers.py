"""Direct tests for api.py script-ratio helpers (coverage for non-hot-path code)."""
from __future__ import annotations

import pytest

from bytesense.api import (
    _arabic_letters_ratio,
    _baltic_latin_score,
    _cjk_ideographs_ratio,
    _cyrillic_letters_ratio,
    _emoji_zwj_rich_text,
    _greek_letters_ratio,
    _hangul_ratio,
    _hebrew_letters_ratio,
    _kana_ratio,
    _language_encoding_alignment,
    _latin_letters_ratio,
    _thai_letters_ratio,
    _turkish_unicode_score,
)


def test_language_encoding_alignment() -> None:
    assert _language_encoding_alignment("", "utf_8") == 0.0
    assert _language_encoding_alignment("English", "utf_8") == 1.0
    assert _language_encoding_alignment("English", "cp1252") == 1.0
    assert _language_encoding_alignment("English", "cp1250") == 0.0


def test_latin_letters_ratio_empty() -> None:
    assert _latin_letters_ratio("") == 0.0


def test_latin_letters_ratio_ascii() -> None:
    r = _latin_letters_ratio("abcXYZ")
    assert r == pytest.approx(1.0)


def test_cyrillic_ratio() -> None:
    assert _cyrillic_letters_ratio("") == 0.0
    assert _cyrillic_letters_ratio("Привет") > 0.8


def test_arabic_greek_cjk_hangul_hebrew_thai_kana_empty() -> None:
    for fn in (
        _arabic_letters_ratio,
        _greek_letters_ratio,
        _cjk_ideographs_ratio,
        _hangul_ratio,
        _hebrew_letters_ratio,
        _thai_letters_ratio,
        _kana_ratio,
    ):
        assert fn("") == 0.0


def test_arabic_greek_samples() -> None:
    assert _arabic_letters_ratio("العربية") > 0.5
    assert _greek_letters_ratio("Ελληνικά") > 0.5


def test_cjk_hangul_kana() -> None:
    assert _cjk_ideographs_ratio("中文") > 0.0
    assert _hangul_ratio("한글") > 0.0
    assert _kana_ratio("ひらがな") > 0.0


def test_hebrew_thai() -> None:
    assert _hebrew_letters_ratio("עברית") > 0.0
    assert _thai_letters_ratio("ไทย") > 0.0


def test_turkish_unicode_score() -> None:
    assert _turkish_unicode_score("") == 0.0
    assert _turkish_unicode_score("İstanbul") > 0.0


def test_baltic_latin_score() -> None:
    assert _baltic_latin_score("") == 0.0
    assert _baltic_latin_score("ąčęėįšųūž") > 0.0


def test_emoji_zwj() -> None:
    assert _emoji_zwj_rich_text("") is False
    assert _emoji_zwj_rich_text("a\u200db") is True
    assert _emoji_zwj_rich_text("\U0001F600" * 50) is True
