from __future__ import annotations

from bytesense.mess import mess_ratio, sliding_window_mess


def test_sliding_window_long_text() -> None:
    text = "The quick brown fox jumps over the lazy dog. " * 200
    mean, exceeded = sliding_window_mess(text, window_size=256, threshold=0.99)
    assert 0.0 <= mean <= 1.0
    assert isinstance(exceeded, bool)


def test_mess_ratio_empty() -> None:
    assert mess_ratio("") == 0.0
