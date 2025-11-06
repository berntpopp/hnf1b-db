"""Tests for variant search endpoint.

This module tests the /aggregate/all-variants endpoint with search and filter
capabilities, including security validation, HGVS notation search, and molecular
consequence filtering.
"""

import pytest
from fastapi import HTTPException

from app.phenopackets.molecular_consequence import (
    compute_molecular_consequence,
    filter_by_consequence,
)
from app.phenopackets.variant_search_validation import (
    validate_classification,
    validate_gene,
    validate_hg38_coordinate,
    validate_hgvs_notation,
    validate_molecular_consequence,
    validate_search_query,
    validate_variant_type,
)


class TestHGVSValidation:
    """Test HGVS notation format validation."""

    def test_valid_c_notation(self):
        """Test valid c. notations."""
        assert validate_hgvs_notation("c.1654-2A>T") is True
        assert validate_hgvs_notation("c.544+1G>T") is True
        assert validate_hgvs_notation("c.1621C>T") is True
        assert validate_hgvs_notation("c.1654_1656del") is True

    def test_valid_p_notation(self):
        """Test valid p. notations."""
        assert validate_hgvs_notation("p.Arg177Ter") is True
        assert validate_hgvs_notation("p.(Ser546Phe)") is True
        assert validate_hgvs_notation("p.Gly319del") is True

    def test_valid_g_notation(self):
        """Test valid g. notations."""
        assert validate_hgvs_notation("g.36098063A>T") is True
        assert validate_hgvs_notation("g.36459258_37832869del") is True

    def test_invalid_hgvs(self):
        """Test invalid HGVS formats."""
        assert validate_hgvs_notation("invalid") is False
        assert validate_hgvs_notation("c.invalid") is False
        assert validate_hgvs_notation("x.123A>T") is False


class TestHG38Validation:
    """Test HG38 genomic coordinate validation."""

    def test_valid_coordinates(self):
        """Test valid HG38 coordinate formats."""
        assert validate_hg38_coordinate("chr17:36098063") is True
        assert validate_hg38_coordinate("chr17-36098063-A-T") is True
        assert validate_hg38_coordinate("17:36459258-37832869") is True
        assert validate_hg38_coordinate("17:36459258-37832869:DEL") is True
        assert validate_hg38_coordinate("chrX:12345") is True
        assert validate_hg38_coordinate("chrY:67890") is True

    def test_invalid_coordinates(self):
        """Test invalid coordinate formats."""
        assert validate_hg38_coordinate("invalid:format") is False
        assert validate_hg38_coordinate("chr:123") is False
        assert validate_hg38_coordinate("abc:123") is False


class TestSearchQueryValidation:
    """Test search query validation and sanitization."""

    def test_valid_search_queries(self):
        """Test valid search queries."""
        assert validate_search_query("c.1654-2A>T") == "c.1654-2A>T"
        assert validate_search_query("chr17:36098063") == "chr17:36098063"
        assert validate_search_query("HNF1B") == "HNF1B"
        assert validate_search_query("Var1") == "Var1"

    def test_query_too_long(self):
        """Test length limit enforcement."""
        long_query = "A" * 201
        with pytest.raises(HTTPException) as exc:
            validate_search_query(long_query)
        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail

    def test_query_invalid_characters(self):
        """Test character whitelist enforcement (SQL injection prevention)."""
        with pytest.raises(HTTPException) as exc:
            validate_search_query("'; DROP TABLE phenopackets;--")
        assert exc.value.status_code == 400
        assert "invalid characters" in exc.value.detail

    def test_query_special_characters_allowed(self):
        """Test that allowed special characters work."""
        assert validate_search_query("c.123+1G>T") is not None
        assert validate_search_query("p.(Arg177*)") is not None

    def test_invalid_hgvs_format(self):
        """Test HGVS format validation."""
        with pytest.raises(HTTPException) as exc:
            validate_search_query("c.invalid")
        assert exc.value.status_code == 400
        assert "Invalid HGVS" in exc.value.detail


class TestVariantTypeValidation:
    """Test variant type filter validation."""

    def test_valid_variant_types(self):
        """Test valid variant types."""
        assert validate_variant_type("SNV") == "SNV"
        assert validate_variant_type("deletion") == "deletion"
        assert validate_variant_type("duplication") == "duplication"
        assert validate_variant_type("insertion") == "insertion"
        assert validate_variant_type("inversion") == "inversion"
        assert validate_variant_type("CNV") == "CNV"

    def test_invalid_variant_type(self):
        """Test invalid variant type."""
        with pytest.raises(HTTPException) as exc:
            validate_variant_type("invalid_type")
        assert exc.value.status_code == 400
        assert "Invalid variant type" in exc.value.detail

    def test_none_variant_type(self):
        """Test None returns None."""
        assert validate_variant_type(None) is None


class TestClassificationValidation:
    """Test ACMG classification filter validation."""

    def test_valid_classifications(self):
        """Test valid classifications."""
        assert validate_classification("PATHOGENIC") == "PATHOGENIC"
        assert (
            validate_classification("LIKELY_PATHOGENIC") == "LIKELY_PATHOGENIC"
        )
        assert (
            validate_classification("UNCERTAIN_SIGNIFICANCE")
            == "UNCERTAIN_SIGNIFICANCE"
        )
        assert validate_classification("LIKELY_BENIGN") == "LIKELY_BENIGN"
        assert validate_classification("BENIGN") == "BENIGN"

    def test_invalid_classification(self):
        """Test invalid classification."""
        with pytest.raises(HTTPException) as exc:
            validate_classification("INVALID")
        assert exc.value.status_code == 400
        assert "Invalid classification" in exc.value.detail


class TestGeneValidation:
    """Test gene symbol filter validation."""

    def test_valid_gene(self):
        """Test valid gene symbol."""
        assert validate_gene("HNF1B") == "HNF1B"

    def test_invalid_gene(self):
        """Test invalid gene symbol."""
        with pytest.raises(HTTPException) as exc:
            validate_gene("INVALID_GENE")
        assert exc.value.status_code == 400
        assert "Invalid gene" in exc.value.detail


class TestMolecularConsequenceValidation:
    """Test molecular consequence filter validation."""

    def test_valid_consequences(self):
        """Test valid molecular consequences."""
        assert validate_molecular_consequence("Frameshift") == "Frameshift"
        assert validate_molecular_consequence("Nonsense") == "Nonsense"
        assert validate_molecular_consequence("Missense") == "Missense"
        assert validate_molecular_consequence("Splice Donor") == "Splice Donor"

    def test_invalid_consequence(self):
        """Test invalid molecular consequence."""
        with pytest.raises(HTTPException) as exc:
            validate_molecular_consequence("Invalid Consequence")
        assert exc.value.status_code == 400
        assert "Invalid molecular consequence" in exc.value.detail


class TestMolecularConsequenceComputation:
    """Test molecular consequence computation from HGVS notations."""

    def test_frameshift(self):
        """Test frameshift detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Arg177fs",
            variant_type=None
        )
        assert result == "Frameshift"

    def test_nonsense(self):
        """Test nonsense/stop-gained detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Arg177Ter",
            variant_type=None
        )
        assert result == "Nonsense"

        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Arg177*",
            variant_type=None
        )
        assert result == "Nonsense"

    def test_missense(self):
        """Test missense detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Arg177Cys",
            variant_type=None
        )
        assert result == "Missense"

    def test_inframe_deletion(self):
        """Test in-frame deletion detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Gly319del",
            variant_type=None
        )
        assert result == "In-frame Deletion"

    def test_splice_donor(self):
        """Test splice donor detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.544+1G>T",
            protein=None,
            variant_type=None
        )
        assert result == "Splice Donor"

    def test_splice_acceptor(self):
        """Test splice acceptor detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.1654-2A>T",
            protein=None,
            variant_type=None
        )
        assert result == "Splice Acceptor"

    def test_intronic_variant(self):
        """Test intronic variant detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.544+15G>T",
            protein=None,
            variant_type=None
        )
        assert result == "Intronic Variant"

    def test_copy_number_loss(self):
        """Test copy number loss (deletion) detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein=None,
            variant_type="deletion"
        )
        assert result == "Copy Number Loss"

    def test_copy_number_gain(self):
        """Test copy number gain (duplication) detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein=None,
            variant_type="duplication"
        )
        assert result == "Copy Number Gain"

    def test_synonymous(self):
        """Test synonymous variant detection."""
        result = compute_molecular_consequence(
            transcript=None,
            protein="NP_000449.3:p.Arg177=",
            variant_type=None
        )
        assert result == "Synonymous"


class TestConsequenceFiltering:
    """Test molecular consequence filtering."""

    def test_filter_by_consequence(self):
        """Test filtering variants by molecular consequence."""
        variants = [
            {
                "variant_id": "var1",
                "transcript": "NM_000458.4:c.544+1G>T",
                "protein": None,
                "structural_type": "SNV"
            },
            {
                "variant_id": "var2",
                "transcript": None,
                "protein": "NP_000449.3:p.Arg177Ter",
                "structural_type": "SNV"
            },
            {
                "variant_id": "var3",
                "transcript": "NM_000458.4:c.1654-2A>T",
                "protein": None,
                "structural_type": "SNV"
            },
        ]

        # Filter for splice donors
        filtered = filter_by_consequence(variants, "Splice Donor")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var1"

        # Filter for nonsense
        filtered = filter_by_consequence(variants, "Nonsense")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var2"

        # Filter for splice acceptor
        filtered = filter_by_consequence(variants, "Splice Acceptor")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var3"

    def test_no_filter(self):
        """Test that None filter returns all variants."""
        variants = [{"variant_id": "var1"}, {"variant_id": "var2"}]
        filtered = filter_by_consequence(variants, None)
        assert len(filtered) == 2


# Integration tests would go here (requires database setup)
# Example:
# @pytest.mark.asyncio
# async def test_variant_search_endpoint():
#     """Test the full /aggregate/all-variants endpoint."""
#     # Would require FastAPI TestClient and database fixture
#     pass
