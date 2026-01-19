"""Tests for CNV parser functionality.

Tests the CNVParser class for parsing HG38 CNV coordinates and creating
GA4GH-compliant phenopacket variant structures.
"""

import pytest

from migration.vrs.cnv_parser import CNVParser


class TestVariantCNVParserCoordinates:
    """Test CNV coordinate parsing."""

    def test_variant_cnv_parse_standard_deletion_succeeds(self):
        """Test parsing standard deletion coordinates."""
        hg38 = "chr17-36459258-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610"

        coords = CNVParser.parse_hg38_coordinates(hg38, hg38_info)

        assert coords is not None
        chromosome, start, end, variant_type = coords
        assert chromosome == "17"
        assert start == 36459258
        assert end == 37832869
        assert variant_type == "DEL"

    def test_variant_cnv_parse_large_deletion_succeeds(self):
        """Test parsing larger deletion with different coordinates."""
        hg38 = "chr17-36466613-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=39698363;SVLEN=-3231750"

        coords = CNVParser.parse_hg38_coordinates(hg38, hg38_info)

        assert coords is not None
        chromosome, start, end, variant_type = coords
        assert chromosome == "17"
        assert start == 36466613
        assert end == 39698363
        assert variant_type == "DEL"

    def test_variant_cnv_parse_duplication_succeeds(self):
        """Test parsing duplication coordinates."""
        hg38 = "chr17-36459258-T-<DUP>"
        hg38_info = "IMPRECISE;SVTYPE=DUP;END=37832869;SVLEN=1373610"

        coords = CNVParser.parse_hg38_coordinates(hg38, hg38_info)

        assert coords is not None
        chromosome, start, end, variant_type = coords
        assert chromosome == "17"
        assert start == 36459258
        assert end == 37832869
        assert variant_type == "DUP"


class TestVariantCNVParserGA4GHNotation:
    """Test GA4GH CNV notation generation."""

    def test_variant_cnv_ga4gh_deletion_notation(self):
        """Test GA4GH notation for deletion."""
        notation = CNVParser.create_ga4gh_cnv_notation("17", 36459258, 37832869, "DEL")

        assert notation == "17:36459258-37832869:DEL"

    def test_variant_cnv_ga4gh_duplication_notation(self):
        """Test GA4GH notation for duplication."""
        notation = CNVParser.create_ga4gh_cnv_notation("17", 36459258, 37832869, "DUP")

        assert notation == "17:36459258-37832869:DUP"

    def test_variant_cnv_ga4gh_x_chromosome_notation(self):
        """Test GA4GH notation for X chromosome CNV."""
        notation = CNVParser.create_ga4gh_cnv_notation("X", 12345678, 23456789, "DEL")

        assert notation == "X:12345678-23456789:DEL"


class TestVariantCNVParserDbVarID:
    """Test dbVar ID generation."""

    def test_variant_cnv_dbvar_del_returns_id(self):
        """Test dbVar ID for DEL type."""
        dbvar_id = CNVParser.get_dbvar_id("DEL")

        assert dbvar_id is not None
        assert "dbVar:" in dbvar_id

    def test_variant_cnv_dbvar_dup_returns_id(self):
        """Test dbVar ID for DUP type."""
        dbvar_id = CNVParser.get_dbvar_id("DUP")

        assert dbvar_id is not None
        assert "dbVar:" in dbvar_id

    def test_variant_cnv_dbvar_unsupported_type_returns_none(self):
        """Test unsupported variant types return None."""
        # The function only supports DEL and DUP, not verbose forms
        assert CNVParser.get_dbvar_id("Deletion") is None
        assert CNVParser.get_dbvar_id("Duplication") is None
        assert CNVParser.get_dbvar_id("INS") is None
        assert CNVParser.get_dbvar_id("unknown") is None


class TestVariantCNVParserPhenopacketVariant:
    """Test full phenopacket variant creation."""

    def test_variant_cnv_phenopacket_deletion_created(self):
        """Test phenopacket variant creation for deletion."""
        hg38 = "chr17-36459258-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610"
        variant_type = "Deletion"
        variant_reported = "1.5 Mb deletion including HNF1B"

        variant = CNVParser.create_phenopacket_cnv_variant(
            hg38, hg38_info, variant_type, variant_reported
        )

        assert variant is not None
        assert "id" in variant
        assert "label" in variant
        assert "structuralType" in variant
        assert "expressions" in variant
        assert len(variant["expressions"]) > 0

    def test_variant_cnv_phenopacket_duplication_created(self):
        """Test phenopacket variant creation for duplication."""
        hg38 = "chr17-36459258-T-<DUP>"
        hg38_info = "IMPRECISE;SVTYPE=DUP;END=37832869;SVLEN=1373610"
        variant_type = "Duplication"
        variant_reported = "17q12 duplication"

        variant = CNVParser.create_phenopacket_cnv_variant(
            hg38, hg38_info, variant_type, variant_reported
        )

        assert variant is not None
        assert "id" in variant
        assert "structuralType" in variant

    def test_variant_cnv_phenopacket_expressions_included(self):
        """Test phenopacket variant includes expression formats."""
        hg38 = "chr17-36459258-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610"
        variant_type = "Deletion"
        variant_reported = "1.5 Mb deletion including HNF1B"

        variant = CNVParser.create_phenopacket_cnv_variant(
            hg38, hg38_info, variant_type, variant_reported
        )

        assert variant is not None
        expressions = variant.get("expressions", [])
        assert len(expressions) > 0

        # Check that expressions have syntax and value
        for expr in expressions:
            assert "syntax" in expr
            assert "value" in expr

    def test_variant_cnv_phenopacket_extensions_included(self):
        """Test phenopacket variant includes extensions."""
        hg38 = "chr17-36459258-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610"
        variant_type = "Deletion"
        variant_reported = "1.5 Mb deletion including HNF1B"

        variant = CNVParser.create_phenopacket_cnv_variant(
            hg38, hg38_info, variant_type, variant_reported
        )

        assert variant is not None
        extensions = variant.get("extensions", [])

        # Check for coordinates extension if present
        coord_ext = next(
            (e for e in extensions if e.get("name") == "coordinates"), None
        )
        if coord_ext:
            assert "value" in coord_ext
            assert "chromosome" in coord_ext["value"]
            assert "start" in coord_ext["value"]
            assert "end" in coord_ext["value"]


class TestVariantCNVParserSizeCalculation:
    """Test CNV size calculation."""

    def test_variant_cnv_size_calculated_correctly(self):
        """Test that CNV size can be calculated from coordinates."""
        hg38 = "chr17-36459258-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=37832869;SVLEN=-1373610"

        coords = CNVParser.parse_hg38_coordinates(hg38, hg38_info)

        assert coords is not None
        _, start, end, _ = coords
        size = end - start + 1

        # Should be approximately 1.37 Mb
        assert size > 1_000_000
        assert size < 2_000_000

    def test_variant_cnv_large_deletion_size(self):
        """Test size calculation for larger deletion."""
        hg38 = "chr17-36466613-T-<DEL>"
        hg38_info = "IMPRECISE;SVTYPE=DEL;END=39698363;SVLEN=-3231750"

        coords = CNVParser.parse_hg38_coordinates(hg38, hg38_info)

        assert coords is not None
        _, start, end, _ = coords
        size = end - start + 1

        # Should be approximately 3.2 Mb
        assert size > 3_000_000
        assert size < 4_000_000


@pytest.mark.skip(reason="Requires network access to Google Sheets")
class TestVariantCNVParserGoogleSheetsIntegration:
    """Integration tests with Google Sheets data (requires network)."""

    def test_variant_cnv_google_sheets_data_parseable(self):
        """Test parsing CNVs from actual Google Sheets data."""
        import pandas as pd

        SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
        GID_INDIVIDUALS = "0"
        url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={GID_INDIVIDUALS}"

        df = pd.read_csv(url)

        # Filter for deletions and duplications
        cnv_df = df[
            df["VariantType"].str.contains("delet|dup", case=False, na=False)
        ].head(5)

        success_count = 0
        for _, row in cnv_df.iterrows():
            hg38 = row["hg38"]
            hg38_info = row["hg38_INFO"]

            if pd.notna(hg38) and pd.notna(hg38_info):
                coords = CNVParser.parse_hg38_coordinates(str(hg38), str(hg38_info))
                if coords:
                    chromosome, start, end, var_type = coords
                    ga4gh = CNVParser.create_ga4gh_cnv_notation(
                        chromosome, start, end, var_type
                    )
                    assert ga4gh is not None
                    success_count += 1

        assert success_count > 0
