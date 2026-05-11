"""Tests for readiness and liveness endpoints."""

import pytest


async def _resolved(value):
    """Return a value from an awaitable helper for monkeypatched checks."""
    return value


@pytest.mark.asyncio
async def test_livez_reports_process_alive(async_client):
    """The liveness endpoint should stay lightweight and always return 200."""
    response = await async_client.get("/livez")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_health_reports_ready_when_dependencies_are_healthy(
    async_client, monkeypatch
):
    """Readiness should report healthy when DB and cache checks pass."""
    monkeypatch.setattr("app.main._database_ready", lambda: _resolved((True, None)))
    monkeypatch.setattr("app.main._cache_ready", lambda: _resolved((True, None)))

    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "version": "2.0.0",
        "phenopackets_schema": "2.0.0",
        "ready": True,
        "dependencies": {
            "database": {"ready": True, "error": None},
            "cache": {"ready": True, "backend": "redis", "error": None},
        },
    }


@pytest.mark.asyncio
async def test_health_reports_not_ready_when_a_dependency_fails(
    async_client, monkeypatch
):
    """Readiness should return 503 with machine-readable dependency failures."""
    monkeypatch.setattr(
        "app.main._database_ready", lambda: _resolved((False, "db down"))
    )
    monkeypatch.setattr("app.main._cache_ready", lambda: _resolved((True, None)))

    response = await async_client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ready"] is False
    assert body["dependencies"]["database"] == {"ready": False, "error": "db down"}
    assert body["dependencies"]["cache"] == {
        "ready": True,
        "backend": "redis",
        "error": None,
    }
