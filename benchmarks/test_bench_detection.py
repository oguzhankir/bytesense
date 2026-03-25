"""
Comprehensive benchmark: bytesense vs charset-normalizer vs chardet.

Datasets (see benchmarks/conftest.py):
  1) Synthetic samples (ground-truth encodings we generate in code).
  2) Official charset-normalizer `data/` files + expected encodings from their
     tests/test_full_detection.py (fetch: python scripts/fetch_cn_benchmark_samples.py).

Accuracy:
  - **Strict**: codec name matches (aliases OK via codecs.lookup).
  - **Functional**: same decoded Unicode text as the reference encoding (counts
    cp1253 vs iso8859_7, utf_8 vs utf_8_sig+BOM, etc. as correct when text matches).

Run: ``scripts/run_all_benchmarks.sh`` or pytest with an explicit ``-k`` list of
``test_bench_*`` functions (not ``-k bench_``, which matches this file's name).
"""
from __future__ import annotations

import codecs
from typing import List, Tuple

import pytest

# ---------------------------------------------------------------------------
# Accuracy helpers
# ---------------------------------------------------------------------------


def _normalise_enc(enc: str | None) -> str:
    """Normalise encoding name for comparison (lowercase, replace - with _)."""
    if enc is None:
        return ""
    return enc.lower().replace("-", "_").replace(" ", "_")


def _encodings_match(detected: str | None, expected: str) -> bool:
    """
    Return True if detected encoding is functionally equivalent to expected.
    Handles aliases: utf_8 == utf8 == utf-8, latin_1 == iso8859_1, etc.
    """
    if detected is None:
        return False
    try:
        det_info = codecs.lookup(_normalise_enc(detected))
        exp_info = codecs.lookup(_normalise_enc(expected))
        return det_info.name == exp_info.name
    except LookupError:
        return _normalise_enc(detected) == _normalise_enc(expected)


def _functional_text_match(data: bytes, detected: str | None, expected: str) -> bool:
    """
    True if strict codec match OR both decodings yield the same Unicode string
    (BOM-insensitive). Use for fair comparison vs charset-normalizer's corpus.
    """
    if _encodings_match(detected, expected):
        return True
    if detected is None:
        return False
    try:
        ta = data.decode(detected, errors="strict")
        tb = data.decode(expected, errors="strict")
    except (UnicodeDecodeError, LookupError):
        return False
    return ta.lstrip("\ufeff") == tb.lstrip("\ufeff")


def _load_dataset_parts() -> Tuple[List[Tuple[str, bytes, str]], List[Tuple[str, bytes, str]]]:
    ds = __import__("benchmarks.conftest", fromlist=["DATASET"]).DATASET
    syn = [(n, d, e) for n, d, e in ds if not n.startswith("cn_official_")]
    cn = [(n, d, e) for n, d, e in ds if n.startswith("cn_official_")]
    return syn, cn


_SYNTHETIC_DATASET, _CN_OFFICIAL_DATASET = _load_dataset_parts()


# ---------------------------------------------------------------------------
# Accuracy tests (NOT benchmarks — run in normal pytest)
# ---------------------------------------------------------------------------


class TestAccuracy:
    """
    Accuracy tests that MUST pass before any benchmark is run.
    These are correctness gates, not performance gates.
    """

    @pytest.mark.parametrize(
        "name,data,expected",
        [
            (name, data, enc)
            for name, data, enc in _SYNTHETIC_DATASET
            if enc in ("utf_8", "utf_8_sig", "ascii")
        ],
        ids=[
            name
            for name, _, enc in _SYNTHETIC_DATASET
            if enc in ("utf_8", "utf_8_sig", "ascii")
        ],
    )
    def test_bytesense_utf8_accuracy(self, name: str, data: bytes, expected: str) -> None:
        from bytesense import from_bytes

        result = from_bytes(data)
        assert _encodings_match(result.encoding, expected), (
            f"[{name}] bytesense detected {result.encoding!r}, expected {expected!r}. "
            f"Why: {result.why}"
        )

    @pytest.mark.parametrize(
        "name,data,expected",
        [(n, d, e) for n, d, e in _SYNTHETIC_DATASET],
        ids=[n for n, _, _ in _SYNTHETIC_DATASET],
    )
    def test_bytesense_full_accuracy(self, name: str, data: bytes, expected: str) -> None:
        from bytesense import from_bytes

        result = from_bytes(data)
        assert _encodings_match(result.encoding, expected), (
            f"[{name}] bytesense detected {result.encoding!r}, expected {expected!r}. "
            f"Chaos: {result.chaos}, Coherence: {result.coherence}. "
            f"Why: {result.why}"
        )

    @pytest.mark.skipif(len(_CN_OFFICIAL_DATASET) == 0, reason="Run scripts/fetch_cn_benchmark_samples.py")
    def test_bytesense_cn_official_functional_minimum(self) -> None:
        """
        charset-normalizer's official data/ files: require same decoded Unicode as reference
        (fair vs cp1253/iso8859_7, etc.). Threshold tracks current engine; raise as detection improves.
        """
        from bytesense import from_bytes

        ok = 0
        bad: List[str] = []
        for name, data, exp in _CN_OFFICIAL_DATASET:
            result = from_bytes(data)
            if _functional_text_match(data, result.encoding, exp):
                ok += 1
            else:
                bad.append(f"{name}: got {result.encoding!r}, expected decode {exp!r}")
        n = len(_CN_OFFICIAL_DATASET)
        assert ok == n, (
            f"CN corpus functional decode mismatch: {ok}/{n}.\n" + "\n".join(bad[:12])
        )

    def test_bytesense_overall_accuracy(self) -> None:
        """Synthetic corpus: strict codec match ≥ 95%."""
        from bytesense import from_bytes

        correct = 0
        total = len(_SYNTHETIC_DATASET)
        failures = []

        for name, data, expected in _SYNTHETIC_DATASET:
            result = from_bytes(data)
            if _encodings_match(result.encoding, expected):
                correct += 1
            else:
                failures.append(f"  {name}: got {result.encoding!r}, expected {expected!r}")

        accuracy = correct / total if total > 0 else 0.0
        failure_report = "\n".join(failures[:10])
        assert accuracy >= 0.95, (
            f"bytesense accuracy {accuracy:.1%} < 95%. "
            f"Failures ({len(failures)}/{total}):\n{failure_report}"
        )

    def test_charset_normalizer_accuracy_for_comparison(self) -> None:
        """
        Run charset-normalizer on the same dataset and print accuracy.
        This is informational — it does NOT fail if charset-normalizer scores lower.
        """
        pytest.importorskip("charset_normalizer")
        from charset_normalizer import from_bytes as cn_from_bytes

        from benchmarks.conftest import DATASET

        correct = 0
        total = len(DATASET)

        for _name, data, expected in DATASET:
            result = cn_from_bytes(data)
            best = result.best()
            detected = best.encoding if best else None
            if _encodings_match(detected, expected):
                correct += 1

        accuracy = correct / total if total > 0 else 0.0
        print(f"\ncharset-normalizer strict codec match: {accuracy:.1%} ({correct}/{total})")
        fn_c = 0
        for _n, data, exp in DATASET:
            b = cn_from_bytes(data).best()
            det = b.encoding if b else None
            if _functional_text_match(data, det, exp):
                fn_c += 1
        print(
            f"charset-normalizer functional (same text): {fn_c / total:.1%} ({fn_c}/{total})"
            if total
            else ""
        )
        # Not asserting — informational only


# ---------------------------------------------------------------------------
# Speed benchmarks
# ---------------------------------------------------------------------------

# Separate fast-path and standard-path samples for clarity
_FAST_PATH_NAMES = {
    "utf8_ascii_only",
    "utf8_english_unicode",
    "utf8_bom",
    "utf8_french_long",
    "utf8_russian",
    "utf8_chinese",
    "utf8_portuguese",
    "utf8_korean",
    "large_utf8_1mb",
}


def _get_samples(names: set[str]) -> List[Tuple[str, bytes]]:
    from benchmarks.conftest import DATASET

    return [(n, d) for n, d, _ in DATASET if n in names]


def _get_all_samples() -> List[Tuple[str, bytes]]:
    from benchmarks.conftest import DATASET

    return [(n, d) for n, d, _ in DATASET]


@pytest.mark.parametrize("name,data", _get_samples(_FAST_PATH_NAMES), ids=list(_FAST_PATH_NAMES))
def test_bench_bytesense_fast_path(benchmark: object, name: str, data: bytes) -> None:
    """Speed: bytesense on UTF-8 / ASCII / BOM fast-path inputs."""
    from bytesense import from_bytes

    result = benchmark(from_bytes, data)  # type: ignore[call-arg]
    assert result.encoding is not None


@pytest.mark.parametrize("name,data", _get_samples(_FAST_PATH_NAMES), ids=list(_FAST_PATH_NAMES))
def test_bench_cn_fast_path(benchmark: object, name: str, data: bytes) -> None:
    """Speed: charset-normalizer on the same fast-path inputs."""
    cn = pytest.importorskip("charset_normalizer")
    result = benchmark(cn.from_bytes, data)  # type: ignore[call-arg]
    assert result.best() is not None


@pytest.mark.parametrize("name,data", _get_all_samples(), ids=[n for n, _ in _get_all_samples()])
def test_bench_bytesense_full(benchmark: object, name: str, data: bytes) -> None:
    """Speed: bytesense on the full dataset."""
    from bytesense import from_bytes

    result = benchmark(from_bytes, data)  # type: ignore[call-arg]
    assert result.encoding is not None


@pytest.mark.parametrize("name,data", _get_all_samples(), ids=[n for n, _ in _get_all_samples()])
def test_bench_cn_full(benchmark: object, name: str, data: bytes) -> None:
    """Speed: charset-normalizer on the full dataset."""
    cn = pytest.importorskip("charset_normalizer")
    result = benchmark(cn.from_bytes, data)  # type: ignore[call-arg]
    assert result.best() is not None


@pytest.mark.parametrize("name,data", _get_all_samples(), ids=[n for n, _ in _get_all_samples()])
def test_bench_chardet_full(benchmark: object, name: str, data: bytes) -> None:
    """Speed: chardet on the full dataset (for three-way comparison)."""
    chardet = pytest.importorskip("chardet")
    result = benchmark(chardet.detect, data)  # type: ignore[call-arg]
    assert result.get("encoding") is not None or True  # chardet may return None


# ---------------------------------------------------------------------------
# Summary report (run with -s to see output)
# ---------------------------------------------------------------------------


def test_print_accuracy_summary() -> None:
    """Print a side-by-side accuracy summary for all three libraries."""
    from benchmarks.conftest import DATASET

    libs = {}

    try:
        from bytesense import from_bytes as bs_detect

        def bs(data: bytes) -> str | None:
            return bs_detect(data).encoding

        libs["bytesense"] = bs
    except ImportError:
        pass

    try:
        from charset_normalizer import from_bytes as cn_fb

        def cn(data: bytes) -> str | None:
            r = cn_fb(data).best()
            return r.encoding if r else None

        libs["charset-normalizer"] = cn
    except ImportError:
        pass

    try:
        import chardet as cd

        def chd(data: bytes) -> str | None:
            return cd.detect(data).get("encoding")

        libs["chardet"] = chd
    except ImportError:
        pass

    if not libs:
        pytest.skip("No libraries available for comparison")

    print("\n\n" + "=" * 70)
    print("Strict codec name match (aliases via codecs.lookup)")
    print(f"{'Library':<25} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 70)

    for lib_name, fn in libs.items():
        correct = 0
        for _, data, expected in DATASET:
            if _encodings_match(fn(data), expected):
                correct += 1
        acc = correct / len(DATASET) if DATASET else 0.0
        print(f"{lib_name:<25} {correct:>8} {len(DATASET):>8} {acc:>9.1%}")

    print("-" * 70)
    print("Functional match (same Unicode text as reference encoding)")
    print(f"{'Library':<25} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 70)

    for lib_name, fn in libs.items():
        correct = 0
        for _, data, expected in DATASET:
            det = fn(data)
            if _functional_text_match(data, det, expected):
                correct += 1
        acc = correct / len(DATASET) if DATASET else 0.0
        print(f"{lib_name:<25} {correct:>8} {len(DATASET):>8} {acc:>9.1%}")

    print("=" * 70 + "\n")
