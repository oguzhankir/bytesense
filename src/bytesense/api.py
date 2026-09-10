"""Encoding detection with bounded statistical scoring and complete decode validation."""

from __future__ import annotations

import codecs
import re
from dataclasses import replace
from os import PathLike
from typing import Any, BinaryIO, List, Optional

from .candidate import CandidateSelector
from .coherence import detect_language
from .constant import ALL_ENCODINGS
from .fingerprint import detect_null_pattern
from .hints import hint_from_content
from .models import DetectionResult, EncodingAlternative
from .scoring import text_quality


def _looks_like_iso2022(data: bytes) -> bool:
    if b"\x1b" not in data:
        return False
    return any(marker in data for marker in (b"\x1b$", b"\x1b(", b"\x1b)", b"\x1b."))


def _make_result(
    encoding: Optional[str],
    chaos: float,
    coherence: float,
    language: str,
    bom_detected: bool,
    alternatives: List[EncodingAlternative],
    why: str,
    byte_count: int,
    confidence: float = 0.0,
) -> DetectionResult:
    return DetectionResult(
        encoding=encoding,
        confidence=confidence,
        confidence_interval=None,
        language=language,
        alternatives=alternatives,
        bom_detected=bom_detected,
        chaos=round(chaos, 4),
        coherence=round(coherence, 4),
        why=why,
        byte_count=byte_count,
    )


# Stable tie preferences. Statistical scoring still considers every supported codec.
_COMMON = [
    "cp1252",
    "latin_1",
    "cp1254",
    "cp1250",
    "cp1251",
    "cp1253",
    "cp1255",
    "cp1256",
    "cp1257",
    "cp1258",
    "shift_jis",
    "cp932",
    "euc_jp",
    "euc_kr",
    "cp949",
    "big5",
    "gb2312",
    "gbk",
    "gb18030",
    "cp850",
    "cp437",
    "cp866",
]
_CANDIDATES = list(dict.fromkeys(_COMMON + ALL_ENCODINGS + ["cp720", "cp874", "cp875"]))


def _from_sample(
    data: bytes,
    threshold: float = 0.2,
    cp_isolation: Optional[List[str]] = None,
    cp_exclusion: Optional[List[str]] = None,
    language_threshold: float = 0.1,
    enable_fallback: bool = False,
) -> DetectionResult:
    """Score a bounded prefix. The caller must validate every final candidate."""
    candidates = _CANDIDATES if cp_isolation is None else cp_isolation
    rows: list[tuple[str, float, float, str]] = []
    # Local only: codecs that produce identical Unicode share statistical work.
    evidence: dict[str, tuple[float, float]] = {}
    for name in candidates:
        encoding = _codec(name)
        if cp_exclusion and encoding in cp_exclusion:
            continue
        try:
            decoded = codecs.getincrementaldecoder(encoding)(errors="strict").decode(
                data, final=False
            )
        except UnicodeError:
            continue
        if decoded not in evidence:
            evidence[decoded] = text_quality(decoded)
        support, bad = evidence[decoded]
        if bad > threshold or support < 0.25:
            continue
        rows.append((encoding, support, bad, decoded))
    if not rows:
        return _make_result(None, 1.0, 0.0, "", False, [], "Insufficient text evidence.", len(data))
    rows.sort(key=lambda item: item[1], reverse=True)
    encoding, support, bad, decoded = rows[0]
    # Same-text aliases are not independent linguistic evidence. Use the margin
    # to the next different decoding; score remains explicitly uncalibrated.
    runner = next((score for _, score, _, text in rows[1:] if text != decoded), support)
    margin = max(0.0, support - runner)
    confidence = round(min(0.95, max(0.1, 0.5 * support + min(0.45, margin * 3))), 4)
    alts = [
        EncodingAlternative(enc, round(min(0.95, max(0.0, score * 0.5)), 4), "")
        for enc, score, _, _ in rows[1:6]
    ]
    return _make_result(
        encoding,
        bad,
        min(1.0, max(0.0, support)),
        "",
        False,
        alts,
        f"Selected {encoding}; character-pair support {support:.3f}, margin {margin:.3f}.",
        len(data),
        confidence=confidence,
    )


_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0e-\x1a\x1c-\x1f\x7f]")
_BINARY_MAGIC = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"PK\x03\x04",
    b"\x1f\x8b",
    b"%PDF-",
    b"\x7fELF",
    b"Rar!\x1a\x07",
)


def _codec(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("encoding names must be strings")
    info = codecs.lookup(name)
    # Reject non-text transforms such as base64, zlib and rot13.
    if not getattr(info, "_is_text_encoding", True):
        raise LookupError(f"{name!r} is not a bytes-to-text codec")
    if info.incrementaldecoder is None:
        raise LookupError(f"{name!r} requires an incremental text decoder")
    if not isinstance(info.incrementaldecoder(errors="strict").decode(b"", final=False), str):
        raise LookupError(f"{name!r} is not a bytes-to-text codec")
    norm = info.name.replace("-", "_")
    return "latin_1" if norm == "iso8859_1" else norm


def _filters(
    isolation: Optional[List[str]], exclusion: Optional[List[str]]
) -> tuple[Optional[List[str]], List[str]]:
    include = (
        list(dict.fromkeys(_codec(name) for name in isolation)) if isolation is not None else None
    )
    exclude = (
        list(dict.fromkeys(_codec(name) for name in exclusion)) if exclusion is not None else []
    )
    if include is not None:
        include = [name for name in include if name not in exclude]
    return include, exclude


def _allowed(name: str, include: Optional[List[str]], exclude: List[str]) -> bool:
    return name not in exclude and (include is None or name in include)


def _binary(data: bytes) -> bool:
    if data.startswith(_BINARY_MAGIC):
        return True
    sample = data[:4096]
    if not sample or detect_null_pattern(sample):
        return False
    return len(_CONTROL_BYTES.findall(sample)) / len(sample) > 0.05


def _valid(data: bytes, encoding: str) -> bool:
    try:
        if len(data) <= 1_048_576:
            data.decode(encoding, errors="strict")
        else:
            decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
            view = memoryview(data)
            for offset in range(0, len(data), 65536):
                decoder.decode(view[offset : offset + 65536], final=False)
            decoder.decode(b"", final=True)
        return True
    except (UnicodeError, LookupError):
        return False


def _result(
    encoding: Optional[str],
    size: int,
    why: str,
    confidence: float = 0.0,
    status: str = "matched",
    examined: Optional[int] = None,
) -> DetectionResult:
    r = _make_result(
        encoding, 0.0 if encoding else 1.0, 0.0, "", False, [], why, size, confidence=confidence
    )
    return replace(
        r,
        bytes_examined=size if examined is None else examined,
        bytes_validated=size if encoding else 0,
        complete=True,
        status=status if encoding else status if status != "matched" else "unknown",
    )


_HIGH_BYTE = re.compile(b"[\x80-\xff\x1b]")


def _informative_sample(data: bytes | bytearray, size: int) -> bytes:
    """Avoid spending the entire linguistic budget on an ASCII file header."""
    first = _HIGH_BYTE.search(data)
    start = max(0, first.start() - 64) if first and first.start() > size // 4 else 0
    return bytes(data[start : start + size])


def _bom_codec(data: bytes, include: Optional[List[str]], exclude: List[str]) -> Optional[str]:
    raw = CandidateSelector(data).bom_encoding()
    if raw is None:
        return None
    canonical = (
        "utf_32" if raw.startswith("utf_32") else "utf_16" if raw.startswith("utf_16") else raw
    )
    if _allowed(canonical, include, exclude):
        return canonical
    return raw if _allowed(raw, include, exclude) else None


def _transport_encoding(data: bytes) -> Optional[str]:
    # Distinctive shift syntax is checked before the ASCII/UTF-8 fast paths.
    if b"~" in data and b"~{" in data and b"~}" in data:
        try:
            decoded = data.decode("hz")
            if len(re.findall(r"[\u4e00-\u9fff]", decoded)) / max(1, len(decoded)) > 0.1:
                return "hz"
        except UnicodeError:
            pass
    if b"+" in data and re.search(rb"\+[A-Za-z0-9/]{3,}(?:-|[^A-Za-z0-9/]|$)", data):
        try:
            decoded = data.decode("utf_7")
            if not decoded.isascii() and all(c.isprintable() or c in "\n\r\t" for c in decoded):
                return "utf_7"
        except UnicodeError:
            pass
    return None


def from_bytes(
    data: bytes | bytearray,
    steps: int = 5,
    chunk_size: int = 512,
    threshold: float = 0.2,
    cp_isolation: Optional[List[str]] = None,
    cp_exclusion: Optional[List[str]] = None,
    language_threshold: float = 0.1,
    enable_fallback: bool = True,
    *,
    sample_size: int = 4096,
    include_language: bool = False,
    min_confidence: float = 0.0,
    encoding_hint: Optional[str] = None,
    use_hints: bool = True,
) -> DetectionResult:
    """Detect bytes and strictly validate the selected codec over the entire input.

    Linguistic scoring is bounded by ``sample_size``; full validation is O(n).
    ``confidence`` is an evidence score, not a calibrated probability.
    Filters apply to all paths. An empty isolation list allows no encodings.
    ``enable_fallback`` permits a validated, explicitly low-confidence last
    candidate; it never returns an encoding that cannot decode the input.
    Language reporting is opt-in. No document text is retained globally.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Expected bytes or bytearray, got {type(data).__name__}")
    if isinstance(data, bytearray):
        data = bytes(data)
    for name, value in [("sample_size", sample_size), ("steps", steps), ("chunk_size", chunk_size)]:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if sample_size < 64:
        raise ValueError("sample_size must be at least 64 bytes")
    for name, score_value in [
        ("threshold", threshold),
        ("language_threshold", language_threshold),
        ("min_confidence", min_confidence),
    ]:
        if not 0.0 <= score_value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    include, exclude = _filters(cp_isolation, cp_exclusion)
    hint = _codec(encoding_hint) if encoding_hint is not None else None
    size = len(data)
    if include == []:
        return _result(None, size, "No encodings allowed by the filters.")
    if not data:
        enc = (
            ("utf_8" if _allowed("utf_8", include, exclude) else (include[0] if include else None))
            if min_confidence == 0
            else None
        )
        return _result(enc, 0, "Empty input; no encoding evidence.", 0.0, "ambiguous")
    bom = _bom_codec(data, include, exclude)
    if bom:
        if not _valid(data, bom):
            return _result(
                None, size, "BOM declares an encoding but the input is invalid.", status="invalid"
            )
        r = _result(bom, size, f"BOM declares {bom}; all bytes validated.", 1.0)
        return replace(r, bom_detected=True)
    transport = _transport_encoding(data) if data.isascii() else None
    if transport and _allowed(transport, include, exclude):
        if min_confidence <= 0.85:
            return _result(
                transport, size, "Recognized and validated 7-bit shift syntax.", 0.85, "ambiguous"
            )
        return _result(None, size, "Below minimum confidence.")
    shape = detect_null_pattern(data)
    if shape and _allowed(shape, include, exclude) and _valid(data, shape):
        return (
            _result(shape, size, "Unicode byte-lane pattern; complete input validated.", 0.9)
            if min_confidence <= 0.9
            else _result(None, size, "Below minimum confidence.")
        )
    if _binary(data):
        return _result(
            None,
            size,
            "Binary signature or excessive control bytes.",
            status="binary",
            examined=min(size, 4096),
        )
    shape = detect_null_pattern(data)
    if not shape and not _looks_like_iso2022(data):
        if data.isascii() and _allowed("ascii", include, exclude):
            return _result("ascii", size, "All bytes are valid ASCII text.", 1.0)
        if _allowed("utf_8", include, exclude) and _valid(data, "utf_8"):
            r = _result("utf_8", size, "All bytes validated as UTF-8.", 0.99)
            if include_language:
                language_sample = codecs.getincrementaldecoder("utf_8")().decode(
                    data[:sample_size], final=False
                )
                langs = detect_language(language_sample, threshold=language_threshold)
                if langs:
                    r = replace(r, language=langs[0][0], coherence=round(langs[0][1], 4))
            return (
                r
                if r.confidence >= min_confidence
                else _result(None, size, "Below minimum confidence.")
            )
    if hint is None and use_hints:
        declared = hint_from_content(data)
        if declared:
            try:
                hint = _codec(declared)
            except (LookupError, TypeError):
                pass
    if hint and _allowed(hint, include, exclude) and _valid(data, hint):
        r = _result(hint, size, f"Encoding hint {hint}; all bytes validated.", 0.95)
        return (
            r
            if r.confidence >= min_confidence
            else _result(None, size, "Below minimum confidence.")
        )
    sample = _informative_sample(data, sample_size)
    r = _from_sample(
        sample,
        threshold=threshold,
        cp_isolation=include,
        cp_exclusion=exclude,
        language_threshold=language_threshold,
        enable_fallback=False,
    )
    ranked = ([r.encoding] if r.encoding else []) + [a.encoding for a in r.alternatives]
    for encoding in ranked:
        if encoding and _allowed(encoding, include, exclude) and _valid(data, encoding):
            confidence = r.confidence if encoding == r.encoding else min(0.5, r.confidence)
            if confidence < min_confidence:
                break
            if include_language and encoding == r.encoding:
                decoded = codecs.getincrementaldecoder(encoding)().decode(sample, final=False)
                langs = detect_language(decoded, threshold=language_threshold)
                if langs:
                    r = replace(r, language=langs[0][0])
            return replace(
                r,
                encoding=encoding,
                confidence=confidence,
                byte_count=size,
                bytes_examined=len(sample),
                bytes_validated=size,
                complete=True,
                status="ambiguous" if r.alternatives else "matched",
                chaos=r.chaos if encoding == r.encoding else 0.0,
                coherence=r.coherence if encoding == r.encoding else 0.0,
                alternatives=[a for a in r.alternatives if a.encoding != encoding],
                language=r.language if include_language and encoding == r.encoding else "",
                why=r.why + " Full input validated."
                if encoding == r.encoding
                else f"Full validation rejected the sampled winner; selected {encoding} as a validated alternative.",
            )
    # An explicit candidate can be absent from the statistical shortlist. It
    # still must pass full validation before being offered as a fallback.
    if enable_fallback and min_confidence <= 0.1:
        for encoding in include or []:
            if _valid(data, encoding):
                return _result(
                    encoding,
                    size,
                    "Validated fallback; insufficient linguistic evidence.",
                    0.1,
                    "ambiguous",
                    len(sample),
                )
    return _result(
        None,
        size,
        "No permitted candidate validates the complete input.",
        status="unknown",
        examined=len(sample),
    )


def from_path(path: str | bytes | PathLike[str], **kwargs: Any) -> DetectionResult:
    """Read a file with bounded memory and validate every byte."""
    with open(path, "rb") as fp:
        return from_fp(fp, **kwargs)


def from_fp(fp: BinaryIO, **kwargs: Any) -> DetectionResult:
    """Consume a binary stream without an unbounded read. Leaves it open."""
    from .streaming import StreamDetector

    detector = StreamDetector(**kwargs)
    try:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            detector.feed(chunk)
        return detector.finalize()
    finally:
        detector.close()


def is_binary(data: bytes | str | PathLike[str], **kwargs: Any) -> bool:
    """Return True only for positive binary evidence, not an unknown encoding."""
    kwargs["enable_fallback"] = False
    if isinstance(data, (str, PathLike)):
        return from_path(data, **kwargs).status == "binary"
    if isinstance(data, (bytes, bytearray)):
        return from_bytes(data, **kwargs).status == "binary"
    return from_fp(data, **kwargs).status == "binary"
