"""Test suite for direct phenopackets migration from Google Sheets."""

import json
from unittest.mock import Mock, patch

import pytest

from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets


class TestDirectPhenopacketsMigration:
    """Test the direct phenopackets migration process."""

    @pytest.fixture
    def migration(self):
        """Create migration instance."""
        # Use test database URL
        test_db_url = "postgresql+asyncpg://test:test@localhost/test_db"
        return DirectSheetsToPhenopackets(test_db_url)

    def test_hpo_mapping_initialization(self, migration):
        """Test that HPO mappings are properly initialized."""
        # Check key mappings exist
        assert "renalinsufficiency" in migration.hpo_mappings
        assert "diabetes" in migration.hpo_mappings
        assert "hypomagnesemia" in migration.hpo_mappings

        # Check correct HPO terms are used
        assert migration.hpo_mappings["mentaldisease"]["id"] == "HP:0000708"
        assert migration.hpo_mappings["brainabnormality"]["id"] == "HP:0012443"
        assert migration.hpo_mappings["abnormalliverphysiology"]["id"] == "HP:0031865"

    def test_subject_id_mapping(self, migration):
        """Test that subject IDs are correctly mapped."""
        row = {
            "individual_id": "IND001",
            "IndividualIdentifier": "HNF1B-001",
            "Sex": "Male",
            "AgeReported": "45"
        }

        subject = migration._build_subject(row)

        # Primary ID should be individual_id
        assert subject["id"] == "IND001"
        # IndividualIdentifier should be in alternateIds
        assert "alternateIds" in subject
        assert "HNF1B-001" in subject["alternateIds"]
        assert subject["sex"] == "MALE"

    def test_age_mapping(self, migration):
        """Test age field mappings."""
        # Test AgeReported mapping
        age_reported = migration._parse_age("P45Y")
        assert age_reported["age"]["iso8601duration"] == "P45Y"

        # Test AgeOnset mapping for disease
        row = {"AgeOnset": "32"}
        onset = migration._parse_disease_onset(row)
        assert onset is not None
        assert "age" in onset
        assert "P32Y" in onset["age"]["iso8601duration"]

    def test_variant_prioritization(self, migration):
        """Test that Varsome column is prioritized for variants."""
        row = {
            "Varsome": "NM_000458.3:c.523C>T",
            "hg38": "chr17:36046434C>T",
            "VariantInterpretation": "Pathogenic"
        }

        variant = migration._extract_variant_from_row(row)

        # Should use Varsome column as primary source
        assert variant is not None
        assert "c.523C>T" in variant.get("label", "")
        assert variant.get("hgvs") == "NM_000458.3:c.523C>T"

    def test_phenotype_extraction(self, migration):
        """Test phenotypic feature extraction."""
        row = {
            "RenalInsufficiency": "1",
            "Diabetes": "1",
            "Hypomagnesemia": "0",
            "MentalDisease": "1"
        }

        features = migration._extract_phenotypes(row)

        # Should have features for positive values
        assert len(features) > 0

        # Check for specific HPO terms
        feature_ids = [f["type"]["id"] for f in features]
        assert "HP:0000083" in feature_ids  # Renal insufficiency
        assert "HP:0000819" in feature_ids  # Diabetes
        assert "HP:0000708" in feature_ids  # Behavioral abnormality (not Schizophrenia)

        # Hypomagnesemia should not be included (value is 0)
        assert "HP:0002917" not in feature_ids

    @patch('pandas.read_csv')
    def test_dry_run_mode(self, mock_read_csv, migration):
        """Test dry run mode outputs to JSON."""
        # Mock CSV data
        mock_df = Mock()
        mock_df.iterrows.return_value = [
            (0, {"individual_id": "TEST001", "Sex": "Female"})
        ]
        mock_df.__len__ = Mock(return_value=1)
        mock_read_csv.return_value = mock_df

        migration.dry_run = True

        # In dry run, should create JSON file instead of database insert
        with patch('builtins.open', create=True) as mock_open:
            with patch('json.dump') as mock_json_dump:
                migration.migrate()

                # Should write to JSON file
                mock_json_dump.assert_called()

    def test_mondo_disease_mapping(self, migration):
        """Test MONDO disease ontology mapping."""
        diseases = migration._map_diseases({})

        # Should have HNF1B disease
        assert len(diseases) > 0
        assert diseases[0]["term"]["id"] == "MONDO:0018874"
        assert "HNF1B" in diseases[0]["term"]["label"]

    def test_metadata_creation(self, migration):
        """Test metadata creation for phenopackets."""
        metadata = migration._create_metadata()

        assert metadata["phenopacketSchemaVersion"] == "2.0.0"
        assert "created" in metadata
        assert "createdBy" in metadata
        assert len(metadata["resources"]) > 0

        # Check for required ontology resources
        resource_ids = [r["id"] for r in metadata["resources"]]
        assert "hpo" in resource_ids
        assert "mondo" in resource_ids

    def test_phenopacket_validation(self, migration):
        """Test that created phenopackets pass basic validation."""
        row = {
            "individual_id": "TEST001",
            "IndividualIdentifier": "HNF1B-TEST001",
            "Sex": "Male",
            "AgeReported": "45",
            "RenalInsufficiency": "1",
            "Diabetes": "1"
        }

        phenopacket = migration._create_phenopacket(row, 1)

        # Basic structure validation
        assert "id" in phenopacket
        assert "subject" in phenopacket
        assert "metaData" in phenopacket
        assert "phenotypicFeatures" in phenopacket
        assert "diseases" in phenopacket

        # Subject validation
        assert phenopacket["subject"]["id"] == "TEST001"
        assert phenopacket["subject"]["sex"] == "MALE"

        # Features validation
        assert len(phenopacket["phenotypicFeatures"]) > 0