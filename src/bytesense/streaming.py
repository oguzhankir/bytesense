from __future__ import annotations

from typing import Optional

from .api import from_bytes
from .models import DetectionResult


class StreamDetector:
    """
    Incremental encoding detector for streaming data.

    Feed byte chunks as they arrive.  Detection confidence increases with
    more data.  Stop early once confidence is sufficient.

    Example::

        detector = StreamDetector()
        for chunk in response.iter_content(1024):
            detector.feed(chunk)
            if detector.confidence >= 0.99:
                break
        print(detector.encoding)   # e.g. "utf_8"
        print(detector.language)   # e.g. "French"
    """

    MIN_BYTES: int = 64  # Do not attempt detection below this
    SATURATION: int = 8192  # After this many bytes, confidence stabilises

    def __init__(
        self,
        threshold: float = 0.2,
        language_threshold: float = 0.1,
    ) -> None:
        self._buf: bytearray = bytearray()
        self._result: Optional[DetectionResult] = None
        self._finalized: bool = False
        self._threshold = threshold
        self._lang_threshold = language_threshold

    # ------------------------------------------------------------------

    def feed(self, chunk: bytes | bytearray) -> None:
        """Append `chunk` and re-run detection if enough data is available."""
        if self._finalized:
            return
        self._buf.extend(chunk)
        if len(self._buf) >= self.MIN_BYTES:
            self._run()
        if len(self._buf) >= self.SATURATION and self._result is not None:
            if self._result.confidence >= 0.95:
                self._finalized = True

    def _run(self) -> None:
        self._result = from_bytes(
            bytes(self._buf),
            threshold=self._threshold,
            language_threshold=self._lang_threshold,
        )

    def finalize(self) -> DetectionResult:
        """Force detection on all buffered data and return the result."""
        if not self._finalized:
            self._run()
            self._finalized = True
        if self._result is None:
            # Empty buffer edge-case
            self._result = from_bytes(b"")
        return self._result

    def hint_from_headers(self, headers: dict[str, str]) -> None:
        """
        Adjust confidence if HTTP headers declare a charset.
        Call before or after feeding data — either works.
        """
        ct = headers.get("Content-Type", headers.get("content-type", ""))
        if "charset=" not in ct:
            return
        declared = ct.split("charset=")[-1].strip().strip(";").strip().strip('"').strip("'")
        if not declared or self._result is None:
            return
        try:
            import codecs

            norm = codecs.lookup(declared).name.replace("-", "_")
            if norm == self._result.encoding:
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

    def reset(self) -> None:
        """Reset state for reuse."""
        self._buf.clear()
        self._result = None
        self._finalized = False

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
