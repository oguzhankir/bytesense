"""Tests for Phase 3A enhanced StreamDetector."""
from __future__ import annotations

from collections.abc import Iterator

from bytesense import StreamDetector, detect_stream


def test_auto_stops_when_stable() -> None:
    """StreamDetector should mark itself stable after STABILITY_ROUNDS rounds."""
    det = StreamDetector(auto_stop_confidence=0.90)
    data = ("Hello world! " * 200).encode("utf-8")
    for i in range(0, len(data), 64):
        det.feed(data[i : i + 64])
        if det.is_stable:
            break
    assert det.encoding is not None
    assert det.is_stable


def test_snapshot_returns_dict() -> None:
    det = StreamDetector()
    det.feed(b"Hello world test data for snapshot method")
    s = det.snapshot()
    assert isinstance(s, dict)
    assert "bytes_fed" in s
    assert "encoding" in s
    assert "confidence" in s
    assert "stable_rounds" in s


def test_inband_html_hint_detected() -> None:
    """Auto-detection of HTML meta charset declaration."""
    data = b'<html><head><meta charset="utf-8"></head><body>Test content here.</body></html>' * 10
    det = StreamDetector()
    det.feed(data)
    assert det._declared_hint in ("utf_8", None)


def test_xml_hint_detected() -> None:
    data = b'<?xml version="1.0" encoding="ISO-8859-1"?><root>content</root>' * 20
    det = StreamDetector()
    det.feed(data)
    if det._declared_hint:
        import codecs

        assert codecs.lookup(det._declared_hint).name == "iso8859-1"


def test_detect_stream_function() -> None:
    data = ("The quick brown fox jumps over the lazy dog. " * 50).encode("utf-8")
    result = detect_stream(iter([data[i : i + 512] for i in range(0, len(data), 512)]))
    assert result.encoding in ("utf_8", "ascii")
    assert result.confidence >= 0.9


def test_detect_stream_stops_at_max_bytes() -> None:
    """detect_stream must respect max_bytes limit."""

    def _infinite() -> Iterator[bytes]:
        while True:
            yield b"Hello World! " * 100

    result = detect_stream(_infinite(), max_bytes=8192)
    assert result.encoding is not None


def test_reset_clears_declared_hint() -> None:
    det = StreamDetector()
    det.feed(b'<meta charset="utf-8">' * 20)
    det.reset()
    assert det._declared_hint is None
    assert det.bytes_fed == 0
