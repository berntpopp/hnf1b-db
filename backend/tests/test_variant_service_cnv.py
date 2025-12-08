"""Tests for CNV format handling in variant service.

Tests the validate_variant_id and _format_variant_for_vep functions
for proper handling of various CNV formats including the new 5-part format
with END position (CHROM-POS-END-REF-<TYPE>).
"""

import pytest

from app.variants.service import (
    _format_variant_for_vep,
    is_cnv_variant,
    validate_variant_id,
)


class TestIsCnvVariant:
    """Test CNV variant detection."""

    def test_snv_not_cnv(self):
        """Test SNV is not detected as CNV."""
        assert is_cnv_variant("17-36459258-A-G") is False

    def test_cnv_symbolic_del(self):
        """Test symbolic deletion is detected as CNV."""
        assert is_cnv_variant("17-36459258-A-<DEL>") is True

    def test_cnv_symbolic_dup(self):
        """Test symbolic duplication is detected as CNV."""
        assert is_cnv_variant("17-36459258-A-<DUP>") is True

    def test_cnv_region_format(self):
        """Test region format CNV is detected."""
        assert is_cnv_variant("17-36459258-37832869-DEL") is True

    def test_cnv_with_end_position(self):
        """Test 5-part CNV with END position is detected."""
        assert is_cnv_variant("17-37733556-37733821-C-<DEL>") is True


class TestValidateVariantId:
    """Test variant ID validation and normalization."""

    # SNV format tests
    def test_snv_basic(self):
        """Test basic SNV format."""
        result = validate_variant_id("17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_snv_with_chr_prefix(self):
        """Test SNV with chr prefix is normalized."""
        result = validate_variant_id("chr17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_snv_lowercase(self):
        """Test SNV with lowercase is uppercased."""
        result = validate_variant_id("17-36459258-a-g")
        assert result == "17-36459258-A-G"

    def test_snv_x_chromosome(self):
        """Test SNV on X chromosome."""
        result = validate_variant_id("X-12345-C-T")
        assert result == "X-12345-C-T"

    # CNV symbolic format (4-part) tests
    def test_cnv_symbolic_del(self):
        """Test 4-part CNV symbolic deletion."""
        result = validate_variant_id("17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_cnv_symbolic_dup(self):
        """Test 4-part CNV symbolic duplication."""
        result = validate_variant_id("17-36459258-A-<DUP>")
        assert result == "17-36459258-A-<DUP>"

    def test_cnv_symbolic_with_chr_prefix(self):
        """Test CNV symbolic with chr prefix is normalized."""
        result = validate_variant_id("chr17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    # CNV with END position (5-part) tests
    def test_cnv_with_end_del(self):
        """Test 5-part CNV deletion with END position."""
        result = validate_variant_id("17-37733556-37733821-C-<DEL>")
        assert result == "17-37733556-37733821-C-<DEL>"

    def test_cnv_with_end_dup(self):
        """Test 5-part CNV duplication with END position."""
        result = validate_variant_id("17-36459258-37832869-C-<DUP>")
        assert result == "17-36459258-37832869-C-<DUP>"

    def test_cnv_with_end_chr_prefix(self):
        """Test 5-part CNV with chr prefix is normalized."""
        result = validate_variant_id("chr17-37733556-37733821-C-<DEL>")
        assert result == "17-37733556-37733821-C-<DEL>"

    def test_cnv_with_end_lowercase(self):
        """Test 5-part CNV with lowercase is uppercased."""
        result = validate_variant_id("17-37733556-37733821-c-<del>")
        assert result == "17-37733556-37733821-C-<DEL>"

    # CNV region format tests
    def test_cnv_region_del(self):
        """Test CNV region format deletion."""
        result = validate_variant_id("17-36459258-37832869-DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_cnv_region_dup(self):
        """Test CNV region format duplication."""
        result = validate_variant_id("17-36459258-37832869-DUP")
        assert result == "17-36459258-37832869-DUP"

    def test_cnv_region_with_colon(self):
        """Test CNV region format with colon separator is normalized."""
        result = validate_variant_id("17:36459258-37832869:DEL")
        assert result == "17-36459258-37832869-DEL"

    # Invalid format tests
    def test_invalid_format_raises(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError):
            validate_variant_id("invalid-format")

    def test_cnv_disabled_raises(self):
        """Test CNV format raises when CNV not allowed."""
        with pytest.raises(ValueError):
            validate_variant_id("17-36459258-A-<DEL>", allow_cnv=False)


class TestFormatVariantForVep:
    """Test VEP format conversion."""

    # SNV format tests
    def test_snv_format(self):
        """Test SNV converts to VCF format for VEP."""
        result = _format_variant_for_vep("17-36459258-A-G")
        assert result == "17 36459258 17-36459258-A-G A G . . ."

    # CNV symbolic format (4-part) tests
    def test_cnv_symbolic_no_end(self):
        """Test 4-part CNV symbolic uses same start/end."""
        result = _format_variant_for_vep("17-36459258-A-<DEL>")
        assert result == "17 36459258 36459258 DEL + 17-36459258-A-<DEL>"

    # CNV with END position (5-part) tests
    def test_cnv_with_end_format(self):
        """Test 5-part CNV converts to VEP SV format with actual coordinates."""
        result = _format_variant_for_vep("17-37733556-37733821-C-<DEL>")
        assert result == "17 37733556 37733821 DEL + 17-37733556-37733821-C-<DEL>"

    def test_cnv_with_end_dup_format(self):
        """Test 5-part CNV duplication converts correctly."""
        result = _format_variant_for_vep("17-36459258-37832869-C-<DUP>")
        assert result == "17 36459258 37832869 DUP + 17-36459258-37832869-C-<DUP>"

    # CNV region format tests
    def test_cnv_region_format(self):
        """Test CNV region format converts to VEP SV format."""
        result = _format_variant_for_vep("17-36459258-37832869-DEL")
        assert result == "17 36459258 37832869 DEL + 17-36459258-37832869-DEL"

    # Invalid format tests
    def test_invalid_format_returns_none(self):
        """Test invalid format returns None."""
        result = _format_variant_for_vep("invalid")
        assert result is None


class TestRealWorldCnvFormats:
    """Test real-world CNV formats from the HNF1B database."""

    def test_hnf1b_deletion_with_end(self):
        """Test real HNF1B deletion format with END position."""
        variant = "17-37733556-37733821-C-<DEL>"
        # Validate
        validated = validate_variant_id(variant)
        assert validated == "17-37733556-37733821-C-<DEL>"
        # Format for VEP
        vep_format = _format_variant_for_vep(validated)
        assert vep_format == "17 37733556 37733821 DEL + 17-37733556-37733821-C-<DEL>"

    def test_hnf1b_large_deletion_with_end(self):
        """Test large HNF1B 17q12 deletion with END position."""
        variant = "17-36459258-37832869-C-<DEL>"
        # Validate
        validated = validate_variant_id(variant)
        assert validated == "17-36459258-37832869-C-<DEL>"
        # Format for VEP
        vep_format = _format_variant_for_vep(validated)
        assert vep_format == "17 36459258 37832869 DEL + 17-36459258-37832869-C-<DEL>"

    def test_variant_id_preserved_in_vep_format(self):
        """Test that original variant ID is preserved as VEP ID field."""
        variants = [
            "17-37733556-37733821-C-<DEL>",
            "17-36459258-A-<DEL>",
            "17-36459258-37832869-DEL",
            "17-36459258-A-G",
        ]
        for variant in variants:
            validated = validate_variant_id(variant)
            vep_format = _format_variant_for_vep(validated)
            assert validated in vep_format, f"ID {validated} not in VEP format"
