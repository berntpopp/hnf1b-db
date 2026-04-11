"""Configurable async rate limiter for the Ensembl REST calls.

Shared helper used by both the VEP annotation and the VEP variant
recoder clients. Mirrors Ensembl's documented guidance:

- 55,000 requests per hour
- Average 15 requests per second
- Must respect ``Retry-After`` on 429 responses
- ``X-RateLimit-Remaining`` is warned on when below 10%

Extracted during Wave 4 from ``variant_validator.py``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Mapping, MutableMapping, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple token-bucket rate limiter.

    Not thread-safe (async-only). Uses monotonic wall-clock time
    rather than ``asyncio.get_event_loop().time()`` so the same
    instance can be shared across event loops in tests that teardown
    and rebuild the loop per-test.
    """

    def __init__(self, requests_per_second: int) -> None:
        """Wire the limiter to a per-second cap."""
        self._requests_per_second = requests_per_second
        self._last_request_time = 0.0
        self._request_count = 0

    async def acquire(self) -> None:
        """Wait until a request slot is available, then reserve it."""
        current_time = time.time()

        if current_time - self._last_request_time >= 1.0:
            self._request_count = 0
            self._last_request_time = current_time

        if self._request_count >= self._requests_per_second:
            sleep_time = 1.0 - (current_time - self._last_request_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self._request_count = 0
            self._last_request_time = time.time()

        self._request_count += 1


def check_rate_limit_headers(
    headers: Mapping[str, str] | MutableMapping[str, str],
) -> Optional[str]:
    """Warn if the Ensembl rate-limit headers show we're near the cap.

    Matches the pre-Wave-4 behaviour: emits a ``print`` to stderr-ish
    (mocked by the regression tests) when we drop below 10 % remaining,
    and returns the warning string so log-based callers can also consume
    it. Returns ``None`` when the headers are missing or we're still
    comfortably above the warning threshold.
    """
    remaining = headers.get("X-RateLimit-Remaining")
    limit = headers.get("X-RateLimit-Limit")
    if not remaining or not limit:
        return None
    try:
        remaining_int = int(remaining)
        limit_int = int(limit)
    except (TypeError, ValueError):
        return None

    if remaining_int < limit_int * 0.1:
        msg = f"Rate limit warning: {remaining}/{limit} requests remaining"
        # Mirrors the legacy flat-module behaviour — the regression test
        # suite patches ``builtins.print`` and asserts a call.
        print(f"\u26a0\ufe0f  {msg}")
        return msg
    return None
