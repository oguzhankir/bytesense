from __future__ import annotations

import pytest

from bytesense import from_bytes, is_binary
from bytesense.models import DetectionResult


class TestFromBytes:
    def test_returns_detection_result(self) -> None:
        result = from_bytes(b"hello")
        assert isinstance(result, DetectionResult)

    def test_empty_bytes_returns_utf8(self) -> None:
        r = from_bytes(b"")
        assert r.encoding == "utf_8"
        assert r.byte_count == 0

    def test_bytearray_accepted(self) -> None:
        r = from_bytes(bytearray(b"hello world"))
        assert r.encoding is not None

    def test_wrong_type_raises(self) -> None:
        with pytest.raises(TypeError):
            from_bytes("not bytes")  # type: ignore[arg-type]

    def test_pure_ascii(self) -> None:
        r = from_bytes(b"Hello World! Pure ASCII text here.")
        assert r.encoding in ("ascii", "utf_8")
        assert r.confidence >= 0.99
        assert r.bom_detected is False

    def test_utf8_bom(self) -> None:
        data = b"\xef\xbb\xbf" + b"Hello!"
        r = from_bytes(data)
        assert r.encoding == "utf_8_sig"
        assert r.bom_detected is True
        assert r.confidence == 1.0

    def test_utf16_le_bom(self) -> None:
        data = "Hello UTF-16".encode("utf-16")  # Python adds LE BOM automatically
        r = from_bytes(data)
        assert r.encoding in ("utf_16", "utf_16_le")
        assert r.bom_detected is True

    def test_utf8_english(self) -> None:
        data = (
            b"The quick brown fox jumps over the lazy dog. Sphinx of black quartz."
        )
        r = from_bytes(data)
        assert r.encoding in ("utf_8", "ascii")
        assert r.confidence >= 0.9

    def test_utf8_french(self) -> None:
        data = (
            "Bonjour le monde! J'aime les \u00e9toiles et la lune. "
            "Le fran\u00e7ais est une belle langue."
        ).encode()
        r = from_bytes(data)
        assert r.encoding == "utf_8"

    def test_result_has_all_fields(self) -> None:
        r = from_bytes(b"hello world test data for encoding")
        assert hasattr(r, "encoding")
        assert hasattr(r, "confidence")
        assert hasattr(r, "confidence_interval")
        assert hasattr(r, "language")
        assert hasattr(r, "alternatives")
        assert hasattr(r, "bom_detected")
        assert hasattr(r, "chaos")
        assert hasattr(r, "coherence")
        assert hasattr(r, "why")
        assert hasattr(r, "byte_count")

    def test_confidence_interval_valid(self) -> None:
        r = from_bytes(b"hello world testing encoding detection")
        lo, hi = r.confidence_interval
        assert 0.0 <= lo <= r.confidence <= hi <= 1.0

    def test_to_dict(self) -> None:
        r = from_bytes(b"hello world")
        d = r.to_dict()
        assert isinstance(d, dict)
        assert "encoding" in d
        assert "confidence" in d

    def test_is_binary_text_returns_false(self) -> None:
        assert is_binary(b"Hello world! This is normal text.") is False

    def test_bool_true_when_detected(self) -> None:
        r = from_bytes(b"hello world")
        assert bool(r) is True

    def test_cp_isolation(self) -> None:
        data = "café résumé".encode()
        r = from_bytes(data, cp_isolation=["utf_8"])
        assert r.encoding == "utf_8"

    def test_cp_exclusion(self) -> None:
        data = "été à la plage".encode()
        r = from_bytes(data, cp_exclusion=["ascii"])
        assert r.encoding is not None
        assert r.encoding != "ascii"
