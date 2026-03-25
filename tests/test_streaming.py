from __future__ import annotations

from bytesense import StreamDetector


def test_single_chunk() -> None:
    det = StreamDetector()
    det.feed(b"Hello world! This is a test of the streaming detector API. " * 3)
    assert det.encoding is not None
    assert det.confidence > 0.0


def test_multi_chunk_converges() -> None:
    data = "Bonjour le monde! " * 200
    enc_data = data.encode("utf-8")
    det = StreamDetector()
    for i in range(0, len(enc_data), 64):
        det.feed(enc_data[i : i + 64])
    assert det.encoding in ("utf_8", "ascii")
    assert det.confidence >= 0.9


def test_empty_chunk_ignored() -> None:
    det = StreamDetector()
    det.feed(b"")
    det.feed(b"Hello world test")
    det.feed(b"")
    assert det.bytes_fed >= 16


def test_finalize_returns_result() -> None:
    det = StreamDetector()
    det.feed(b"Hello world testing finalize method")
    result = det.finalize()
    assert result is not None
    assert result.encoding is not None


def test_reset() -> None:
    det = StreamDetector()
    det.feed(b"Hello world test data for the detector")
    det.reset()
    assert det.encoding is None
    assert det.bytes_fed == 0
    assert det.confidence == 0.0


def test_http_header_hint_boosts_confidence() -> None:
    det = StreamDetector()
    det.feed(b"Hello world test text." * 5)
    before = det.confidence
    det.hint_from_headers({"Content-Type": "text/html; charset=utf-8"})
    after = det.confidence
    assert after >= before
