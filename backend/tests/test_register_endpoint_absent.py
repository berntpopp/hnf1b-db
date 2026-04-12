"""Negative test: self-registration endpoint must not exist.

HNF1B-DB is invite-only. POST /api/v2/auth/register must return
404 (no route) or 405 (method not allowed). If this test fails,
someone added a registration endpoint — that is a policy violation.
"""

import pytest


@pytest.mark.asyncio
async def test_register_endpoint_absent(async_client):
    """POST /api/v2/auth/register returns 404 or 405."""
    resp = await async_client.post(
        "/api/v2/auth/register",
        json={
            "username": "hacker",
            "email": "hacker@example.com",
            "password": "H4ck3rP4ss!",
        },
    )
    assert resp.status_code in (404, 405), (
        f"Expected 404 or 405 but got {resp.status_code}. "
        "A registration endpoint exists — HNF1B-DB is invite-only."
    )
