"""Test suite for phenopackets migration."""

import asyncio
import json
from typing import Any, Dict, List

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketValidator
from migration.phenopackets_migration import PhenopacketsMigrationFixed as PhenopacketsMigration


@pytest.mark.asyncio
class TestPhenopacketsMigration:
    """Test the phenopackets migration process."""

    @pytest.fixture
    async def test_db(self):
        """Create test database session."""
        engine = create_async_engine(
            "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_test"
        )
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            yield session
        await engine.dispose()

    @pytest.fixture
    def sample_individual(self) -> Dict[str, Any]:
        """Sample individual data."""
        return {
            "id": "test-001",
            "individual_id": "IND001",
            "sex": "female",
            "dup_check": "DUP001",
            "individual_identifier": "ORIG001",
        }

    @pytest.fixture
    def sample_report(self) -> Dict[str, Any]:
        """Sample report data."""
        return {
            "id": "report-001",
            "individual_id": "test-001",
            "report_date": "2024-01-15",
            "age_reported": 25,
            "age_onset": 10,
            "egfr": 45.0,
            "phenotypes": {
                "renalInsufficiency": {
                    "described": "yes, stage 3",
                    "age_onset": 15,
                    "phenotype_id": "HP:0012622",
                    "name": "Chronic kidney disease",
                },
                "kidneyBiopsy": {
                    "multipleGlomerularCysts": {
                        "described": "yes",
                        "phenotype_id": "HP:0100611",
                        "name": "Multiple glomerular cysts",
                    }
                },
                "genitalTractAbnormalities": {
                    "described": "bicornuate uterus",
                    "phenotype_id": "HP:0000078",
                },
                "diabetes": {
                    "described": "type 2",
                    "age_onset": 20,
                },
                "hypomagnesemia": {
                    "described": "yes",
                    "phenotype_id": "HP:0002917",
                },
            },
        }

    @pytest.fixture
    def sample_variant(self) -> Dict[str, Any]:
        """Sample variant data."""
        return {
            "id": "var-001",
            "individual_id": "test-001",
            "c_dot": "c.544C>T",
            "p_dot": "p.Arg182*",
            "acmg_classification": "Pathogenic",
            "zygosity": "heterozygous",
            "is_current": True,
        }

    def test_phenotype_mapping_completeness(self):
        """Test that key HPO phenotypes are mapped."""
        # Mock database URLs for testing
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)
        mappings = migration.phenotype_mappings

        # Test that important phenotypes are mapped (using actual keys)
        key_phenotypes = [
            "HP:0012622",  # Chronic kidney disease
            "HP:0100611",  # Multiple glomerular cysts
            "Hypomagnesemia",  # Hypomagnesemia
            "GenitalTractAbnormality",  # Genital tract abnormality
        ]

        for phenotype_key in key_phenotypes:
            assert phenotype_key in mappings, f"Missing mapping for {phenotype_key}"
            mapping = mappings[phenotype_key]
            if isinstance(mapping, dict) and "id" in mapping:
                assert "label" in mapping

    def test_disease_mapping_completeness(self):
        """Test that all required diseases are mapped."""
        # Mock database URLs for testing
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)
        mappings = migration.disease_mappings

        required_diseases = ["hnf1b", "diabetes_type1", "diabetes_type2", "mody"]

        for disease in required_diseases:
            assert disease in mappings, f"Missing mapping for {disease}"
            assert "id" in mappings[disease]
            assert "label" in mappings[disease]

    @pytest.mark.asyncio
    async def test_transform_to_phenopacket(
        self, sample_individual, sample_report, sample_variant
    ):
        """Test transformation of normalized data to phenopacket format."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)

        data = {
            "individuals": [sample_individual],
            "reports": [sample_report],
            "variants": [sample_variant],
            "users": [],
        }

        phenopackets = await migration.transform_to_phenopackets(data)

        assert len(phenopackets) == 1
        phenopacket = phenopackets[0]

        # Check basic structure
        assert phenopacket["id"] == "phenopacket:HNF1B:IND001"
        assert "subject" in phenopacket
        assert "phenotypicFeatures" in phenopacket
        assert "diseases" in phenopacket
        assert "interpretations" in phenopacket
        assert "metaData" in phenopacket

        # Check subject
        subject = phenopacket["subject"]
        assert subject["id"] == "IND001"
        assert subject["sex"] == "FEMALE"
        assert "timeAtLastEncounter" in subject

        # Check phenotypic features
        features = phenopacket["phenotypicFeatures"]
        assert len(features) > 0

        # Check for renal insufficiency
        renal_features = [f for f in features if f["type"]["id"] == "HP:0012622"]
        assert len(renal_features) == 1
        assert renal_features[0]["type"]["label"] == "Chronic kidney disease"

        # Check for hypomagnesemia
        hypo_features = [f for f in features if f["type"]["id"] == "HP:0002917"]
        assert len(hypo_features) == 1

        # Check diseases
        diseases = phenopacket["diseases"]
        assert len(diseases) >= 1
        hnf1b_disease = [d for d in diseases if "HNF1B" in d["term"]["label"]]
        assert len(hnf1b_disease) == 1

        # Check interpretations
        interpretations = phenopacket["interpretations"]
        assert len(interpretations) == 1
        assert interpretations[0]["progressStatus"] == "COMPLETED"
        assert "diagnosis" in interpretations[0]

    def test_phenopacket_validation(self, sample_individual, sample_report):
        """Test phenopacket validation."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)
        validator = PhenopacketValidator()

        # Create a minimal valid phenopacket
        phenopacket = {
            "id": "test-phenopacket",
            "subject": {"id": "test-subject", "sex": "FEMALE"},
            "meta_data": {
                "created": "2024-01-01T00:00:00Z",
                "created_by": "test",
                "resources": [
                    {
                        "id": "hpo",
                        "name": "Human Phenotype Ontology",
                        "namespace_prefix": "HP",
                    }
                ],
            },
        }

        errors = validator.validate(phenopacket)
        assert len(errors) == 0, f"Valid phenopacket failed validation: {errors}"

        # Test invalid phenopacket (missing required fields)
        invalid_phenopacket = {"id": "test"}
        errors = validator.validate(invalid_phenopacket)
        assert len(errors) > 0, "Invalid phenopacket passed validation"

    def test_sex_mapping(self):
        """Test sex value mapping."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)

        assert migration._map_sex("female") == "FEMALE"
        assert migration._map_sex("F") == "FEMALE"
        assert migration._map_sex("male") == "MALE"
        assert migration._map_sex("M") == "MALE"
        assert migration._map_sex(None) == "UNKNOWN_SEX"
        assert migration._map_sex("other") == "OTHER_SEX"

    def test_age_parsing(self):
        """Test age to ISO8601 duration parsing."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)

        assert migration._parse_age_to_iso8601(25) == {"iso8601duration": "P25Y"}
        assert migration._parse_age_to_iso8601("30") == {"iso8601duration": "P30Y"}
        assert migration._parse_age_to_iso8601("15 years") == {"iso8601duration": "P15Y"}
        assert migration._parse_age_to_iso8601(None) == {"iso8601duration": "P0Y"}

    def test_pathogenicity_mapping(self):
        """Test ACMG classification mapping."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)

        assert migration._map_pathogenicity("Pathogenic") == "PATHOGENIC"
        assert migration._map_pathogenicity("Likely pathogenic") == "LIKELY_PATHOGENIC"
        assert (
            migration._map_pathogenicity("Uncertain significance")
            == "UNCERTAIN_SIGNIFICANCE"
        )
        assert migration._map_pathogenicity("Likely benign") == "LIKELY_BENIGN"
        assert migration._map_pathogenicity("Benign") == "BENIGN"
        assert migration._map_pathogenicity("Unknown") == "UNCERTAIN_SIGNIFICANCE"

    def test_variant_label_building(self):
        """Test variant label construction."""
        mock_source = "postgresql+asyncpg://test:test@localhost/test_source"
        mock_target = "postgresql+asyncpg://test:test@localhost/test_target"
        migration = PhenopacketsMigration(mock_source, mock_target)

        variant = {"c_dot": "c.544C>T", "p_dot": "p.Arg182*"}
        label = migration._build_variant_label(variant)
        assert label == "HNF1B:c.544C>T:(p.Arg182*)"

        variant_no_p = {"c_dot": "c.544C>T"}
        label = migration._build_variant_label(variant_no_p)
        assert label == "HNF1B:c.544C>T"

    @pytest.mark.asyncio
    async def test_end_to_end_migration(self):
        """Test complete migration process with sample data."""
        # This would require a test database setup
        # Skipping for now as it needs database infrastructure
        pass

    def test_sanitizer(self):
        """Test phenopacket sanitizer."""
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Test removing nulls
        data = {
            "id": "test",
            "subject": {"id": "sub1", "sex": None},
            "features": [None, {"type": "HP:0001234"}],
            "empty_array": [],
            "empty_object": {},
        }

        sanitized = sanitizer.sanitize_phenopacket(data)

        assert "sex" not in sanitized["subject"]
        assert None not in sanitized["features"]
        assert "empty_array" not in sanitized
        assert "empty_object" not in sanitized

    def test_ontology_term_normalization(self):
        """Test ontology term normalization."""
        from app.phenopackets.validator import PhenopacketSanitizer

        sanitizer = PhenopacketSanitizer()

        # Test uppercase normalization
        term = {"id": "hp:0001234", "label": "Test"}
        normalized = sanitizer.normalize_ontology_term(term)
        assert normalized["id"] == "HP:0001234"

        term = {"id": "mondo:0005147", "label": "Diabetes"}
        normalized = sanitizer.normalize_ontology_term(term)
        assert normalized["id"] == "MONDO:0005147"

        # Test non-standard terms are unchanged
        term = {"id": "custom:001", "label": "Custom"}
        normalized = sanitizer.normalize_ontology_term(term)
        assert normalized["id"] == "custom:001"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_migration_integration():
    """Integration test for migration (requires database)."""
    # This test would run the actual migration on a test database
    # Requires proper test database setup
    pass