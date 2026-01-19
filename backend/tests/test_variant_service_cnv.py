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


class TestVariantCNVDetection:
    """Test CNV variant detection."""

    def test_variant_cnv_snv_not_detected(self):
        """Test SNV is not detected as CNV."""
        assert is_cnv_variant("17-36459258-A-G") is False

    def test_variant_cnv_symbolic_del_detected(self):
        """Test symbolic deletion is detected as CNV."""
        assert is_cnv_variant("17-36459258-A-<DEL>") is True

    def test_variant_cnv_symbolic_dup_detected(self):
        """Test symbolic duplication is detected as CNV."""
        assert is_cnv_variant("17-36459258-A-<DUP>") is True

    def test_variant_cnv_region_format_detected(self):
        """Test region format CNV is detected."""
        assert is_cnv_variant("17-36459258-37832869-DEL") is True

    def test_variant_cnv_with_end_position_detected(self):
        """Test 5-part CNV with END position is detected."""
        assert is_cnv_variant("17-37733556-37733821-C-<DEL>") is True


class TestVariantCNVValidation:
    """Test variant ID validation and normalization."""

    # SNV format tests
    def test_variant_snv_basic_format_accepted(self):
        """Test basic SNV format."""
        result = validate_variant_id("17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_variant_snv_chr_prefix_normalized(self):
        """Test SNV with chr prefix is normalized."""
        result = validate_variant_id("chr17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_variant_snv_lowercase_uppercased(self):
        """Test SNV with lowercase is uppercased."""
        result = validate_variant_id("17-36459258-a-g")
        assert result == "17-36459258-A-G"

    def test_variant_snv_x_chromosome_accepted(self):
        """Test SNV on X chromosome."""
        result = validate_variant_id("X-12345-C-T")
        assert result == "X-12345-C-T"

    # CNV symbolic format (4-part) tests
    def test_variant_cnv_symbolic_del_validated(self):
        """Test 4-part CNV symbolic deletion."""
        result = validate_variant_id("17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_variant_cnv_symbolic_dup_validated(self):
        """Test 4-part CNV symbolic duplication."""
        result = validate_variant_id("17-36459258-A-<DUP>")
        assert result == "17-36459258-A-<DUP>"

    def test_variant_cnv_symbolic_chr_prefix_normalized(self):
        """Test CNV symbolic with chr prefix is normalized."""
        result = validate_variant_id("chr17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    # CNV with END position (5-part) tests
    def test_variant_cnv_5part_del_validated(self):
        """Test 5-part CNV deletion with END position."""
        result = validate_variant_id("17-37733556-37733821-C-<DEL>")
        assert result == "17-37733556-37733821-C-<DEL>"

    def test_variant_cnv_5part_dup_validated(self):
        """Test 5-part CNV duplication with END position."""
        result = validate_variant_id("17-36459258-37832869-C-<DUP>")
        assert result == "17-36459258-37832869-C-<DUP>"

    def test_variant_cnv_5part_chr_prefix_normalized(self):
        """Test 5-part CNV with chr prefix is normalized."""
        result = validate_variant_id("chr17-37733556-37733821-C-<DEL>")
        assert result == "17-37733556-37733821-C-<DEL>"

    def test_variant_cnv_5part_lowercase_uppercased(self):
        """Test 5-part CNV with lowercase is uppercased."""
        result = validate_variant_id("17-37733556-37733821-c-<del>")
        assert result == "17-37733556-37733821-C-<DEL>"

    # CNV region format tests
    def test_variant_cnv_region_del_validated(self):
        """Test CNV region format deletion."""
        result = validate_variant_id("17-36459258-37832869-DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_variant_cnv_region_dup_validated(self):
        """Test CNV region format duplication."""
        result = validate_variant_id("17-36459258-37832869-DUP")
        assert result == "17-36459258-37832869-DUP"

    def test_variant_cnv_region_colon_normalized(self):
        """Test CNV region format with colon separator is normalized."""
        result = validate_variant_id("17:36459258-37832869:DEL")
        assert result == "17-36459258-37832869-DEL"

    # Invalid format tests
    def test_variant_invalid_format_raises_error(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError):
            validate_variant_id("invalid-format")

    def test_variant_cnv_disabled_raises_error(self):
        """Test CNV format raises when CNV not allowed."""
        with pytest.raises(ValueError):
            validate_variant_id("17-36459258-A-<DEL>", allow_cnv=False)


class TestVariantVEPFormatConversion:
    """Test VEP format conversion."""

    # SNV format tests
    def test_variant_vep_snv_format_succeeds(self):
        """Test SNV converts to VCF format for VEP."""
        result = _format_variant_for_vep("17-36459258-A-G")
        assert result == "17 36459258 17-36459258-A-G A G . . ."

    # CNV symbolic format (4-part) tests
    def test_variant_vep_cnv_symbolic_same_start_end(self):
        """Test 4-part CNV symbolic uses same start/end."""
        result = _format_variant_for_vep("17-36459258-A-<DEL>")
        assert result == "17 36459258 36459258 DEL + 17-36459258-A-<DEL>"

    # CNV with END position (5-part) tests
    def test_variant_vep_cnv_5part_format_succeeds(self):
        """Test 5-part CNV converts to VEP SV format with actual coordinates."""
        result = _format_variant_for_vep("17-37733556-37733821-C-<DEL>")
        assert result == "17 37733556 37733821 DEL + 17-37733556-37733821-C-<DEL>"

    def test_variant_vep_cnv_5part_dup_format_succeeds(self):
        """Test 5-part CNV duplication converts correctly."""
        result = _format_variant_for_vep("17-36459258-37832869-C-<DUP>")
        assert result == "17 36459258 37832869 DUP + 17-36459258-37832869-C-<DUP>"

    # CNV region format tests
    def test_variant_vep_cnv_region_format_succeeds(self):
        """Test CNV region format converts to VEP SV format."""
        result = _format_variant_for_vep("17-36459258-37832869-DEL")
        assert result == "17 36459258 37832869 DEL + 17-36459258-37832869-DEL"

    # Invalid format tests
    def test_variant_vep_invalid_returns_none(self):
        """Test invalid format returns None."""
        result = _format_variant_for_vep("invalid")
        assert result is None


class TestVariantCNVRealWorldFormats:
    """Test real-world CNV formats from the HNF1B database."""

    def test_variant_cnv_hnf1b_deletion_with_end(self):
        """Test real HNF1B deletion format with END position."""
        variant = "17-37733556-37733821-C-<DEL>"
        # Validate
        validated = validate_variant_id(variant)
        assert validated == "17-37733556-37733821-C-<DEL>"
        # Format for VEP
        vep_format = _format_variant_for_vep(validated)
        assert vep_format == "17 37733556 37733821 DEL + 17-37733556-37733821-C-<DEL>"

    def test_variant_cnv_hnf1b_large_deletion(self):
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
