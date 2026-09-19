"""Strict UTF-8 validation across SIMD, BOM, and incremental decoder boundaries."""

from __future__ import annotations

import codecs
import platform
import tracemalloc

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bytesense import api, from_bytes
from bytesense._rust import is_rust_available, rust_utf8_check


def _strictly_valid(data: bytes, encoding: str) -> bool:
    try:
        data.decode(encoding, errors="strict")
    except UnicodeError:
        return False
    return True


@pytest.mark.parametrize("encoding", ["utf_8", "utf_8_sig"])
@given(data=st.one_of(st.binary(max_size=4096), st.text(max_size=4096).map(str.encode)))
@settings(max_examples=300, deadline=None)
def test_utf8_validation_matches_strict_python(data: bytes, encoding: str) -> None:
    assert api._valid(data, encoding) == _strictly_valid(data, encoding)


@pytest.mark.parametrize("encoding", ["utf_8", "utf_8_sig"])
@pytest.mark.parametrize("offset", [31, 32, 63, 64, 65, 65535, 65536, 65537, 1_048_575])
@pytest.mark.parametrize(
    "suffix",
    [
        "é中🙂".encode(),
        b"\xc0\xaf",  # Overlong sequence.
        b"\xed\xa0\x80",  # Surrogate scalar.
        b"\xf4\x90\x80\x80",  # Above U+10FFFF.
        b"\xe2\x82",  # Truncated code point.
        b"\x80",  # Unpaired continuation byte.
    ],
)
def test_utf8_boundaries_preserve_full_input_validation(
    encoding: str, offset: int, suffix: bytes
) -> None:
    prefix = codecs.BOM_UTF8 if encoding == "utf_8_sig" else b""
    data = prefix + b"a" * offset + suffix
    expected = _strictly_valid(data, encoding)
    assert api._valid(data, encoding) == expected
    result = from_bytes(data, cp_isolation=[encoding], enable_fallback=False)
    assert (result.encoding is not None) == expected
    if expected:
        assert result.bytes_validated == len(data)


@pytest.mark.skipif(not is_rust_available(), reason="Native extension not compiled")
@given(data=st.binary(max_size=8192))
@settings(max_examples=500, deadline=None)
def test_native_error_offset_matches_python(data: bytes) -> None:
    try:
        data.decode("utf_8", errors="strict")
        expected = (True, 1.0)
    except UnicodeDecodeError as error:
        expected = (False, error.start / len(data))
    assert rust_utf8_check(data) == expected


@pytest.mark.skipif(platform.python_implementation() != "CPython", reason="CPython allocation probe")
@pytest.mark.parametrize("native", [False, True])
def test_utf8_validation_does_not_allocate_full_decoded_input(monkeypatch, native: bool) -> None:
    if native and not is_rust_available():
        pytest.skip("Native extension not compiled")
    if not native:
        monkeypatch.setattr(api, "is_rust_available", lambda: False)
    data = ("Merhaba dünya! 日本語 Ελληνικά 🙂 ".encode() * 30_000)[:1_048_576]
    data = data.decode("utf_8", errors="ignore").encode("utf_8")
    # Warm the decoder and feature dispatch before measuring call allocations.
    assert api._valid(data, "utf_8")
    tracemalloc.start()
    try:
        assert api._valid(data, "utf_8")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 600_000


def test_non_utf8_custom_codec_keeps_existing_one_shot_boundary() -> None:
    class BytesOnlyDecoder(codecs.IncrementalDecoder):
        def decode(self, data: bytes, final: bool = False) -> str:
            if not isinstance(data, bytes):
                raise TypeError("decoder requires bytes")
            return data.decode("ascii")

    def search(name: str) -> codecs.CodecInfo | None:
        if name != "bytesense_test_bytes_only":
            return None
        return codecs.CodecInfo(
            name=name,
            encode=codecs.ascii_encode,
            decode=codecs.ascii_decode,
            incrementaldecoder=BytesOnlyDecoder,
        )

    codecs.register(search)
    assert api._valid(b"a" * 65537, "bytesense_test_bytes_only")
