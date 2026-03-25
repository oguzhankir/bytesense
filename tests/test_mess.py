from __future__ import annotations

from bytesense.mess import mess_ratio, sliding_window_mess


def test_mess_clean_ascii() -> None:
    assert mess_ratio("Hello world this is clean text.") < 0.2


def test_sliding_window_short() -> None:
    r, ex = sliding_window_mess("short")
    assert isinstance(r, float)
    assert isinstance(ex, bool)
