"""Tests for the helpers in aggregations/common.py (Wave 3 additions)."""

import pytest

from app.phenopackets.routers.aggregations.common import calculate_percentages


class _FakeMappingRow:
    """Mimic a SQLAlchemy Row that exposes ._mapping and __getitem__."""

    def __init__(self, **fields):
        self._mapping = fields

    def __getitem__(self, key):
        return self._mapping[key]


class TestCalculatePercentages:
    """Unit tests for the calculate_percentages helper."""

    def test_basic_percentages_with_dict_rows(self):
        """Plain dict rows — happy path, no weight on total."""
        rows = [{"count": 50}, {"count": 30}, {"count": 20}]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [50.0, 30.0, 20.0]

    def test_basic_percentages_with_mapping_rows(self):
        """SQLAlchemy-style rows exposing ``_mapping`` are supported."""
        rows = [_FakeMappingRow(count=75), _FakeMappingRow(count=25)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [75.0, 25.0]

    def test_mixed_input_shapes(self):
        """Dicts and mapping rows can be interleaved in the same call."""
        rows = [{"count": 40}, _FakeMappingRow(count=60)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [40.0, 60.0]

    def test_total_zero_returns_zero_percentages(self):
        """Total of zero must return 0 percentages (no ZeroDivisionError)."""
        rows = [{"count": 10}, {"count": 5}]
        result = calculate_percentages(rows, total=0)
        for row in result:
            assert row["percentage"] == 0

    def test_preserves_other_fields(self):
        """Non-count fields are preserved from dict rows."""
        rows = [
            {"count": 10, "label": "alpha", "group": "a"},
            {"count": 90, "label": "beta", "group": "b"},
        ]
        result = calculate_percentages(rows, total=100)
        assert result[0]["label"] == "alpha"
        assert result[0]["group"] == "a"
        assert result[1]["label"] == "beta"
        assert result[1]["group"] == "b"

    def test_preserves_other_fields_from_mapping_row(self):
        """Non-count fields are preserved from SQLAlchemy mapping rows."""
        rows = [_FakeMappingRow(count=10, label="alpha")]
        result = calculate_percentages(rows, total=10)
        assert result[0]["label"] == "alpha"
        assert result[0]["percentage"] == 100.0

    def test_does_not_mutate_dict_input(self):
        """The input row dicts are not mutated in place."""
        rows = [{"count": 10}]
        calculate_percentages(rows, total=100)
        assert "percentage" not in rows[0]

    def test_empty_input(self):
        """Empty input returns empty output."""
        assert calculate_percentages([], total=100) == []

    def test_custom_count_key(self):
        """A custom count_key (e.g. features.py's present_count) is respected."""
        rows = [{"present_count": 40, "label": "a"}]
        result = calculate_percentages(rows, total=100, count_key="present_count")
        assert result[0]["percentage"] == 40.0
        assert result[0]["present_count"] == 40

    def test_rejects_unknown_row_shape(self):
        """Non-dict, non-mapping rows should raise, not silently hoover attrs."""

        class Opaque:
            count = 10

        with pytest.raises((TypeError, AttributeError)):
            calculate_percentages([Opaque()], total=100)
