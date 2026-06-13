"""Tests for the version source of truth and the /api/v2/version endpoint.

Issue #7: a single, non-hardcoded version source (pyproject.toml) plus an
endpoint exposing the app version and the live Alembic schema revision.
"""

import re
from pathlib import Path

import pytest
import tomllib

from app.core.version import (
    API_PATH_VERSION,
    APP_VERSION,
    PHENOPACKET_SCHEMA_VERSION,
    get_app_version,
)

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
# Loose semver: MAJOR.MINOR.PATCH with an optional pre/build suffix.
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+([.+-].*)?$")


def _pyproject_version() -> str:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


class TestVersionSourceOfTruth:
    """The app version comes from pyproject.toml and nowhere else."""

    def test_app_version_matches_pyproject(self):
        """APP_VERSION is resolved from pyproject.toml — the single source."""
        assert APP_VERSION == _pyproject_version()

    def test_app_version_is_beta_semver(self):
        """The project is in beta (0.X.Y) and the string is a valid semver."""
        assert _SEMVER_RE.match(APP_VERSION), APP_VERSION
        assert APP_VERSION.startswith("0."), f"expected beta 0.X.Y, got {APP_VERSION}"

    def test_app_version_is_not_the_legacy_hardcode_or_sentinel(self):
        """Guards against regressing to the old hardcoded 2.0.0 or failing soft."""
        assert APP_VERSION != "2.0.0"
        assert APP_VERSION != "0.0.0+unknown"

    def test_get_app_version_is_cached_and_stable(self):
        """Repeated resolution returns the same cached value."""
        assert get_app_version() == get_app_version() == APP_VERSION


@pytest.mark.asyncio
class TestVersionEndpoint:
    """GET /api/v2/version reports app + DB schema versions."""

    async def test_returns_all_fields(self, async_client):
        """The endpoint reports the app, path, and phenopacket schema versions."""
        resp = await async_client.get("/api/v2/version")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["api_version"] == APP_VERSION
        assert body["api_path_version"] == API_PATH_VERSION == "v2"
        assert body["phenopacket_schema_version"] == PHENOPACKET_SCHEMA_VERSION

    async def test_db_schema_revision_in_sync(self, async_client):
        """The migrated test DB is at head, so applied == head and in_sync."""
        resp = await async_client.get("/api/v2/version")
        body = resp.json()
        assert body["db_schema_revision"], "expected an applied Alembic revision"
        assert body["db_schema_head"], "expected a codebase head revision"
        assert body["db_schema_revision"] == body["db_schema_head"]
        assert body["db_schema_in_sync"] is True


@pytest.mark.asyncio
class TestVersionPropagation:
    """The single source feeds every version-reporting endpoint."""

    @pytest.mark.parametrize(
        "path,key",
        [
            ("/", "version"),
            ("/livez", "version"),
            ("/api/v2/info", "version"),
        ],
    )
    async def test_endpoints_report_app_version(self, async_client, path, key):
        """Every version-reporting endpoint returns the single-sourced version."""
        resp = await async_client.get(path)
        assert resp.status_code == 200, resp.text
        assert resp.json()[key] == APP_VERSION
