"""Tests for mojibake repair engine."""
from __future__ import annotations

from bytesense import RepairResult, is_mojibake, repair, repair_bytes


class TestRepair:
    def test_clean_text_unchanged(self) -> None:
        text = "Hello, world! Normal text."
        result = repair(text)
        assert result.improved is False
        assert str(result) == text

    def test_classic_utf8_latin1_mojibake(self) -> None:
        """UTF-8 read as Latin-1: 'été' becomes 'Ã©tÃ©'"""
        original = "été"
        garbled = original.encode("utf-8").decode("latin-1")
        result = repair(garbled)
        assert result.improved is True
        assert result.repaired == original
        assert result.chain == ("latin_1", "utf_8")

    def test_cyrillic_mojibake(self) -> None:
        """Cyrillic UTF-8 read as Latin-1."""
        original = "Привет мир"
        garbled = original.encode("utf-8").decode("latin-1")
        result = repair(garbled)
        assert result.improved is True
        assert result.repaired == original

    def test_result_dataclass(self) -> None:
        garbled = "Ã©tÃ©"
        result = repair(garbled)
        assert isinstance(result, RepairResult)
        assert hasattr(result, "original")
        assert hasattr(result, "repaired")
        assert hasattr(result, "improved")
        assert hasattr(result, "chain")
        assert hasattr(result, "original_mess")
        assert hasattr(result, "repaired_mess")
        assert hasattr(result, "iterations")

    def test_improvement_property(self) -> None:
        garbled = "Ã©tÃ©"
        result = repair(garbled)
        if result.improved:
            assert result.improvement >= 0

    def test_repair_bytes_auto_detect(self) -> None:
        original = "café résumé"
        garbled_bytes = original.encode("utf-8")
        result = repair_bytes(garbled_bytes)
        assert isinstance(result, RepairResult)

    def test_is_mojibake_true(self) -> None:
        garbled = "Ã©tÃ©" * 10
        assert is_mojibake(garbled) is True

    def test_is_mojibake_false_for_clean(self) -> None:
        clean = "Hello, world! Normal ASCII text."
        assert is_mojibake(clean) is False

    def test_empty_string(self) -> None:
        result = repair("")
        assert result.improved is False
        assert result.repaired == ""

    def test_max_iterations_1(self) -> None:
        """Single iteration should not apply double-step repair."""
        garbled = "été".encode("utf-8").decode("latin-1")
        result = repair(garbled, max_iterations=1)
        assert isinstance(result, RepairResult)
        if result.improved:
            assert result.iterations == 1

    def test_str_representation(self) -> None:
        garbled = "Ã©tÃ©"
        result = repair(garbled)
        if result.improved:
            assert str(result) == result.repaired
        else:
            assert str(result) == result.original
