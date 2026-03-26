"""Edge cases for hints module."""
from __future__ import annotations

from bytesense.hints import _normalise, hint_from_content, hint_from_http_headers


def test_normalise_invalid_codec() -> None:
    assert _normalise("not-a-real-codec-name-xyz") is None


def test_hint_from_http_headers_empty() -> None:
    assert hint_from_http_headers({}) is None


def test_hint_from_content_malformed_meta() -> None:
    data = b"<meta charset=\xff\xff>"
    out = hint_from_content(data)
    assert out is None or isinstance(out, str)
