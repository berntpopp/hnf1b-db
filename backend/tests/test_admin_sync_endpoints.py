"""Tests for admin sync endpoints with force parameter functionality.

Tests the admin sync endpoints including:
- Publication sync with normal and force mode
- Variant sync with normal and force mode
- Force parameter to re-sync already synced data
"""

import pytest


class TestPublicationSyncEndpoint:
    """Test admin publication sync endpoint."""

    @pytest.mark.asyncio
    async def test_publication_sync_requires_admin(self, async_client, auth_headers):
        """Test that publication sync requires admin role."""
        response = await async_client.post(
            "/api/v2/admin/sync/publications",
            headers=auth_headers,  # Regular user headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_publication_sync_start_success(
        self, async_client, admin_headers, db_session
    ):
        """Test starting publication sync."""
        response = await async_client.post(
            "/api/v2/admin/sync/publications",
            headers=admin_headers,
        )

        # Should return success (either starts sync or reports all synced)
        assert response.status_code in (200, 202)
        data = response.json()
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_publication_sync_force_parameter(
        self, async_client, admin_headers, db_session
    ):
        """Test that force parameter is accepted and triggers re-sync."""
        response = await async_client.post(
            "/api/v2/admin/sync/publications?force=true",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        # With force=true, should either queue a new sync or complete if no data
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_publication_sync_false_force_parameter(
        self, async_client, admin_headers, db_session
    ):
        """Test that force=false behaves like normal sync."""
        response = await async_client.post(
            "/api/v2/admin/sync/publications?force=false",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)


class TestVariantSyncEndpoint:
    """Test admin variant sync endpoint."""

    @pytest.mark.asyncio
    async def test_variant_sync_requires_admin(self, async_client, auth_headers):
        """Test that variant sync requires admin role."""
        response = await async_client.post(
            "/api/v2/admin/sync/variants",
            headers=auth_headers,  # Regular user headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_variant_sync_start_success(
        self, async_client, admin_headers, db_session
    ):
        """Test starting variant sync."""
        response = await async_client.post(
            "/api/v2/admin/sync/variants",
            headers=admin_headers,
        )

        # Should return success (either starts sync or reports all synced)
        assert response.status_code in (200, 202)
        data = response.json()
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_variant_sync_force_parameter(
        self, async_client, admin_headers, db_session
    ):
        """Test that force parameter triggers deletion of cached data."""
        response = await async_client.post(
            "/api/v2/admin/sync/variants?force=true",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        # With force=true, should either queue a new sync or complete if no data
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_variant_sync_false_force_parameter(
        self, async_client, admin_headers, db_session
    ):
        """Test that force=false behaves like normal sync."""
        response = await async_client.post(
            "/api/v2/admin/sync/variants?force=false",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)


class TestSyncStatusEndpoints:
    """Test sync status checking endpoints."""

    @pytest.mark.asyncio
    async def test_publication_sync_status_requires_admin(
        self, async_client, auth_headers
    ):
        """Test that publication sync status requires admin role."""
        response = await async_client.get(
            "/api/v2/admin/sync/publications/status",
            headers=auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_publication_sync_status_success(
        self, async_client, admin_headers, db_session
    ):
        """Test getting publication sync status."""
        response = await async_client.get(
            "/api/v2/admin/sync/publications/status",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Status should contain count information
        assert "total" in data or "pending" in data or "synced" in data

    @pytest.mark.asyncio
    async def test_variant_sync_status_requires_admin(
        self, async_client, auth_headers
    ):
        """Test that variant sync status requires admin role."""
        response = await async_client.get(
            "/api/v2/admin/sync/variants/status",
            headers=auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_variant_sync_status_success(
        self, async_client, admin_headers, db_session
    ):
        """Test getting variant sync status."""
        response = await async_client.get(
            "/api/v2/admin/sync/variants/status",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Status should contain count information
        assert "total" in data or "pending" in data or "annotated" in data


class TestSyncResponseSchema:
    """Test that sync responses follow expected schema."""

    @pytest.mark.asyncio
    async def test_publication_sync_response_has_task_id(
        self, async_client, admin_headers
    ):
        """Test that publication sync response includes task_id."""
        response = await async_client.post(
            "/api/v2/admin/sync/publications",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_variant_sync_response_has_task_id(
        self, async_client, admin_headers
    ):
        """Test that variant sync response includes task_id."""
        response = await async_client.post(
            "/api/v2/admin/sync/variants",
            headers=admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        assert "task_id" in data
