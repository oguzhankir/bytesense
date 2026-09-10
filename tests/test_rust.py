from __future__ import annotations

import pytest

from bytesense._rust import is_rust_available

pytestmark = pytest.mark.skipif(
    not is_rust_available(),
    reason="Rust extension not compiled",
)


def test_rust_available() -> None:
    assert is_rust_available() is True


def test_rust_histogram_length() -> None:
    from bytesense._rust_core import byte_histogram  # type: ignore[import-untyped]

    h = byte_histogram(b"hello world")
    assert len(h) == 256


def test_rust_histogram_counts() -> None:
    from bytesense._rust_core import byte_histogram  # type: ignore[import-untyped]

    h = byte_histogram(b"aab")
    assert h[ord("a")] == 2
    assert h[ord("b")] == 1


def test_rust_utf8_check_valid() -> None:
    from bytesense._rust_core import utf8_check  # type: ignore[import-untyped]

    valid, conf = utf8_check("héllo".encode())
    assert valid is True
    assert conf == pytest.approx(1.0)


def test_rust_utf8_check_invalid() -> None:
    from bytesense._rust_core import utf8_check  # type: ignore[import-untyped]

    valid, conf = utf8_check(b"\xff\xfe\x00hello")
    assert valid is False
    assert 0.0 <= conf <= 1.0


def test_native_histogram_matches_independent_python_implementation() -> None:
    from bytesense._rust_core import byte_histogram as rust_hist

    from bytesense.fingerprint import _byte_histogram_pure

    for data in (b"", bytes(range(256)) * 400, b"x" * 100003):
        assert rust_hist(data) == list(_byte_histogram_pure(data))


def test_native_properties_cache_only_bmp_scalars() -> None:
    from bytesense._rust_core import NgramModel

    from bytesense.scoring import _classify

    model = NgramModel("abα𐐨", [("ab", 0.9), ("α𐐨", 0.8)])
    classified = []

    def classify(chars: str) -> list[tuple[bool, bool, bool]]:
        classified.append(set(chars))
        return _classify(chars)

    text = "Abα\uffff𐐨"
    expected = model.quality(text, text.lower(), classify)
    assert classified == [set(text + text.lower())]
    classified.clear()
    assert model.quality(text, text.lower(), classify) == expected
    assert classified == [{"𐐨"}]
    classified.clear()
    model.quality("Abα\uffff", "abα\uffff", classify)
    assert classified == []


def test_native_rejects_incomplete_property_records_without_caching_them() -> None:
    from bytesense._rust_core import NgramModel

    from bytesense.scoring import _classify

    model = NgramModel("ab", [("ab", 1.0)])
    with pytest.raises(ValueError, match="one property record per scalar"):
        model.quality("ab", "ab", lambda _: [])
    assert model.quality("ab", "ab", _classify) == pytest.approx((1.0, 0.0))


def test_native_cold_property_cache_is_thread_safe() -> None:
    from concurrent.futures import ThreadPoolExecutor

    from bytesense._rust_core import NgramModel

    from bytesense.scoring import _classify, _prepare, _score_pure

    letters = frozenset("abασ𐐨")
    pairs = {"ab": 0.9, "ασ": 0.8, "σ𐐨": 0.7}
    model = NgramModel("".join(sorted(letters)), list(pairs.items()))
    texts = ["Ab ΑΣ𐐨\x00", "ab αΣ𐐨\uffff", "😀\ue000ab\t", "Σίσυφος"] * 16
    expected = []
    for text in texts:
        normalized, bad, symbols = _prepare(text)
        expected.append((_score_pure(normalized, bad, symbols, letters, pairs), bad))

    def quality(text: str) -> tuple[float, float]:
        return model.quality(text, text.lower(), _classify)

    with ThreadPoolExecutor(max_workers=8) as pool:
        actual = list(pool.map(quality, texts))
    for got, want in zip(actual, expected):
        assert got == pytest.approx(want, abs=1e-12)


def test_native_dense_pair_table_matches_sparse_lookup_boundaries() -> None:
    from bytesense._rust_core import NgramModel

    from bytesense.scoring import _classify, _prepare, _score_pure

    letters = frozenset("aþÿā")
    entries = [("aþ", 0.2), ("þÿ", 0.7), ("ÿā", 0.8), ("āa", 0.9), ("aþ", 0.6)]
    pairs = dict(entries)
    model = NgramModel("".join(sorted(letters)), entries)
    text = "aþÿāaa" * 100
    normalized, bad, symbols = _prepare(text)
    expected = _score_pure(normalized, bad, symbols, letters, pairs)
    assert model.score(normalized, bad, symbols) == pytest.approx(expected, abs=1e-12)
    assert model.quality(text, text.lower(), _classify)[0] == pytest.approx(expected, abs=1e-12)
