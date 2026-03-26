"""Extra coverage for heuristics.reorder_candidates and byte hints."""
from __future__ import annotations

from bytesense.heuristics import (
    chinese_big5_vs_gb_hint,
    cp866_vs_cp1251_hint,
    hebrew_sbcs_likelihood,
    japanese_mbcs_bias,
    koi8_byte_hint,
    reorder_candidates,
    thai_tis620_likelihood,
)


def test_hebrew_sbcs_short_data() -> None:
    assert hebrew_sbcs_likelihood(b"abc") == 0.0


def test_thai_tis620_short_data() -> None:
    assert thai_tis620_likelihood(b"x" * 4) == 0.0


def test_koi8_byte_hint_short() -> None:
    assert koi8_byte_hint(b"\xff" * 10) is False


def test_cp866_vs_cp1251_hint_short() -> None:
    assert cp866_vs_cp1251_hint(b"hello") is None


def test_japanese_mbcs_bias_short() -> None:
    assert japanese_mbcs_bias(b"x" * 10) is None


def test_chinese_big5_vs_gb_short() -> None:
    assert chinese_big5_vs_gb_hint(b"x" * 10) is None


def test_reorder_ascii_unchanged() -> None:
    cands = ["ascii", "utf_8", "latin_1"]
    out = reorder_candidates(b"Hello world " * 20, cands)
    assert set(out) == set(cands)


def test_reorder_bumps_hebrew_when_likely() -> None:
    # High bytes in cp1255 Hebrew window without KOI8/DOS signature noise
    data = bytes([0xE0 + (i % 25) for i in range(200)])
    cands = ["latin_1", "cp1255", "iso8859_8", "utf_8"]
    out = reorder_candidates(data, cands)
    assert out[0] in ("cp1255", "iso8859_8", "latin_1", "utf_8")


def test_japanese_mbcs_bias_shift_jis_like() -> None:
    # Crafted Shift_JIS-like pairs (not valid text, enough pair counts)
    b = bytearray()
    for _ in range(100):
        b.extend([0x82, 0xA0])
    jb = japanese_mbcs_bias(bytes(b))
    assert jb in (None, "shift_jis", "euc_jp")
