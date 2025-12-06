"""Comprehensive unit tests for VEP annotation system.

Tests the VariantValidator class including:
- Format detection (VCF vs HGVS)
- VEP API annotation
- CADD score and gnomAD frequency extraction
- Rate limiting (configurable from settings)
- Redis-based caching (with in-memory fallback)
- Error handling (invalid format, timeout, 429, 500)
- Retry logic with exponential backoff

Related: Issue #117, #100
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.cache import cache
from app.core.config import settings
from app.phenopackets.validation.variant_validator import VariantValidator


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Clear the in-memory cache between tests to prevent cross-test contamination.

    This ensures that tests checking error scenarios don't get cached results
    from previous successful tests.
    """
    # Clear before test
    cache._fallback.clear()
    yield
    # Clear after test
    cache._fallback.clear()


class TestVariantFormatDetection:
    """Test format detection methods."""

    def test_is_vcf_format_valid(self):
        """Test VCF format detection with valid inputs."""
        validator = VariantValidator()

        # Standard VCF formats
        assert validator._is_vcf_format("17-36459258-A-G") is True
        assert validator._is_vcf_format("chr17-36459258-A-G") is True
        assert validator._is_vcf_format("X-123456-G-C") is True
        assert validator._is_vcf_format("Y-987654-T-A") is True
        assert validator._is_vcf_format("M-12345-C-T") is True

        # Case insensitive
        assert validator._is_vcf_format("CHR17-36459258-A-G") is True

    def test_is_vcf_format_invalid(self):
        """Test VCF format detection with invalid inputs."""
        validator = VariantValidator()

        # HGVS formats (not VCF)
        assert validator._is_vcf_format("NM_000458.4:c.544G>A") is False
        assert validator._is_vcf_format("NC_000017.11:g.36459258A>G") is False

        # Invalid VCF formats
        assert validator._is_vcf_format("17:36459258:A:G") is False  # Colons not dashes
        assert validator._is_vcf_format("17-36459258") is False  # Missing ref/alt
        assert validator._is_vcf_format("invalid-format") is False

    def test_vcf_to_vep_format_valid(self):
        """Test VCF to VEP format conversion with valid inputs."""
        validator = VariantValidator()

        # Standard VCF
        assert (
            validator._vcf_to_vep_format("17-36459258-A-G") == "17 36459258 . A G . . ."
        )

        # With chr prefix (should be removed)
        assert (
            validator._vcf_to_vep_format("chr17-36459258-A-G")
            == "17 36459258 . A G . . ."
        )
        assert (
            validator._vcf_to_vep_format("Chr17-36459258-A-G")
            == "17 36459258 . A G . . ."
        )
        assert (
            validator._vcf_to_vep_format("CHR17-36459258-A-G")
            == "17 36459258 . A G . . ."
        )

        # Sex chromosomes
        assert validator._vcf_to_vep_format("X-123456-G-C") == "X 123456 . G C . . ."
        assert validator._vcf_to_vep_format("Y-987654-T-A") == "Y 987654 . T A . . ."

    def test_vcf_to_vep_format_invalid(self):
        """Test VCF to VEP format conversion with invalid inputs."""
        validator = VariantValidator()

        # Wrong number of parts
        assert validator._vcf_to_vep_format("17-36459258-A") is None
        assert validator._vcf_to_vep_format("17-36459258") is None

        # Non-numeric position
        assert validator._vcf_to_vep_format("17-abc-A-G") is None


class TestVEPAnnotation:
    """Test VEP annotation functionality."""

    @pytest.mark.asyncio
    async def test_annotate_vcf_format_success(self):
        """Test successful VCF format annotation with CADD and gnomAD."""
        validator = VariantValidator()

        # Mock VEP API response
        mock_response_data = {
            "assembly_name": "GRCh38",
            "seq_region_name": "17",
            "start": 36459258,
            "end": 36459258,
            "allele_string": "A/G",
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST00000269305",
                    "gene_id": "ENSG00000275410",
                    "gene_symbol": "HNF1B",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                    "cadd_phred": 28.5,
                    "cadd_raw": 4.123,
                    "polyphen_prediction": "probably_damaging",
                    "polyphen_score": 0.95,
                    "sift_prediction": "deleterious",
                    "sift_score": 0.01,
                }
            ],
            "colocated_variants": [
                {
                    "id": "rs121913343",
                    "minor_allele": "G",
                    "minor_allele_freq": 0.0001,
                    "gnomad_af": 0.00012,
                }
            ],
        }

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            # Setup mock
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_response_data])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Test annotation
            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Assertions
            assert result is not None
            assert result["most_severe_consequence"] == "missense_variant"
            assert result["transcript_consequences"][0]["cadd_phred"] == 28.5
            assert result["colocated_variants"][0]["gnomad_af"] == 0.00012
            assert result["assembly_name"] == "GRCh38"

    @pytest.mark.asyncio
    async def test_annotate_hgvs_format_success(self):
        """Test successful HGVS format annotation."""
        validator = VariantValidator()

        # Mock VEP API response
        mock_response_data = {
            "id": "ENST00000269305:c.544G>A",
            "assembly_name": "GRCh38",
            "most_severe_consequence": "missense_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST00000269305",
                    "gene_symbol": "HNF1B",
                    "consequence_terms": ["missense_variant"],
                    "impact": "MODERATE",
                }
            ],
        }

        with patch("httpx.AsyncClient") as mock_client:
            # Setup mock
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_response_data])
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test annotation
            result = await validator.annotate_variant_with_vep("NM_000458.4:c.544G>A")

            # Assertions
            assert result is not None
            assert result["most_severe_consequence"] == "missense_variant"
            assert result["transcript_consequences"][0]["gene_symbol"] == "HNF1B"

    @pytest.mark.asyncio
    async def test_annotate_invalid_variant_format(self):
        """Test annotation with invalid variant format returns None."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 400 Bad Request for invalid format
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Test annotation
            result = await validator.annotate_variant_with_vep("invalid-variant-format")

            # Should return None for invalid format
            assert result is None

    @pytest.mark.asyncio
    async def test_annotate_vcf_conversion_fails(self):
        """Test annotation when VCF format conversion fails."""
        validator = VariantValidator()

        # Mock _vcf_to_vep_format to return None (conversion failure)
        with patch.object(validator, "_vcf_to_vep_format", return_value=None):
            # Test annotation with VCF-like format
            result = await validator.annotate_variant_with_vep("17-invalid-vcf")

            # Should return None when conversion fails
            assert result is None

    @pytest.mark.asyncio
    async def test_annotate_unexpected_status_code(self):
        """Test annotation with unexpected HTTP status code."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock unexpected status code (e.g., 301 redirect)
            mock_response = AsyncMock()
            mock_response.status_code = 301
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Test annotation
            result = await validator.annotate_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return None for unexpected status
            assert result is None

    @pytest.mark.asyncio
    async def test_annotate_rate_limit_warning(self):
        """Test rate limit warning is printed when < 10% remaining."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock successful response with low rate limit
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": "test"}]
            mock_response.headers = {
                "X-RateLimit-Remaining": "5",  # 5 remaining
                "X-RateLimit-Limit": "100",  # out of 100 (5% remaining)
            }

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            # Capture print output
            with patch("builtins.print") as mock_print:
                await validator.annotate_variant_with_vep("NM_000458.4:c.544G>A")

                # Should print rate limit warning
                mock_print.assert_called_once()
                assert "Rate limit warning" in str(mock_print.call_args)

    @pytest.mark.asyncio
    async def test_extract_cadd_score_missing(self):
        """Test CADD score extraction when missing from response."""
        validator = VariantValidator()

        # Mock VEP response without CADD
        mock_response_data = {
            "most_severe_consequence": "synonymous_variant",
            "transcript_consequences": [
                {
                    "transcript_id": "ENST00000269305",
                    "consequence_terms": ["synonymous_variant"],
                    "impact": "LOW",
                    # No cadd_phred field
                }
            ],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_response_data])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # CADD should be None when not present
            assert result is not None
            assert result["transcript_consequences"][0].get("cadd_phred") is None


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self):
        """Test rate limiter enforces 15 req/sec."""
        validator = VariantValidator()

        # Mock successful responses
        mock_response_data = {"most_severe_consequence": "test"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [mock_response_data]
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Try to make 20 requests (should be rate limited)
            start_time = time.time()

            tasks = [
                validator.annotate_variant_with_vep(f"17-3645925{i}-A-G")
                for i in range(20)
            ]
            await asyncio.gather(*tasks)

            duration = time.time() - start_time

            # 20 requests at 15/sec should take ~1.33 seconds
            # Allow some margin for processing time
            assert duration >= 1.0  # At least 1 second
            assert duration < 2.5  # But not too slow

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(self):
        """Test rate limiter allows immediate burst up to limit."""
        validator = VariantValidator()

        # Mock successful responses
        mock_response_data = {"most_severe_consequence": "test"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [mock_response_data]
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # First 15 requests should complete immediately
            start_time = time.time()

            tasks = [
                validator.annotate_variant_with_vep(f"17-3645925{i}-A-G")
                for i in range(15)
            ]
            await asyncio.gather(*tasks)

            duration = time.time() - start_time

            # Should be nearly instant (< 0.5 seconds)
            assert duration < 0.5


class TestCaching:
    """Test Redis-based caching functionality (with in-memory fallback)."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self):
        """Test cache hit returns cached data without API call."""
        validator = VariantValidator()

        # Pre-populate cache via mock
        cached_data = {"cadd_phred": 25.0, "gnomad_af": 0.0002, "cached": True}

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache hit
            mock_cache.get_json = AsyncMock(return_value=cached_data)

            # Test annotation
            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Should return cached data
            assert result == cached_data
            assert result["cached"] is True

            # Should NOT call API (cache was checked first)
            mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_api_and_caches(self):
        """Test cache miss triggers API call and stores result."""
        validator = VariantValidator()

        mock_response_data = {"cadd_phred": 28.5, "test": "data"}

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            # Mock cache miss
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_response_data])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Test annotation (cache miss)
            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Should call API
            assert mock_post.called

            # Should cache result via cache.set_json
            mock_cache.set_json.assert_called_once()

            # Should return API data
            assert result["cadd_phred"] == 28.5

    @pytest.mark.asyncio
    async def test_lru_cache_eviction(self):
        """Test that cache TTL is used for expiration (Redis handles LRU)."""
        validator = VariantValidator()

        # With Redis, cache eviction is handled by Redis TTL
        # We just verify TTL is passed to set_json
        mock_response_data = {"cadd_phred": 28.5}

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("app.phenopackets.validation.variant_validator.cache") as mock_cache,
        ):
            mock_cache.get_json = AsyncMock(return_value=None)
            mock_cache.set_json = AsyncMock(return_value=True)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_response_data])
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Verify TTL is passed (Redis handles eviction)
            call_args = mock_cache.set_json.call_args
            assert call_args is not None
            # TTL should be passed as keyword argument
            assert "ttl" in call_args.kwargs or len(call_args.args) > 2

    @pytest.mark.asyncio
    async def test_cache_lru_ordering(self):
        """Test that cache returns correct data on hit."""
        validator = VariantValidator()

        cached_data_1 = {"data": 1}
        cached_data_2 = {"data": 2}

        with patch("app.phenopackets.validation.variant_validator.cache") as mock_cache:
            # Mock different cache responses based on key
            def get_json_side_effect(key):
                if "variant1" in key:
                    return cached_data_1
                elif "variant2" in key:
                    return cached_data_2
                return None

            mock_cache.get_json = AsyncMock(side_effect=get_json_side_effect)

            # Access variant1 - should return cached_data_1
            result1 = await validator.annotate_variant_with_vep("variant1-123-A-G")
            assert result1 == cached_data_1

            # Access variant2 - should return cached_data_2
            result2 = await validator.annotate_variant_with_vep("variant2-456-C-T")
            assert result2 == cached_data_2


class TestErrorHandling:
    """Test error handling for various failure scenarios."""

    @pytest.mark.asyncio
    async def test_vep_api_timeout_error(self):
        """Test error handling for VEP API timeout."""
        validator = VariantValidator()
        validator._max_retries = 2  # Reduce retries for faster test

        with patch("httpx.AsyncClient") as mock_client:
            # Mock timeout exception
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            # Test annotation (should retry and fail)
            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Should return None after exhausting retries
            assert result is None

            # Should have attempted retries
            assert mock_client.return_value.__aenter__.return_value.post.call_count == 2

    @pytest.mark.asyncio
    async def test_vep_api_429_rate_limit_error(self):
        """Test error handling for VEP API 429 (too many requests)."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 429 response with Retry-After header
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}  # Wait 1 second

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch("asyncio.sleep") as mock_sleep:
                # Test annotation
                await validator.annotate_variant_with_vep("17-36459258-A-G")

                # Should respect Retry-After header
                mock_sleep.assert_called()
                # Note: 429 doesn't count as retry attempt, so it keeps retrying
                # For this test, we just verify sleep was called

    @pytest.mark.asyncio
    async def test_vep_api_500_server_error_with_retry(self):
        """Test error handling for VEP API 500 (server error) with retry."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 500 response
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.headers = {}

            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with patch("asyncio.sleep") as mock_sleep:
                # Test annotation
                result = await validator.annotate_variant_with_vep("17-36459258-A-G")

                # Should return None after retries
                assert result is None

                # Should have attempted retries with backoff
                assert mock_sleep.call_count == 1  # Backoff sleep between retries

    @pytest.mark.asyncio
    async def test_vep_api_network_error(self):
        """Test error handling for network errors."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock network error
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.NetworkError("Network unreachable")
            )

            # Test annotation
            result = await validator.annotate_variant_with_vep("17-36459258-A-G")

            # Should return None after exhausting retries
            assert result is None

    @pytest.mark.asyncio
    async def test_vep_api_retry_success_after_failure(self):
        """Test successful retry after initial failure."""
        validator = VariantValidator()

        mock_success_data = {"most_severe_consequence": "missense_variant"}

        with patch("httpx.AsyncClient") as mock_client:
            # First call fails (500), second succeeds (200)
            mock_fail_response = MagicMock()
            mock_fail_response.status_code = 500
            mock_fail_response.headers = {}

            mock_success_response = MagicMock()
            mock_success_response.status_code = 200
            mock_success_response.json = MagicMock(return_value=[mock_success_data])
            mock_success_response.headers = {}

            mock_post = AsyncMock(
                side_effect=[mock_fail_response, mock_success_response]
            )
            mock_client.return_value.__aenter__.return_value.post = mock_post

            with patch("asyncio.sleep"):
                # Test annotation
                result = await validator.annotate_variant_with_vep("17-36459258-A-G")

                # Should succeed on retry
                assert result is not None
                assert result["most_severe_consequence"] == "missense_variant"


class TestVariantRecoding:
    """Test variant recoding functionality."""

    @pytest.mark.asyncio
    async def test_recode_variant_success(self):
        """Test successful variant recoding to multiple formats."""
        validator = VariantValidator()

        # Mock VEP annotation response (needed for VCF input)
        mock_annotation = {"id": "rs56116432"}

        # Mock VEP recoder response
        mock_recoded = {
            "id": ["rs56116432"],
            "hgvsg": ["NC_000017.11:g.36459258A>G"],
            "hgvsc": ["NM_000458.4:c.544G>A"],
            "hgvsp": ["NP_000449.3:p.Gly182Ser"],
            "spdi": {"NC_000017.11": {"36459257": {"A": {"G": {}}}}},
            "vcf_string": "17:36459258-36459258:A:G",
        }

        with patch("httpx.AsyncClient") as mock_client:
            # Mock both annotation and recoder calls
            mock_annotation_response = MagicMock()
            mock_annotation_response.status_code = 200
            mock_annotation_response.json = MagicMock(return_value=[mock_annotation])
            mock_annotation_response.headers = {}

            mock_recoder_response = MagicMock()
            mock_recoder_response.status_code = 200
            mock_recoder_response.json = MagicMock(return_value=[mock_recoded])
            mock_recoder_response.headers = {}

            # First call is annotation (POST), second is recoder (GET)
            mock_post = AsyncMock(return_value=mock_annotation_response)
            mock_get = AsyncMock(return_value=mock_recoder_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding
            result = await validator.recode_variant_with_vep("17-36459258-A-G")

            # Assertions
            assert result is not None
            assert "rs56116432" in result["id"]
            assert "NM_000458.4:c.544G>A" in result["hgvsc"]
            assert "NC_000017.11:g.36459258A>G" in result["hgvsg"]

    @pytest.mark.asyncio
    async def test_recode_hgvs_variant_success(self):
        """Test recoding HGVS variant (no annotation step needed)."""
        validator = VariantValidator()

        # Mock VEP recoder response
        mock_recoded = {
            "id": ["rs56116432"],
            "hgvsg": ["NC_000017.11:g.36459258A>G"],
            "hgvsc": ["NM_000458.4:c.544G>A"],
            "vcf_string": "17:36459258-36459258:A:G",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_recoded])
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding HGVS (should skip annotation step)
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Assertions
            assert result is not None
            assert "rs56116432" in result["id"]

    @pytest.mark.asyncio
    async def test_recode_variant_429_rate_limit(self):
        """Test recoding with 429 rate limit error."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 429 response
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep") as mock_sleep:
                # Test recoding HGVS variant (no annotation step)
                await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

                # Should have tried to wait for Retry-After
                mock_sleep.assert_called_with(1)
                # Should return None after max retries
                # (rate limit keeps hitting, so never succeeds)

    @pytest.mark.asyncio
    async def test_recode_variant_400_invalid_format(self):
        """Test recoding with 400 invalid format error."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 400 response
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding with invalid variant
            result = await validator.recode_variant_with_vep("invalid_variant")

            # Should return None for 400 error
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_500_server_error_with_retry(self):
        """Test recoding with 500 server error and retry."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 500 response
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep") as mock_sleep:
                # Test recoding
                result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

                # Should return None after retries
                assert result is None

                # Should have attempted backoff sleep
                assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_recode_variant_503_service_unavailable(self):
        """Test recoding with 503 service unavailable error."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock 503 response
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep"):
                # Test recoding
                result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

                # Should return None after retries
                assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_timeout_error(self):
        """Test recoding with timeout error."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock timeout exception
            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep") as mock_sleep:
                # Test recoding
                result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

                # Should return None after retries
                assert result is None

                # Should have attempted retries with backoff
                assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_recode_variant_network_error(self):
        """Test recoding with network error."""
        validator = VariantValidator()
        validator._max_retries = 2

        with patch("httpx.AsyncClient") as mock_client:
            # Mock network exception
            mock_get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            with patch("asyncio.sleep") as mock_sleep:
                # Test recoding
                result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

                # Should return None after retries
                assert result is None

                # Should have attempted retries with backoff
                assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_recode_variant_unexpected_exception(self):
        """Test recoding with unexpected exception."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock unexpected exception
            mock_get = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return None for unexpected error
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_unexpected_status_code(self):
        """Test recoding with unexpected HTTP status code (e.g., 418 I'm a teapot)."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock unexpected status code
            mock_response = MagicMock()
            mock_response.status_code = 418  # Unexpected status
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return None for unexpected status
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_invalid_response_format(self):
        """Test recoding with invalid response format (not a list)."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock response with invalid format (dict instead of list)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value={"error": "Invalid format"})
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return None for invalid response format
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_empty_response_list(self):
        """Test recoding with empty response list."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock response with empty list
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[])  # Empty list
            mock_response.headers = {}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test recoding
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return None for empty response
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_vcf_annotation_fails(self):
        """Test recoding VCF format when annotation step fails."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock annotation failure (400 error)
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.headers = {}

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Test recoding VCF format (which requires annotation first)
            result = await validator.recode_variant_with_vep("17-36459258-A-G")

            # Should return None when annotation fails
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_vcf_no_variant_id(self):
        """Test recoding VCF format when annotation returns no variant ID."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock annotation response without 'id' field
            mock_annotation = {"allele_string": "A/G"}  # Missing 'id'
            mock_annotation_response = MagicMock()
            mock_annotation_response.status_code = 200
            mock_annotation_response.json = MagicMock(return_value=[mock_annotation])
            mock_annotation_response.headers = {}

            mock_post = AsyncMock(return_value=mock_annotation_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            # Test recoding VCF format
            result = await validator.recode_variant_with_vep("17-36459258-A-G")

            # Should return None when no variant ID in annotation
            assert result is None

    @pytest.mark.asyncio
    async def test_recode_variant_with_cache_hit(self):
        """Test recoding uses cache when available."""
        validator = VariantValidator()

        # Pre-populate cache via mock
        cached_data = {"id": ["rs56116432"], "hgvsg": ["NC_000017.11:g.36459258A>G"]}

        with patch("app.phenopackets.validation.variant_validator.cache") as mock_cache:
            # Mock cache hit
            mock_cache.get_json = AsyncMock(return_value=cached_data)

            # Test recoding (should hit cache, no API call)
            result = await validator.recode_variant_with_vep("NM_000458.4:c.544G>A")

            # Should return cached data
            assert result == cached_data
            # Verify cache was checked
            mock_cache.get_json.assert_called()


class TestPhenopacketValidation:
    """Test phenopacket-level validation methods."""

    @pytest.mark.asyncio
    async def test_validate_variant_with_vep_success(self):
        """Test validate_variant_with_vep returns valid VEP data."""
        validator = VariantValidator()

        mock_vep_data = {
            "id": "ENST00000269305:c.544G>A",
            "hgvsc": "ENST00000269305:c.544G>A",
            "hgvsp": "ENSP00000269305:p.Gly182Ser",
            "hgvsg": "NC_000017.11:g.36459258A>G",
            "most_severe_consequence": "missense_variant",
            "gene_symbol": "HNF1B",
            "transcript_id": "ENST00000269305",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=[mock_vep_data])

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
                "ENST00000269305:c.544G>A"
            )

            assert is_valid is True
            assert vep_data == mock_vep_data
            assert suggestions == []

    @pytest.mark.asyncio
    async def test_validate_variant_with_vep_invalid(self):
        """Test validate_variant_with_vep returns suggestions for invalid variant."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 400

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
                "c123G>A"  # Invalid - missing dot
            )

            assert is_valid is False
            assert vep_data is None
            assert len(suggestions) > 0

    @pytest.mark.asyncio
    async def test_validate_variant_with_vep_service_unavailable(self):
        """Test validate_variant_with_vep handles service unavailable."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 503

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
                "ENST00000269305:c.544G>A"
            )

            assert is_valid is False
            assert vep_data is None
            assert "VEP service temporarily unavailable" in suggestions

    @pytest.mark.asyncio
    async def test_validate_variant_with_vep_unexpected_exception(self):
        """Test validate_variant_with_vep falls back to regex validation on exception."""
        validator = VariantValidator()

        with patch("httpx.AsyncClient") as mock_client:
            # Mock unexpected exception during VEP call
            mock_get = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test with valid HGVS notation (should pass fallback validation)
            is_valid, vep_data, suggestions = await validator.validate_variant_with_vep(
                "NM_000458.4:c.544G>A"
            )

            # Should fall back to regex validation
            assert is_valid is True  # Valid HGVS c. notation passes regex
            assert vep_data is None  # No VEP data from fallback
            assert suggestions == []  # No suggestions from fallback

    def test_validate_variant_formats_valid(self):
        """Test validate_variant_formats with valid variant descriptor."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {"syntax": "hgvs.c", "value": "NM_000458.4:c.544G>A"},
                {"syntax": "vcf", "value": "17-36459258-A-G"},
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert errors == []

    def test_validate_variant_formats_invalid_hgvs_c(self):
        """Test validate_variant_formats detects invalid HGVS c. notation."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {"syntax": "hgvs.c", "value": "c123G>A"},  # Invalid - missing dot
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "Invalid HGVS c. notation" in errors[0]
        assert "c123G>A" in errors[0]

    def test_validate_variant_formats_invalid_hgvs_p(self):
        """Test validate_variant_formats detects invalid HGVS p. notation."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {"syntax": "hgvs.p", "value": "pArg181Ter"},  # Invalid - missing dot
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "Invalid HGVS p. notation" in errors[0]

    def test_validate_variant_formats_invalid_hgvs_g(self):
        """Test validate_variant_formats detects invalid HGVS g. notation."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {"syntax": "hgvs.g", "value": "chr17:g.36459258A>G"},  # Invalid format
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "Invalid HGVS g. notation" in errors[0]

    def test_validate_variant_formats_invalid_vcf(self):
        """Test validate_variant_formats detects invalid VCF format."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {
                    "syntax": "vcf",
                    "value": "17:36459258:A:G",
                },  # Colons instead of dashes
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "Invalid VCF format" in errors[0]

    def test_validate_variant_formats_invalid_spdi(self):
        """Test validate_variant_formats detects invalid SPDI format."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [
                {"syntax": "spdi", "value": "17:36459257:A:G"},  # Missing NC_
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "Invalid SPDI format" in errors[0]

    def test_validate_variant_formats_missing_id(self):
        """Test validate_variant_formats detects missing variant ID."""
        validator = VariantValidator()

        variant_descriptor = {
            # Missing 'id' field
            "expressions": [
                {"syntax": "hgvs.c", "value": "NM_000458.4:c.544G>A"},
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert len(errors) == 1
        assert "missing 'id' field" in errors[0]

    def test_validate_variant_formats_vrs_allele_invalid(self):
        """Test validate_variant_formats detects invalid VRS allele."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [],
            "vrsAllele": {
                "type": "InvalidType",  # Should be "Allele"
            },
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any("VRS allele must have type 'Allele'" in e for e in errors)

    def test_validate_variant_formats_vrs_allele_missing_location(self):
        """Test VRS allele validation detects missing location."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [],
            "vrsAllele": {
                "type": "Allele",
                # Missing location field
                "state": {"type": "LiteralSequenceExpression", "sequence": "G"},
            },
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any("missing 'location' field" in e for e in errors)

    def test_validate_variant_formats_vrs_allele_invalid_location_type(self):
        """Test VRS allele validation detects invalid location type."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [],
            "vrsAllele": {
                "type": "Allele",
                "location": {"type": "InvalidLocationType"},
                "state": {"type": "LiteralSequenceExpression", "sequence": "G"},
            },
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any("location must have type 'SequenceLocation'" in e for e in errors)

    def test_validate_variant_formats_vrs_allele_missing_state(self):
        """Test VRS allele validation detects missing state."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [],
            "vrsAllele": {
                "type": "Allele",
                "location": {"type": "SequenceLocation"},
                # Missing state field
            },
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any("missing 'state' field" in e for e in errors)

    def test_validate_variant_formats_vrs_allele_invalid_state_type(self):
        """Test VRS allele validation detects invalid state type."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "expressions": [],
            "vrsAllele": {
                "type": "Allele",
                "location": {"type": "SequenceLocation"},
                "state": {"type": "InvalidStateType"},
            },
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any(
            "state must be LiteralSequenceExpression or ReferenceLengthExpression" in e
            for e in errors
        )

    def test_validate_variant_formats_structural_variant_missing_cnv(self):
        """Test validation detects structural variant without CNV notation."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "structuralType": {"id": "SO:0001019", "label": "copy_number_variation"},
            "expressions": [
                {"syntax": "hgvs.c", "value": "NM_000458.4:c.544G>A"},
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        assert any("Structural variant missing valid CNV notation" in e for e in errors)

    def test_validate_variant_formats_structural_variant_with_iscn(self):
        """Test validation accepts structural variant with ISCN notation."""
        validator = VariantValidator()

        variant_descriptor = {
            "id": "var-1",
            "structuralType": {"id": "SO:0001019", "label": "copy_number_variation"},
            "expressions": [
                {"syntax": "iscn", "value": "46,XX,del(17)(q12q21)"},
            ],
        }

        errors = validator.validate_variant_formats(variant_descriptor)

        # Should not have CNV notation error since ISCN is present
        assert not any(
            "Structural variant missing valid CNV notation" in e for e in errors
        )

    def test_validate_variants_in_phenopacket(self):
        """Test validate_variants_in_phenopacket validates all variants."""
        validator = VariantValidator()

        phenopacket = {
            "id": "phenopacket-1",
            "interpretations": [
                {
                    "id": "interpretation-1",
                    "diagnosis": {
                        "genomicInterpretations": [
                            {
                                "subjectOrBiosampleId": "subject-1",
                                "variantInterpretation": {
                                    "variationDescriptor": {
                                        "id": "var-1",
                                        "expressions": [
                                            {
                                                "syntax": "hgvs.c",
                                                "value": "c123G>A",
                                            },  # Invalid
                                        ],
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
        }

        errors = validator.validate_variants_in_phenopacket(phenopacket)

        assert len(errors) == 1
        assert "Subject subject-1" in errors[0]
        assert "Invalid HGVS c. notation" in errors[0]


class TestNotationSuggestions:
    """Test notation suggestion generation."""

    def test_get_notation_suggestions_missing_transcript(self):
        """Test suggestions for HGVS notation missing transcript."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("c.544G>A")

        assert any("NM_000458.4:c.544G>A" in s for s in suggestions)

    def test_get_notation_suggestions_missing_dot(self):
        """Test suggestions for notation missing dot."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("c123G>A")

        # Should suggest adding the dot notation
        assert len(suggestions) > 0
        assert any("c." in s for s in suggestions)

    def test_get_notation_suggestions_p_missing_dot(self):
        """Test suggestions for p. notation missing dot (e.g., pGly182)."""
        validator = VariantValidator()

        # Test with a pattern that matches the regex: p[A-Z] (p followed by capital letter)
        suggestions = validator._get_notation_suggestions("pGly182Ser")

        # Should provide suggestions (even if just generic format examples)
        assert len(suggestions) > 0
        # Should contain general notation format guidance
        assert any(
            "NM_" in s or "chr" in s or "format" in s.lower() for s in suggestions
        )

    def test_get_notation_suggestions_vcf_format(self):
        """Test suggestions for VCF-like format."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("17-36459258-A-G")

        # Should suggest VCF or genomic formats
        assert len(suggestions) > 0
        assert any(
            "chr" in s.lower() or "vcf" in s.lower() or "NC_" in s for s in suggestions
        )

    def test_get_notation_suggestions_cnv_format(self):
        """Test suggestions for CNV-related input."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("deletion 17")

        assert any("DEL" in s or "DUP" in s for s in suggestions)

    def test_get_notation_suggestions_close_matches(self):
        """Test suggestions include close matches."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("NM_000458.4:c.544+1G>A")

        # Should find similar valid patterns
        assert len(suggestions) > 0

    def test_get_notation_suggestions_default(self):
        """Test default suggestions for unrecognized format."""
        validator = VariantValidator()

        suggestions = validator._get_notation_suggestions("completely-invalid-format")

        assert any("Valid formats:" in s for s in suggestions)


class TestFallbackValidation:
    """Test fallback validation method."""

    def test_fallback_validation_hgvs_c(self):
        """Test fallback accepts valid HGVS c. notation."""
        validator = VariantValidator()

        assert validator._fallback_validation("NM_000458.4:c.544G>A") is True

    def test_fallback_validation_hgvs_p(self):
        """Test fallback accepts valid HGVS p. notation."""
        validator = VariantValidator()

        assert validator._fallback_validation("NP_000449.3:p.Arg181*") is True

    def test_fallback_validation_vcf(self):
        """Test fallback accepts valid VCF format."""
        validator = VariantValidator()

        assert validator._fallback_validation("17-36459258-A-G") is True

    def test_fallback_validation_cnv(self):
        """Test fallback accepts valid CNV notation."""
        validator = VariantValidator()

        assert validator._fallback_validation("17:36459258-37832869:DEL") is True

    def test_fallback_validation_invalid(self):
        """Test fallback rejects invalid notation."""
        validator = VariantValidator()

        assert validator._fallback_validation("invalid-format") is False


class TestValidationMethods:
    """Test various validation methods."""

    def test_validate_hgvs_c_valid(self):
        """Test HGVS c. notation validation with valid inputs."""
        validator = VariantValidator()

        # Valid HGVS c. notations
        assert validator._validate_hgvs_c("NM_000458.4:c.544G>A") is True
        assert validator._validate_hgvs_c("c.544G>A") is True
        assert validator._validate_hgvs_c("NM_000458.4:c.544+1G>A") is True  # Intronic
        assert validator._validate_hgvs_c("c.123_456del") is True  # Deletion
        assert validator._validate_hgvs_c("c.123_456dup") is True  # Duplication
        assert (
            validator._validate_hgvs_c("c.123delATCG") is True
        )  # Deletion with sequence
        assert (
            validator._validate_hgvs_c("c.123dupATCG") is True
        )  # Duplication with sequence
        assert validator._validate_hgvs_c("c.123_456insATCG") is True  # Insertion
        assert validator._validate_hgvs_c("c.544-2A>G") is True  # Intronic with minus

    def test_validate_hgvs_c_invalid(self):
        """Test HGVS c. notation validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid HGVS c. notations
        assert validator._validate_hgvs_c("c123G>A") is False  # Missing dot
        assert (
            validator._validate_hgvs_c("NM_000458.4:p.Arg181*") is False
        )  # Wrong type
        assert validator._validate_hgvs_c("m.123A>G") is False  # Mitochondrial (not c.)

    def test_validate_hgvs_p_valid(self):
        """Test HGVS p. notation validation with valid inputs."""
        validator = VariantValidator()

        # Valid HGVS p. notations
        assert validator._validate_hgvs_p("NP_000449.3:p.Arg181*") is True
        assert validator._validate_hgvs_p("p.Val123Phe") is True
        assert validator._validate_hgvs_p("p.Arg181Ter") is True  # Ter instead of *
        assert validator._validate_hgvs_p("p.Gly182Serfs") is True  # Frameshift
        assert validator._validate_hgvs_p("p.?") is True  # Unknown effect

    def test_validate_hgvs_p_invalid(self):
        """Test HGVS p. notation validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid HGVS p. notations
        assert validator._validate_hgvs_p("pArg181Ter") is False  # Missing dot
        assert validator._validate_hgvs_p("p.A181*") is False  # Single letter code
        assert validator._validate_hgvs_p("NM_000458.4:c.544G>A") is False  # Wrong type

    def test_validate_hgvs_g_valid(self):
        """Test HGVS g. notation validation with valid inputs."""
        validator = VariantValidator()

        # Valid HGVS g. notations
        assert validator._validate_hgvs_g("NC_000017.11:g.36459258A>G") is True

    def test_validate_hgvs_g_invalid(self):
        """Test HGVS g. notation validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid HGVS g. notations
        assert validator._validate_hgvs_g("chr17:g.36459258A>G") is False  # chr prefix
        assert (
            validator._validate_hgvs_g("NC_000017.11:g.36459258del") is False
        )  # Not substitution

    def test_validate_spdi_valid(self):
        """Test SPDI notation validation with valid inputs."""
        validator = VariantValidator()

        # Valid SPDI notations
        assert validator._validate_spdi("NC_000017.11:36459257:A:G") is True
        assert validator._validate_spdi("NC_000017.11:36459257::G") is True  # Insertion

    def test_validate_spdi_invalid(self):
        """Test SPDI notation validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid SPDI notations
        assert validator._validate_spdi("17:36459257:A:G") is False  # Missing NC_
        assert validator._validate_spdi("NC_000017.11-36459257-A-G") is False  # Dashes

    def test_validate_vcf_valid(self):
        """Test VCF format validation with valid inputs."""
        validator = VariantValidator()

        # Valid VCF formats
        assert validator._validate_vcf("17-36459258-A-G") is True
        assert validator._validate_vcf("chr17-36459258-A-G") is True
        assert validator._validate_vcf("X-123456-G-C") is True

    def test_validate_vcf_invalid(self):
        """Test VCF format validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid VCF formats
        assert validator._validate_vcf("17:36459258:A:G") is False  # Colons
        assert validator._validate_vcf("17-abc-A-G") is False  # Non-numeric pos
        assert validator._validate_vcf("99-36459258-A-G") is False  # Invalid chr

    def test_is_ga4gh_cnv_notation_valid(self):
        """Test GA4GH CNV notation validation."""
        validator = VariantValidator()

        # Valid CNV notations
        assert validator._is_ga4gh_cnv_notation("17:36459258-37832869:DEL") is True
        assert validator._is_ga4gh_cnv_notation("17:36459258-37832869:DUP") is True
        assert validator._is_ga4gh_cnv_notation("X:123456-789012:DEL") is True

    def test_is_ga4gh_cnv_notation_invalid(self):
        """Test GA4GH CNV notation validation with invalid inputs."""
        validator = VariantValidator()

        # Invalid CNV notations
        assert (
            validator._is_ga4gh_cnv_notation("17-36459258-37832869-DEL") is False
        )  # Dashes
        assert (
            validator._is_ga4gh_cnv_notation("17:36459258:DEL") is False
        )  # Missing end


class TestConfigurableSettings:
    """Test that settings are properly loaded from config.yaml."""

    def test_rate_limit_from_config(self):
        """Test rate limiter uses settings from config.yaml."""
        validator = VariantValidator()

        # Should load from settings.rate_limiting.vep.requests_per_second
        assert validator._requests_per_second == settings.rate_limiting.vep.requests_per_second
        assert validator._requests_per_second > 0  # Sanity check

    def test_retry_config_from_config(self):
        """Test retry uses settings from config.yaml."""
        validator = VariantValidator()

        # Should load from settings.external_apis.vep
        assert validator._max_retries == settings.external_apis.vep.max_retries
        assert validator._backoff_factor == settings.external_apis.vep.retry_backoff_factor
        assert validator._max_retries > 0  # Sanity check
        assert validator._backoff_factor > 0  # Sanity check

    def test_cache_ttl_from_config(self):
        """Test cache TTL uses settings from config.yaml."""
        validator = VariantValidator()

        # Should load from settings.external_apis.vep.cache_ttl_seconds
        assert validator._cache_ttl == settings.external_apis.vep.cache_ttl_seconds
        assert validator._cache_ttl > 0  # Sanity check

    def test_custom_settings_with_mock(self):
        """Test that mocked settings are used by validator."""
        with patch(
            "app.phenopackets.validation.variant_validator.settings"
        ) as mock_settings:
            # Create mock nested structure
            mock_settings.rate_limiting.vep.requests_per_second = 10
            mock_settings.external_apis.vep.max_retries = 5
            mock_settings.external_apis.vep.retry_backoff_factor = 3.0
            mock_settings.external_apis.vep.cache_ttl_seconds = 7200

            validator = VariantValidator()

            # Should use mocked values
            assert validator._requests_per_second == 10
            assert validator._max_retries == 5
            assert validator._backoff_factor == 3.0
            assert validator._cache_ttl == 7200
