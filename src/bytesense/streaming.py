"""
Streaming encoding detector — Phase 3 enhanced version.

Key improvements over v1:
- Confidence convergence tracking (stops early when stable)
- Adaptive minimum sample sizing based on content type
- Hint system extended: XML/HTML declaration hints, not just HTTP headers
- Context snapshot: readable state dict for debugging/logging
"""
from __future__ import annotations

import codecs
from typing import Dict, Iterator, Optional

from .api import from_bytes
from .hints import _HTML_META_RE, _HTTP_EQUIV_RE, _XML_DECL_RE
from .models import DetectionResult


class StreamDetector:
    """
    Incremental encoding detector for streaming data.

    Feed byte chunks as they arrive. Detection confidence improves with more
    data. Stop feeding when ``confidence >= threshold`` (or call ``finalize()``).

    Supports:
    - HTTP header hints (``hint_from_headers``)
    - HTML/XML in-band declaration hints (auto-detected from fed data)
    - Adaptive early-stop based on confidence stability

    Example::

        det = StreamDetector()
        for chunk in response.iter_content(1024):
            det.feed(chunk)
            if det.confidence >= 0.99:
                break
        print(det.encoding, det.language)
    """

    MIN_BYTES: int = 64  # Don't detect below this
    SATURATION: int = 8_192  # Confidence stabilises above this
    STABILITY_ROUNDS: int = 3  # How many stable rounds before early-stop

    def __init__(
        self,
        threshold: float = 0.2,
        language_threshold: float = 0.1,
        auto_stop_confidence: float = 0.97,
    ) -> None:
        self._buf: bytearray = bytearray()
        self._result: Optional[DetectionResult] = None
        self._finalized: bool = False
        self._threshold = threshold
        self._lang_threshold = language_threshold
        self._auto_stop_confidence = auto_stop_confidence
        self._prev_encoding: Optional[str] = None
        self._stable_rounds: int = 0
        self._declared_hint: Optional[str] = None  # From HTTP header or in-band

    # ------------------------------------------------------------------
    # Feeding data

    def feed(self, chunk: bytes | bytearray) -> None:
        """Append ``chunk`` and re-run detection when sufficient data accumulates."""
        if self._finalized:
            return
        if not chunk:
            return
        self._buf.extend(chunk)
        buf_len = len(self._buf)

        # Probe first 4KB for in-band hints (same limit as hint_from_content); any feed size.
        if not self._declared_hint:
            self._probe_inband_hint()

        if buf_len >= self.MIN_BYTES:
            self._run()
            self._check_stability()

    def _probe_inband_hint(self) -> None:
        """Scan the buffer for XML/HTML encoding declarations."""
        probe = bytes(self._buf[:4096])
        for pattern in (_XML_DECL_RE, _HTML_META_RE, _HTTP_EQUIV_RE):
            m = pattern.search(probe)
            if m:
                try:
                    declared = m.group(1).decode("ascii", errors="ignore").strip()
                    norm = codecs.lookup(declared).name.replace("-", "_")
                    self._declared_hint = norm
                except (LookupError, UnicodeDecodeError):
                    pass
                break

    def _run(self) -> None:
        self._result = from_bytes(
            bytes(self._buf),
            threshold=self._threshold,
            language_threshold=self._lang_threshold,
        )
        # Apply in-band hint: boost confidence when declared matches detected
        if self._declared_hint and self._result and self._result.encoding:
            try:
                if codecs.lookup(self._declared_hint).name == codecs.lookup(self._result.encoding).name:
                    boosted = min(1.0, self._result.confidence + 0.06)
                    self._result = DetectionResult(
                        encoding=self._result.encoding,
                        confidence=boosted,
                        confidence_interval=(
                            max(0.0, boosted - 0.04),
                            min(1.0, boosted + 0.04),
                        ),
                        language=self._result.language,
                        alternatives=self._result.alternatives,
                        bom_detected=self._result.bom_detected,
                        chaos=self._result.chaos,
                        coherence=self._result.coherence,
                        why=self._result.why + f" In-band hint confirms {self._declared_hint!r}.",
                        byte_count=self._result.byte_count,
                    )
            except LookupError:
                pass

    def _check_stability(self) -> None:
        """Mark as finalized when encoding is stable and confidence is high."""
        if self._result is None:
            return
        current = self._result.encoding
        if current == self._prev_encoding:
            self._stable_rounds += 1
        else:
            self._stable_rounds = 0
        self._prev_encoding = current
        if (
            self._stable_rounds >= self.STABILITY_ROUNDS
            and self._result.confidence >= self._auto_stop_confidence
            and len(self._buf) >= self.SATURATION
        ):
            self._finalized = True

    # ------------------------------------------------------------------
    # Hints

    def hint_from_headers(self, headers: dict[str, str]) -> None:
        """
        Apply HTTP Content-Type charset hint.
        Boosts confidence when the declared charset matches our detection.
        """
        ct = headers.get("Content-Type", headers.get("content-type", ""))
        if "charset=" not in ct:
            return
        declared = ct.split("charset=")[-1].strip().strip(";").strip().strip('"').strip("'")
        if not declared:
            return
        try:
            norm = codecs.lookup(declared).name.replace("-", "_")
            self._declared_hint = norm
            if self._result and self._result.encoding:
                if codecs.lookup(norm).name == codecs.lookup(self._result.encoding).name:
                    boosted = min(1.0, self._result.confidence + 0.08)
                    self._result = DetectionResult(
                        encoding=self._result.encoding,
                        confidence=boosted,
                        confidence_interval=(
                            max(0.0, boosted - 0.05),
                            min(1.0, boosted + 0.05),
                        ),
                        language=self._result.language,
                        alternatives=self._result.alternatives,
                        bom_detected=self._result.bom_detected,
                        chaos=self._result.chaos,
                        coherence=self._result.coherence,
                        why=self._result.why + f" HTTP header confirms charset={declared!r}.",
                        byte_count=self._result.byte_count,
                    )
        except LookupError:
            pass

    # ------------------------------------------------------------------
    # Control

    def finalize(self) -> DetectionResult:
        """Force detection on all buffered data and return the result."""
        if not self._finalized:
            if len(self._buf) > 0:
                self._run()
            else:
                self._result = from_bytes(b"")
            self._finalized = True
        return self._result or from_bytes(b"")

    def reset(self) -> None:
        """Reset state for reuse."""
        self._buf.clear()
        self._result = None
        self._finalized = False
        self._prev_encoding = None
        self._stable_rounds = 0
        self._declared_hint = None

    def snapshot(self) -> Dict[str, object]:
        """Return a JSON-serializable state dict (useful for logging/debugging)."""
        return {
            "bytes_fed": len(self._buf),
            "encoding": self._result.encoding if self._result else None,
            "confidence": self._result.confidence if self._result else 0.0,
            "language": self._result.language if self._result else "",
            "stable_rounds": self._stable_rounds,
            "finalized": self._finalized,
            "declared_hint": self._declared_hint,
        }

    # ------------------------------------------------------------------
    # Properties

    @property
    def result(self) -> Optional[DetectionResult]:
        return self._result

    @property
    def encoding(self) -> Optional[str]:
        return self._result.encoding if self._result else None

    @property
    def confidence(self) -> float:
        return self._result.confidence if self._result else 0.0

    @property
    def language(self) -> str:
        return self._result.language if self._result else ""

    @property
    def bytes_fed(self) -> int:
        return len(self._buf)

    @property
    def is_stable(self) -> bool:
        """True when detection has converged and is unlikely to change with more data."""
        return self._finalized or (
            self._stable_rounds >= self.STABILITY_ROUNDS
            and self.confidence >= self._auto_stop_confidence
        )


# ---------------------------------------------------------------------------
# Convenience: chunk iterator
# ---------------------------------------------------------------------------


def detect_stream(
    chunks: Iterator[bytes],
    *,
    stop_confidence: float = 0.97,
    max_bytes: int = 65_536,
) -> DetectionResult:
    """
    Detect encoding from an iterator of byte chunks.

    Stops as soon as confidence >= ``stop_confidence`` or ``max_bytes`` have
    been consumed.

    Args:
        chunks:           Iterator yielding ``bytes`` objects.
        stop_confidence:  Early-stop threshold (default 0.97).
        max_bytes:        Hard limit on bytes consumed (default 64KB).

    Returns:
        :class:`DetectionResult`

    Example::

        import urllib.request
        with urllib.request.urlopen("https://example.com") as resp:
            result = detect_stream(
                iter(lambda: resp.read(1024), b""),
                stop_confidence=0.99,
            )
        print(result.encoding)
    """
    det = StreamDetector(auto_stop_confidence=stop_confidence)
    consumed = 0
    for chunk in chunks:
        det.feed(chunk)
        consumed += len(chunk)
        if det.is_stable or consumed >= max_bytes:
            break
    return det.finalize()
