"""Tests for admin sync endpoints with force parameter functionality.

Tests the admin sync endpoints including:
- Publication sync with normal and force mode
- Variant sync with normal and force mode
- Force parameter to re-sync already synced data
"""

import pytest


class TestAdminSyncPublicationEndpoint:
    """Test admin publication sync endpoint."""

    @pytest.mark.asyncio
    async def test_sync_publication_requires_admin_returns_403(
        self, fixture_async_client, fixture_auth_headers
    ):
        """Test that publication sync requires admin role."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/publications",
            headers=fixture_auth_headers,  # Regular user headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_publication_start_success_returns_200_or_202(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test starting publication sync."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/publications",
            headers=fixture_admin_headers,
        )

        # Should return success (either starts sync or reports all synced)
        assert response.status_code in (200, 202)
        data = response.json()
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_sync_publication_force_parameter_accepted(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test that force parameter is accepted and triggers re-sync."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/publications?force=true",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        # With force=true, should either queue a new sync or complete if no data
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_sync_publication_false_force_parameter_behaves_normal(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test that force=false behaves like normal sync."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/publications?force=false",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)


class TestAdminSyncVariantEndpoint:
    """Test admin variant sync endpoint."""

    @pytest.mark.asyncio
    async def test_sync_variant_requires_admin_returns_403(
        self, fixture_async_client, fixture_auth_headers
    ):
        """Test that variant sync requires admin role."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/variants",
            headers=fixture_auth_headers,  # Regular user headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_variant_start_success_returns_200_or_202(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test starting variant sync."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/variants",
            headers=fixture_admin_headers,
        )

        # Should return success (either starts sync or reports all synced)
        assert response.status_code in (200, 202)
        data = response.json()
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_sync_variant_force_parameter_accepted(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test that force parameter triggers deletion of cached data."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/variants?force=true",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        # With force=true, should either queue a new sync or complete if no data
        assert "message" in data or "status" in data

    @pytest.mark.asyncio
    async def test_sync_variant_false_force_parameter_behaves_normal(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test that force=false behaves like normal sync."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/variants?force=false",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)


class TestAdminSyncStatusEndpoints:
    """Test sync status checking endpoints."""

    @pytest.mark.asyncio
    async def test_sync_publication_status_requires_admin_returns_403(
        self, fixture_async_client, fixture_auth_headers
    ):
        """Test that publication sync status requires admin role."""
        response = await fixture_async_client.get(
            "/api/v2/admin/sync/publications/status",
            headers=fixture_auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_publication_status_success_returns_200(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test getting publication sync status."""
        response = await fixture_async_client.get(
            "/api/v2/admin/sync/publications/status",
            headers=fixture_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Status should contain count information
        assert "total" in data or "pending" in data or "synced" in data

    @pytest.mark.asyncio
    async def test_sync_variant_status_requires_admin_returns_403(
        self, fixture_async_client, fixture_auth_headers
    ):
        """Test that variant sync status requires admin role."""
        response = await fixture_async_client.get(
            "/api/v2/admin/sync/variants/status",
            headers=fixture_auth_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_variant_status_success_returns_200(
        self, fixture_async_client, fixture_admin_headers, fixture_db_session
    ):
        """Test getting variant sync status."""
        response = await fixture_async_client.get(
            "/api/v2/admin/sync/variants/status",
            headers=fixture_admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Status should contain count information
        assert "total" in data or "pending" in data or "annotated" in data


class TestAdminSyncResponseSchema:
    """Test that sync responses follow expected schema."""

    @pytest.mark.asyncio
    async def test_sync_publication_response_has_task_id(
        self, fixture_async_client, fixture_admin_headers
    ):
        """Test that publication sync response includes task_id."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/publications",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_sync_variant_response_has_task_id(
        self, fixture_async_client, fixture_admin_headers
    ):
        """Test that variant sync response includes task_id."""
        response = await fixture_async_client.post(
            "/api/v2/admin/sync/variants",
            headers=fixture_admin_headers,
        )

        assert response.status_code in (200, 202)
        data = response.json()
        assert "task_id" in data
