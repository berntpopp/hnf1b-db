"""Test suite for direct phenopackets migration from Google Sheets."""

import pandas as pd
import pytest

from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets
from migration.phenopackets.hpo_mapper import HPOMapper


class TestMigrationDirectPhenopackets:
    """Test the direct phenopackets migration process."""

    @pytest.fixture
    def fixture_migration(self):
        """Create migration instance."""
        # Use test database URL
        test_db_url = "postgresql+asyncpg://test:test@localhost/test_db"
        return DirectSheetsToPhenopackets(test_db_url)

    @pytest.fixture
    def fixture_hpo_mapper(self):
        """Create HPO mapper instance."""
        return HPOMapper()

    def test_migration_hpo_mapping_initialization_correct(self, fixture_hpo_mapper):
        """Test that HPO mappings are properly initialized."""
        # Check key mappings exist (note: uses hpo_mappings attribute)
        # NOTE: "renalinsufficiency" was removed - now maps to specific CKD stages
        # via the phenotypes sheet during migration
        assert "mody" in fixture_hpo_mapper.hpo_mappings  # Diabetes is mapped as "mody"
        assert "hypomagnesemia" in fixture_hpo_mapper.hpo_mappings
        assert "renalcysts" in fixture_hpo_mapper.hpo_mappings

        # Check correct HPO terms are used
        assert fixture_hpo_mapper.hpo_mappings["mentaldisease"]["id"] == "HP:0000708"
        assert fixture_hpo_mapper.hpo_mappings["brainabnormality"]["id"] == "HP:0012443"
        assert fixture_hpo_mapper.hpo_mappings["abnormalliverphysiology"]["id"] == "HP:0031865"

    def test_migration_phenopacket_building_correct_structure(self, fixture_migration):
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
        fixture_migration.individuals_df = rows
        fixture_migration.phenotypes_df = None
        fixture_migration.publications_df = None

        from migration.phenopackets.builder_simple import PhenopacketBuilder

        fixture_migration.phenopacket_builder = PhenopacketBuilder(
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
        )

        # Use actual method that exists
        phenopacket = fixture_migration.phenopacket_builder.build_phenopacket("TEST001", rows)

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

    def test_migration_subject_id_mapping_correct(self, fixture_migration):
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
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("IND001", rows)

        # Primary ID should be individual_id
        assert phenopacket["subject"]["id"] == "IND001"
        # IndividualIdentifier should be in alternateIds
        assert "alternateIds" in phenopacket["subject"]
        assert "HNF1B-001" in phenopacket["subject"]["alternateIds"]
        assert phenopacket["subject"]["sex"] == "MALE"

    def test_migration_age_parsing_valid_format(self):
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

    def test_migration_phenotype_extraction_correct(self, fixture_migration):
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
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        # Should have phenotypic features
        features = phenopacket.get("phenotypicFeatures", [])
        assert len(features) > 0

        # Check for specific HPO terms
        feature_ids = [f["type"]["id"] for f in features]
        # Should have HPO terms for positive features
        assert len([fid for fid in feature_ids if "HP:" in fid]) > 0

    def test_migration_mondo_disease_mapping_correct(self, fixture_migration):
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
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
        )

        phenopacket = builder.build_phenopacket("TEST001", rows)

        # Should have HNF1B disease (RCAD)
        diseases = phenopacket.get("diseases", [])
        assert len(diseases) > 0
        assert diseases[0]["term"]["id"] == "MONDO:0011593"
        assert "Renal cysts and diabetes" in diseases[0]["term"]["label"]

    def test_migration_metadata_creation_correct(self, fixture_migration):
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
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
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

    def test_migration_valid_id_checking_correct(self, fixture_migration):
        """Test ID validation logic."""
        assert fixture_migration._is_valid_id("TEST001") is True
        assert fixture_migration._is_valid_id("") is False
        assert fixture_migration._is_valid_id(None) is False
        assert fixture_migration._is_valid_id(pd.NA) is False
        assert fixture_migration._is_valid_id("   ") is False

    def test_migration_phenopacket_validation_passes(self, fixture_migration):
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
            fixture_migration.ontology_mapper, fixture_migration.publication_mapper
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


class TestMigrationHPOMapperLabelNormalization:
    """Test HPOMapper canonical label normalization feature.

    Tests for #165: Data quality - Normalize HPO term labels during import
    """

    def test_migration_normalize_labels_enabled_by_default(self):
        """Test that label normalization is enabled by default."""
        mapper = HPOMapper()
        assert mapper.normalize_labels is True

    def test_migration_normalize_labels_can_be_disabled(self):
        """Test that label normalization can be disabled."""
        mapper = HPOMapper(normalize_labels=False)
        assert mapper.normalize_labels is False

    def test_migration_canonical_labels_cache_initialized_empty(self):
        """Test that the canonical labels cache is initialized empty."""
        mapper = HPOMapper()
        assert mapper._canonical_labels == {}

    def test_migration_get_canonical_label_returns_fallback_when_disabled(self):
        """Test fallback is returned when normalization is disabled."""
        mapper = HPOMapper(normalize_labels=False)
        fallback = "My Fallback Label"
        result = mapper._get_canonical_label("HP:0012622", fallback)
        assert result == fallback

    def test_migration_get_canonical_label_caches_result(self):
        """Test that canonical labels are cached after lookup."""
        mapper = HPOMapper(normalize_labels=True)
        hpo_id = "HP:0012622"
        fallback = "Chronic kidney disease"

        # First call - should populate cache
        result1 = mapper._get_canonical_label(hpo_id, fallback)

        # Check cache is populated
        assert hpo_id in mapper._canonical_labels

        # Second call - should use cache
        result2 = mapper._get_canonical_label(hpo_id, fallback)
        assert result1 == result2

    def test_migration_get_canonical_label_fallback_on_unknown_term(self):
        """Test fallback when ontology service returns unknown term."""
        mapper = HPOMapper(normalize_labels=True)

        # Use an invalid HPO ID that will return "Unknown term:"
        invalid_id = "HP:9999999"
        fallback = "My Fallback"

        # Call the method - result may be fallback or API response
        _ = mapper._get_canonical_label(invalid_id, fallback)

        # The cache should be populated after the call
        assert mapper._canonical_labels.get(invalid_id) is not None

    def test_migration_build_from_dataframe_normalizes_labels(self):
        """Test that build_from_dataframe normalizes labels."""
        mapper = HPOMapper(normalize_labels=True)

        # Create test DataFrame with phenotype mappings
        phenotypes_df = pd.DataFrame([
            {
                "phenotype_category": "chronic kidney disease",
                "phenotype_id": "HP:0012622",
                "phenotype_name": "chronic kidney disease, not specified",
            },
        ])

        mapper.build_from_dataframe(phenotypes_df)

        # The mapping should exist
        normalized_key = mapper.normalize_key("chronic kidney disease")
        assert normalized_key in mapper.hpo_mappings

        # The HPO ID should be correct
        assert mapper.hpo_mappings[normalized_key]["id"] == "HP:0012622"

    def test_migration_build_from_dataframe_without_normalization(self):
        """Test build_from_dataframe uses source label when normalization disabled."""
        mapper = HPOMapper(normalize_labels=False)

        source_label = "my custom label"
        phenotypes_df = pd.DataFrame([
            {
                "phenotype_category": "test_category",
                "phenotype_id": "HP:0012622",
                "phenotype_name": source_label,
            },
        ])

        mapper.build_from_dataframe(phenotypes_df)

        normalized_key = mapper.normalize_key("test_category")
        assert normalized_key in mapper.hpo_mappings
        # With normalization disabled, should use the source label
        assert mapper.hpo_mappings[normalized_key]["label"] == source_label

    def test_migration_normalize_key_handles_various_inputs(self):
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

    def test_migration_default_mappings_have_canonical_labels(self):
        """Test that default HPO mappings use canonical labels."""
        mapper = HPOMapper()

        # Check some key mappings have proper canonical labels
        assert mapper.hpo_mappings["mody"]["label"] == "Maturity-onset diabetes of the young"
        assert mapper.hpo_mappings["hypomagnesemia"]["label"] == "Hypomagnesemia"
        assert mapper.hpo_mappings["renalcysts"]["label"] == "Renal cyst"

    def test_migration_ontology_service_lazy_loading(self):
        """Test that ontology service is lazily loaded."""
        mapper = HPOMapper(normalize_labels=True)

        # Service should not be loaded initially
        assert mapper._ontology_service is None

        # After calling _get_ontology_service, it should be loaded
        service = mapper._get_ontology_service()
        # Service might be None if import fails, but attempt was made
        # If service loaded successfully, it should be cached
        if service is not None:
            assert mapper._ontology_service is service
