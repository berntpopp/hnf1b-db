"""Tests for VEP variant annotation functionality.

Tests the VariantValidator class with Redis-based caching (or in-memory fallback).
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.config import settings
from app.phenopackets.validation.variant_validator import VariantValidator


@pytest.fixture
def validator():
    """Create a VariantValidator instance."""
    return VariantValidator()


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
        "most_severe_consequence": "splice_donor_variant",
        "transcript_consequences": [
            {
                "gene_id": "ENSG00000108753",
                "gene_symbol": "HNF1B",
                "transcript_id": "ENST00000366667",
                "consequence_terms": ["splice_donor_variant"],
                "impact": "HIGH",
                "mane_select": "ENST00000366667.8",
                "hgvsc": "ENST00000366667.8:c.544+1G>A",
                "hgvsp": None,
                "cadd_phred": 34.0,
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
            "hgvsc": ["ENST00000366667.8:c.544+1G>A", "NM_000458.4:c.544+1G>A"],
            "hgvsp": [],
            "spdi": {
                "seq_id": "NC_000017.11",
                "position": 36459257,
                "deleted_sequence": "A",
                "inserted_sequence": "G",
            },
            "vcf_string": "17:36459258-36459258:A:G",
        }
    ]


class TestVariantValidator:
    """Test VariantValidator VEP integration."""

    def test_init(self, validator):
        """Test validator initialization with config values."""
        # Rate limiting state
        assert validator._last_request_time == 0.0
        assert validator._request_count == 0

        # Values from config (may differ from defaults)
        assert validator._requests_per_second == settings.rate_limiting.vep.requests_per_second
        assert validator._max_retries == settings.external_apis.vep.max_retries
        assert validator._backoff_factor == settings.external_apis.vep.retry_backoff_factor
        assert validator._cache_ttl == settings.external_apis.vep.cache_ttl_seconds

    def test_is_vcf_format(self, validator):
        """Test VCF format detection."""
        assert validator._is_vcf_format("17-36459258-A-G") is True
        assert validator._is_vcf_format("chr17-36459258-A-G") is True
        assert validator._is_vcf_format("X-12345-C-T") is True
        assert validator._is_vcf_format("NM_000458.4:c.544+1G>A") is False
        assert validator._is_vcf_format("rs56116432") is False

    def test_vcf_to_vep_format(self, validator):
        """Test VCF to VEP format conversion."""
        result = validator._vcf_to_vep_format("17-36459258-A-G")
        assert result == "17 36459258 . A G . . ."

        result = validator._vcf_to_vep_format("chr17-36459258-A-G")
        assert result == "17 36459258 . A G . . ."

        result = validator._vcf_to_vep_format("invalid-format")
        assert result is None

    @pytest.mark.asyncio
    async def test_annotate_variant_vcf_success(
        self, validator, mock_vep_annotation_response
    ):
        """Test VCF variant annotation with mock response."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [mock_vep_annotation_response]
            mock_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            assert result is not None
            assert result["most_severe_consequence"] == "splice_donor_variant"
            assert result["id"] == "rs56116432"
            assert len(result["transcript_consequences"]) > 0

    @pytest.mark.asyncio
    async def test_annotate_variant_hgvs_success(
        self, validator, mock_vep_annotation_response
    ):
        """Test HGVS variant annotation with mock response."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [mock_vep_annotation_response]
            mock_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.annotate_variant_with_vep("NM_000458.4:c.544+1G>A")

            assert result is not None
            assert result["most_severe_consequence"] == "splice_donor_variant"

    @pytest.mark.asyncio
    async def test_annotate_variant_caching(
        self, validator, mock_vep_annotation_response
    ):
        """Test that annotations are cached using Redis."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # First call - cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [mock_vep_annotation_response]
            mock_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result1 = await validator.annotate_variant_with_vep(
                "NM_000458.4:c.544+1G>A"
            )
            assert result1 is not None

            # Verify cache.set_json was called
            mock_cache.set_json.assert_called_once()

            # Second call - cache hit
            mock_cache.get_json = AsyncMock(return_value=mock_vep_annotation_response)
            result2 = await validator.annotate_variant_with_vep(
                "NM_000458.4:c.544+1G>A"
            )
            assert result2 is not None
            assert result2 == mock_vep_annotation_response

            # API should NOT have been called again (only 1 call)
            assert mock_client_instance.get.call_count == 1

    @pytest.mark.asyncio
    async def test_annotate_variant_rate_limiting_429(self, validator):
        """Test handling of 429 rate limit response."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
            patch("asyncio.sleep"),
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_429_response = Mock()
            mock_429_response.status_code = 429
            mock_429_response.headers = {"Retry-After": "1"}

            mock_200_response = Mock()
            mock_200_response.status_code = 200
            mock_200_response.json.return_value = [{"id": "test"}]
            mock_200_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = [
                mock_429_response,
                mock_200_response,
            ]
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.annotate_variant_with_vep(
                "NM_000458.4:c.544+1G>A"
            )

            assert result is not None
            assert result["id"] == "test"

    @pytest.mark.asyncio
    async def test_annotate_variant_invalid_format(self, validator):
        """Test handling of invalid variant format (400 error)."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)

            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.annotate_variant_with_vep("invalid-variant")

            assert result is None

    @pytest.mark.asyncio
    async def test_annotate_variant_retry_on_500(self, validator):
        """Test retry logic on 500 server error."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
            patch("asyncio.sleep"),
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_500_response = Mock()
            mock_500_response.status_code = 500
            mock_500_response.headers = {}

            mock_200_response = Mock()
            mock_200_response.status_code = 200
            mock_200_response.json.return_value = [{"id": "test"}]
            mock_200_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = [
                mock_500_response,
                mock_200_response,
            ]
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.annotate_variant_with_vep(
                "NM_000458.4:c.544+1G>A"
            )

            assert result is not None
            assert result["id"] == "test"

    @pytest.mark.asyncio
    async def test_recode_variant_success(self, validator, mock_vep_recoder_response):
        """Test variant recoding with mock response."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_vep_recoder_response
            mock_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.recode_variant_with_vep("rs56116432")

            assert result is not None
            assert result["input"] == "rs56116432"
            assert "hgvsg" in result
            assert "hgvsc" in result
            assert "vcf_string" in result

    @pytest.mark.asyncio
    async def test_recode_variant_vcf_format(
        self, validator, mock_vep_annotation_response, mock_vep_recoder_response
    ):
        """Test recoding VCF format variant."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss for both annotation and recoder
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            # Mock annotation call first
            mock_annotation_response = Mock()
            mock_annotation_response.status_code = 200
            mock_annotation_response.json.return_value = [mock_vep_annotation_response]
            mock_annotation_response.headers = {}

            # Mock recoder call
            mock_recoder_response = Mock()
            mock_recoder_response.status_code = 200
            mock_recoder_response.json.return_value = mock_vep_recoder_response
            mock_recoder_response.headers = {}

            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_annotation_response
            mock_client_instance.get.return_value = mock_recoder_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance

            result = await validator.recode_variant_with_vep("17-36459258-A-G")

            assert result is not None


class TestCacheIntegration:
    """Test cache integration with Redis/in-memory fallback."""

    @pytest.mark.asyncio
    async def test_cache_enabled_setting(self, validator):
        """Test that cache behavior respects settings."""
        # Cache should be enabled by default in config
        assert settings.external_apis.vep.cache_enabled is True

    @pytest.mark.asyncio
    async def test_cache_ttl_from_config(self, validator):
        """Test that cache TTL is loaded from config."""
        expected_ttl = settings.external_apis.vep.cache_ttl_seconds
        assert validator._cache_ttl == expected_ttl
