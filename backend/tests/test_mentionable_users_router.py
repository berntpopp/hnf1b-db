"""Mentionable users endpoint — smoke + role filtering."""
import pytest

from app.auth.password import get_password_hash
from app.models.user import User


@pytest.mark.asyncio
async def test_mentionable_q_too_short_returns_422(async_client, curator_headers):
    resp = await async_client.get(
        "/api/v2/users/mentionable?q=a",
        headers=curator_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mentionable_returns_active_curators_admins_only(
    async_client, curator_headers, db_session
):
    # Create four users matching prefix "ad"
    for username, role, active in [
        ("adam_test", "curator", True),
        ("admin2_test", "admin", True),
        ("adrian_test", "viewer", True),  # excluded — viewer
        ("adele_test", "curator", False),  # excluded — inactive
    ]:
        u = User(
            username=username,
            email=f"{username}@t.local",
            hashed_password=get_password_hash("x"),
            role=role,
            is_active=active,
            is_verified=True,
        )
        db_session.add(u)
    await db_session.commit()

    resp = await async_client.get(
        "/api/v2/users/mentionable?q=ad",
        headers=curator_headers,
    )
    assert resp.status_code == 200, resp.json()
    names = {u["username"] for u in resp.json()["data"]}
    # Two qualifying users (adam, admin2) must be present; excluded ones absent.
    assert "adam_test" in names
    assert "admin2_test" in names
    assert "adrian_test" not in names
    assert "adele_test" not in names
