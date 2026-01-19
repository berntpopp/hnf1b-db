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


class TestVariantCNVAnnotationDetection:
    """Test CNV/structural variant detection."""

    def test_variant_cnv_symbolic_del_detected(self):
        """Test detection of symbolic DEL allele."""
        assert is_cnv_variant("17-36459258-A-<DEL>") is True
        assert is_cnv_variant("chr17-36459258-A-<DEL>") is True

    def test_variant_cnv_symbolic_dup_detected(self):
        """Test detection of symbolic DUP allele."""
        assert is_cnv_variant("17-36459258-A-<DUP>") is True

    def test_variant_cnv_region_format_detected(self):
        """Test detection of region format CNVs."""
        assert is_cnv_variant("17-36459258-37832869-DEL") is True
        assert is_cnv_variant("17:36459258-37832869:DEL") is True
        assert is_cnv_variant("17-36459258-37832869-DUP") is True

    def test_variant_cnv_other_sv_types_detected(self):
        """Test detection of other SV types."""
        assert is_cnv_variant("17-36459258-A-<INS>") is True
        assert is_cnv_variant("17-36459258-A-<INV>") is True
        assert is_cnv_variant("17-36459258-A-<CNV>") is True

    def test_variant_cnv_snv_not_detected(self):
        """Test that SNVs are not detected as CNVs."""
        assert is_cnv_variant("17-36459258-A-G") is False
        assert is_cnv_variant("17-36459258-AT-G") is False

    def test_variant_cnv_case_insensitive_detected(self):
        """Test case insensitivity."""
        assert is_cnv_variant("17-36459258-A-<del>") is True
        assert is_cnv_variant("17-36459258-37832869-Del") is True


class TestVariantCNVAnnotationValidation:
    """Test CNV variant ID validation."""

    def test_variant_cnv_symbolic_format_validated(self):
        """Test validation of symbolic CNV format."""
        result = validate_variant_id("17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_variant_cnv_symbolic_chr_prefix_normalized(self):
        """Test validation with chr prefix."""
        result = validate_variant_id("chr17-36459258-A-<DEL>")
        assert result == "17-36459258-A-<DEL>"

    def test_variant_cnv_region_format_validated(self):
        """Test validation of region format."""
        result = validate_variant_id("17-36459258-37832869-DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_variant_cnv_region_colon_format_normalized(self):
        """Test validation of region format with colons."""
        result = validate_variant_id("17:36459258-37832869:DEL")
        assert result == "17-36459258-37832869-DEL"

    def test_variant_cnv_disabled_raises_error(self):
        """Test that CNVs are rejected when allow_cnv=False."""
        with pytest.raises(ValueError):
            validate_variant_id("17-36459258-A-<DEL>", allow_cnv=False)

    def test_variant_cnv_all_sv_types_validated(self):
        """Test validation of all SV types."""
        sv_types = ["DEL", "DUP", "INS", "INV", "CNV"]
        for sv_type in sv_types:
            # Symbolic format
            result = validate_variant_id(f"17-36459258-A-<{sv_type}>")
            assert sv_type in result

            # Region format
            result = validate_variant_id(f"17-36459258-37832869-{sv_type}")
            assert sv_type in result

    def test_variant_cnv_snv_validation_still_works(self):
        """Test that SNV validation still works."""
        result = validate_variant_id("17-36459258-A-G")
        assert result == "17-36459258-A-G"

    def test_variant_cnv_indel_validation_still_works(self):
        """Test that indel validation still works."""
        result = validate_variant_id("17-36459258-AT-G")
        assert result == "17-36459258-AT-G"


class TestVariantCNVAnnotationVEPFormatting:
    """Test VEP formatting for CNVs."""

    def test_variant_cnv_vep_region_format_succeeds(self):
        """Test VEP format for region-style CNV."""
        result = _format_variant_for_vep("17-36459258-37832869-DEL")
        # Expected: "CHROM START END SV_TYPE STRAND ID"
        assert result == "17 36459258 37832869 DEL + 17-36459258-37832869-DEL"

    def test_variant_cnv_vep_dup_format_succeeds(self):
        """Test VEP format for DUP variant."""
        result = _format_variant_for_vep("17-36459258-37832869-DUP")
        assert result == "17 36459258 37832869 DUP + 17-36459258-37832869-DUP"

    def test_variant_cnv_vep_symbolic_format_succeeds(self):
        """Test VEP format for symbolic CNV."""
        result = _format_variant_for_vep("17-36459258-A-<DEL>")
        # For symbolic without end, use same start/end
        assert result == "17 36459258 36459258 DEL + 17-36459258-A-<DEL>"

    def test_variant_cnv_vep_snv_format_succeeds(self):
        """Test VEP format for SNV (existing behavior)."""
        result = _format_variant_for_vep("17-36459258-A-G")
        # VCF format: "CHROM POS ID REF ALT . . ."
        assert result == "17 36459258 17-36459258-A-G A G . . ."

    def test_variant_cnv_vep_indel_format_succeeds(self):
        """Test VEP format for indel (existing behavior)."""
        result = _format_variant_for_vep("17-36459258-AT-G")
        assert result == "17 36459258 17-36459258-AT-G AT G . . ."

    def test_variant_cnv_vep_invalid_returns_none(self):
        """Test that invalid format returns None."""
        result = _format_variant_for_vep("invalid-format")
        assert result is None

    def test_variant_cnv_vep_all_sv_types_format_succeeds(self):
        """Test VEP formatting for all SV types."""
        sv_types = ["DEL", "DUP", "INS", "INV", "CNV"]
        for sv_type in sv_types:
            result = _format_variant_for_vep(f"17-36459258-37832869-{sv_type}")
            assert sv_type in result
            assert "17 36459258 37832869" in result


class TestVariantCNVAnnotationEdgeCases:
    """Test edge cases and corner cases for CNV handling."""

    def test_variant_cnv_x_chromosome_accepted(self):
        """Test CNV on X chromosome."""
        result = validate_variant_id("X-12345678-98765432-DEL")
        assert result == "X-12345678-98765432-DEL"
        formatted = _format_variant_for_vep(result)
        assert formatted.startswith("X ")

    def test_variant_cnv_y_chromosome_accepted(self):
        """Test CNV on Y chromosome."""
        result = validate_variant_id("Y-12345678-98765432-DUP")
        assert result == "Y-12345678-98765432-DUP"

    def test_variant_cnv_uppercase_normalized(self):
        """Test that CNV types are normalized to uppercase."""
        result = validate_variant_id("17-36459258-37832869-del")
        assert result == "17-36459258-37832869-DEL"

    def test_variant_cnv_mixed_case_symbolic_normalized(self):
        """Test mixed case symbolic allele."""
        result = validate_variant_id("17-36459258-a-<Del>")
        assert "<DEL>" in result or "DEL" in result

    def test_variant_cnv_real_world_hnf1b_format(self):
        """Test real-world CNV variant from the database.

        This tests the actual variant format found in the HNF1B database:
        chr17-36466613-T-<DEL>
        """
        result = validate_variant_id("chr17-36466613-T-<DEL>")
        assert result == "17-36466613-T-<DEL>"
        assert is_cnv_variant(result) is True

        # Test VEP formatting
        formatted = _format_variant_for_vep(result)
        assert formatted == "17 36466613 36466613 DEL + 17-36466613-T-<DEL>"


class TestVariantCNVAnnotationDatabaseConstraints:
    """Test that CNV formats match the database constraint patterns.

    The variant_annotations table has a CHECK constraint that validates variant_id:
    - SNVs/indels: ^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$
    - CNVs symbolic: ^[0-9XYM]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$
    - CNVs region: ^[0-9XYM]+-[0-9]+-[0-9]+-(DEL|DUP|INS|INV|CNV)$
    """

    def test_variant_cnv_snv_matches_db_constraint(self):
        """Test SNV format matches database constraint."""
        import re

        snv_pattern = r"^[0-9XYM]+-[0-9]+-[ACGT]+-[ACGT]+$"
        valid_snvs = [
            "17-36459258-A-G",
            "1-12345-C-T",
            "X-1000000-AT-G",
            "Y-500-ACGT-T",
            "M-100-A-TGCA",
        ]
        for vid in valid_snvs:
            result = validate_variant_id(vid)
            assert re.match(snv_pattern, result), f"{result} should match SNV pattern"

    def test_variant_cnv_symbolic_matches_db_constraint(self):
        """Test CNV symbolic format matches database constraint."""
        import re

        cnv_symbolic_pattern = r"^[0-9XYM]+-[0-9]+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
        valid_cnvs = [
            "17-36459258-A-<DEL>",
            "1-12345-C-<DUP>",
            "X-1000000-T-<INS>",
            "Y-500-G-<INV>",
            "17-36466613-T-<DEL>",  # Real variant from database
        ]
        for vid in valid_cnvs:
            result = validate_variant_id(vid)
            assert re.match(cnv_symbolic_pattern, result), (
                f"{result} should match CNV symbolic pattern"
            )

    def test_variant_cnv_region_matches_db_constraint(self):
        """Test CNV region format matches database constraint."""
        import re

        cnv_region_pattern = r"^[0-9XYM]+-[0-9]+-[0-9]+-(DEL|DUP|INS|INV|CNV)$"
        valid_cnvs = [
            "17-36459258-37832869-DEL",
            "1-100-200-DUP",
            "X-1000-2000-INS",
            "Y-500-1500-INV",
            "17-36466613-37832869-CNV",
        ]
        for vid in valid_cnvs:
            result = validate_variant_id(vid)
            assert re.match(cnv_region_pattern, result), (
                f"{result} should match CNV region pattern"
            )

    def test_variant_cnv_invalid_formats_rejected(self):
        """Test that invalid formats are rejected."""
        invalid_variants = [
            "invalid",
            "17-pos-A-G",  # Non-numeric position
            "17-36459258-A",  # Missing ALT
            "17-36459258-A-<INVALID>",  # Invalid SV type
            "chr",
            "",
        ]
        for vid in invalid_variants:
            with pytest.raises(ValueError):
                validate_variant_id(vid)


class TestVariantCNVAnnotationIntegration:
    """Integration tests for CNV handling with mocked VEP API."""

    def test_variant_cnv_normalization_chain_complete(self):
        """Test complete normalization chain for CNV variants."""
        # Input from external source with various formats
        test_cases = [
            ("chr17-36466613-T-<DEL>", "17-36466613-T-<DEL>"),
            ("CHR17-36466613-t-<del>", "17-36466613-T-<DEL>"),
            ("17:36459258-37832869:DEL", "17-36459258-37832869-DEL"),
            ("chr17:36459258-37832869:del", "17-36459258-37832869-DEL"),
        ]
        for input_id, expected in test_cases:
            result = validate_variant_id(input_id)
            assert result == expected, f"Expected {expected} for input {input_id}"

    def test_variant_cnv_vep_format_preserves_id(self):
        """Test that VEP format includes original variant ID for matching."""
        # The variant ID should be included in VEP format for result matching
        test_cases = [
            "17-36459258-A-G",
            "17-36459258-A-<DEL>",
            "17-36459258-37832869-DEL",
        ]
        for vid in test_cases:
            formatted = _format_variant_for_vep(vid)
            assert vid in formatted, f"Variant ID {vid} should be in VEP format"

    def test_variant_cnv_all_sv_types_valid_vep_format(self):
        """Test all SV types produce valid VEP format."""
        sv_types = ["DEL", "DUP", "INS", "INV", "CNV"]
        for sv_type in sv_types:
            # Test symbolic format
            symbolic = f"17-36459258-A-<{sv_type}>"
            formatted = _format_variant_for_vep(symbolic)
            assert formatted is not None
            assert sv_type in formatted
            assert "17 36459258" in formatted

            # Test region format
            region = f"17-36459258-37832869-{sv_type}"
            formatted = _format_variant_for_vep(region)
            assert formatted is not None
            assert sv_type in formatted
            assert "17 36459258 37832869" in formatted
