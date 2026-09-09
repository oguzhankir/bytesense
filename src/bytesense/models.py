from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_SLOTS_KW = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(frozen=True, **_SLOTS_KW)
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


@dataclass(**_SLOTS_KW)
class DetectionResult:
    """
    Full result object returned by all bytesense detection functions.

    Attributes:
        encoding:            Python codec name, e.g. ``"utf_8"``, ``"cp1252"``.
                             ``None`` if detection failed completely.
        confidence:          Heuristic evidence score in 0.0–1.0, not a probability.
        confidence_interval: Always None; heuristic scores have no statistical CI.
        language:            Human-readable language name, e.g. ``"French"``.
                             Empty string if not determined.
        alternatives:        Other plausible encodings, sorted by confidence descending.
        bom_detected:        ``True`` if a BOM/SIG was found.
        chaos:               Control-character ratio in the scoring sample.
        coherence:           Character-pair support (legacy) or optional language support (UTF-8).
        why:                 Human-readable explanation of the detection decision.
        byte_count:          Number of bytes accepted by this call or stream.
        bytes_examined:      Bytes used for scoring or a direct fast-path decision.
        bytes_validated:     Bytes strictly validated under the returned codec.
        complete:            The input ended; False for previews/explicit budgets.
        status:              matched, ambiguous, unknown, binary, or invalid.
    """

    encoding: Optional[str]
    confidence: float
    confidence_interval: Optional[Tuple[float, float]]
    language: str
    alternatives: List[EncodingAlternative]
    bom_detected: bool
    chaos: float
    coherence: float
    why: str
    byte_count: int
    bytes_examined: int = 0
    bytes_validated: int = 0
    complete: bool = False
    status: str = "unknown"

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
            "confidence_interval": None,
            "language": self.language,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "bom_detected": self.bom_detected,
            "chaos": self.chaos,
            "coherence": self.coherence,
            "why": self.why,
            "byte_count": self.byte_count,
            "bytes_examined": self.bytes_examined,
            "bytes_validated": self.bytes_validated,
            "complete": self.complete,
            "status": self.status,
        }
