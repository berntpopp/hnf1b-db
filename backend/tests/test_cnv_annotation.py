"""Tests for CNV (Copy Number Variant) annotation functionality.

Tests the extended VariantService support for structural variants including:
- CNV format detection and validation
- VEP formatting for structural variants
- CNV annotation parsing
"""

import pytest

from app.variants.service import (
    _format_variant_for_vep,
    is_cnv_variant,
    validate_variant_id,
)


class TestCNVDetection:
    """Test CNV/structural variant detection."""

    def test_is_cnv_symbolic_del(self):
        """Test detection of symbolic DEL allele."""
        assert is_cnv_variant("17-36459258-A-<DEL>") is True
        assert is_cnv_variant("chr17-36459258-A-<DEL>") is True

    def test_is_cnv_symbolic_dup(self):
        """Test detection of symbolic DUP allele."""
        assert is_cnv_variant("17-36459258-A-<DUP>") is True

    def test_is_cnv_region_format(self):
        """Test detection of region format CNVs."""
        assert is_cnv_variant("17-36459258-37832869-DEL") is True
        assert is_cnv_variant("17:36459258-37832869:DEL") is True
        assert is_cnv_variant("17-36459258-37832869-DUP") is True

    def test_is_cnv_other_sv_types(self):
        """Test detection of other SV types."""
        assert is_cnv_variant("17-36459258-A-<INS>") is True
        assert is_cnv_variant("17-36459258-A-<INV>") is True
        assert is_cnv_variant("17-36459258-A-<CNV>") is True

    def test_is_cnv_negative_snv(self):
        """Test that SNVs are not detected as CNVs."""
        assert is_cnv_variant("17-36459258-A-G") is False
        assert is_cnv_variant("17-36459258-AT-G") is False

    def test_is_cnv_case_insensitive(self):
        """Test case insensitivity."""
        assert is_cnv_variant("17-36459258-A-<del>") is True
        assert is_cnv_variant("17-36459258-37832869-Del") is True


class TestCNVValidation:
    """Test CNV variant ID validation."""

    def test_validate_cnv_symbolic_format(self):
        """Test validation of symbolic CNV format."""
        result = validate_variant_id("17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_validate_cnv_symbolic_with_chr(self):
        """Test validation with chr prefix."""
        result = validate_variant_id("chr17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_validate_cnv_region_format(self):
        """Test validation of region format."""
        result = validate_variant_id("17-36459258-37832869-DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_validate_cnv_region_colon_format(self):
        """Test validation of region format with colons."""
        result = validate_variant_id("17:36459258-37832869:DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_validate_cnv_disabled(self):
        """Test that CNVs are rejected when allow_cnv=False."""
        with pytest.raises(ValueError):
            validate_variant_id("17-36459258-A-<DEL>", allow_cnv=False)

    def test_validate_cnv_all_sv_types(self):
        """Test validation of all SV types."""
        sv_types = ["DEL", "DUP", "INS", "INV", "CNV"]
        for sv_type in sv_types:
            # Symbolic format
            result = validate_variant_id(f"17-36459258-A-<{sv_type}>")
            assert sv_type in result

            # Region format
            result = validate_variant_id(f"17-36459258-37832869-{sv_type}")
            assert sv_type in result

    def test_validate_snv_still_works(self):
        """Test that SNV validation still works."""
        result = validate_variant_id("17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_validate_indel_still_works(self):
        """Test that indel validation still works."""
        result = validate_variant_id("17-36459258-AT-G")
        assert result == "17-36459258-AT-G"


class TestCNVVEPFormatting:
    """Test VEP formatting for CNVs."""

    def test_format_cnv_region(self):
        """Test VEP format for region-style CNV."""
        result = _format_variant_for_vep("17-36459258-37832869-DEL")
        # Expected: "CHROM START END SV_TYPE STRAND ID"
        assert result == "17 36459258 37832869 DEL + 17-36459258-37832869-DEL"

    def test_format_cnv_dup(self):
        """Test VEP format for DUP variant."""
        result = _format_variant_for_vep("17-36459258-37832869-DUP")
        assert result == "17 36459258 37832869 DUP + 17-36459258-37832869-DUP"

    def test_format_cnv_symbolic(self):
        """Test VEP format for symbolic CNV."""
        result = _format_variant_for_vep("17-36459258-A-<DEL>")
        # For symbolic without end, use same start/end
        assert result == "17 36459258 36459258 DEL + 17-36459258-A-<DEL>"

    def test_format_snv(self):
        """Test VEP format for SNV (existing behavior)."""
        result = _format_variant_for_vep("17-36459258-A-G")
        # VCF format: "CHROM POS ID REF ALT . . ."
        assert result == "17 36459258 17-36459258-A-G A G . . ."

    def test_format_indel(self):
        """Test VEP format for indel (existing behavior)."""
        result = _format_variant_for_vep("17-36459258-AT-G")
        assert result == "17 36459258 17-36459258-AT-G AT G . . ."

    def test_format_invalid_returns_none(self):
        """Test that invalid format returns None."""
        result = _format_variant_for_vep("invalid-format")
        assert result is None

    def test_format_all_sv_types(self):
        """Test VEP formatting for all SV types."""
        sv_types = ["DEL", "DUP", "INS", "INV", "CNV"]
        for sv_type in sv_types:
            result = _format_variant_for_vep(f"17-36459258-37832869-{sv_type}")
            assert sv_type in result
            assert "17 36459258 37832869" in result


class TestCNVEdgeCases:
    """Test edge cases and corner cases for CNV handling."""

    def test_x_chromosome_cnv(self):
        """Test CNV on X chromosome."""
        result = validate_variant_id("X-12345678-98765432-DEL")
        assert result == "X-12345678-98765432-DEL"
        formatted = _format_variant_for_vep(result)
        assert formatted.startswith("X ")

    def test_y_chromosome_cnv(self):
        """Test CNV on Y chromosome."""
        result = validate_variant_id("Y-12345678-98765432-DUP")
        assert result == "Y-12345678-98765432-DUP"

    def test_cnv_uppercase_normalization(self):
        """Test that CNV types are normalized to uppercase."""
        result = validate_variant_id("17-36459258-37832869-del")
        assert result == "17-36459258-37832869-DEL"

    def test_mixed_case_symbolic(self):
        """Test mixed case symbolic allele."""
        result = validate_variant_id("17-36459258-a-<Del>")
        assert "<DEL>" in result or "DEL" in result
