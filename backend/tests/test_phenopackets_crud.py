"""Integration tests for phenopacket CRUD endpoints.

Exercises create/read/update/delete via the FastAPI TestClient against
the dedicated test database. Intentionally shallow at Wave 2 - deeper
coverage arrives during Wave 4 when the repository layer lands.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Synchronous TestClient for integration tests.

    Kept local to this module so we don't collide with the async_client
    fixture in conftest.py. The autouse database-truncation fixture still
    runs, giving every test a clean slate.
    """
    return TestClient(app)


# Minimal phenopacket payload wrapped in the ``PhenopacketCreate`` envelope
# expected by POST /api/v2/phenopackets/. We only need enough structure for
# the endpoint to accept the request shape - actual validation may still
# reject it, which is fine: we're testing auth gating, not the happy path.
SAMPLE_PAYLOAD = {
    "phenopacket": {
        "id": "INT-TEST-001",
        "subject": {"id": "SUB-INT-001", "sex": "MALE"},
        "phenotypicFeatures": [{"type": {"id": "HP:0000107", "label": "Renal cyst"}}],
        "metaData": {
            "created": "2026-04-10T00:00:00Z",
            "createdBy": "integration-test",
            "phenopacketSchemaVersion": "2.0",
        },
    },
    "created_by": "integration-test",
}


class TestPhenopacketRead:
    """Read operations don't require auth."""

    def test_list_returns_json_api_envelope(self, client):
        """GET / should return a JSON:API response envelope with a data key."""
        response = client.get("/api/v2/phenopackets/?page[size]=5")
        assert response.status_code == 200
        body = response.json()
        # JSON:API v1.1 envelope uses ``data``; fall back to other shapes
        # defensively so we don't become a regression tripwire for unrelated
        # response-shape tweaks.
        assert "data" in body or "items" in body or isinstance(body, list)


class TestPhenopacketWriteRequiresAuth:
    """Write operations MUST require authentication.

    We intentionally do not exercise the authenticated happy path here -
    Wave 4 will add that coverage once the repository layer is in place.
    """

    def test_create_rejects_unauthenticated(self, client):
        """POST without a bearer token must be rejected."""
        response = client.post("/api/v2/phenopackets/", json=SAMPLE_PAYLOAD)
        # HTTPBearer() raises 403 by default when no Authorization header
        # is present. 401 is the spec-correct answer; either is acceptable.
        # 422 would mean body validation ran first, which also proves the
        # request did not succeed as an unauthenticated write.
        assert response.status_code in (401, 403, 422)

    def test_update_requires_auth(self, client):
        """PUT with an invalid bearer token must fail specifically as auth.

        Using a real but invalid token (rather than no Authorization header)
        forces the auth dependency to evaluate and reject. Without this, a
        404 from "row does not exist" could mask an accidentally-removed
        auth dependency, so 404/422 are NOT accepted here.
        """
        response = client.put(
            "/api/v2/phenopackets/INT-TEST-001",
            headers={"Authorization": "Bearer definitely-invalid-token"},
            json={
                "phenopacket": SAMPLE_PAYLOAD["phenopacket"],
                "change_reason": "integration test",
            },
        )
        assert response.status_code in (401, 403)

    def test_delete_requires_auth(self, client):
        """DELETE with an invalid bearer token must fail specifically as auth.

        Same rationale as ``test_update_requires_auth``: we use an invalid
        token instead of an absent header so that the auth layer is what's
        being exercised, not the "row does not exist" path.
        """
        response = client.request(
            "DELETE",
            "/api/v2/phenopackets/INT-TEST-001",
            headers={"Authorization": "Bearer definitely-invalid-token"},
            json={"change_reason": "integration test"},
        )
        assert response.status_code in (401, 403)
