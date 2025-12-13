"""Tests for protein domain survival analysis handler.

Tests cover:
- Handler registration in factory
- Group names and definitions
- Comparison type identifier
- Domain classification logic
- Missense filter patterns
- Amino acid position extraction
- Metadata generation

These tests validate the ProteinDomainHandler implementation
without requiring database access.
"""

import re

import pytest

from app.phenopackets.routers.aggregations.sql_fragments import (
    AMINO_ACID_POSITION_PATTERN,
    HNF1B_PROTEIN_DOMAINS,
    MISSENSE_HGVS_P_PATTERN,
    get_cnv_exclusion_filter,
    get_missense_filter_sql,
    get_protein_domain_classification_sql,
)
from app.phenopackets.routers.aggregations.survival_handlers import (
    ProteinDomainHandler,
    SurvivalHandlerFactory,
)


class TestProteinDomainHandlerRegistration:
    """Tests for handler registration in factory."""

    def test_handler_registered_in_factory(self):
        """Verify protein_domain handler is registered in factory."""
        handler = SurvivalHandlerFactory.get_handler("protein_domain")
        assert isinstance(handler, ProteinDomainHandler)

    def test_protein_domain_in_valid_types(self):
        """Verify protein_domain is in valid comparison types."""
        valid_types = SurvivalHandlerFactory.get_valid_comparison_types()
        assert "protein_domain" in valid_types

    def test_factory_returns_new_instances(self):
        """Factory should return new handler instances each call."""
        handler1 = SurvivalHandlerFactory.get_handler("protein_domain")
        handler2 = SurvivalHandlerFactory.get_handler("protein_domain")
        assert handler1 is not handler2


class TestProteinDomainHandlerProperties:
    """Tests for handler properties."""

    def test_comparison_type(self):
        """Verify comparison type identifier."""
        handler = ProteinDomainHandler()
        assert handler.comparison_type == "protein_domain"

    def test_group_names(self):
        """Verify correct domain groups."""
        handler = ProteinDomainHandler()
        assert handler.group_names == ["POU-S", "POU-H", "TAD", "Other"]

    def test_group_field(self):
        """Verify group field name for SQL queries."""
        handler = ProteinDomainHandler()
        assert handler.get_group_field() == "domain_group"

    def test_group_definitions_contains_all_groups(self):
        """Verify all groups have definitions."""
        handler = ProteinDomainHandler()
        definitions = handler.group_definitions
        for group in handler.group_names:
            assert group in definitions
            assert len(definitions[group]) > 0

    def test_group_definitions_contain_amino_acid_ranges(self):
        """Verify domain definitions include amino acid ranges."""
        handler = ProteinDomainHandler()
        definitions = handler.group_definitions

        assert "90-173" in definitions["POU-S"]
        assert "232-305" in definitions["POU-H"]
        assert "314-557" in definitions["TAD"]


class TestHNF1BProteinDomains:
    """Tests for HNF1B protein domain constants."""

    def test_domain_structure(self):
        """Verify domain constant structure."""
        assert "POU-S" in HNF1B_PROTEIN_DOMAINS
        assert "POU-H" in HNF1B_PROTEIN_DOMAINS
        assert "TAD" in HNF1B_PROTEIN_DOMAINS

    def test_domain_boundaries(self):
        """Verify domain boundary values."""
        pou_s = HNF1B_PROTEIN_DOMAINS["POU-S"]
        assert pou_s["start"] == 90
        assert pou_s["end"] == 173

        pou_h = HNF1B_PROTEIN_DOMAINS["POU-H"]
        assert pou_h["start"] == 232
        assert pou_h["end"] == 305

        tad = HNF1B_PROTEIN_DOMAINS["TAD"]
        assert tad["start"] == 314
        assert tad["end"] == 557

    def test_domains_non_overlapping(self):
        """Verify domains do not overlap."""
        pou_s = HNF1B_PROTEIN_DOMAINS["POU-S"]
        pou_h = HNF1B_PROTEIN_DOMAINS["POU-H"]
        tad = HNF1B_PROTEIN_DOMAINS["TAD"]

        # POU-S ends before POU-H starts
        assert pou_s["end"] < pou_h["start"]
        # POU-H ends before TAD starts
        assert pou_h["end"] < tad["start"]

    def test_domains_have_labels(self):
        """Verify all domains have human-readable labels."""
        for name, domain in HNF1B_PROTEIN_DOMAINS.items():
            assert "label" in domain
            assert len(domain["label"]) > 0


class TestMissenseHGVSPattern:
    """Tests for missense variant HGVS.p pattern matching."""

    @pytest.mark.parametrize(
        "hgvs_p",
        [
            "p.Arg177Cys",
            "p.Met1Val",
            "p.Gly400Ser",
            "p.Ala100Thr",
            "p.Lys556Asn",
        ],
    )
    def test_valid_missense_matches(self, hgvs_p):
        """Valid missense variants should match the pattern."""
        assert re.match(MISSENSE_HGVS_P_PATTERN, hgvs_p)

    @pytest.mark.parametrize(
        "hgvs_p",
        [
            "p.Arg177Ter",  # Nonsense (termination)
            "p.Arg177*",  # Stop gained
            "p.Arg177fs",  # Frameshift
            "p.Arg177Glufs*2",  # Frameshift with extension
            "p.Arg177del",  # Deletion
            "p.Arg177_Gly180del",  # Multi-residue deletion
            "p.Met1?",  # Start lost
        ],
    )
    def test_truncating_variants_excluded(self, hgvs_p):
        """Truncating variants should NOT match missense pattern."""
        assert not re.match(MISSENSE_HGVS_P_PATTERN, hgvs_p)

    @pytest.mark.parametrize(
        "invalid",
        [
            "c.529C>T",  # cDNA notation, not protein
            "Arg177Cys",  # Missing p. prefix
            "p.177Cys",  # Missing reference amino acid
            "p.ArgCys",  # Missing position
            "p.R177C",  # Single-letter amino acid code (not supported)
        ],
    )
    def test_invalid_formats_excluded(self, invalid):
        """Invalid formats should NOT match."""
        assert not re.match(MISSENSE_HGVS_P_PATTERN, invalid)


class TestAminoAcidPositionExtraction:
    """Tests for amino acid position extraction from HGVS.p."""

    @pytest.mark.parametrize(
        "hgvs_p,expected_position",
        [
            ("p.Arg177Cys", 177),
            ("p.Met1Val", 1),
            ("p.Gly400Ser", 400),
            ("p.Ala100Thr", 100),
            ("p.Lys556Asn", 556),
        ],
    )
    def test_position_extraction(self, hgvs_p, expected_position):
        """Extract correct amino acid position from HGVS.p notation."""
        match = re.search(AMINO_ACID_POSITION_PATTERN, hgvs_p)
        assert match is not None
        position = int(match.group(1))
        assert position == expected_position

    def test_position_extraction_from_nonsense(self):
        """Position extraction should work even for nonsense variants."""
        # This is for testing the regex - domain classification
        # would still exclude these via the missense filter
        match = re.search(AMINO_ACID_POSITION_PATTERN, "p.Arg177Ter")
        assert match is not None
        assert int(match.group(1)) == 177


class TestDomainClassification:
    """Tests for classifying amino acid positions into domains."""

    def classify_position(self, position):
        """Helper to classify an amino acid position into a domain."""
        pou_s = HNF1B_PROTEIN_DOMAINS["POU-S"]
        pou_h = HNF1B_PROTEIN_DOMAINS["POU-H"]
        tad = HNF1B_PROTEIN_DOMAINS["TAD"]

        if pou_s["start"] <= position <= pou_s["end"]:
            return "POU-S"
        elif pou_h["start"] <= position <= pou_h["end"]:
            return "POU-H"
        elif tad["start"] <= position <= tad["end"]:
            return "TAD"
        else:
            return "Other"

    @pytest.mark.parametrize(
        "hgvs_p,expected_domain",
        [
            # POU-S domain (90-173)
            ("p.Arg90Cys", "POU-S"),  # Start of POU-S
            ("p.Arg137Cys", "POU-S"),  # Middle of POU-S
            ("p.Arg173Cys", "POU-S"),  # End of POU-S
            # POU-H domain (232-305)
            ("p.Arg232Cys", "POU-H"),  # Start of POU-H
            ("p.Arg267His", "POU-H"),  # Middle of POU-H
            ("p.Arg305Cys", "POU-H"),  # End of POU-H
            # TAD domain (314-557)
            ("p.Arg314Cys", "TAD"),  # Start of TAD
            ("p.Gly400Ser", "TAD"),  # Middle of TAD
            ("p.Lys557Asn", "TAD"),  # End of TAD (last residue)
            # Other (outside defined domains)
            ("p.Met1Val", "Other"),  # Before POU-S
            ("p.Arg50Cys", "Other"),  # Between N-term and POU-S
            ("p.Arg200Cys", "Other"),  # Between POU-S and POU-H (linker)
            ("p.Arg310Cys", "Other"),  # Between POU-H and TAD
        ],
    )
    def test_domain_classification(self, hgvs_p, expected_domain):
        """Test amino acid position to domain mapping."""
        match = re.search(AMINO_ACID_POSITION_PATTERN, hgvs_p)
        position = int(match.group(1))
        domain = self.classify_position(position)
        assert domain == expected_domain

    def test_boundary_positions(self):
        """Test exact boundary positions."""
        # Just inside POU-S
        assert self.classify_position(90) == "POU-S"
        assert self.classify_position(173) == "POU-S"
        # Just outside POU-S
        assert self.classify_position(89) == "Other"
        assert self.classify_position(174) == "Other"

        # Just inside POU-H
        assert self.classify_position(232) == "POU-H"
        assert self.classify_position(305) == "POU-H"
        # Just outside POU-H
        assert self.classify_position(231) == "Other"
        assert self.classify_position(306) == "Other"

        # Just inside TAD
        assert self.classify_position(314) == "TAD"
        assert self.classify_position(557) == "TAD"
        # Just outside TAD
        assert self.classify_position(313) == "Other"


class TestSQLGenerators:
    """Tests for SQL fragment generators."""

    def test_missense_filter_sql_structure(self):
        """Verify missense filter SQL structure."""
        sql = get_missense_filter_sql("vd")
        assert "EXISTS" in sql
        assert "hgvs.p" in sql
        assert "expressions" in sql

    def test_missense_filter_sql_custom_path(self):
        """Verify custom path is used in SQL."""
        custom_path = "gi->'variantInterpretation'->'variationDescriptor'"
        sql = get_missense_filter_sql(custom_path)
        assert custom_path in sql

    def test_domain_classification_sql_structure(self):
        """Verify domain classification SQL structure."""
        sql = get_protein_domain_classification_sql("vd")
        assert "CASE" in sql
        assert "WHEN" in sql
        assert "POU-S" in sql
        assert "POU-H" in sql
        assert "TAD" in sql
        assert "Other" in sql

    def test_domain_classification_sql_contains_boundaries(self):
        """Verify domain boundaries are in SQL."""
        sql = get_protein_domain_classification_sql("vd")
        # Check POU-S boundaries
        assert "90" in sql
        assert "173" in sql
        # Check POU-H boundaries
        assert "232" in sql
        assert "305" in sql
        # Check TAD boundaries
        assert "314" in sql
        assert "557" in sql

    def test_cnv_exclusion_filter_structure(self):
        """Verify CNV exclusion filter structure."""
        sql = get_cnv_exclusion_filter()
        assert "NOT" in sql
        assert "DEL" in sql
        assert "DUP" in sql


class TestProteinDomainHandlerMetadata:
    """Tests for handler metadata generation."""

    def test_inclusion_criteria_mentions_missense(self):
        """Inclusion criteria should mention missense-only."""
        handler = ProteinDomainHandler()
        criteria = handler._get_inclusion_exclusion_criteria()
        assert "missense" in criteria["inclusion_criteria"].lower()

    def test_exclusion_criteria_mentions_cnv(self):
        """Exclusion criteria should mention CNV exclusion."""
        handler = ProteinDomainHandler()
        criteria = handler._get_inclusion_exclusion_criteria()
        assert "cnv" in criteria["exclusion_criteria"].lower()

    def test_exclusion_criteria_mentions_truncating(self):
        """Exclusion criteria should mention truncating exclusion."""
        handler = ProteinDomainHandler()
        criteria = handler._get_inclusion_exclusion_criteria()
        assert "truncating" in criteria["exclusion_criteria"].lower()


class TestProteinDomainHandlerQueries:
    """Tests for SQL query generation."""

    def test_current_age_query_includes_missense_filter(self):
        """Current age query should include missense filter."""
        handler = ProteinDomainHandler()
        query = handler.build_current_age_query()
        # Check for missense pattern elements
        assert "hgvs.p" in query
        assert "expressions" in query

    def test_current_age_query_excludes_cnv(self):
        """Current age query should exclude CNVs."""
        handler = ProteinDomainHandler()
        query = handler.build_current_age_query()
        assert "DEL" in query
        assert "DUP" in query
        assert "NOT" in query

    def test_standard_query_includes_domain_classification(self):
        """Standard query should include domain classification."""
        handler = ProteinDomainHandler()
        query = handler.build_standard_query(["HP:0012626"])
        assert "domain_group" in query
        assert "CASE" in query

    def test_censored_query_includes_filters(self):
        """Censored query should include same filters."""
        handler = ProteinDomainHandler()
        query = handler._build_censored_query(["HP:0012626"])
        # Should have missense filter
        assert "hgvs.p" in query
        # Should exclude CNVs
        assert "DEL" in query
