"""Unit tests for the token-bucket rate limiter (Task 3b).

All tests are pure in-process and require no Redis or external services.
The clock is injected to ensure fully deterministic behaviour.
"""
from __future__ import annotations

import pytest

from hnf1b_mcp.server_ratelimit import (
    HEAVY_TOOLS,
    RateLimiter,
    _TokenBucket,
    get_limiter,
    set_limiter,
)

# ---------------------------------------------------------------------------
# _TokenBucket unit tests
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_full_bucket_allows_first_request(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=5.0, rate=1.0, clock=lambda: clock_val[0])
        assert bucket.consume() is True

    def test_empty_bucket_blocks(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=3.0, rate=1.0, clock=lambda: clock_val[0])
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        # Fourth request — bucket exhausted.
        assert bucket.consume() is False

    def test_refill_over_time(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=2.0, rate=2.0, clock=lambda: clock_val[0])
        # Drain the bucket.
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False
        # Advance clock by 1 second: should get 2 new tokens (at 2 rps).
        clock_val[0] = 1.0
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False

    def test_refill_capped_at_capacity(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=5.0, rate=5.0, clock=lambda: clock_val[0])
        # Drain partially.
        assert bucket.consume() is True
        # Advance far into the future: bucket should be capped at capacity.
        clock_val[0] = 100.0
        assert bucket.available == pytest.approx(5.0)

    def test_partial_refill(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=10.0, rate=1.0, clock=lambda: clock_val[0])
        # Consume all 10 tokens.
        for _ in range(10):
            assert bucket.consume() is True
        assert bucket.consume() is False
        # Advance 5 seconds — get 5 tokens back.
        clock_val[0] = 5.0
        for _ in range(5):
            assert bucket.consume() is True
        assert bucket.consume() is False

    def test_available_property(self):
        clock_val = [0.0]
        bucket = _TokenBucket(capacity=4.0, rate=2.0, clock=lambda: clock_val[0])
        bucket.consume()
        bucket.consume()
        assert bucket.available == pytest.approx(2.0)
        clock_val[0] = 1.0
        # After 1 second at rate=2: 2 existing + 2 refilled = 4, capped at 4.
        assert bucket.available == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# RateLimiter — global bucket
# ---------------------------------------------------------------------------

class TestRateLimiterGlobal:
    def test_allow_within_global_budget(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=10.0,
            tool_capacity=100.0,
            heavy_tool_capacity=100.0,
            clock=lambda: clock_val[0],
        )
        # Should allow at least 10 calls (capacity = 2×rps = 20).
        for _ in range(10):
            assert limiter.allow("hnf1b_search") is True

    def test_blocks_past_global_budget(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=5.0,
            # Capacity = 2×5 = 10 tokens.
            tool_capacity=100.0,
            heavy_tool_capacity=100.0,
            clock=lambda: clock_val[0],
        )
        # Drain 10 global tokens (capacity = 10).
        allowed = sum(1 for _ in range(20) if limiter.allow("hnf1b_search"))
        assert allowed == 10  # global capacity = 2×rps = 10

    def test_global_refills_over_time(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=2.0,
            # capacity = 2×2 = 4 tokens.
            tool_capacity=100.0,
            heavy_tool_capacity=100.0,
            clock=lambda: clock_val[0],
        )
        # Drain global bucket (4 tokens).
        while limiter.allow("hnf1b_search"):
            pass
        # After 2 seconds at 2 rps → 4 tokens back.
        clock_val[0] = 2.0
        assert limiter.allow("hnf1b_search") is True


# ---------------------------------------------------------------------------
# RateLimiter — per-tool budgets
# ---------------------------------------------------------------------------

class TestRateLimiterPerTool:
    def test_per_tool_blocks_independently(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=1000.0,   # large — never the bottleneck here
            tool_capacity=3.0,
            heavy_tool_capacity=3.0,
            clock=lambda: clock_val[0],
        )
        # Drain the per-tool bucket for search (3 tokens).
        assert limiter.allow("hnf1b_search") is True
        assert limiter.allow("hnf1b_search") is True
        assert limiter.allow("hnf1b_search") is True
        assert limiter.allow("hnf1b_search") is False
        # A different tool is unaffected.
        assert limiter.allow("hnf1b_get_capabilities") is True

    def test_heavy_tool_capacity_smaller_than_standard(self):
        clock_val = [0.0]
        heavy_cap = 3.0
        standard_cap = 10.0
        limiter = RateLimiter(
            global_rps=1000.0,
            tool_capacity=standard_cap,
            heavy_tool_capacity=heavy_cap,
            clock=lambda: clock_val[0],
        )
        heavy_tool = next(iter(HEAVY_TOOLS))
        # Drain heavy tool budget.
        heavy_allowed = sum(
            1 for _ in range(20) if limiter.allow(heavy_tool)
        )
        assert heavy_allowed == int(heavy_cap)

        # A standard tool still has a larger budget.
        # (We need a fresh limiter to not interfere with global bucket.)
        limiter2 = RateLimiter(
            global_rps=1000.0,
            tool_capacity=standard_cap,
            heavy_tool_capacity=heavy_cap,
            clock=lambda: clock_val[0],
        )
        standard_allowed = sum(
            1 for _ in range(50) if limiter2.allow("hnf1b_search")
        )
        assert standard_allowed == int(standard_cap)
        assert heavy_allowed < standard_allowed

    def test_heavy_tools_are_in_set(self):
        assert "hnf1b_get_statistics" in HEAVY_TOOLS
        assert "hnf1b_get_individuals" in HEAVY_TOOLS

    def test_per_tool_refills_over_time(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=1000.0,
            tool_capacity=2.0,
            heavy_tool_capacity=2.0,
            clock=lambda: clock_val[0],
        )
        # Drain per-tool bucket for statistics.
        while limiter.allow("hnf1b_get_statistics"):
            pass
        # Advance the clock so the per-tool bucket refills.
        clock_val[0] = 2.0
        assert limiter.allow("hnf1b_get_statistics") is True


# ---------------------------------------------------------------------------
# RateLimiter — no-Redis path
# ---------------------------------------------------------------------------

class TestRateLimiterNoRedis:
    def test_works_without_redis_url(self):
        limiter = RateLimiter(global_rps=50.0, redis_url=None)
        assert limiter.allow("hnf1b_get_capabilities") is True

    def test_stats(self):
        clock_val = [0.0]
        limiter = RateLimiter(
            global_rps=10.0,
            tool_capacity=5.0,
            heavy_tool_capacity=5.0,
            clock=lambda: clock_val[0],
        )
        limiter.allow("hnf1b_search")
        stats = limiter.stats()
        assert "global_available" in stats
        assert "tools" in stats
        assert "hnf1b_search" in stats["tools"]

    def test_from_settings_params(self):
        limiter = RateLimiter.from_settings_params(global_rps=100.0, redis_url=None)
        assert limiter.allow("hnf1b_get_capabilities") is True


# ---------------------------------------------------------------------------
# Module singleton helpers
# ---------------------------------------------------------------------------

class TestLimiterSingleton:
    def test_set_and_get_limiter(self):
        original = get_limiter()
        try:
            lim = RateLimiter(global_rps=50.0)
            set_limiter(lim)
            assert get_limiter() is lim
        finally:
            set_limiter(original)

    def test_set_limiter_none(self):
        original = get_limiter()
        try:
            set_limiter(None)
            assert get_limiter() is None
        finally:
            set_limiter(original)


# ---------------------------------------------------------------------------
# Default limits are generous enough for tests
# ---------------------------------------------------------------------------

class TestDefaultLimitsAreGenerousEnough:
    def test_default_global_rps_is_high(self):
        """Default global_rps must not throttle normal test/interactive use.

        With default global_rps=100 and global capacity=200, the per-tool
        budget (DEFAULT_TOOL_CAPACITY=30) is the first constraint.  20 back-to-
        back calls on a single tool should always be allowed.
        """
        limiter = RateLimiter()  # uses defaults: global_rps=100.0
        # Should allow at least 20 calls instantly without global throttling.
        allowed = sum(1 for _ in range(20) if limiter.allow("hnf1b_search"))
        assert allowed == 20

    def test_heavy_tools_default_budget_is_reasonable(self):
        """Heavy tool default budget (10) should allow normal use."""
        limiter = RateLimiter()
        heavy_tool = "hnf1b_get_statistics"
        # Default heavy_tool_capacity = 10; must allow at least 5 back-to-back.
        allowed = sum(1 for _ in range(5) if limiter.allow(heavy_tool))
        assert allowed == 5
