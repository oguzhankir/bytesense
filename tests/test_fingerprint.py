from __future__ import annotations

import array

import pytest

from bytesense.fingerprint import (
    _cosine_similarity,
    byte_histogram,
    cp1252_zone_ratio,
    detect_null_pattern,
    high_byte_ratio,
    histogram_to_ratios,
    null_byte_ratio,
    utf8_continuation_score,
)


def test_histogram_length() -> None:
    h = byte_histogram(b"hello")
    assert len(h) == 256


def test_histogram_counts() -> None:
    h = byte_histogram(b"aab")
    assert h[ord("a")] == 2
    assert h[ord("b")] == 1
    assert h[ord("c")] == 0


def test_histogram_type() -> None:
    h = byte_histogram(b"test")
    assert isinstance(h, array.array)


def test_histogram_empty() -> None:
    h = byte_histogram(b"")
    assert sum(h) == 0


def test_high_byte_ratio_pure_ascii() -> None:
    h = byte_histogram(b"hello")
    assert high_byte_ratio(h, 5) == 0.0


def test_high_byte_ratio_nonzero() -> None:
    data = bytes([0x80, 0x90, 0xA0, 0x00, 0x41])
    h = byte_histogram(data)
    r = high_byte_ratio(h, len(data))
    assert r == pytest.approx(3 / 5)


def test_null_byte_ratio() -> None:
    data = bytes([0, 0, 65, 66])
    h = byte_histogram(data)
    assert null_byte_ratio(h, 4) == pytest.approx(0.5)


def test_cp1252_zone_zero_for_ascii() -> None:
    h = byte_histogram(b"hello world")
    assert cp1252_zone_ratio(h, 11) == 0.0


def test_utf8_continuation_score_valid_utf8() -> None:
    data = "\u00e9\u00e0\u00fc".encode()
    score = utf8_continuation_score(data)
    assert score >= 0.9


def test_utf8_continuation_score_ascii() -> None:
    score = utf8_continuation_score(b"hello world")
    assert score == 0.0


def test_detect_null_pattern_utf16_le() -> None:
    data = "Hello".encode("utf-16-le")
    # utf-16-le: H=0x48,0x00  e=0x65,0x00 ...
    result = detect_null_pattern(data * 20)
    assert result == "utf_16_le"


def test_detect_null_pattern_none_for_ascii() -> None:
    result = detect_null_pattern(b"Hello world! This is ASCII text " * 5)
    assert result is None


def test_cosine_similarity_identical() -> None:
    v = [1.0, 0.0, 0.5, 0.3]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_histogram_to_ratios_empty() -> None:
    h = byte_histogram(b"")
    assert histogram_to_ratios(h, 0) == [0.0] * 256
