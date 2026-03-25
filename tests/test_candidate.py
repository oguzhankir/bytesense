from __future__ import annotations

from bytesense.candidate import CandidateSelector


def test_ascii_candidates() -> None:
    sel = CandidateSelector(b"hello")
    assert sel.get_candidates() == ["ascii", "utf_8"]


def test_bom_utf8_sig() -> None:
    sel = CandidateSelector(b"\xef\xbb\xbf" + b"x")
    assert sel.get_candidates()[0] == "utf_8_sig"
