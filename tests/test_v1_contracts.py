from __future__ import annotations

import codecs
import io
import subprocess
import sys
import tracemalloc

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from bytesense import StreamDetector, detect_multi, detect_stream, from_bytes, from_fp, repair_bytes


@pytest.mark.parametrize("encoding", ["utf_8_sig", "utf_16", "utf_32"])
def test_bom_uses_codec_that_consumes_the_signature(encoding: str) -> None:
    text = "Hello Ελληνικά 中文 🎉"
    data = text.encode(encoding)
    r = from_bytes(data)
    assert r.encoding is not None
    assert data.decode(r.encoding) == text
    assert r.complete and r.bytes_validated == len(data)


@pytest.mark.parametrize(
    "data", [b"hello", "é".encode(), b"\xef\xbb\xbfhello", b"\xff\xfeh\x00", b""]
)
def test_filters_cover_fast_paths_and_empty_inputs(data: bytes) -> None:
    assert from_bytes(data, cp_isolation=[]).encoding is None
    assert from_bytes(data, cp_isolation=["UTF-8"], cp_exclusion=["utf8"]).encoding is None
    r = from_bytes(data, cp_isolation=["windows-1252"])
    assert r.encoding in (None, "cp1252")
    assert all(a.encoding == "cp1252" for a in r.alternatives)


@pytest.mark.parametrize("bad", ["base64_codec", "rot_13", "not-a-codec"])
def test_filters_require_text_decoders(bad: str) -> None:
    with pytest.raises((LookupError, TypeError)):
        from_bytes(b"hello", cp_isolation=[bad])


@given(st.binary(max_size=1024))
@settings(max_examples=100, deadline=None)
def test_every_returned_codec_decodes_every_byte(data: bytes) -> None:
    r = from_bytes(data)
    assert r.byte_count == len(data)
    assert r.complete
    assert 0 <= r.bytes_examined <= len(data)
    if r.encoding:
        data.decode(r.encoding, errors="strict")
        assert r.bytes_validated == len(data)
    else:
        assert r.bytes_validated == 0


@pytest.mark.parametrize("suffix", [b"\xff", b"\xe2\x82"])
def test_invalid_tail_is_not_hidden_by_sampling(suffix: bytes) -> None:
    data = b"a" * 1_100_000 + suffix
    r = from_bytes(data, cp_isolation=["utf8"], sample_size=64)
    assert r.encoding is None
    assert r.complete


@pytest.mark.parametrize("codec", ["utf_8", "utf_16_le", "utf_32_be", "shift_jis", "cp1254"])
def test_stream_chunk_boundaries_do_not_drop_data(codec: str) -> None:
    text = (
        "日本語テストです。"
        if codec == "shift_jis"
        else "İstanbul güzel."
        if codec == "cp1254"
        else "Hello 世界 🙂"
    ) * 700
    data = text.encode(codec)
    r = detect_stream((data[i : i + 7] for i in range(0, len(data), 7)), cp_isolation=[codec])
    assert r.encoding == codecs.lookup(codec).name.replace("-", "_")
    assert r.byte_count == r.bytes_validated == len(data)
    assert r.complete
    assert data.decode(r.encoding) == text


def test_stream_consumes_late_legacy_bytes_even_in_one_large_chunk() -> None:
    data = b"plain header\n" * 20000 + (
        "İstanbul çalışanları güzel bir gün bekliyor. " * 40
    ).encode("cp1254")
    r = detect_stream(iter([data]), cp_isolation=["cp1254"])
    assert r.encoding == "cp1254"
    assert r.complete and r.bytes_validated == len(data)


def test_stream_lifecycle_and_budget() -> None:
    detector = StreamDetector(memory_limit=64)
    detector.feed(b"abc" * 100)
    assert detector.result is not None and not detector.result.complete
    result = detector.finalize()
    assert detector.finalize() is result
    with pytest.raises(RuntimeError):
        detector.feed(b"no silent loss")
    detector.reset()
    detector.feed(b"new")
    assert detector.finalize().byte_count == 3
    limited = detect_stream(iter([b"a" * 5000]), max_bytes=100)
    assert not limited.complete
    assert limited.byte_count == limited.bytes_validated == 100


def test_oversized_stream_chunk_does_not_duplicate_it_in_memory() -> None:
    data = b"a" * 8_000_000
    tracemalloc.start()
    try:
        with StreamDetector(memory_limit=65536) as detector:
            detector.feed(data)
            r = detector.finalize()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert r.byte_count == len(data)
    assert peak < 1_000_000


def test_from_fp_uses_bounded_reads_and_keeps_callers_file_open() -> None:
    class BoundedReader(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            assert 0 < size <= 65536
            return super().read(size)

    source = BoundedReader(b"a" * 200000)
    assert from_fp(source).bytes_validated == 200000
    assert not source.closed


@given(st.binary(min_size=1, max_size=300), st.integers(min_value=1, max_value=100))
@settings(max_examples=40, deadline=None)
def test_segments_cover_every_byte_exactly_once(data: bytes, size: int) -> None:
    r = detect_multi(data, segment_size=size)
    assert b"".join(s.data for s in r.segments) == data
    assert r.segments[0].start == 0 and r.segments[-1].end == len(data)
    assert all(a.end == b.start for a, b in zip(r.segments, r.segments[1:]))
    for segment in r.segments:
        assert segment.data == data[segment.start : segment.end]
        if segment.encoding:
            assert segment.text == segment.data.decode(segment.encoding)


def test_multi_preserves_unicode_characters_at_segment_edges() -> None:
    text = "字🙂é" * 1000
    r = detect_multi(text.encode(), segment_size=127)
    assert r.full_text == text


def test_repair_does_not_silently_replace_undecodable_bytes() -> None:
    with pytest.raises(UnicodeDecodeError):
        repair_bytes(b"\xffbroken", encoding="utf_8")
    with pytest.raises(LookupError):
        repair_bytes(b"hello", encoding="missing-codec")


def test_cli_stdin_and_failure_exit_codes() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "bytesense.cli", "-m", "-"],
        input="café".encode(),
        capture_output=True,
    )
    assert r.returncode == 0 and r.stdout.strip() == b"utf_8"
    r = subprocess.run(
        [sys.executable, "-m", "bytesense.cli", "-m", "-"],
        input=b"\x89PNG\r\n\x1a\n",
        capture_output=True,
    )
    assert r.returncode == 1 and r.stdout.strip() == b"unknown"


def test_native_and_python_language_scores_agree() -> None:
    from bytesense.scoring import _model, _prepare, _score_pure

    letters, pairs, native = _model()
    if native is None:
        pytest.skip("native model not installed")
    for text in [
        "İstanbul çalışanları",
        "日本語テスト。" * 30,
        'F"ô\\½#vFv¾vHöt',
        "Σίσυφος",
        "😀\x00\ue000",
        "",
        "ёabc 123\n",
    ]:
        normalized, bad, symbols = _prepare(text)
        assert native.score(normalized, bad, symbols) == pytest.approx(
            _score_pure(normalized, bad, symbols, letters, pairs), abs=1e-12
        )


def test_requested_backend_is_present() -> None:
    import os

    from bytesense._rust import is_rust_available

    expected = os.environ.get("BYTESENSE_EXPECT_RUST")
    if expected is not None:
        assert is_rust_available() == (expected == "1")


@pytest.mark.parametrize("codec", ["utf_7", "hz", "iso2022_jp"])
def test_seven_bit_shift_encodings_are_not_ascii(codec: str) -> None:
    text = ("日本語のテストです。" if codec != "hz" else "中文编码测试。") * 10
    data = text.encode(codec)
    r = from_bytes(data)
    assert r.encoding is not None and data.decode(r.encoding) == text


def test_hint_filters_and_invalid_declarations() -> None:
    data = b"<meta charset=windows-1250>" + "Příliš žluťoučký kůň.".encode("cp1250")
    assert from_bytes(data).encoding == "cp1250"
    assert from_bytes(data, cp_exclusion=["cp1250"]).encoding != "cp1250"
    assert from_bytes("café".encode(), encoding_hint="cp1252").encoding == "utf_8"


def test_no_document_cache_changes_results() -> None:
    from bytesense import from_bytes
    from bytesense.scoring import _model

    a = "İstanbul çalışanları doğru çözümleme bekliyor. ".encode("cp1254") * 30
    before = from_bytes(a).to_dict()
    for encoding, text in [("cp1251", "Русский текст"), ("big5", "中文測試文字")]:
        from_bytes(text.encode(encoding) * 20)
    assert from_bytes(a).to_dict() == before
    assert _model.cache_info().currsize == 1


@pytest.mark.parametrize("chunk_size", [1, 7, 4096, 100000])
def test_late_statistical_sample_is_independent_of_chunks(chunk_size: int) -> None:
    data = b"header\n" * 1000 + ("İstanbul çalışanları doğru çözümleme bekliyor. " * 70).encode(
        "cp1254"
    )
    reference = from_bytes(data)
    streamed = detect_stream(
        iter(data[i : i + chunk_size] for i in range(0, len(data), chunk_size))
    )
    assert reference.encoding == streamed.encoding == "cp1254"
    assert streamed.bytes_validated == len(data)


@given(st.text(max_size=512))
@settings(max_examples=100, deadline=None)
def test_fused_native_score_matches_python_unicode_semantics(text: str) -> None:
    from bytesense.scoring import _classify, _model, _prepare, _score_pure

    letters, pairs, native = _model()
    if native is None:
        pytest.skip("native model not installed")
    normalized, bad, symbols = _prepare(text)
    score, native_bad = native.quality(text, text.lower(), _classify)
    assert score == pytest.approx(_score_pure(normalized, bad, symbols, letters, pairs), abs=1e-12)
    assert native_bad == pytest.approx(bad, abs=1e-12)


def test_parallel_detection_is_deterministic() -> None:
    from concurrent.futures import ThreadPoolExecutor

    corpus = [
        "İstanbul çalışanları".encode("cp1254") * 30,
        "日本語テストです。".encode("euc_jp") * 30,
        "Русский текст".encode("cp1251") * 30,
    ]
    expected = [from_bytes(d).to_dict() for d in corpus]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = list(pool.map(lambda i: from_bytes(corpus[i % 3]).to_dict(), range(24)))
    assert actual == [expected[i % 3] for i in range(24)]
