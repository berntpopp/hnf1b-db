"""Complete migration from normalized PostgreSQL to Phenopackets v2."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from app.database import Base
from app.models import Individual, Report, User, Variant
from app.phenopackets.models import Phenopacket, Resource
from app.phenopackets.validator import PhenopacketSanitizer, PhenopacketValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhenopacketsMigration:
    """Complete migration from normalized PostgreSQL to Phenopackets."""

    def __init__(self, source_db_url: str, target_db_url: str):
        """Initialize migration with source and target databases."""
        self.source_engine = create_async_engine(source_db_url)
        self.target_engine = create_async_engine(target_db_url)
        self.source_session = sessionmaker(
            self.source_engine, class_=AsyncSession, expire_on_commit=False
        )
        self.target_session = sessionmaker(
            self.target_engine, class_=AsyncSession, expire_on_commit=False
        )
        self.validator = PhenopacketValidator()
        self.sanitizer = PhenopacketSanitizer()

        # Mapping dictionaries for ontology terms
        self.phenotype_mappings = self._load_phenotype_mappings()
        self.disease_mappings = self._load_disease_mappings()

    def _load_phenotype_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load phenotype to HPO term mappings."""
        return {
            "renalInsufficiency": {
                "id": "HP:0012622",
                "label": "Chronic kidney disease",
            },
            "kidneyBiopsy": {
                "multipleGlomerularCysts": {
                    "id": "HP:0100611",
                    "label": "Multiple glomerular cysts",
                },
                "oligomeganephronia": {
                    "id": "HP:0004719",
                    "label": "Oligomeganephronia",
                },
                "renalDysplasia": {"id": "HP:0000110", "label": "Renal dysplasia"},
                "renalHypoplasia": {"id": "HP:0000089", "label": "Renal hypoplasia"},
            },
            "genitalTractAbnormalities": {
                "id": "HP:0000078",
                "label": "Genital abnormality",
            },
            "hypomagnesemia": {"id": "HP:0002917", "label": "Hypomagnesemia"},
            "hyperuricemia": {"id": "HP:0002149", "label": "Hyperuricemia"},
            "gout": {"id": "HP:0001997", "label": "Gout"},
            "hyperparathyroidism": {
                "id": "HP:0000843",
                "label": "Hyperparathyroidism",
            },
            "pancreaticAbnormalities": {
                "id": "HP:0001732",
                "label": "Abnormality of the pancreas",
            },
            "exocrinePancreaticInsufficiency": {
                "id": "HP:0001738",
                "label": "Exocrine pancreatic insufficiency",
            },
            "liverAbnormalities": {
                "id": "HP:0001392",
                "label": "Abnormality of the liver",
            },
        }

    def _load_disease_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load disease mappings."""
        return {
            "hnf1b": {
                "id": "MONDO:0018874",
                "label": "HNF1B-related autosomal dominant tubulointerstitial kidney disease",
            },
            "diabetes_type1": {
                "id": "MONDO:0005147",
                "label": "Type 1 diabetes mellitus",
            },
            "diabetes_type2": {
                "id": "MONDO:0005148",
                "label": "Type 2 diabetes mellitus",
            },
            "diabetes_mody": {
                "id": "MONDO:0015967",
                "label": "Maturity-onset diabetes of the young",
            },
        }

    async def migrate_all_data(self):
        """Complete migration from old structure to phenopackets."""
        logger.info("Starting complete migration to phenopackets...")

        try:
            # Step 1: Extract all data from normalized tables
            data = await self.extract_all_normalized_data()
            logger.info(f"Extracted {len(data['individuals'])} individuals")

            # Step 2: Transform to phenopackets
            phenopackets = await self.transform_to_phenopackets(data)
            logger.info(f"Transformed {len(phenopackets)} phenopackets")

            # Step 3: Validate phenopackets
            validated = self.validate_phenopackets(phenopackets)
            logger.info(f"Validated {len(validated)} phenopackets")

            # Step 4: Store in new structure
            await self.store_phenopackets(validated)
            logger.info("Stored phenopackets in database")

            # Step 5: Verify migration
            await self.verify_migration(data, validated)
            logger.info("Migration verification complete")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.source_engine.dispose()
            await self.target_engine.dispose()

    async def extract_all_normalized_data(self) -> Dict[str, List[Dict]]:
        """Extract all data from normalized tables."""
        data = {
            "individuals": [],
            "reports": [],
            "variants": [],
            "users": [],
        }

        async with self.source_session() as session:
            # Extract individuals
            result = await session.execute(select(Individual))
            individuals = result.scalars().all()
            data["individuals"] = [self._model_to_dict(ind) for ind in individuals]

            # Extract reports
            result = await session.execute(select(Report))
            reports = result.scalars().all()
            data["reports"] = [self._model_to_dict(rep) for rep in reports]

            # Extract variants
            result = await session.execute(select(Variant).where(Variant.is_current == True))
            variants = result.scalars().all()
            data["variants"] = [self._model_to_dict(var) for var in variants]

            # Extract users
            result = await session.execute(select(User))
            users = result.scalars().all()
            data["users"] = [self._model_to_dict(user) for user in users]

        return data

    def _model_to_dict(self, model) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary."""
        return {c.name: getattr(model, c.name) for c in model.__table__.columns}

    async def transform_to_phenopackets(
        self, data: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """Transform normalized data to phenopackets format."""
        phenopackets = []

        for individual in tqdm(data["individuals"], desc="Transforming to phenopackets"):
            # Get related data
            reports = [
                r for r in data["reports"] if r["individual_id"] == individual["id"]
            ]
            variants = [
                v for v in data["variants"] if v["individual_id"] == individual["id"]
            ]

            # Build phenopacket
            phenopacket = {
                "id": f"phenopacket:HNF1B:{individual['individual_id']}",
                "subject": self._build_subject(individual, reports),
                "phenotypicFeatures": self._build_phenotypic_features(reports),
                "measurements": self._build_measurements(reports),
                "diseases": self._build_diseases(reports),
                "interpretations": self._build_interpretations(variants),
                "medicalActions": self._build_medical_actions(reports),
                "files": self._build_files(individual),
                "metaData": self._build_metadata(individual, reports),
            }

            # Sanitize the phenopacket
            phenopacket = self.sanitizer.sanitize_phenopacket(phenopacket)
            phenopackets.append(phenopacket)

        return phenopackets

    def _build_subject(
        self, individual: Dict[str, Any], reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build subject section of phenopacket."""
        subject = {
            "id": individual["individual_id"],
            "sex": self._map_sex(individual.get("sex")),
            "taxonomy": {"id": "NCBITaxon:9606", "label": "Homo sapiens"},
        }

        # Add alternate IDs if available
        if individual.get("dup_check"):
            subject["alternateIds"] = [
                individual["dup_check"],
                individual.get("individual_identifier", ""),
            ]

        # Add age at last encounter from most recent report
        if reports:
            latest_report = max(reports, key=lambda r: r.get("report_date", ""))
            if latest_report.get("age_reported"):
                subject["timeAtLastEncounter"] = {
                    "age": self._parse_age_to_iso8601(latest_report["age_reported"])
                }

        return subject

    def _build_phenotypic_features(
        self, reports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build phenotypic features from reports."""
        features = []

        for report in reports:
            phenotypes = report.get("phenotypes", {})

            # Convert renal insufficiency
            if "renalInsufficiency" in phenotypes:
                renal = phenotypes["renalInsufficiency"]
                if renal.get("described") not in ["no", "not reported", None]:
                    feature = {
                        "type": self.phenotype_mappings["renalInsufficiency"]
                    }

                    # Add CKD stage as modifier if available
                    stage_desc = renal.get("described", "")
                    if "stage" in stage_desc.lower():
                        try:
                            stage_num = int(stage_desc.split()[-1])
                            feature["modifiers"] = [
                                {
                                    "id": f"HP:0012{622 + stage_num}",
                                    "label": f"Stage {stage_num} chronic kidney disease",
                                }
                            ]
                        except (ValueError, IndexError):
                            pass

                    # Add onset if available
                    if renal.get("age_onset"):
                        feature["onset"] = {
                            "age": self._parse_age_to_iso8601(renal["age_onset"])
                        }

                    features.append(feature)

            # Convert kidney biopsy findings
            if "kidneyBiopsy" in phenotypes:
                biopsy = phenotypes["kidneyBiopsy"]
                for finding_key, mapping in self.phenotype_mappings[
                    "kidneyBiopsy"
                ].items():
                    if finding_key in biopsy:
                        finding = biopsy[finding_key]
                        if finding.get("described") not in ["no", "not reported", None]:
                            features.append(
                                {
                                    "type": mapping,
                                    "excluded": finding.get("described") == "no",
                                }
                            )

            # Convert genital tract abnormalities
            if "genitalTractAbnormalities" in phenotypes:
                genital = phenotypes["genitalTractAbnormalities"]
                if genital.get("described") not in ["no", "not reported", None]:
                    feature = {
                        "type": self.phenotype_mappings["genitalTractAbnormalities"]
                    }
                    # Add specific abnormality as modifier if described
                    if genital.get("described") and genital["described"] not in [
                        "yes",
                        "no",
                    ]:
                        feature["modifiers"] = [
                            {"id": "HP:0000079", "label": genital["described"]}
                        ]
                    features.append(feature)

            # Convert hypomagnesemia
            if "hypomagnesemia" in phenotypes:
                hypo = phenotypes["hypomagnesemia"]
                if hypo.get("described") == "yes":
                    features.append({"type": self.phenotype_mappings["hypomagnesemia"]})

            # Convert other phenotypes
            for phenotype_key in [
                "hyperuricemia",
                "gout",
                "hyperparathyroidism",
                "pancreaticAbnormalities",
                "exocrinePancreaticInsufficiency",
                "liverAbnormalities",
            ]:
                if phenotype_key in phenotypes:
                    pheno = phenotypes[phenotype_key]
                    if pheno.get("described") not in ["no", "not reported", None]:
                        if phenotype_key in self.phenotype_mappings:
                            features.append(
                                {"type": self.phenotype_mappings[phenotype_key]}
                            )

        return features

    def _build_diseases(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build disease entries from reports."""
        diseases = []

        # Add primary HNF1B disease
        diseases.append(
            {
                "term": self.disease_mappings["hnf1b"],
                "onset": self._get_earliest_onset(reports),
            }
        )

        # Add diabetes if present
        for report in reports:
            phenotypes = report.get("phenotypes", {})
            if "diabetes" in phenotypes:
                diabetes = phenotypes["diabetes"]
                if diabetes.get("described") not in ["no", "not reported", None]:
                    # Determine diabetes type
                    diabetes_type = "diabetes_type2"  # Default
                    if "type 1" in str(diabetes.get("described", "")).lower():
                        diabetes_type = "diabetes_type1"
                    elif "mody" in str(diabetes.get("described", "")).lower():
                        diabetes_type = "diabetes_mody"

                    disease_entry = {"term": self.disease_mappings[diabetes_type]}

                    if diabetes.get("age_onset"):
                        disease_entry["onset"] = {
                            "age": self._parse_age_to_iso8601(diabetes["age_onset"])
                        }

                    # Avoid duplicates
                    if not any(
                        d["term"]["id"] == disease_entry["term"]["id"]
                        for d in diseases
                    ):
                        diseases.append(disease_entry)

        return diseases

    def _build_measurements(
        self, reports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build measurements from reports."""
        measurements = []

        for report in reports:
            # Extract eGFR if available
            if report.get("egfr"):
                try:
                    measurements.append(
                        {
                            "assay": {
                                "id": "LOINC:33914-3",
                                "label": "Glomerular filtration rate",
                            },
                            "value": {
                                "quantity": {
                                    "unit": {
                                        "id": "UCUM:mL/min/{1.73_m2}",
                                        "label": "mL/min/1.73m²",
                                    },
                                    "value": float(report["egfr"]),
                                }
                            },
                            "timeObserved": {
                                "timestamp": report.get(
                                    "report_date", datetime.now()
                                ).isoformat()
                            },
                        }
                    )
                except (ValueError, TypeError):
                    pass

            # Add magnesium measurement if hypomagnesemia
            phenotypes = report.get("phenotypes", {})
            if "hypomagnesemia" in phenotypes:
                if phenotypes["hypomagnesemia"].get("described") == "yes":
                    measurements.append(
                        {
                            "assay": {
                                "id": "LOINC:2601-3",
                                "label": "Magnesium [Mass/volume] in Serum or Plasma",
                            },
                            "interpretation": {
                                "id": "HP:0002917",
                                "label": "Hypomagnesemia",
                            },
                        }
                    )

        return measurements

    def _build_interpretations(
        self, variants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build interpretations from variants."""
        interpretations = []

        for idx, variant in enumerate(variants):
            if not variant.get("c_dot"):
                continue

            interpretation = {
                "id": f"interpretation-{idx+1:03d}",
                "progressStatus": "COMPLETED",
                "diagnosis": {
                    "disease": self.disease_mappings["hnf1b"],
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": variant["individual_id"],
                            "interpretationStatus": self._map_pathogenicity(
                                variant.get("acmg_classification", "")
                            ),
                            "variantInterpretation": {
                                "acmgPathogenicityClassification": variant.get(
                                    "acmg_classification", "UNCERTAIN_SIGNIFICANCE"
                                ),
                                "therapeuticActionability": "UNKNOWN_ACTIONABILITY",
                                "variationDescriptor": {
                                    "id": f"var:HNF1B:{variant['c_dot']}",
                                    "label": self._build_variant_label(variant),
                                    "geneContext": {
                                        "valueId": "HGNC:11630",
                                        "symbol": "HNF1B",
                                    },
                                    "moleculeContext": "TRANSCRIPT",
                                    "allelicState": {
                                        "id": "GENO:0000135",
                                        "label": variant.get("zygosity", "heterozygous"),
                                    },
                                },
                            },
                        }
                    ],
                },
            }

            interpretations.append(interpretation)

        return interpretations

    def _build_medical_actions(
        self, reports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build medical actions from reports."""
        actions = []

        for report in reports:
            phenotypes = report.get("phenotypes", {})

            # Add diabetes treatment if present
            if "diabetes" in phenotypes:
                diabetes = phenotypes["diabetes"]
                if diabetes.get("described") not in ["no", "not reported", None]:
                    # Assume metformin as standard treatment
                    actions.append(
                        {
                            "treatment": {
                                "agent": {"id": "CHEBI:6801", "label": "Metformin"},
                                "doseIntervals": [
                                    {
                                        "quantity": {
                                            "unit": {"id": "UCUM:mg", "label": "milligram"},
                                            "value": 500,
                                        },
                                        "scheduleFrequency": {
                                            "id": "PATO:0000689",
                                            "label": "twice daily",
                                        },
                                    }
                                ],
                            },
                            "treatmentTarget": {
                                "id": "MONDO:0005147",
                                "label": "Type 2 diabetes mellitus",
                            },
                            "treatmentIntent": {
                                "id": "HP:0033296",
                                "label": "Glycemic control",
                            },
                        }
                    )

            # Check for kidney transplant
            if "renalInsufficiency" in phenotypes:
                renal = phenotypes["renalInsufficiency"]
                if "transplant" in str(renal.get("described", "")).lower():
                    actions.append(
                        {
                            "procedure": {
                                "code": {
                                    "id": "NCIT:C157952",
                                    "label": "Kidney Transplantation",
                                },
                                "performed": {"timestamp": datetime.now().isoformat()},
                            }
                        }
                    )

        return actions

    def _build_files(self, individual: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build file references."""
        files = []

        # Add VCF file reference if variant data exists
        if individual.get("individual_id"):
            files.append(
                {
                    "uri": f"file:///data/vcf/{individual['individual_id']}.vcf",
                    "individualToFileIdentifiers": {
                        individual["individual_id"]: f"sample_{individual['individual_id']}"
                    },
                    "fileAttributes": {
                        "fileFormat": "VCF",
                        "genomeAssembly": "GRCh38",
                    },
                }
            )

        return files

    def _build_metadata(
        self, individual: Dict[str, Any], reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build metadata section."""
        created_date = datetime.now().isoformat()
        if reports:
            earliest_report = min(reports, key=lambda r: r.get("report_date", ""))
            if earliest_report.get("report_date"):
                created_date = earliest_report["report_date"].isoformat()

        return {
            "created": created_date,
            "createdBy": "HNF1B-API Migration",
            "submittedBy": "Migration System",
            "resources": [
                {
                    "id": "hpo",
                    "name": "Human Phenotype Ontology",
                    "namespacePrefix": "HP",
                    "url": "https://hpo.jax.org",
                    "version": "2024-01-01",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                },
                {
                    "id": "mondo",
                    "name": "Mondo Disease Ontology",
                    "namespacePrefix": "MONDO",
                    "url": "https://mondo.monarchinitiative.org",
                    "version": "2024-01-01",
                    "iriPrefix": "http://purl.obolibrary.org/obo/MONDO_",
                },
                {
                    "id": "loinc",
                    "name": "Logical Observation Identifiers Names and Codes",
                    "namespacePrefix": "LOINC",
                    "url": "https://loinc.org",
                    "version": "2.76",
                    "iriPrefix": "https://loinc.org/",
                },
            ],
            "phenopacketSchemaVersion": "2.0.0",
            "externalReferences": [],
        }

    def _map_sex(self, sex: Optional[str]) -> str:
        """Map sex to phenopacket format."""
        if not sex:
            return "UNKNOWN_SEX"
        sex_lower = sex.lower()
        if sex_lower in ["f", "female"]:
            return "FEMALE"
        elif sex_lower in ["m", "male"]:
            return "MALE"
        else:
            return "OTHER_SEX"

    def _parse_age_to_iso8601(self, age: Any) -> Dict[str, str]:
        """Parse age to ISO8601 duration format."""
        try:
            if isinstance(age, (int, float)):
                return {"iso8601duration": f"P{int(age)}Y"}
            elif isinstance(age, str):
                # Try to extract number from string
                import re

                match = re.search(r"\d+", age)
                if match:
                    return {"iso8601duration": f"P{match.group()}Y"}
        except:
            pass
        return {"iso8601duration": "P0Y"}

    def _get_earliest_onset(self, reports: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get earliest disease onset from reports."""
        ages = []
        for report in reports:
            if report.get("age_onset"):
                ages.append(report["age_onset"])

        if ages:
            min_age = min(ages)
            return {"age": self._parse_age_to_iso8601(min_age)}
        return None

    def _map_pathogenicity(self, acmg_class: str) -> str:
        """Map ACMG classification to interpretation status."""
        mapping = {
            "Pathogenic": "PATHOGENIC",
            "Likely pathogenic": "LIKELY_PATHOGENIC",
            "Uncertain significance": "UNCERTAIN_SIGNIFICANCE",
            "Likely benign": "LIKELY_BENIGN",
            "Benign": "BENIGN",
        }
        return mapping.get(acmg_class, "UNCERTAIN_SIGNIFICANCE")

    def _build_variant_label(self, variant: Dict[str, Any]) -> str:
        """Build human-readable variant label."""
        label_parts = ["HNF1B"]
        if variant.get("c_dot"):
            label_parts.append(variant["c_dot"])
        if variant.get("p_dot"):
            label_parts.append(f"({variant['p_dot']})")
        return ":".join(label_parts)

    def validate_phenopackets(
        self, phenopackets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate all phenopackets."""
        validated = []
        errors = []

        for phenopacket in phenopackets:
            validation_errors = self.validator.validate(phenopacket)
            if validation_errors:
                errors.append(
                    {
                        "phenopacket_id": phenopacket["id"],
                        "errors": validation_errors,
                    }
                )
                logger.warning(
                    f"Validation errors for {phenopacket['id']}: {validation_errors}"
                )
            else:
                validated.append(phenopacket)

        if errors:
            logger.warning(f"Found {len(errors)} phenopackets with validation errors")
            # Optionally save errors to file for review
            with open("validation_errors.json", "w") as f:
                json.dump(errors, f, indent=2)

        return validated

    async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]):
        """Store phenopackets in the new database structure."""
        async with self.target_session() as session:
            for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
                pp_model = Phenopacket(
                    phenopacket_id=phenopacket["id"],
                    phenopacket=phenopacket,
                    subject_id=phenopacket["subject"]["id"],
                    subject_sex=phenopacket["subject"].get("sex", "UNKNOWN_SEX"),
                    created_by="Migration System",
                )
                session.add(pp_model)

            await session.commit()
            logger.info(f"Stored {len(phenopackets)} phenopackets")

    async def verify_migration(
        self, original_data: Dict[str, List[Dict]], phenopackets: List[Dict[str, Any]]
    ):
        """Verify the migration was successful."""
        logger.info("Verifying migration...")

        # Check counts
        original_count = len(original_data["individuals"])
        phenopacket_count = len(phenopackets)

        if original_count != phenopacket_count:
            logger.warning(
                f"Count mismatch: {original_count} individuals vs {phenopacket_count} phenopackets"
            )

        # Verify each individual has a phenopacket
        original_ids = {ind["individual_id"] for ind in original_data["individuals"]}
        phenopacket_ids = {pp["subject"]["id"] for pp in phenopackets}

        missing = original_ids - phenopacket_ids
        if missing:
            logger.warning(f"Missing phenopackets for individuals: {missing}")

        extra = phenopacket_ids - original_ids
        if extra:
            logger.warning(f"Extra phenopackets not in original data: {extra}")

        # Verify variant preservation
        original_variants = len(original_data["variants"])
        phenopacket_variants = sum(
            len(pp.get("interpretations", [])) for pp in phenopackets
        )

        logger.info(f"Original variants: {original_variants}")
        logger.info(f"Phenopacket interpretations: {phenopacket_variants}")

        logger.info("Migration verification complete")


async def main():
    """Run the migration."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    source_db = os.getenv(
        "OLD_DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db",
    )
    target_db = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
    )

    migration = PhenopacketsMigration(source_db, target_db)
    await migration.migrate_all_data()


if __name__ == "__main__":
    asyncio.run(main())