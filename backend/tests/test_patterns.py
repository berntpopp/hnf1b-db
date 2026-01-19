"""Tests for centralized regex patterns module.

Tests cover all pattern validation functions to ensure:
1. Valid inputs are accepted
2. Invalid inputs are rejected
3. Edge cases are handled correctly
4. Security patterns prevent injection
"""

import pytest

from app.core.patterns import (
    CNV_PATTERN,
    HG38_PATTERN,
    HG38_SIMPLE_PATTERN,
    HGVS_C_PATTERNS,
    HGVS_C_SEARCH_PATTERN,
    HGVS_G_PATTERN,
    HGVS_G_SEARCH_PATTERN,
    HGVS_P_PATTERN,
    HGVS_P_SEARCH_PATTERN,
    HPO_PATTERN,
    MONDO_PATTERN,
    PMID_PATTERN,
    SEARCH_WHITELIST_PATTERN,
    SPDI_PATTERN,
    VCF_PATTERN,
    VCF_SIMPLE_PATTERN,
    is_cnv_format,
    is_hg38_coordinate,
    is_hgvs_c,
    is_hgvs_g,
    is_hgvs_p,
    is_safe_search_query,
    is_valid_pmid,
    is_vcf_format,
    normalize_pmid,
)


class TestVCFPatterns:
    """Tests for VCF format patterns."""

    @pytest.mark.parametrize(
        "variant",
        [
            "17-36459258-A-G",
            "chr17-36459258-A-G",
            "1-12345-ATCG-A",
            "22-100-A-T",
            "X-1000-G-C",
            "Y-500-T-A",
            "M-200-C-G",
        ],
    )
    def test_patterns_vcf_valid_input_matches(self, variant):
        """Test VCF pattern matches valid formats."""
        assert VCF_PATTERN.match(variant)
        assert is_vcf_format(variant)

    @pytest.mark.parametrize(
        "variant",
        [
            "invalid",
            "17:36459258-A-G",  # Wrong separator
            "17-36459258-A",  # Missing alt
            "17-36459258--G",  # Missing ref
            "chr23-100-A-G",  # Invalid chromosome
            "17-abc-A-G",  # Non-numeric position
        ],
    )
    def test_patterns_vcf_invalid_input_no_match(self, variant):
        """Test VCF pattern rejects invalid formats."""
        assert not is_vcf_format(variant)

    def test_patterns_vcf_simple_quick_check_matches(self):
        """Test simple VCF pattern for quick checks."""
        assert VCF_SIMPLE_PATTERN.match("17-36459258-A-G")
        assert VCF_SIMPLE_PATTERN.match("chr17-100-ACGT-T")
        assert not VCF_SIMPLE_PATTERN.match("invalid")


class TestCNVPatterns:
    """Tests for CNV/structural variant patterns."""

    @pytest.mark.parametrize(
        "variant",
        [
            "17:36459258-37832869:DEL",
            "X:1000-2000:DUP",
            "1:100-200:INS",
            "22:5000-10000:INV",
        ],
    )
    def test_patterns_cnv_valid_input_matches(self, variant):
        """Test CNV pattern matches valid formats."""
        assert CNV_PATTERN.match(variant)
        assert is_cnv_format(variant)

    @pytest.mark.parametrize(
        "variant",
        [
            "chr17:36459258-37832869:DEL",  # chr prefix not allowed
            "17-36459258-37832869:DEL",  # Wrong separator
            "17:36459258:DEL",  # Missing end position
            "17:36459258-37832869:UNKNOWN",  # Invalid type
            "0:100-200:DEL",  # Invalid chromosome
        ],
    )
    def test_patterns_cnv_invalid_input_no_match(self, variant):
        """Test CNV pattern rejects invalid formats."""
        assert not is_cnv_format(variant)


class TestHGVSCPatterns:
    """Tests for HGVS c. notation patterns."""

    @pytest.mark.parametrize(
        "variant",
        [
            "c.544+1G>A",
            "c.123A>G",
            "NM_000458.4:c.544+1G>A",
            "c.123del",
            "c.123_456del",
            "c.123dup",
            "c.123_124insATG",
            "c.123delinsAT",
        ],
    )
    def test_patterns_hgvs_c_valid_input_matches(self, variant):
        """Test HGVS c. pattern matches valid formats."""
        assert is_hgvs_c(variant)

    @pytest.mark.parametrize(
        "variant",
        [
            "p.Arg181Ter",  # Wrong prefix
            "g.123A>G",  # Wrong prefix
            "c.",  # Incomplete
            "c.abc",  # Non-numeric
            "invalid",
        ],
    )
    def test_patterns_hgvs_c_invalid_input_no_match(self, variant):
        """Test HGVS c. pattern rejects invalid formats."""
        assert not is_hgvs_c(variant)

    def test_patterns_hgvs_c_search_pattern_validates_user_input(self):
        """Test HGVS c. search pattern for user input validation."""
        assert HGVS_C_SEARCH_PATTERN.match("c.544+1G>A")
        assert HGVS_C_SEARCH_PATTERN.match("c.123del")
        assert HGVS_C_SEARCH_PATTERN.match("c.123dup")
        assert not HGVS_C_SEARCH_PATTERN.match("invalid")


class TestHGVSPPatterns:
    """Tests for HGVS p. notation patterns."""

    @pytest.mark.parametrize(
        "variant",
        [
            "p.Arg181Ter",
            "p.Val123Phe",
            "p.(Ser546Phe)",
            "p.Arg181*",
            "NP_000449.1:p.Arg181Ter",
            "p.Lys100del",
        ],
    )
    def test_patterns_hgvs_p_valid_input_matches(self, variant):
        """Test HGVS p. pattern matches valid formats."""
        assert is_hgvs_p(variant)

    @pytest.mark.parametrize(
        "variant",
        [
            "c.123A>G",  # Wrong prefix
            "p.",  # Incomplete
            "p.123",  # Missing amino acid
            "p.arg181ter",  # Wrong case
            "invalid",
        ],
    )
    def test_patterns_hgvs_p_invalid_input_no_match(self, variant):
        """Test HGVS p. pattern rejects invalid formats."""
        assert not is_hgvs_p(variant)

    def test_patterns_hgvs_p_search_pattern_validates_user_input(self):
        """Test HGVS p. search pattern for user input validation."""
        assert HGVS_P_SEARCH_PATTERN.match("p.Arg181Ter")
        assert HGVS_P_SEARCH_PATTERN.match("p.(Val123Phe)")
        assert not HGVS_P_SEARCH_PATTERN.match("invalid")


class TestHGVSGPatterns:
    """Tests for HGVS g. notation patterns."""

    @pytest.mark.parametrize(
        "variant",
        [
            "NC_000017.11:g.36459258A>G",
            "NC_000001.10:g.12345C>T",
        ],
    )
    def test_patterns_hgvs_g_valid_input_matches(self, variant):
        """Test HGVS g. pattern matches valid formats."""
        assert HGVS_G_PATTERN.match(variant)
        assert is_hgvs_g(variant)

    @pytest.mark.parametrize(
        "variant",
        [
            "g.36459258A>G",  # Missing accession
            "NC_000017:g.36459258A>G",  # Missing version
            "NC_000017.11:g.A>G",  # Missing position
            "invalid",
        ],
    )
    def test_patterns_hgvs_g_invalid_input_no_match(self, variant):
        """Test HGVS g. pattern rejects invalid formats."""
        assert not is_hgvs_g(variant)

    def test_patterns_hgvs_g_search_pattern_validates_user_input(self):
        """Test HGVS g. search pattern for user input validation."""
        assert HGVS_G_SEARCH_PATTERN.match("g.36459258A>G")
        assert HGVS_G_SEARCH_PATTERN.match("g.123del")
        assert not HGVS_G_SEARCH_PATTERN.match("invalid")


class TestHG38Patterns:
    """Tests for HG38 coordinate patterns."""

    @pytest.mark.parametrize(
        "coord",
        [
            "chr17:36098063",
            "17:36098063",
            "17:36459258-37832869",
            "chr17:36459258-37832869:DEL",
            "X:1000",
            "Y:500-1000",
        ],
    )
    def test_patterns_hg38_valid_input_matches(self, coord):
        """Test HG38 pattern matches valid coordinates."""
        assert HG38_PATTERN.match(coord)
        assert is_hg38_coordinate(coord)

    @pytest.mark.parametrize(
        "coord",
        [
            "invalid",
            "chr:123",  # Missing chromosome number
            "17",  # Missing position
        ],
    )
    def test_patterns_hg38_invalid_input_no_match(self, coord):
        """Test HG38 pattern rejects invalid coordinates."""
        assert not is_hg38_coordinate(coord)

    def test_patterns_hg38_simple_quick_check_matches(self):
        """Test simple HG38 pattern for quick checks."""
        assert HG38_SIMPLE_PATTERN.match("chr17:36098063")
        assert HG38_SIMPLE_PATTERN.match("17-36098063")
        assert not HG38_SIMPLE_PATTERN.match("invalid")


class TestIdentifierPatterns:
    """Tests for identifier patterns (PMID, SPDI)."""

    @pytest.mark.parametrize(
        "pmid",
        [
            "PMID:12345678",
            "PMID:1",
            "PMID:123",
        ],
    )
    def test_patterns_pmid_valid_input_matches(self, pmid):
        """Test PMID pattern matches valid formats."""
        assert PMID_PATTERN.match(pmid)
        assert is_valid_pmid(pmid)

    @pytest.mark.parametrize(
        "pmid",
        [
            "12345678",  # Missing prefix
            "PMID:123456789",  # Too long (9 digits)
            "PMID:",  # Missing number
            "pmid:123",  # Wrong case
            "invalid",
        ],
    )
    def test_patterns_pmid_invalid_input_no_match(self, pmid):
        """Test PMID pattern rejects invalid formats."""
        assert not is_valid_pmid(pmid)

    def test_patterns_pmid_normalize_with_prefix_unchanged(self):
        """Test normalize_pmid with existing prefix."""
        assert normalize_pmid("PMID:12345678") == "PMID:12345678"

    def test_patterns_pmid_normalize_without_prefix_adds_prefix(self):
        """Test normalize_pmid adds prefix."""
        assert normalize_pmid("12345678") == "PMID:12345678"
        assert normalize_pmid("123") == "PMID:123"

    def test_patterns_pmid_normalize_invalid_raises_error(self):
        """Test normalize_pmid raises for invalid format."""
        with pytest.raises(ValueError, match="Invalid PMID format"):
            normalize_pmid("123456789")  # Too long

    def test_patterns_spdi_valid_input_matches(self):
        """Test SPDI pattern."""
        assert SPDI_PATTERN.match("NC_000017.11:36459257:A:G")
        assert SPDI_PATTERN.match("NC_000001.10:100::T")  # Empty deleted
        assert not SPDI_PATTERN.match("invalid")


class TestOntologyPatterns:
    """Tests for ontology term patterns."""

    @pytest.mark.parametrize(
        "term",
        [
            "HP:0000001",
            "HP:1234567",
            "HP:0001622",
        ],
    )
    def test_patterns_hpo_valid_input_matches(self, term):
        """Test HPO pattern matches valid formats."""
        assert HPO_PATTERN.match(term)

    @pytest.mark.parametrize(
        "term",
        [
            "HP:123456",  # Too short
            "HP:12345678",  # Too long
            "HP123456",  # Missing colon
            "hp:0000001",  # Wrong case
            "MONDO:0000001",  # Wrong ontology
        ],
    )
    def test_patterns_hpo_invalid_input_no_match(self, term):
        """Test HPO pattern rejects invalid formats."""
        assert not HPO_PATTERN.match(term)

    @pytest.mark.parametrize(
        "term",
        [
            "MONDO:0000001",
            "MONDO:1234567",
        ],
    )
    def test_patterns_mondo_valid_input_matches(self, term):
        """Test MONDO pattern matches valid formats."""
        assert MONDO_PATTERN.match(term)

    @pytest.mark.parametrize(
        "term",
        [
            "MONDO:123456",  # Too short
            "MONDO:12345678",  # Too long
            "HP:0000001",  # Wrong ontology
        ],
    )
    def test_patterns_mondo_invalid_input_no_match(self, term):
        """Test MONDO pattern rejects invalid formats."""
        assert not MONDO_PATTERN.match(term)


class TestSecurityPatterns:
    """Tests for security-related patterns."""

    @pytest.mark.parametrize(
        "query",
        [
            "c.544+1G>A",
            "p.Arg181Ter",
            "17:36459258",
            "HNF1B",
            "test query",
            "variant-1/2",
            "score=10",
        ],
    )
    def test_patterns_search_whitelist_valid_input_allowed(self, query):
        """Test search whitelist accepts safe queries."""
        assert SEARCH_WHITELIST_PATTERN.match(query)
        assert is_safe_search_query(query)

    @pytest.mark.parametrize(
        "query",
        [
            "'; DROP TABLE--",
            "<script>alert(1)</script>",
            "test$variable",
            "query%20encoded",
            "test\\escape",
            "SELECT * FROM users;",
            "test'injection",
            'test"quotes',
            "test|pipe",
            "test&ampersand",
            "test`backtick`",
        ],
    )
    def test_patterns_search_whitelist_injection_attempt_blocked(self, query):
        """Test search whitelist rejects SQL injection attempts."""
        assert not is_safe_search_query(query)

    def test_patterns_search_whitelist_empty_query_rejected(self):
        """Test that empty queries are rejected."""
        assert not is_safe_search_query("")


class TestPatternConsistency:
    """Tests to ensure patterns are consistent across modules."""

    def test_patterns_all_precompiled_for_performance(self):
        """Verify all patterns are pre-compiled for performance."""
        import re

        patterns = [
            VCF_PATTERN,
            VCF_SIMPLE_PATTERN,
            CNV_PATTERN,
            HG38_PATTERN,
            HG38_SIMPLE_PATTERN,
            HGVS_G_PATTERN,
            HGVS_P_PATTERN,
            HGVS_C_SEARCH_PATTERN,
            HGVS_P_SEARCH_PATTERN,
            HGVS_G_SEARCH_PATTERN,
            PMID_PATTERN,
            SPDI_PATTERN,
            HPO_PATTERN,
            MONDO_PATTERN,
            SEARCH_WHITELIST_PATTERN,
        ]

        for pattern in patterns:
            assert isinstance(pattern, re.Pattern), (
                f"{pattern} is not a compiled pattern"
            )

    def test_patterns_hgvs_c_list_contains_compiled_patterns(self):
        """Verify HGVS_C_PATTERNS is a list of patterns."""
        import re

        assert isinstance(HGVS_C_PATTERNS, list)
        assert len(HGVS_C_PATTERNS) > 0
        for pattern in HGVS_C_PATTERNS:
            assert isinstance(pattern, re.Pattern), (
                f"{pattern} is not a compiled pattern"
            )


class TestRealWorldVariants:
    """Tests using real HNF1B variants from the database."""

    @pytest.mark.parametrize(
        "variant",
        [
            "NM_000458.4:c.544+1G>A",  # Splice site
            "c.1654-2A>T",  # Splice site
            "c.826C>T",  # Substitution
            "p.Arg181*",  # Nonsense
            "p.(Ser546Phe)",  # Missense with parentheses
            "17:36459258-37832869:DEL",  # CNV
        ],
    )
    def test_patterns_real_hnf1b_variant_matches_pattern(self, variant):
        """Test patterns work with real HNF1B variants."""
        # Should match at least one pattern
        matched = (
            is_hgvs_c(variant)
            or is_hgvs_p(variant)
            or is_cnv_format(variant)
            or is_vcf_format(variant)
        )
        assert matched, f"No pattern matched real variant: {variant}"
