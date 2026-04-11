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
``tests/fixtures/wave4_http_baselines/``. Verify mode re-hits every endpoint
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

BASELINE_DIR = Path(__file__).parent / "fixtures" / "wave4_http_baselines"

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
    - Dict   → {key: shape-of-value}.
    - List   → ``["list", shape-of-first-item-or-empty]`` capped at length 1.

    This is strictly stronger than ``_normalize`` because it compares
    types on every field. Used as the primary assertion.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return {k: _shape(v) for k, v in data.items()}
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
    assert capture["shape"] == baseline["shape"], (
        f"{name}: response shape changed"
    )
    assert capture["normalized_body"] == baseline["normalized_body"], (
        f"{name}: normalised response body changed"
    )
