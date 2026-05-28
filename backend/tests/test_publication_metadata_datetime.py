"""Regression tests for timezone handling in ``app/publications/service.py``.

Background
----------
``GET /api/v2/publications/{pmid}/metadata`` returned **HTTP 500** for every
publication that already had a cached row, while non-existent PMIDs returned
200. The cause was a naive/aware datetime subtraction in the cache-hit log
line::

    "cache_age_days": (datetime.now() - cached["fetched_at"]).days

``publication_metadata.fetched_at`` is ``TIMESTAMPTZ`` (migration
``a7f1c2d9e5b3``) so it reads back timezone-aware, and subtracting it from a
naive ``datetime.now()`` raises::

    TypeError: can't subtract offset-naive and offset-aware datetimes

The fix introduces the tz-safe ``_cache_age_days`` helper and stores
``fetched_at`` as ``datetime.now(timezone.utc)``. These tests pin both the
helper's behaviour and the end-to-end cache-hit path so the 500 cannot return.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.patterns import normalize_pmid
from app.publications.service import (
    _cache_age_days,
    get_publication_metadata,
)

# ---------------------------------------------------------------------------
# Unit tests for the pure helper (no database required)
# ---------------------------------------------------------------------------


class TestCacheAgeDays:
    """``_cache_age_days`` must never raise on real (tz-aware) cache values."""

    def test_aware_fetched_at_returns_whole_days(self):
        """A tz-aware timestamp 3 days ago yields 3 — and does not raise.

        This is the exact shape PostgreSQL hands back for a ``TIMESTAMPTZ``
        column and is what triggered the production ``TypeError``.
        """
        fetched_at = datetime.now(timezone.utc) - timedelta(days=3, hours=1)
        assert _cache_age_days(fetched_at) == 3

    def test_naive_fetched_at_is_treated_as_utc(self):
        """A naive timestamp is assumed UTC instead of raising.

        Covers legacy rows written before the fix and SQLite-backed contexts
        where the driver returns naive datetimes.
        """
        fetched_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=10, hours=1
        )
        assert _cache_age_days(fetched_at) == 10

    def test_just_fetched_is_zero_days(self):
        """A timestamp from moments ago is 0 days old."""
        assert _cache_age_days(datetime.now(timezone.utc)) == 0


# ---------------------------------------------------------------------------
# End-to-end regression: a cache hit must not 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_with_tzaware_fetched_at_does_not_raise(db_session):
    """``get_publication_metadata`` returns the cached row without crashing.

    Seeds a ``publication_metadata`` row with a tz-aware ``fetched_at`` (as the
    real schema stores it), then exercises the cache-hit branch that previously
    raised ``TypeError`` and surfaced as HTTP 500.
    """
    pmid = normalize_pmid("31198537")
    await db_session.execute(
        text("""
            INSERT INTO publication_metadata (
                pmid, title, authors, journal, year, doi, fetched_at, fetched_by
            )
            VALUES (
                :pmid, :title, CAST(:authors AS JSONB), :journal, :year,
                :doi, :fetched_at, 'test'
            )
            ON CONFLICT (pmid) DO UPDATE SET fetched_at = EXCLUDED.fetched_at
        """),
        {
            "pmid": pmid,
            "title": "Variable phenotype in HNF1B mutations",
            "authors": __import__("json").dumps([{"name": "Madariaga L"}]),
            "journal": "Clinical kidney journal",
            "year": 2019,
            "doi": "10.1093/ckj/sfy102",
            # tz-aware UTC, exactly as a TIMESTAMPTZ column round-trips it.
            "fetched_at": datetime.now(timezone.utc) - timedelta(days=5),
        },
    )
    await db_session.commit()

    result = await get_publication_metadata(pmid, db_session, fetched_by="api")

    assert result["pmid"] == pmid
    assert result["title"] == "Variable phenotype in HNF1B mutations"
