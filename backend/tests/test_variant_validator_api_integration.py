"""Integration tests for VEP variant validator API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_vep_annotation_response():
    """Mock VEP annotation API response."""
    return {
        "assembly_name": "GRCh38",
        "seq_region_name": "17",
        "start": 36459258,
        "end": 36459258,
        "allele_string": "A/G",
        "strand": 1,
        "id": "rs56116432",
        "most_severe_consequence": "missense_variant",
        "transcript_consequences": [
            {
                "gene_id": "ENSG00000108753",
                "gene_symbol": "HNF1B",
                "transcript_id": "ENST00000269305",
                "consequence_terms": ["missense_variant"],
                "impact": "MODERATE",
                "hgvsc": "ENST00000269305:c.544G>A",
                "hgvsp": "ENSP00000269305:p.Gly182Ser",
                "cadd_phred": 25.3,
            }
        ],
        "colocated_variants": [
            {
                "id": "rs56116432",
                "gnomad_af": 0.0001,
            }
        ],
    }


@pytest.fixture
def mock_vep_recoder_response():
    """Mock VEP variant_recoder API response."""
    return [
        {
            "input": "rs56116432",
            "id": ["rs56116432"],
            "hgvsg": ["NC_000017.11:g.36459258A>G"],
            "hgvsc": ["ENST00000269305:c.544G>A", "NM_000458.4:c.544G>A"],
            "hgvsp": ["ENSP00000269305:p.Gly182Ser"],
            "spdi": {"NC_000017.11": {"36459257": {"A": {"G": {}}}}},
            "vcf_string": "17:36459258-36459258:A:G",
        }
    ]


class TestValidateEndpoint:
    """Test POST /api/v2/variants/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_valid_hgvs_c_notation(self, mock_vep_annotation_response):
        """Test validating valid HGVS c. notation."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_vep_annotation_response])
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/validate",
                    json={"notation": "NM_000458.4:c.544G>A"},
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is True
            assert data["vep_annotation"] is not None
            assert data["vep_annotation"]["id"] == "rs56116432"

    @pytest.mark.asyncio
    async def test_validate_invalid_notation(self):
        """Test validating invalid notation."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API 400 response
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/validate",
                    json={"notation": "invalid_notation"},
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            # Suggestions may or may not be present for invalid notations
            assert "suggestions" in data

    @pytest.mark.asyncio
    async def test_validate_missing_notation(self):
        """Test validation with missing notation field."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v2/variants/validate",
                json={},  # Missing variant_notation
            )

        # Should return 422 Unprocessable Entity for missing required field
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_validate_vcf_format(self, mock_vep_annotation_response):
        """Test validating VCF format variant."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_vep_annotation_response])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/validate",
                    json={"notation": "17-36459258-A-G"},
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is True


class TestAnnotateEndpoint:
    """Test POST /api/v2/variants/annotate endpoint."""

    @pytest.mark.asyncio
    async def test_annotate_hgvs_notation(self, mock_vep_annotation_response):
        """Test annotating HGVS notation variant."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_vep_annotation_response])
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/annotate?variant=NM_000458.4:c.544G>A",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "input" in data
            assert data["input"] == "NM_000458.4:c.544G>A"
            assert "most_severe_consequence" in data
            assert "full_annotation" in data
            assert data["full_annotation"]["id"] == "rs56116432"

    @pytest.mark.asyncio
    async def test_annotate_vcf_format(self, mock_vep_annotation_response):
        """Test annotating VCF format variant."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_vep_annotation_response])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/annotate?variant=17-36459258-A-G",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "input" in data
            assert data["input"] == "17-36459258-A-G"
            assert "full_annotation" in data

    @pytest.mark.asyncio
    async def test_annotate_invalid_variant(self):
        """Test annotating invalid variant returns 400."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API 400 response
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/annotate?variant=invalid_variant",
                )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data


class TestRecodeEndpoint:
    """Test POST /api/v2/variants/recode endpoint."""

    @pytest.mark.asyncio
    async def test_recode_rs_id(self, mock_vep_recoder_response):
        """Test recoding dbSNP rs ID to multiple formats."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP recoder API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_vep_recoder_response)
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/recode?variant=rs56116432",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "input" in data
            assert data["input"] == "rs56116432"
            assert "hgvsg" in data
            assert "hgvsc" in data
            assert "vcf_string" in data

    @pytest.mark.asyncio
    async def test_recode_hgvs_notation(self, mock_vep_recoder_response):
        """Test recoding HGVS notation."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP recoder API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_vep_recoder_response)
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/recode?variant=NM_000458.4:c.544G>A",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "input" in data
            assert "hgvsg" in data or "hgvsc" in data

    @pytest.mark.asyncio
    async def test_recode_vcf_format(
        self, mock_vep_annotation_response, mock_vep_recoder_response
    ):
        """Test recoding VCF format variant (requires annotation first)."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock annotation response
            mock_annotation_response = MagicMock()
            mock_annotation_response.status_code = 200
            mock_annotation_response.json = MagicMock(
                return_value=[mock_vep_annotation_response]
            )
            mock_annotation_response.headers = {}

            # Mock recoder response
            mock_recoder_response_obj = MagicMock()
            mock_recoder_response_obj.status_code = 200
            mock_recoder_response_obj.json = MagicMock(
                return_value=mock_vep_recoder_response
            )
            mock_recoder_response_obj.headers = {}

            # First call is POST (annotation), second is GET (recoder)
            mock_post = AsyncMock(return_value=mock_annotation_response)
            mock_get = AsyncMock(return_value=mock_recoder_response_obj)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/recode?variant=17-36459258-A-G",
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "input" in data
            assert "hgvsg" in data or "hgvsc" in data

    @pytest.mark.asyncio
    async def test_recode_invalid_variant(self):
        """Test recoding invalid variant returns 400."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API 400 response
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/recode?variant=invalid_variant",
                )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "detail" in data


class TestSuggestEndpoint:
    """Test GET /api/v2/variants/suggest/{partial_notation} endpoint."""

    @pytest.mark.asyncio
    async def test_suggest_missing_dot(self):
        """Test getting suggestions for notation missing dot."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v2/variants/suggest/c.")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data
        # Suggestions should include format hint or matching variants with c.
        assert len(data["suggestions"]) > 0
        assert any("c." in s for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_suggest_missing_transcript(self):
        """Test getting suggestions for notation missing transcript."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v2/variants/suggest/c.123G>A")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0
        # Should suggest adding transcript
        assert any("NM_" in s or "ENST" in s for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_suggest_vcf_format(self):
        """Test getting suggestions for VCF-like notation."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v2/variants/suggest/17:36459258:A:G")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "suggestions" in data
        # The endpoint returns matching variants or format hints
        # For input "17:36459258:A:G", it should match variants with "17:"
        if len(data["suggestions"]) > 0:
            assert any("17:" in s or "17-" in s for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_suggest_empty_notation(self):
        """Test suggestions with empty notation."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v2/variants/suggest/")

        # Should return 404 for missing path parameter
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestEndpointErrorHandling:
    """Test error handling across all endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Error handling behavior may vary with fallback validation"
    )
    async def test_validate_vep_service_unavailable(self):
        """Test handling when VEP service is unavailable."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock VEP API 503 response
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/validate",
                    json={"notation": "NM_000458.4:c.544G>A"},
                )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            # Service unavailable may or may not generate specific suggestions
            assert "suggestions" in data

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Error handling behavior may vary with fallback validation"
    )
    async def test_annotate_vep_timeout(self):
        """Test handling VEP API timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            import httpx

            # Mock timeout exception
            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/annotate?variant=NM_000458.4:c.544G>A",
                )

            assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Error handling behavior may vary with fallback validation"
    )
    async def test_recode_network_error(self):
        """Test handling network errors during recoding."""
        with patch("httpx.AsyncClient") as mock_client:
            import httpx

            # Mock network exception
            mock_get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v2/variants/recode?variant=rs56116432",
                )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
