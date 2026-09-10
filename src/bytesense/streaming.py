"""Bounded-memory streaming with explicit finalization and full decode validation."""

from __future__ import annotations

import codecs
import tempfile
from dataclasses import replace
from typing import Any, Iterator, Optional

from .api import (
    _HIGH_BYTE,
    _allowed,
    _binary,
    _bom_codec,
    _filters,
    _from_sample,
    _result,
    _transport_encoding,
    from_bytes,
)
from .fingerprint import detect_null_pattern
from .hints import hint_from_content, hint_from_http_headers
from .models import DetectionResult


class StreamDetector:
    """Consume every fed byte; spool beyond ``memory_limit`` to a local temp file.

    Preview scoring runs at exponentially increasing checkpoints, then stops
    after the sample fills. ``is_stable`` describes a guess, never end-of-input.
    ``finalize`` strictly validates the chosen codec over the complete stream.
    Feeding after finalization raises instead of silently dropping data.
    Use a context manager or ``close()`` to release an unfinished stream.
    """

    MIN_BYTES = 64
    SATURATION = 8192
    STABILITY_ROUNDS = 2

    def __init__(
        self,
        threshold: float = 0.2,
        language_threshold: float = 0.1,
        auto_stop_confidence: float = 0.97,
        *,
        memory_limit: int = 1_048_576,
        **kwargs: Any,
    ) -> None:
        if not isinstance(memory_limit, int) or isinstance(memory_limit, bool) or memory_limit < 64:
            raise ValueError("memory_limit must be an integer of at least 64 bytes")
        if not 0.0 <= auto_stop_confidence <= 1.0:
            raise ValueError("auto_stop_confidence must be between 0 and 1")
        self._options = dict(kwargs, threshold=threshold, language_threshold=language_threshold)
        from_bytes(b"", **self._options)  # Validate configuration before accepting any data.
        self._memory_limit = memory_limit
        self._auto_stop_confidence = auto_stop_confidence
        self._sample_size = kwargs.get("sample_size", 4096)
        self._spool = tempfile.SpooledTemporaryFile(max_size=memory_limit, mode="w+b")
        self._buf = bytearray()
        self._late_sample = bytearray()
        self._tail = b""
        self._bytes_fed = 0
        self._ascii = True
        self._escape = False
        self._next_probe = self.MIN_BYTES
        self._result: Optional[DetectionResult] = None
        self._finalized = False
        self._stable_rounds = 0
        self._prev_encoding: Optional[str] = None
        self._declared_hint: Optional[str] = None

    def feed(self, chunk: bytes | bytearray) -> None:
        if self._finalized or self._spool.closed:
            raise RuntimeError("stream is closed; call reset() before feeding more data")
        if not isinstance(chunk, (bytes, bytearray)):
            raise TypeError("stream chunks must be bytes or bytearray")
        if not chunk:
            return
        if self._bytes_fed + len(chunk) > self._memory_limit:
            self._spool.rollover()
        self._spool.write(chunk)
        self._bytes_fed += len(chunk)
        ascii_chunk = chunk.isascii()
        if self._late_sample and len(self._late_sample) < self._sample_size:
            self._late_sample.extend(chunk[: self._sample_size - len(self._late_sample)])
        # Preserve a continuous informative window, independent of chunk sizes.
        if (self._ascii and not ascii_chunk) or (not self._escape and b"\x1b" in chunk):
            signal = _HIGH_BYTE.search(chunk)
            if (
                signal is not None
                and self._bytes_fed - len(chunk) + signal.start() > self._sample_size // 4
            ):
                start = signal.start() - 64
                probe = (
                    self._tail[start:] + bytes(chunk[: self._sample_size])
                    if start < 0
                    else bytes(chunk[start : start + self._sample_size])
                )
                self._late_sample = bytearray(probe[: self._sample_size])
        self._tail = bytes(chunk[-64:]) if len(chunk) >= 64 else (self._tail + bytes(chunk))[-64:]
        self._ascii = self._ascii and ascii_chunk
        self._escape = self._escape or b"\x1b" in chunk
        if len(self._buf) < self._sample_size:
            self._buf.extend(chunk[: self._sample_size - len(self._buf)])
        if not self._declared_hint and self._options.get("use_hints", True):
            self._declared_hint = hint_from_content(bytes(self._buf))
        if self._bytes_fed >= self._next_probe and self._next_probe <= self._sample_size:
            self._run()
            while self._next_probe <= self._bytes_fed:
                self._next_probe *= 4

    def _run(self) -> None:
        probe = bytes(self._late_sample or self._buf)
        r = from_bytes(probe, **self._options)
        self._result = replace(r, byte_count=self._bytes_fed, complete=False, bytes_validated=0)
        if r.encoding == self._prev_encoding:
            self._stable_rounds += 1
        else:
            self._stable_rounds = 0
        self._prev_encoding = r.encoding

    def hint_from_headers(self, headers: dict[str, str]) -> None:
        if self._finalized:
            raise RuntimeError("cannot change hints on a finalized stream")
        hint = hint_from_http_headers(headers)
        if hint:
            self._declared_hint = hint

    def _validate(self, encoding: str) -> tuple[bool, bytes]:
        self._spool.seek(0)
        try:
            decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        except LookupError:
            return False, b""
        chunk = b""
        try:
            while True:
                chunk = self._spool.read(65536)
                if not chunk:
                    break
                decoder.decode(chunk, final=False)
            decoder.decode(b"", final=True)
            return True, b""
        except UnicodeDecodeError as exc:
            start = max(0, exc.start - 64)
            return False, chunk[start : start + self._sample_size]
        except UnicodeError:
            return False, chunk[: self._sample_size]

    def finalize(self) -> DetectionResult:
        if self._finalized:
            assert self._result is not None
            return self._result
        if self._spool.closed:
            raise RuntimeError("stream is closed")
        try:
            self._result = self._finish()
            self._finalized = True
            return self._result
        finally:
            self._spool.close()

    def _finish(self) -> DetectionResult:
        prefix = bytes(self._buf)
        n = self._bytes_fed
        if n <= self._sample_size:
            options = dict(self._options)
            if self._declared_hint and not options.get("encoding_hint"):
                options["encoding_hint"] = self._declared_hint
            return from_bytes(prefix, **options)
        include, exclude = _filters(
            self._options.get("cp_isolation"), self._options.get("cp_exclusion")
        )
        minimum = self._options.get("min_confidence", 0.0)
        if include == []:
            return _result(None, n, "No encodings allowed.", examined=len(prefix))
        bom = _bom_codec(prefix, include, exclude)
        if bom:
            valid, _ = self._validate(bom)
            if valid:
                return replace(
                    _result(bom, n, "BOM; complete stream validated.", 1.0, examined=len(prefix)),
                    bom_detected=True,
                )
            return _result(
                None,
                n,
                "Invalid complete stream under its declared BOM.",
                status="invalid",
                examined=len(prefix),
            )
        if _binary(prefix):
            return _result(
                None,
                n,
                "Binary signature or excessive control bytes.",
                status="binary",
                examined=len(prefix),
            )
        transport = _transport_encoding(prefix) if self._ascii else None
        if transport and _allowed(transport, include, exclude):
            valid, _ = self._validate(transport)
            if valid and minimum <= 0.85:
                return _result(
                    transport,
                    n,
                    "7-bit shift syntax; complete stream validated.",
                    0.85,
                    "ambiguous",
                    len(prefix),
                )
        shape = detect_null_pattern(prefix)
        if shape and _allowed(shape, include, exclude):
            valid, _ = self._validate(shape)
            if valid:
                return (
                    _result(
                        shape,
                        n,
                        "Unicode byte-lane pattern; complete stream validated.",
                        0.9,
                        examined=len(prefix),
                    )
                    if minimum <= 0.9
                    else _result(None, n, "Below minimum confidence.", examined=len(prefix))
                )
        if not shape and not self._escape:
            if self._ascii and _allowed("ascii", include, exclude):
                return _result("ascii", n, "All stream bytes are ASCII text.", 1.0, examined=n)
            if _allowed("utf_8", include, exclude):
                valid, _ = self._validate("utf_8")
                if valid:
                    r = _result("utf_8", n, "Complete stream validated as UTF-8.", 0.99, examined=n)
                    if self._options.get("include_language"):
                        from .coherence import detect_language

                        decoded = codecs.getincrementaldecoder("utf_8")().decode(
                            prefix, final=False
                        )
                        langs = detect_language(
                            decoded, threshold=self._options["language_threshold"]
                        )
                        if langs:
                            r = replace(r, language=langs[0][0], coherence=round(langs[0][1], 4))
                    return (
                        r
                        if r.confidence >= minimum
                        else _result(None, n, "Below minimum confidence.", examined=len(prefix))
                    )
        probe = bytes(self._late_sample) or prefix
        options = {key: self._options[key] for key in ("threshold", "language_threshold")}
        r = _from_sample(
            probe, cp_isolation=include, cp_exclusion=exclude, enable_fallback=False, **options
        )
        candidates = ([r.encoding] if r.encoding else []) + [alt.encoding for alt in r.alternatives]
        hint = self._options.get("encoding_hint") or self._declared_hint
        if hint:
            from .api import _codec

            try:
                hint = _codec(hint)
            except (LookupError, TypeError):
                hint = None
            if hint and _allowed(hint, include, exclude):
                candidates.insert(0, hint)
        if self._options.get("enable_fallback", True) and include:
            candidates.extend(include)
        tried: set[str] = set()
        examined = len(probe)
        for enc in candidates:
            if enc in tried or not _allowed(enc, include, exclude):
                continue
            tried.add(enc)
            valid, failure = self._validate(enc)
            if valid:
                confidence = 0.95 if enc == hint else r.confidence if enc == r.encoding else 0.1
                if confidence < minimum:
                    continue
                if self._options.get("include_language"):
                    from .coherence import detect_language

                    decoded = codecs.getincrementaldecoder(enc)().decode(probe, final=False)
                    langs = detect_language(decoded, threshold=self._options["language_threshold"])
                    if langs:
                        r = replace(r, language=langs[0][0])
                return replace(
                    r,
                    encoding=enc,
                    confidence=confidence,
                    byte_count=n,
                    bytes_examined=min(n, examined),
                    bytes_validated=n,
                    complete=True,
                    status="ambiguous" if r.alternatives else "matched",
                    chaos=r.chaos if enc == r.encoding else 0.0,
                    coherence=r.coherence if enc == r.encoding else 0.0,
                    alternatives=[a for a in r.alternatives if a.encoding != enc],
                    language=r.language
                    if self._options.get("include_language") and enc == r.encoding
                    else "",
                    why=(r.why if enc == r.encoding else f"Selected validated alternative {enc}.")
                    + " Complete stream validated."
                    + (f" Hint: {hint}." if hint else ""),
                )
            if failure and len(tried) <= 4:
                alternate = _from_sample(
                    failure,
                    cp_isolation=include,
                    cp_exclusion=list(set(exclude) | tried),
                    enable_fallback=False,
                    **options,
                )
                examined += len(failure)
                if alternate.encoding:
                    candidates.append(alternate.encoding)
        return _result(
            None,
            n,
            "No permitted encoding validates the complete stream.",
            examined=min(n, examined),
        )

    def close(self) -> None:
        self._spool.close()

    def reset(self) -> None:
        self.close()
        StreamDetector.__init__(
            self,
            auto_stop_confidence=self._auto_stop_confidence,
            memory_limit=self._memory_limit,
            **self._options,
        )

    def __enter__(self) -> StreamDetector:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def snapshot(self) -> dict[str, object]:
        return {
            "bytes_fed": self.bytes_fed,
            "buffered_bytes": len(self._buf),
            "encoding": self.encoding,
            "confidence": self.confidence,
            "language": self.language,
            "stable_rounds": self._stable_rounds,
            "finalized": self._finalized,
            "declared_hint": self._declared_hint,
        }

    @property
    def result(self) -> Optional[DetectionResult]:
        return self._result

    @property
    def encoding(self) -> Optional[str]:
        return self._result.encoding if self._result is not None else None

    @property
    def confidence(self) -> float:
        return self._result.confidence if self._result is not None else 0.0

    @property
    def language(self) -> str:
        return self._result.language if self._result is not None else ""

    @property
    def bytes_fed(self) -> int:
        return self._bytes_fed

    @property
    def is_stable(self) -> bool:
        return self._finalized or (
            self._stable_rounds >= self.STABILITY_ROUNDS
            and self.confidence >= self._auto_stop_confidence
        )


def detect_stream(
    chunks: Iterator[bytes],
    *,
    stop_confidence: float = 0.97,
    max_bytes: Optional[int] = None,
    early_stop: bool = False,
    **kwargs: Any,
) -> DetectionResult:
    """Consume to EOF by default. Explicit budgets/early stopping mark incomplete results.

    An oversized yielded chunk is sliced before analysis. Its unused remainder
    has already been yielded by the source and cannot be restored by this API.
    """
    if max_bytes is not None and (
        not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0
    ):
        raise ValueError("max_bytes must be a positive integer or None")
    with StreamDetector(auto_stop_confidence=stop_confidence, **kwargs) as detector:
        limited = False
        for chunk in chunks:
            if not isinstance(chunk, (bytes, bytearray)):
                raise TypeError("stream chunks must be bytes or bytearray")
            if max_bytes is not None:
                chunk = chunk[: max_bytes - detector.bytes_fed]
            detector.feed(chunk)
            if (max_bytes is not None and detector.bytes_fed >= max_bytes) or (
                early_stop and detector.is_stable
            ):
                limited = True
                break
        r = detector.finalize()
        return (
            replace(r, complete=False, why=r.why + " Input stopped before confirmed EOF.")
            if limited
            else r
        )
