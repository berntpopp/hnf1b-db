"""HTTP-surface baselines for Wave 4 decomposition.

Captures a JSON snapshot of every endpoint touched by the Wave 4 backend
decomposition and verifies that subsequent refactors do not change the
observable response shape (keys, status code, nesting). Content fields
that vary between runs (timestamps, counters, IDs) are masked via
``_normalize`` before the comparison.

Usage
-----

Capture once at the start of Wave 4 (runs against the current code)::

    WAVE4_CAPTURE_BASELINE=1 uv run pytest tests/test_http_surface_baseline.py \
        -k capture -v -s

Verify after every decomposition step::

    uv run pytest tests/test_http_surface_baseline.py -k verify -v

Capture mode writes one JSON file per endpoint into
``tests/fixtures/http_baselines/``. Verify mode re-hits every endpoint
for which a baseline file exists and asserts byte-identical normalised
shape + status code.

Endpoints affected by Wave 4 and covered here
---------------------------------------------

- ``admin_endpoints.py``          → ``GET /api/v2/admin/status`` (admin auth)
- ``crud.py``                     → ``GET /api/v2/phenopackets/``
- ``phenopackets/routers/search`` → ``GET /api/v2/phenopackets/search``
- ``comparisons.py``              → ``GET /api/v2/phenopackets/compare/variant-types``
- ``aggregations/sql_fragments``  → ``GET /api/v2/phenopackets/aggregate/summary``
- ``publications/endpoints.py``   → ``GET /api/v2/publications/``
- ``reference/router + service``  → ``GET /api/v2/reference/genes``
- ``search/services.py``          → ``GET /api/v2/search/autocomplete``

``variant_validator.py``, ``variant_validator_endpoint.py`` and
``variants/service.py`` are deliberately excluded because they depend on
the live Ensembl REST API (flaky in CI) and already have their own
dedicated test suites (``test_variant_validator_enhanced.py``,
``test_variant_annotation_vep.py``, ``test_variant_service_cnv.py``) which
serve as the refactor safety net for those files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

BASELINE_DIR = Path(__file__).parent / "fixtures" / "http_baselines"

# Each tuple describes one HTTP interaction:
#   (baseline_name, auth_required, method, path, query_params, body)
# - auth_required is "admin" | "user" | None
# - query_params is a dict that will be passed via httpx's params= (handles
#   bracketed keys like ``page[size]`` correctly)
AFFECTED_ENDPOINTS: list[tuple[str, str | None, str, str, dict | None, dict | None]] = [
    (
        "admin_status",
        "admin",
        "GET",
        "/api/v2/admin/status",
        None,
        None,
    ),
    (
        "phenopackets_list",
        None,
        "GET",
        "/api/v2/phenopackets/",
        {"page[size]": "3"},
        None,
    ),
    (
        "phenopackets_search",
        None,
        "GET",
        "/api/v2/phenopackets/search",
        {"q": "renal", "page[size]": "3"},
        None,
    ),
    (
        "phenopackets_compare_variant_types",
        None,
        "GET",
        "/api/v2/phenopackets/compare/variant-types",
        {"comparison": "truncating_vs_non_truncating", "limit": "5"},
        None,
    ),
    (
        "phenopackets_aggregate_summary",
        None,
        "GET",
        "/api/v2/phenopackets/aggregate/summary",
        None,
        None,
    ),
    (
        "publications_list",
        None,
        "GET",
        "/api/v2/publications/",
        {"page[size]": "3"},
        None,
    ),
    (
        "reference_genes",
        None,
        "GET",
        "/api/v2/reference/genes",
        None,
        None,
    ),
    (
        "search_autocomplete",
        None,
        "GET",
        "/api/v2/search/autocomplete",
        {"q": "HNF", "limit": "5"},
        None,
    ),
    # Wave 5b Task 14: admin user-management baselines
    (
        "auth_users_list",
        "admin",
        "GET",
        "/api/v2/auth/users",
        {"role": "admin"},
        None,
    ),
    (
        "auth_users_create",
        "admin",
        "POST",
        "/api/v2/auth/users",
        None,
        {
            "username": "baseline-create-probe",
            "email": "baseline-create@example.com",
            "password": "BaselinePass!2026",
            "full_name": "Baseline Create Probe",
            "role": "viewer",
        },
    ),
    (
        "auth_users_delete",
        "admin",
        "DELETE",
        "/api/v2/auth/users/999999",
        None,
        None,
    ),
]


_VOLATILE_KEYS = {
    "created_at",
    "updated_at",
    "timestamp",
    "request_id",
    "total",
    "count",
    "phenopackets_count",
    "users_count",
    "publications_cached",
    "last_sync",
    "last_sync_at",
    "duration_ms",
    "elapsed_ms",
    "uptime",
    "ran_at",
    "next_run_at",
    "generated_at",
    "time",
    "id",
    "phenopacket_id",
    # Wave 5a: dev-auth tokens must never land in a checked-in baseline.
    "access_token",
    "refresh_token",
    # Wave 5b Task 14: user last_login varies between captures.
    "last_login",
    # Wave 5b review fix: reference gene fields that differ between
    # local dev and CI because the Ensembl API / migration seed data
    # produces different structures depending on the data source version.
    # extra_data is a JSONB bag with environment-dependent keys (biotype,
    # version, aliases, chromosome_band, etc.); extra_info contains
    # Ensembl-sourced descriptions with varying suffixes.
    "extra_data",
    "extra_info",
    "hgnc_id",
    "ncbi_gene_id",
    "omim_id",
    "source_url",
}

# Baselines whose response BODY is inherently environment-dependent.
# CI seeds reference genes from a different data source (NCBI Gene)
# than local dev (Ensembl REST API), producing different gene records
# (names, coordinates, ensembl IDs, sources). These baselines still
# assert status_code + response shape; only the exact body values are
# skipped so the suite passes across environments.
_ENV_DEPENDENT_BASELINES = {
    "reference_genes",
    "search_autocomplete",
}


def _normalize(data: Any) -> Any:
    """Replace volatile field values with ``"<normalized>"`` so the
    baseline reflects shape rather than content.

    - Keys in ``_VOLATILE_KEYS`` always have their value replaced.
    - Lists are capped at 3 elements (the ``page[size]=3`` matches).
    - Scalars pass through as-is; nested dicts/lists recurse.
    """
    if isinstance(data, dict):
        return {
            k: "<normalized>" if k in _VOLATILE_KEYS else _normalize(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_normalize(item) for item in data[:3]]
    return data


def _shape(data: Any) -> Any:
    """Return a structural fingerprint of ``data`` — the shape only, no
    values.

    - Scalar → the Python type name (``"int"``, ``"str"``, ``None``).
    - Dict   → {key: shape-of-value}, with ``_VOLATILE_KEYS`` mapped to
      ``"volatile"`` so environment-dependent fields (e.g. reference gene
      ``extra_data`` whose sub-keys differ between Ensembl versions) don't
      break cross-environment shape assertions.
    - List   → ``["list", shape-of-first-item-or-empty]`` capped at length 1.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return {
            k: "volatile" if k in _VOLATILE_KEYS else _shape(v) for k, v in data.items()
        }
    if isinstance(data, list):
        return ["list", _shape(data[0]) if data else "empty"]
    return type(data).__name__


async def _call(client, auth_headers_map: dict, spec) -> dict:
    """Execute one HTTP call and return a normalized capture."""
    name, auth, method, path, params, body = spec
    headers = {}
    if auth == "admin":
        headers = auth_headers_map.get("admin", {})
    elif auth == "user":
        headers = auth_headers_map.get("user", {})

    if method == "GET":
        response = await client.get(path, params=params, headers=headers)
    else:
        response = await client.request(
            method, path, params=params, json=body or {}, headers=headers
        )

    try:
        payload = response.json()
    except Exception:
        payload = None

    return {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }


@pytest.fixture
async def _auth_headers_map(admin_headers):
    """Consolidate every auth header variant the baselines might need."""
    return {"admin": admin_headers}


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", AFFECTED_ENDPOINTS, ids=lambda s: s[0])
async def test_capture_baseline(async_client, _auth_headers_map, spec):
    """Capture current response as baseline. Skipped unless
    ``WAVE4_CAPTURE_BASELINE=1`` is set in the environment.
    """
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    name = spec[0]
    capture = await _call(async_client, _auth_headers_map, spec)

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{name}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", AFFECTED_ENDPOINTS, ids=lambda s: s[0])
async def test_verify_baseline(async_client, _auth_headers_map, spec):
    """Verify that the current endpoint response matches the captured
    baseline. Any endpoint without a captured baseline is skipped so the
    suite is forgiving to partial captures.
    """
    name = spec[0]
    baseline_path = BASELINE_DIR / f"{name}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {name}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    capture = await _call(async_client, _auth_headers_map, spec)

    assert capture["status_code"] == baseline["status_code"], (
        f"{name}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], f"{name}: response shape changed"
    # Baselines whose content is inherently environment-dependent (e.g.
    # reference gene records seeded from different data sources on CI vs
    # local) skip the normalized-body value comparison. Shape + status
    # code still assert the API contract; only the exact values differ.
    if name not in _ENV_DEPENDENT_BASELINES:
        assert capture["normalized_body"] == baseline["normalized_body"], (
            f"{name}: normalised response body changed"
        )


# ---------------------------------------------------------------------------
# Wave 5a dev-auth baseline
# ---------------------------------------------------------------------------
#
# The dev-only ``/api/v2/dev/login-as/{username}`` endpoint has to go through
# the ``dev_auth_client`` fixture (which flips ``enable_dev_auth`` and mounts
# the router) AND requires a seeded fixture user in the DB. The other
# Wave 4 baselines all share a single parametrised test that uses
# ``async_client`` + ``admin_headers`` — grafting a dev endpoint onto that
# parametrisation would force every other endpoint to pay the dev-mode
# setup cost on every run. So the dev baseline gets its own tiny pair of
# capture / verify tests that mirrors the existing mechanism exactly.

_DEV_BASELINE_NAME = "dev_login_as_admin"


async def _seed_dev_fixture_admin(db_session):
    """Create a fixture admin user for the dev baseline to log in as."""
    from app.auth.password import get_password_hash
    from app.models.user import User

    user = User(
        username="dev-admin",
        email="dev-admin@example.com",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
        is_fixture_user=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_capture_dev_login_as_baseline(dev_auth_client, db_session):
    """Capture the dev-login-as response shape. Opt-in via the same
    ``WAVE4_CAPTURE_BASELINE=1`` env knob as the Wave 4 endpoints so that
    running the full suite never accidentally rewrites the fixture.
    """
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    await _seed_dev_fixture_admin(db_session)

    response = await dev_auth_client.post("/api/v2/dev/login-as/dev-admin")
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{_DEV_BASELINE_NAME}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
async def test_verify_dev_login_as_baseline(dev_auth_client, db_session):
    """Verify the dev-login-as response still matches the captured shape.

    Skipped when the baseline file is absent so CI environments that
    have not captured the fixture (e.g. production-shaped smoke runs)
    still pass. When the fixture file exists, the test seeds a fixture
    admin on demand and re-runs the same capture path through
    ``_normalize`` / ``_shape`` to assert byte-identical shape.
    """
    baseline_path = BASELINE_DIR / f"{_DEV_BASELINE_NAME}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {_DEV_BASELINE_NAME}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    await _seed_dev_fixture_admin(db_session)
    response = await dev_auth_client.post("/api/v2/dev/login-as/dev-admin")
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    assert capture["status_code"] == baseline["status_code"], (
        f"{_DEV_BASELINE_NAME}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], (
        f"{_DEV_BASELINE_NAME}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{_DEV_BASELINE_NAME}: normalised response body changed"
    )


# ---------------------------------------------------------------------------
# Wave 5b auth/users/{id}/unlock baseline
# ---------------------------------------------------------------------------
#
# Wave 5b Task 6 introduces PATCH /api/v2/auth/users/{user_id}/unlock.
# The endpoint needs a seeded target user (with failed_login_attempts and
# locked_until populated) before the capture, so it cannot use the generic
# AFFECTED_ENDPOINTS parametrize loop — templated URLs don't compose with
# the 6-tuple `(name, auth, method, path, params, body)` shape. Instead,
# this baseline follows the same structure as
# ``test_capture_dev_login_as_baseline``.

_UNLOCK_BASELINE_NAME = "auth_users_unlock"


async def _seed_locked_target_user(db_session) -> int:
    """Insert a locked curator and return its id for the unlock baseline."""
    from datetime import datetime, timedelta, timezone

    from app.auth.password import get_password_hash
    from app.models.user import User

    locked = User(
        username="wave5b-baseline-locked",
        email="wave5b-baseline-locked@hnf1b-db.local",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        full_name="Baseline Locked Curator",
        role="curator",
        is_active=True,
        is_verified=True,
        is_fixture_user=False,
        failed_login_attempts=5,
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add(locked)
    await db_session.commit()
    await db_session.refresh(locked)
    return locked.id


@pytest.mark.asyncio
async def test_capture_auth_users_unlock_baseline(
    async_client, admin_headers, db_session
):
    """Capture the unlock-response shape. Opt-in via WAVE4_CAPTURE_BASELINE=1."""
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    user_id = await _seed_locked_target_user(db_session)

    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock", headers=admin_headers
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{_UNLOCK_BASELINE_NAME}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
async def test_verify_auth_users_unlock_baseline(
    async_client, admin_headers, db_session
):
    """Verify the unlock response against the captured baseline."""
    baseline_path = BASELINE_DIR / f"{_UNLOCK_BASELINE_NAME}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {_UNLOCK_BASELINE_NAME}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    user_id = await _seed_locked_target_user(db_session)

    response = await async_client.patch(
        f"/api/v2/auth/users/{user_id}/unlock", headers=admin_headers
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    assert capture["status_code"] == baseline["status_code"], (
        f"{_UNLOCK_BASELINE_NAME}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], (
        f"{_UNLOCK_BASELINE_NAME}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{_UNLOCK_BASELINE_NAME}: normalised response body changed"
    )


# ---------------------------------------------------------------------------
# Wave 5b Task 14: auth/users/{id} PUT (update) baseline
# ---------------------------------------------------------------------------
#
# The update endpoint needs a seeded target user before the capture, so it
# cannot use the generic AFFECTED_ENDPOINTS parametrise loop.

_UPDATE_BASELINE_NAME = "auth_users_update"


async def _seed_update_target_user(db_session) -> int:
    """Insert a curator target and return its id for the update baseline."""
    from app.auth.password import get_password_hash
    from app.models.user import User

    target = User(
        username="wave5b-baseline-update",
        email="wave5b-baseline-update@example.com",
        hashed_password=get_password_hash("IrrelevantPass123!"),
        full_name="Baseline Update Target",
        role="curator",
        is_active=True,
        is_verified=True,
        is_fixture_user=False,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    return target.id


@pytest.mark.asyncio
async def test_capture_auth_users_update_baseline(
    async_client, admin_headers, db_session
):
    """Capture the update-response shape. Opt-in via WAVE4_CAPTURE_BASELINE=1."""
    if os.environ.get("WAVE4_CAPTURE_BASELINE") != "1":
        pytest.skip("Baseline capture only runs when WAVE4_CAPTURE_BASELINE=1")

    user_id = await _seed_update_target_user(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"full_name": "baseline updated"},
        headers=admin_headers,
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    with (BASELINE_DIR / f"{_UPDATE_BASELINE_NAME}.json").open("w") as f:
        json.dump(capture, f, indent=2, sort_keys=True)


@pytest.mark.asyncio
async def test_verify_auth_users_update_baseline(
    async_client, admin_headers, db_session
):
    """Verify the update response against the captured baseline."""
    baseline_path = BASELINE_DIR / f"{_UPDATE_BASELINE_NAME}.json"
    if not baseline_path.exists():
        pytest.skip(f"No baseline captured for {_UPDATE_BASELINE_NAME}")

    with baseline_path.open() as f:
        baseline = json.load(f)

    user_id = await _seed_update_target_user(db_session)

    response = await async_client.put(
        f"/api/v2/auth/users/{user_id}",
        json={"full_name": "baseline updated"},
        headers=admin_headers,
    )
    try:
        payload = response.json()
    except Exception:
        payload = None

    capture = {
        "status_code": response.status_code,
        "normalized_body": _normalize(payload) if payload is not None else None,
        "shape": _shape(payload) if payload is not None else None,
    }

    assert capture["status_code"] == baseline["status_code"], (
        f"{_UPDATE_BASELINE_NAME}: status code changed "
        f"{baseline['status_code']} → {capture['status_code']}"
    )
    assert capture["shape"] == baseline["shape"], (
        f"{_UPDATE_BASELINE_NAME}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{_UPDATE_BASELINE_NAME}: normalised response body changed"
    )
