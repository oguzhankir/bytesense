from __future__ import annotations

from bytesense.coherence import coherence_score, detect_language


def test_coherence_english() -> None:
    s = coherence_score(
        "The quick brown fox jumps over the lazy dog. " * 5,
        "English",
    )
    assert s > 0.0


def test_detect_language_french() -> None:
    text = (
        "Bonjour le monde, comment allez-vous aujourd'hui? "
        "Le français est une langue magnifique avec des accents: é à è ç ô."
    ) * 8
    langs = detect_language(text, candidates=["French"], threshold=0.05)
    assert langs
    assert langs[0][0] == "French"
