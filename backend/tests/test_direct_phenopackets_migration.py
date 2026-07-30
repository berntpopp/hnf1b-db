"""Test suite for direct phenopackets migration from Google Sheets."""

import pandas as pd
import pytest

from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets
from migration.phenopackets.hpo_mapper import HPOMapper


class TestDirectPhenopacketsMigration:
    """Test the direct phenopackets migration process."""

    @pytest.fixture
    def migration(self):
        """Create migration instance."""
        # Use test database URL
        test_db_url = "postgresql+asyncpg://test:test@localhost/test_db"
        return DirectSheetsToPhenopackets(test_db_url)

    @pytest.fixture
    def hpo_mapper(self):
        """Create HPO mapper instance."""
        return HPOMapper()

    def test_hpo_mapping_initialization(self, hpo_mapper):
        """Test that HPO mappings are properly initialized."""
        # Check key mappings exist (note: uses hpo_mappings attribute)
        # NOTE: "renalinsufficiency" was removed - now maps to specific CKD stages
        # via the phenotypes sheet during migration
        assert "mody" in hpo_mapper.hpo_mappings  # Diabetes is mapped as "mody"
        assert "hypomagnesemia" in hpo_mapper.hpo_mappings
        assert "renalcysts" in hpo_mapper.hpo_mappings

        # Check correct HPO terms are used
        assert hpo_mapper.hpo_mappings["mentaldisease"]["id"] == "HP:0000708"
        assert hpo_mapper.hpo_mappings["brainabnormality"]["id"] == "HP:0012443"
        assert hpo_mapper.hpo_mappings["abnormalliverphysiology"]["id"] == "HP:0031865"

    def test_phenopacket_building(self, migration):
        """Test actual phenopacket construction."""
        # Create test data
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "TEST001",
                    "IndividualIdentifier": "HNF1B-001",
                    "Sex": "Male",
                    "AgeReported": "45",
                    "RenalInsufficiency": "1",
                    "Diabetes": "1",
                    "Hypomagnesemia": "0",
                }
            ]
        )

        # Initialize required components
        migration.individuals_df = rows
        migration.phenotypes_df = None
        migration.publications_df = None

        from migration.phenopackets.builder_simple import PhenopacketBuilder

        migration.phenopacket_builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        # Use actual method that exists
        phenopacket = migration.phenopacket_builder.build_phenopacket("TEST001", rows)

        # Basic structure validation
        assert phenopacket["id"] == "phenopacket-TEST001"
        assert phenopacket["subject"]["id"] == "TEST001"
        assert phenopacket["subject"]["sex"] == "MALE"

        # Check for phenotypic features
        assert "phenotypicFeatures" in phenopacket
        feature_ids = [
            f["type"]["id"] for f in phenopacket.get("phenotypicFeatures", [])
        ]
        # Should have renal insufficiency and diabetes
        assert any("HP:" in fid for fid in feature_ids)

    def test_subject_id_mapping(self, migration):
        """Test that subject IDs are correctly mapped."""
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "IND001",
                    "IndividualIdentifier": "HNF1B-001",
                    "Sex": "Male",
                    "AgeReported": "45",
                }
            ]
        )

        # Initialize builder
        from migration.phenopackets.builder_simple import PhenopacketBuilder

        builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("IND001", rows)

        # Primary ID should be individual_id
        assert phenopacket["subject"]["id"] == "IND001"
        # IndividualIdentifier should be in alternateIds
        assert "alternateIds" in phenopacket["subject"]
        assert "HNF1B-001" in phenopacket["subject"]["alternateIds"]
        assert phenopacket["subject"]["sex"] == "MALE"

    def test_age_parsing(self):
        """Test age field parsing."""
        from migration.phenopackets.age_parser import AgeParser

        parser = AgeParser()

        # Test valid age
        age_obj = parser.parse_age("45")
        assert age_obj is not None
        assert "iso8601duration" in age_obj
        assert age_obj["iso8601duration"] == "P45Y"

        # Test empty age
        assert parser.parse_age(None) is None
        assert parser.parse_age("") is None

    def test_phenotype_extraction(self, migration):
        """Test phenotypic feature extraction."""
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "TEST001",
                    "Sex": "Male",
                    "RenalInsufficiency": "1",
                    "Diabetes": "1",
                    "Hypomagnesemia": "0",
                    "MentalDisease": "1",
                }
            ]
        )

        # Initialize builder
        from migration.phenopackets.builder_simple import PhenopacketBuilder

        builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        # Should have phenotypic features
        features = phenopacket.get("phenotypicFeatures", [])
        assert len(features) > 0

        # Check for specific HPO terms
        feature_ids = [f["type"]["id"] for f in features]
        # Should have HPO terms for positive features
        assert len([fid for fid in feature_ids if "HP:" in fid]) > 0

    def test_mondo_disease_mapping(self, migration):
        """Test MONDO disease ontology mapping."""
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "TEST001",
                    "Sex": "Female",
                }
            ]
        )

        # Initialize builder
        from migration.phenopackets.builder_simple import PhenopacketBuilder

        builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        # Should have HNF1B disease (RCAD). MONDO:0011593 is "seizures, benign
        # familial infantile, 2" -- the pre-correction value this test used to
        # assert; see docs/ontology-defect-report-2026-07-30.md T2 and commit
        # 2acfe03, which fixed builder_simple.py to emit the correct term.
        diseases = phenopacket.get("diseases", [])
        assert len(diseases) > 0
        assert diseases[0]["term"]["id"] == "MONDO:0007669"
        assert "renal cysts and diabetes" in diseases[0]["term"]["label"]

    def test_metadata_creation(self, migration):
        """Test metadata creation for phenopackets."""
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "TEST001",
                    "Sex": "Female",
                }
            ]
        )

        # Initialize builder
        from migration.phenopackets.builder_simple import PhenopacketBuilder

        builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        metadata = phenopacket["metaData"]

        assert metadata["phenopacketSchemaVersion"] == "2.0.0"
        assert "created" in metadata
        assert "createdBy" in metadata
        assert len(metadata["resources"]) > 0

        # Check for required ontology resources (note: uses "hp" not "hpo")
        resource_ids = [r["id"] for r in metadata["resources"]]
        assert "hp" in resource_ids
        assert "mondo" in resource_ids

    def test_valid_id_checking(self, migration):
        """Test ID validation logic."""
        assert migration._is_valid_id("TEST001") is True
        assert migration._is_valid_id("") is False
        assert migration._is_valid_id(None) is False
        assert migration._is_valid_id(pd.NA) is False
        assert migration._is_valid_id("   ") is False

    def test_phenopacket_validation(self, migration):
        """Test that created phenopackets pass basic validation."""
        rows = pd.DataFrame(
            [
                {
                    "individual_id": "TEST001",
                    "IndividualIdentifier": "HNF1B-TEST001",
                    "Sex": "Male",
                    "AgeReported": "45",
                    "RenalInsufficiency": "1",
                    "Diabetes": "1",
                }
            ]
        )

        # Initialize builder
        from migration.phenopackets.builder_simple import PhenopacketBuilder

        builder = PhenopacketBuilder(
            migration.ontology_mapper, migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        # Basic structure validation
        assert "id" in phenopacket
        assert "subject" in phenopacket
        assert "metaData" in phenopacket
        assert "diseases" in phenopacket

        # Subject validation
        assert phenopacket["subject"]["id"] == "TEST001"
        assert phenopacket["subject"]["sex"] == "MALE"

        # Features validation (phenotypicFeatures may be present if features exist)
        # Note: empty features are not included in output
        features = phenopacket.get("phenotypicFeatures", [])
        # If features exist, they should be valid
        if features:
            assert len(features) > 0


class TestHPOMapperLabelNormalization:
    """Test HPOMapper's default term table and verbatim label handling.

    Originally written for #165 ("Data quality: Normalize HPO term labels
    during import"), which added HPOMapper._get_canonical_label to rewrite
    a curator's phenotype_name to whatever the HPO API considered canonical
    for the sheet's phenotype_id. That silently inverted a clinical finding
    for HP:0033133 across 460 records (see
    docs/ontology-defect-report-2026-07-30.md §4.1): the importer trusted
    the identifier and overwrote the name, so a name/id mismatch could never
    surface. The tests that exercised that machinery (normalize_labels flag,
    _canonical_labels cache, _get_canonical_label, _get_ontology_service)
    have been removed along with the code; a name that disagrees with its
    identifier is now a defect for a human to resolve, never something the
    importer repairs. See tests/migration/test_no_label_laundering.py for
    the regression coverage.
    """

    def test_build_from_dataframe_uses_source_label_verbatim(self):
        """build_from_dataframe must never substitute a canonical label."""
        mapper = HPOMapper()

        source_label = "my custom label"
        phenotypes_df = pd.DataFrame(
            [
                {
                    "phenotype_category": "test_category",
                    "phenotype_id": "HP:0012622",
                    "phenotype_name": source_label,
                    # A1 (check_source_row, spec §3.3) corroborates the id
                    # against this description before the row is used; it is
                    # HP:0012622's own canonical definition, so the row
                    # passes even though the name is a made-up local label.
                    "phenotype_description": (
                        "Functional anomaly of the kidney persisting for at "
                        "least three months."
                    ),
                },
            ]
        )

        mapper.build_from_dataframe(phenotypes_df)

        normalized_key = mapper.normalize_key("test_category")
        assert normalized_key in mapper.hpo_mappings
        # The curator's label is used as-is, never replaced with the
        # canonical HPO name for HP:0012622.
        assert mapper.hpo_mappings[normalized_key]["label"] == source_label

    def test_normalize_key_handles_various_inputs(self):
        """Test normalize_key handles various input formats."""
        mapper = HPOMapper()

        # Standard input
        assert mapper.normalize_key("Chronic Kidney Disease") == "chronickidneydisease"

        # With underscores
        assert mapper.normalize_key("chronic_kidney_disease") == "chronickidneydisease"

        # With spaces and mixed case
        assert mapper.normalize_key("CHRONIC kidney Disease") == "chronickidneydisease"

        # Empty/None handling
        assert mapper.normalize_key("") == ""
        assert mapper.normalize_key(None) == ""

    def test_default_mappings_have_canonical_labels(self):
        """Test that default HPO mappings use canonical labels."""
        mapper = HPOMapper()

        # Check some key mappings have proper canonical labels
        assert (
            mapper.hpo_mappings["mody"]["label"]
            == "Maturity-onset diabetes of the young"
        )
        assert mapper.hpo_mappings["hypomagnesemia"]["label"] == "Hypomagnesemia"
        assert mapper.hpo_mappings["renalcysts"]["label"] == "Renal cyst"
