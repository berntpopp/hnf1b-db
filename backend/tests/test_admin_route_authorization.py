"""Explicit BFLA authorization matrix for every admin-gated route.

Wave 5b Task 8 — first of three commits in the router-level BFLA
migration (scope doc S5 R4).  This module parametrizes three tests over
every admin-gated route:

  1. ``test_admin_route_forbidden_for_viewer``  -- viewer token -> 403
  2. ``test_admin_route_forbidden_for_curator`` -- curator token -> 403
  3. ``test_admin_route_reachable_for_admin``   -- admin token -> non-{401,403}

The tests pass against the CURRENT per-endpoint ``Depends(require_admin)``
state and MUST continue passing unchanged through Task 9 (router-level
guard) and Task 10 (per-endpoint guard removal).

Any new admin-gated route added in the future should be appended to
``ADMIN_ROUTES`` in the same PR.
"""

from __future__ import annotations

from typing import Optional

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Route inventory — every admin-gated endpoint in the application
# ---------------------------------------------------------------------------
# (name, HTTP method, URL template, optional JSON body)
#
# URL templates may contain ``{admin_user_id}`` which is resolved at
# test time via the ``admin_user_id`` fixture.

ADMIN_ROUTES: list[tuple[str, str, str, Optional[dict]]] = [
    # auth_endpoints.py — user management
    (
        "create_user",
        "POST",
        "/api/v2/auth/users",
        {
            "username": "wave5b-bfla-probe",
            "email": "wave5b-bfla-probe@hnf1b-db.local",
            "password": "ProbePass!2026",
            "full_name": "BFLA Probe",
            "role": "viewer",
        },
    ),
    ("list_users", "GET", "/api/v2/auth/users", None),
    ("get_user", "GET", "/api/v2/auth/users/{admin_user_id}", None),
    (
        "update_user",
        "PUT",
        "/api/v2/auth/users/{admin_user_id}",
        {"full_name": "updated"},
    ),
    ("delete_user", "DELETE", "/api/v2/auth/users/{admin_user_id}", None),
    (
        "unlock_user",
        "PATCH",
        "/api/v2/auth/users/{admin_user_id}/unlock",
        None,
    ),
    # admin sub-router — status_routes.py
    ("admin_status", "GET", "/api/v2/admin/status", None),
    ("admin_statistics", "GET", "/api/v2/admin/statistics", None),
    ("admin_reference_status", "GET", "/api/v2/admin/reference/status", None),
    # admin sub-router — sync_publications_routes.py
    ("admin_sync_publications", "POST", "/api/v2/admin/sync/publications", None),
    (
        "admin_sync_publications_status",
        "GET",
        "/api/v2/admin/sync/publications/status",
        None,
    ),
    # admin sub-router — sync_variants_routes.py
    ("admin_sync_variants", "POST", "/api/v2/admin/sync/variants", None),
    (
        "admin_sync_variants_status",
        "GET",
        "/api/v2/admin/sync/variants/status",
        None,
    ),
    # admin sub-router — sync_reference_routes.py
    (
        "admin_sync_reference_init",
        "POST",
        "/api/v2/admin/sync/reference/init",
        None,
    ),
    ("admin_sync_genes", "POST", "/api/v2/admin/sync/genes", None),
    ("admin_sync_genes_status", "GET", "/api/v2/admin/sync/genes/status", None),
]

_ROUTE_IDS = [name for name, *_ in ADMIN_ROUTES]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _probe(
    client: AsyncClient,
    method: str,
    url: str,
    body: Optional[dict],
    headers: dict[str, str],
) -> int:
    """Dispatch an arbitrary HTTP method and return the status code."""
    method_upper = method.upper()
    if method_upper == "GET":
        resp = await client.get(url, headers=headers)
    elif method_upper == "POST":
        resp = await client.post(url, json=body or {}, headers=headers)
    elif method_upper == "PUT":
        resp = await client.put(url, json=body or {}, headers=headers)
    elif method_upper == "PATCH":
        resp = await client.patch(url, json=body or {}, headers=headers)
    elif method_upper == "DELETE":
        resp = await client.delete(url, headers=headers)
    else:
        msg = f"Unsupported HTTP method: {method}"
        raise ValueError(msg)
    return resp.status_code


# ---------------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "method", "url_template", "body"),
    ADMIN_ROUTES,
    ids=_ROUTE_IDS,
)
async def test_admin_route_forbidden_for_viewer(
    async_client: AsyncClient,
    viewer_headers: dict[str, str],
    admin_user_id: int,
    name: str,
    method: str,
    url_template: str,
    body: Optional[dict],
) -> None:
    """Viewer token must receive 403 on every admin-gated route."""
    url = url_template.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, url, body, viewer_headers)
    assert status_code == 403, (
        f"[{name}] {method} {url} returned {status_code} for viewer (expected 403)"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "method", "url_template", "body"),
    ADMIN_ROUTES,
    ids=_ROUTE_IDS,
)
async def test_admin_route_forbidden_for_curator(
    async_client: AsyncClient,
    curator_headers: dict[str, str],
    admin_user_id: int,
    name: str,
    method: str,
    url_template: str,
    body: Optional[dict],
) -> None:
    """Curator token must receive 403 on every admin-gated route."""
    url = url_template.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, url, body, curator_headers)
    assert status_code == 403, (
        f"[{name}] {method} {url} returned {status_code} for curator (expected 403)"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "method", "url_template", "body"),
    ADMIN_ROUTES,
    ids=_ROUTE_IDS,
)
async def test_admin_route_reachable_for_admin(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user_id: int,
    name: str,
    method: str,
    url_template: str,
    body: Optional[dict],
) -> None:
    """Admin token must get past the authorization guard (non-401/403).

    We accept any status that is NOT 401 or 403 — the route may return
    200, 201, 204, 400, 404, or 409 depending on application state, but
    the authorization layer must not reject the request.
    """
    url = url_template.format(admin_user_id=admin_user_id)
    status_code = await _probe(async_client, method, url, body, admin_headers)
    assert status_code not in {401, 403}, (
        f"[{name}] {method} {url} returned {status_code} for admin "
        f"(expected non-{{401, 403}})"
    )
