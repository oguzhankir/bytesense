from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class EncodingAlternative:
    """A plausible alternative encoding that did not win."""

    encoding: str
    confidence: float
    language: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "encoding": self.encoding,
            "confidence": self.confidence,
            "language": self.language,
        }


@dataclass
class DetectionResult:
    """
    Full result object returned by all bytesense detection functions.

    Attributes:
        encoding:            IANA encoding name, e.g. ``"utf_8"``, ``"cp1252"``.
                             ``None`` if detection failed completely.
        confidence:          Float 0.0–1.0.  1.0 = certain (BOM found or pure ASCII).
        confidence_interval: (low, high) 95% CI tuple.
        language:            Human-readable language name, e.g. ``"French"``.
                             Empty string if not determined.
        alternatives:        Other plausible encodings, sorted by confidence descending.
        bom_detected:        ``True`` if a BOM/SIG was found.
        chaos:               Mess ratio of the winning encoding.  0.0 = clean text.
        coherence:           Language coherence score.  0.0 = no language match.
        why:                 Human-readable explanation of the detection decision.
        byte_count:          Length of the input byte sequence.
    """

    encoding: Optional[str]
    confidence: float
    confidence_interval: Tuple[float, float]
    language: str
    alternatives: List[EncodingAlternative]
    bom_detected: bool
    chaos: float
    coherence: float
    why: str
    byte_count: int

    # ------------------------------------------------------------------
    # chardet / charset-normalizer compatibility helpers
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return (
            f"DetectionResult(encoding={self.encoding!r}, "
            f"confidence={self.confidence:.3f}, "
            f"language={self.language!r})"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __bool__(self) -> bool:
        return self.encoding is not None

    def to_dict(self) -> Dict[str, object]:
        return {
            "encoding": self.encoding,
            "confidence": self.confidence,
            "confidence_interval": list(self.confidence_interval),
            "language": self.language,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "bom_detected": self.bom_detected,
            "chaos": self.chaos,
            "coherence": self.coherence,
            "why": self.why,
            "byte_count": self.byte_count,
        }
