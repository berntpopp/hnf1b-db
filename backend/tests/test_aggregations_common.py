"""Tests for the helpers in aggregations/common.py (Wave 3 additions).

This suite exercises all three row shapes the aggregation endpoints
produce, because a regression where ``calculate_percentages`` only
accepted two of them caused a live runtime ``TypeError`` on every
endpoint that uses ``result.mappings().all()``:

1. Plain ``dict`` rows.
2. SQLAlchemy ``RowMapping`` objects — a ``collections.abc.Mapping``
   subclass that is **not** a ``dict`` subclass and does **not** expose
   a ``._mapping`` attribute. Modelled below by ``_FakeRowMapping``,
   which inherits from ``collections.abc.Mapping`` directly.
3. SQLAlchemy ``Row`` objects — exposes a ``._mapping`` attribute
   pointing at the underlying RowMapping. Modelled by
   ``_FakeRow``.
"""

from collections.abc import Mapping

import pytest

from app.phenopackets.routers.aggregations.common import calculate_percentages


class _FakeRowMapping(Mapping):
    """Mimic a SQLAlchemy ``RowMapping`` from ``result.mappings().all()``.

    A RowMapping is a ``collections.abc.Mapping`` subclass that supports
    dict-style access but is **not** a ``dict`` subclass and does **not**
    expose a ``._mapping`` attribute (it IS the mapping).
    """

    def __init__(self, **fields):
        self._fields = dict(fields)

    def __getitem__(self, key):
        return self._fields[key]

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)


class _FakeRow:
    """Mimic a SQLAlchemy ``Row`` from ``result.fetchall()``.

    A Row is a sequence-like object that exposes its column data via a
    ``._mapping`` attribute of type RowMapping. It is NOT a Mapping
    subclass — it is tuple-like on the outside.
    """

    def __init__(self, **fields):
        self._mapping = _FakeRowMapping(**fields)


class TestCalculatePercentages:
    """Unit tests for the calculate_percentages helper."""

    def test_basic_percentages_with_dict_rows(self):
        """Plain dict rows — happy path, no weight on total."""
        rows = [{"count": 50}, {"count": 30}, {"count": 20}]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [50.0, 30.0, 20.0]

    def test_basic_percentages_with_rowmapping(self):
        """SQLAlchemy RowMapping (``result.mappings().all()``) is supported.

        This is the shape that broke the initial Wave 3 draft: a Mapping
        subclass that is not a dict and has no ._mapping attribute.
        """
        rows = [_FakeRowMapping(count=75), _FakeRowMapping(count=25)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [75.0, 25.0]

    def test_basic_percentages_with_row(self):
        """SQLAlchemy Row (``result.fetchall()``) via its ._mapping attribute."""
        rows = [_FakeRow(count=60), _FakeRow(count=40)]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [60.0, 40.0]

    def test_mixed_input_shapes(self):
        """Dicts, RowMapping, and Row can be interleaved in the same call."""
        rows = [
            {"count": 10},
            _FakeRowMapping(count=20),
            _FakeRow(count=70),
        ]
        result = calculate_percentages(rows, total=100)
        assert [r["percentage"] for r in result] == [10.0, 20.0, 70.0]

    def test_total_zero_returns_zero_percentages(self):
        """Total of zero must return 0.0 percentages (no ZeroDivisionError)."""
        rows = [{"count": 10}, {"count": 5}]
        result = calculate_percentages(rows, total=0)
        for row in result:
            # 0.0 (not int 0) so the percentage field stays a float in all cases
            assert row["percentage"] == 0.0
            assert isinstance(row["percentage"], float)

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

    def test_preserves_other_fields_from_rowmapping(self):
        """Non-count fields are preserved from SQLAlchemy RowMapping rows."""
        rows = [_FakeRowMapping(count=10, label="alpha")]
        result = calculate_percentages(rows, total=10)
        assert result[0]["label"] == "alpha"
        assert result[0]["percentage"] == 100.0

    def test_preserves_other_fields_from_row(self):
        """Non-count fields are preserved from SQLAlchemy Row (via ._mapping)."""
        rows = [_FakeRow(count=10, label="beta")]
        result = calculate_percentages(rows, total=10)
        assert result[0]["label"] == "beta"
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

    def test_missing_count_key_raises_keyerror(self):
        """Fail-loud: a row missing ``count_key`` raises KeyError.

        This guards against silent data corruption when a call-site has
        a typo (e.g. ``count_key="counnt"``). Previously the helper used
        ``.get(count_key, 0)`` which defaulted to 0 and emitted
        all-zero percentages to the API. Now the typo surfaces
        immediately at the first row.
        """
        rows = [{"present_count": 10, "label": "a"}]
        with pytest.raises(KeyError, match="missing count_key 'count'"):
            calculate_percentages(rows, total=100)

    def test_missing_custom_count_key_raises_keyerror(self):
        """The fail-loud guard applies to any ``count_key``, not just ``count``."""
        rows = [{"count": 10, "label": "a"}]
        with pytest.raises(KeyError, match="missing count_key 'present_count'"):
            calculate_percentages(rows, total=100, count_key="present_count")

    def test_missing_count_key_on_rowmapping_raises(self):
        """The same fail-loud guard applies to SQLAlchemy RowMapping rows."""
        rows = [_FakeRowMapping(label="no_count_here")]
        with pytest.raises(KeyError, match="missing count_key"):
            calculate_percentages(rows, total=100)
