"""Tests for multi-encoding document detection."""
from __future__ import annotations

import json

from bytesense import DocumentSegment, MultiEncodingResult, detect_multi


def test_single_encoding_document() -> None:
    data = ("Hello world! " * 1000).encode("utf-8")
    result = detect_multi(data)
    assert isinstance(result, MultiEncodingResult)
    assert result.is_uniform is True
    assert result.dominant in ("utf_8", "ascii")


def test_result_has_segments() -> None:
    data = ("Test content. " * 500).encode("utf-8")
    result = detect_multi(data)
    assert len(result.segments) >= 1
    for seg in result.segments:
        assert isinstance(seg, DocumentSegment)
        assert seg.encoding is not None
        assert seg.end > seg.start


def test_full_text_reconstruction() -> None:
    text = "Hello world! " * 200
    data = text.encode("utf-8")
    result = detect_multi(data)
    full = result.full_text
    assert isinstance(full, str)
    assert len(full) > 0


def test_to_dict_serializable() -> None:
    data = ("Test " * 500).encode("utf-8")
    result = detect_multi(data)
    d = result.to_dict()
    json.dumps(d)


def test_small_document_single_segment() -> None:
    data = b"Short text."
    result = detect_multi(data)
    assert len(result.segments) == 1
