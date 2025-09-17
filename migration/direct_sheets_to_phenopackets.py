#!/usr/bin/env python3
"""Direct migration from Google Sheets to Phenopackets v2.

This script directly converts data from Google Sheets into GA4GH Phenopackets v2 format,
eliminating the intermediate PostgreSQL normalization step.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Google Sheets configuration
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
GID_INDIVIDUALS = "0"
GID_PHENOTYPES = "934433647"
GID_MODIFIERS = "1350764936"
GID_PUBLICATIONS = "1670256162"
GID_REVIEWERS = "1321366018"


class DirectSheetsToPhenopackets:
    """Direct migration from Google Sheets to Phenopackets format."""

    def __init__(self, target_db_url: str):
        """Initialize migration with target database."""
        self.target_engine = create_async_engine(target_db_url)
        self.target_session = sessionmaker(
            self.target_engine, class_=AsyncSession, expire_on_commit=False
        )

        # Data storage
        self.individuals_df = None
        self.phenotypes_df = None
        self.modifiers_df = None
        self.publications_df = None
        self.reviewers_df = None

        # Mappings
        self.hpo_mappings = self._init_hpo_mappings()
        self.mondo_mappings = self._init_mondo_mappings()

    def _init_hpo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize HPO term mappings for phenotypes."""
        return {
            # Kidney phenotypes
            "renalinsufficancy": {"id": "HP:0000083", "label": "Renal insufficiency"},
            "chronic kidney disease": {"id": "HP:0012622", "label": "Chronic kidney disease"},
            "stage 1 chronic kidney disease": {"id": "HP:0012623", "label": "Stage 1 chronic kidney disease"},
            "stage 2 chronic kidney disease": {"id": "HP:0012624", "label": "Stage 2 chronic kidney disease"},
            "stage 3 chronic kidney disease": {"id": "HP:0012625", "label": "Stage 3 chronic kidney disease"},
            "stage 4 chronic kidney disease": {"id": "HP:0012626", "label": "Stage 4 chronic kidney disease"},
            "stage 5 chronic kidney disease": {"id": "HP:0003774", "label": "Stage 5 chronic kidney disease"},
            "renalcysts": {"id": "HP:0000107", "label": "Renal cyst"},
            "renalhypoplasia": {"id": "HP:0000089", "label": "Renal hypoplasia"},
            "solitarykidney": {"id": "HP:0004729", "label": "Solitary functioning kidney"},
            "multicysticdysplastickidney": {"id": "HP:0000003", "label": "Multicystic kidney dysplasia"},
            "hyperechogenicity": {"id": "HP:0010935", "label": "Increased echogenicity of kidneys"},
            "urinarytractmalformation": {"id": "HP:0000079", "label": "Abnormality of the urinary system"},
            "antenatalrenalabnormalities": {"id": "HP:0010945", "label": "Fetal renal anomaly"},
            "multiple glomerular cysts": {"id": "HP:0100611", "label": "Multiple glomerular cysts"},
            "oligomeganephronia": {"id": "HP:0004719", "label": "Oligomeganephronia"},

            # Metabolic phenotypes
            "hypomagnesemia": {"id": "HP:0002917", "label": "Hypomagnesemia"},
            "hyperuricemia": {"id": "HP:0002149", "label": "Hyperuricemia"},
            "gout": {"id": "HP:0001997", "label": "Gout"},
            "hypokalemia": {"id": "HP:0002900", "label": "Hypokalemia"},
            "hyperparathyroidism": {"id": "HP:0000843", "label": "Hyperparathyroidism"},

            # Diabetes/Pancreas
            "mody": {"id": "HP:0004904", "label": "Maturity-onset diabetes of the young"},
            "pancreatichypoplasia": {"id": "HP:0100575", "label": "Pancreatic hypoplasia"},
            "exocrinepancreaticinsufficiency": {"id": "HP:0001738", "label": "Exocrine pancreatic insufficiency"},

            # Liver
            "abnormalliverphysiology": {"id": "HP:0031865", "label": "Abnormal liver physiology"},  # More suitable term
            "elevatedhepatictransaminase": {"id": "HP:0002910", "label": "Elevated hepatic transaminase"},

            # Genital
            "genitaltractabnormality": {"id": "HP:0000078", "label": "Abnormality of the genital system"},

            # Developmental
            "neurodevelopmentaldisorder": {"id": "HP:0012759", "label": "Neurodevelopmental abnormality"},
            "mentaldisease": {"id": "HP:0000708", "label": "Behavioral abnormality"},  # More general term
            "dysmorphicfeatures": {"id": "HP:0001999", "label": "Abnormal facial shape"},
            "shortstature": {"id": "HP:0004322", "label": "Short stature"},
            "prematurebirth": {"id": "HP:0001622", "label": "Premature birth"},

            # Neurological
            "brainabnormality": {"id": "HP:0012443", "label": "Abnormality of brain morphology"},  # More inclusive term
            "seizures": {"id": "HP:0001250", "label": "Seizures"},

            # Other systems
            "eyeabnormality": {"id": "HP:0000478", "label": "Abnormality of the eye"},
            "congenitalcardiacanomalies": {"id": "HP:0001627", "label": "Abnormal heart morphology"},
            "musculoskeletalfeatures": {"id": "HP:0033127", "label": "Abnormality of the musculoskeletal system"},
        }

    def _init_mondo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize MONDO disease mappings."""
        return {
            "hnf1b": {
                "id": "MONDO:0018874",
                "label": "HNF1B-related disorder"
            },
            "mody5": {
                "id": "MONDO:0010953",
                "label": "Maturity-onset diabetes of the young type 5"
            },
            "rcad": {
                "id": "ORPHA:93111",
                "label": "Renal cysts and diabetes syndrome"
            }
        }

    def _csv_url(self, spreadsheet_id: str, gid: str) -> str:
        """Generate Google Sheets CSV export URL."""
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

    async def load_google_sheets(self) -> None:
        """Load all data from Google Sheets."""
        logger.info("Loading data from Google Sheets...")

        # Load individuals sheet (contains phenotypes and variants data)
        url = self._csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
        self.individuals_df = pd.read_csv(url)
        self.individuals_df = self.individuals_df.dropna(how='all')
        logger.info(f"Loaded {len(self.individuals_df)} rows from individuals sheet")
        logger.info(f"Columns: {list(self.individuals_df.columns)[:10]}...")  # Log first 10 columns

        # Load publications (optional)
        try:
            url = self._csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
            self.publications_df = pd.read_csv(url)
            self.publications_df = self.publications_df.dropna(how='all')
            logger.info(f"Loaded {len(self.publications_df)} rows from publications sheet")
        except Exception as e:
            logger.warning(f"Could not load publications sheet: {e}")
            self.publications_df = pd.DataFrame()

        # Load reviewers (optional)
        try:
            url = self._csv_url(SPREADSHEET_ID, GID_REVIEWERS)
            self.reviewers_df = pd.read_csv(url)
            self.reviewers_df = self.reviewers_df.dropna(how='all')
            logger.info(f"Loaded {len(self.reviewers_df)} rows from reviewers sheet")
        except Exception as e:
            logger.warning(f"Could not load reviewers sheet: {e}")
            self.reviewers_df = pd.DataFrame()

    def _normalize_column_name(self, name: str) -> str:
        """Normalize column names to lowercase without spaces."""
        if pd.isna(name):
            return ""
        return str(name).strip().lower().replace(" ", "").replace("_", "")

    def _safe_value(self, value: Any) -> Optional[str]:
        """Safely convert value to string, handling NaN."""
        if pd.isna(value) or value == "" or value == "NaN":
            return None
        return str(value).strip()

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
            return "UNKNOWN_SEX"

    def _parse_age(self, age_str: Any) -> Optional[Dict[str, str]]:
        """Parse age to ISO8601 duration format."""
        if pd.isna(age_str):
            return None

        try:
            # Try to extract number from string
            if isinstance(age_str, (int, float)):
                years = int(age_str)
            else:
                match = re.search(r'(\d+)', str(age_str))
                if match:
                    years = int(match.group(1))
                else:
                    return None

            return {"iso8601duration": f"P{years}Y"}
        except:
            return None

    def _extract_phenotypes(self, row: pd.Series) -> List[Dict[str, Any]]:
        """Extract phenotypic features from a row."""
        phenotypes = []

        # Normalize column names
        normalized_cols = {self._normalize_column_name(col): col for col in row.index}

        # Process each phenotype column
        for pheno_key, hpo_info in self.hpo_mappings.items():
            if pheno_key in normalized_cols:
                original_col = normalized_cols[pheno_key]
                value = self._safe_value(row[original_col])

                if value and value.lower() not in ["no", "not reported", "unknown", ""]:
                    # Determine if phenotype is present
                    excluded = False
                    if value.lower() in ["absent", "negative", "none"]:
                        excluded = True

                    phenotype = {
                        "type": {
                            "id": hpo_info["id"],
                            "label": hpo_info["label"]
                        },
                        "excluded": excluded
                    }

                    # Add modifier if applicable (for bilateral/unilateral features)
                    if value.lower() in ["bilateral", "unilateral", "left", "right"]:
                        modifier_map = {
                            "bilateral": {"id": "HP:0012832", "label": "Bilateral"},
                            "unilateral": {"id": "HP:0012833", "label": "Unilateral"},
                            "left": {"id": "HP:0012835", "label": "Left"},
                            "right": {"id": "HP:0012834", "label": "Right"}
                        }
                        if value.lower() in modifier_map:
                            phenotype["modifiers"] = [modifier_map[value.lower()]]

                    phenotypes.append(phenotype)

        return phenotypes

    def _extract_variants(self, row: pd.Series) -> List[Dict[str, Any]]:
        """Extract variant information from row, prioritizing Varsome data."""
        interpretations = []

        # Get all variant-related columns
        varsome = self._safe_value(row.get('Varsome'))
        variant_reported = self._safe_value(row.get('VariantReported'))
        hg38 = self._safe_value(row.get('hg38'))
        verdict = self._safe_value(row.get('verdict_classification'))
        variant_type = self._safe_value(row.get('VariantType'))
        segregation = self._safe_value(row.get('Segregation'))

        # Initialize variant components
        c_dot = None
        p_dot = None
        transcript = None

        # PRIORITY 1: Parse Varsome (GA4GH compliant format)
        if varsome:
            # Example: HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)
            import re

            # Extract transcript
            transcript_match = re.search(r'NM_\d+\.\d+', varsome)
            if transcript_match:
                transcript = transcript_match.group()

            # Extract c.dot notation
            c_dot_match = re.search(r'c\.[^\s\)]+', varsome)
            if c_dot_match:
                c_dot = c_dot_match.group()

            # Extract p.dot notation
            p_dot_match = re.search(r'p\.[^\)]+', varsome)
            if p_dot_match:
                p_dot = p_dot_match.group()

        # PRIORITY 2: Parse VariantReported if Varsome didn't provide everything
        if variant_reported and (not c_dot or not p_dot):
            if ',' in variant_reported:
                parts = variant_reported.split(',')
                for part in parts:
                    part = part.strip()
                    if not c_dot and part.startswith('c.'):
                        c_dot = part
                    elif not p_dot and part.startswith('p.'):
                        p_dot = part
            elif not c_dot and variant_reported.startswith('c.'):
                c_dot = variant_reported

        # Only create interpretation if we have meaningful variant data
        if c_dot or hg38 or varsome:
            # Create variant label
            variant_label = f"HNF1B:{c_dot if c_dot else 'variant'}"
            if p_dot:
                variant_label += f" ({p_dot})"

            # Determine variant type
            molecular_consequence = None
            if variant_type:
                type_lower = variant_type.lower()
                if 'snv' in type_lower or 'snp' in type_lower:
                    molecular_consequence = {"id": "SO:0001483", "label": "SNV"}
                elif 'delet' in type_lower:
                    molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
                elif 'dup' in type_lower:
                    molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
                elif 'indel' in type_lower:
                    molecular_consequence = {"id": "SO:1000032", "label": "indel"}
            elif hg38 and '<DEL>' in hg38:
                molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
            elif hg38 and '<DUP>' in hg38:
                molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
            elif c_dot:
                if 'del' in c_dot:
                    molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
                elif 'dup' in c_dot:
                    molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
                elif 'ins' in c_dot:
                    molecular_consequence = {"id": "SO:0000667", "label": "insertion"}
                elif '>' in c_dot:
                    molecular_consequence = {"id": "SO:0001483", "label": "SNV"}

            # Create unique interpretation ID
            interpretation_id = f"interpretation-{len(interpretations)+1:03d}"

            interpretation = {
                "id": interpretation_id,
                "progressStatus": "COMPLETED",
                "diagnosis": {
                    "disease": self.mondo_mappings["hnf1b"],
                    "genomicInterpretations": [{
                        "subjectOrBiosampleId": row.get("IndividualIdentifier", row.get("individual_id", "unknown")),
                        "interpretationStatus": "UNCERTAIN_SIGNIFICANCE",
                        "variantInterpretation": {
                            "variationDescriptor": {
                                "id": f"var:HNF1B:{c_dot if c_dot else hg38 if hg38 else 'unknown'}",
                                "label": variant_label,
                                "geneContext": {
                                    "valueId": "HGNC:5024",
                                    "symbol": "HNF1B"
                                },
                                "expressions": [],
                                "moleculeContext": "genomic"
                            }
                        }
                    }]
                }
            }

            # Add molecular consequence if determined
            if molecular_consequence:
                interpretation["diagnosis"]["genomicInterpretations"][0]["variantInterpretation"]["variationDescriptor"]["molecularConsequences"] = [molecular_consequence]

            # Add allelicState based on segregation
            if segregation:
                seg_lower = segregation.lower()
                if 'de novo' in seg_lower:
                    interpretation["diagnosis"]["genomicInterpretations"][0]["variantInterpretation"]["variationDescriptor"]["allelicState"] = {
                        "id": "GENO:0000135",
                        "label": "heterozygous"
                    }
                elif 'inherited' in seg_lower:
                    interpretation["diagnosis"]["genomicInterpretations"][0]["variantInterpretation"]["variationDescriptor"]["allelicState"] = {
                        "id": "GENO:0000135",
                        "label": "heterozygous"
                    }

            # Add HGVS expressions
            expressions = interpretation["diagnosis"]["genomicInterpretations"][0]["variantInterpretation"]["variationDescriptor"]["expressions"]

            # Add c. notation with proper transcript
            if c_dot:
                if transcript:
                    expressions.append({
                        "syntax": "hgvs.c",
                        "value": f"{transcript}:{c_dot}"
                    })
                else:
                    expressions.append({
                        "syntax": "hgvs.c",
                        "value": f"NM_000458.4:{c_dot}"
                    })

            # Add p. notation if available
            if p_dot:
                expressions.append({
                    "syntax": "hgvs.p",
                    "value": f"NP_000449.3:{p_dot}"
                })

            # Add genomic position if available
            if hg38:
                expressions.append({
                    "syntax": "hgvs.g",
                    "value": hg38
                })

            # Map pathogenicity if available
            if verdict:
                path_map = {
                    "pathogenic": "PATHOGENIC",
                    "likely pathogenic": "LIKELY_PATHOGENIC",
                    "uncertain significance": "UNCERTAIN_SIGNIFICANCE",
                    "likely benign": "LIKELY_BENIGN",
                    "benign": "BENIGN"
                }
                verdict_lower = verdict.lower()
                for key, value in path_map.items():
                    if key in verdict_lower:
                        interpretation["diagnosis"]["genomicInterpretations"][0]["interpretationStatus"] = value
                        break

            interpretations.append(interpretation)

        return interpretations

    def build_phenopacket(self, individual_id: str, rows: pd.DataFrame) -> Dict[str, Any]:
        """Build a complete phenopacket from individual data rows."""
        # Get first row for basic demographics
        first_row = rows.iloc[0]

        # Extract IDs - use individual_id as primary, IndividualIdentifier as alternate
        individual_identifier = self._safe_value(first_row.get("IndividualIdentifier"))

        phenopacket_id = f"phenopacket-{individual_id}"

        # Build subject
        subject = {
            "id": individual_id,  # Use individual_id as primary ID
            "sex": self._map_sex(self._safe_value(first_row.get("Sex")))
        }

        # Add IndividualIdentifier as alternateIds if it exists
        if individual_identifier:
            subject["alternateIds"] = [individual_identifier]

        # Add age if available - use AgeReported for timeAtLastEncounter
        age_reported = self._parse_age(first_row.get("AgeReported"))
        if age_reported:
            subject["timeAtLastEncounter"] = age_reported

        # Parse AgeOnset separately for disease onset
        age_onset = self._parse_age(first_row.get("AgeOnset"))

        # Extract phenotypic features from all rows
        all_phenotypes = []
        seen_phenotypes = set()

        for _, row in rows.iterrows():
            phenotypes = self._extract_phenotypes(row)
            for pheno in phenotypes:
                pheno_id = pheno["type"]["id"]
                if pheno_id not in seen_phenotypes:
                    all_phenotypes.append(pheno)
                    seen_phenotypes.add(pheno_id)

        # Extract variants/interpretations from all rows
        all_interpretations = []
        for _, row in rows.iterrows():
            interpretations = self._extract_variants(row)
            all_interpretations.extend(interpretations)

        # Build diseases list
        disease_onset = None
        if age_onset:
            # Use actual age of onset if available
            disease_onset = {"age": age_onset}
        else:
            # Default to congenital onset for HNF1B
            disease_onset = {"ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}}

        diseases = [{
            "term": self.mondo_mappings["hnf1b"],
            "onset": disease_onset
        }]

        # Check for MODY in phenotypes
        mody_col = next((col for col in first_row.index if 'mody' in col.lower()), None)
        if mody_col:
            mody_val = self._safe_value(first_row[mody_col])
            if mody_val and mody_val.lower() not in ["no", "not reported", ""]:
                diseases.append({
                    "term": self.mondo_mappings["mody5"],
                    "onset": {"ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}}
                })

        # Build metadata
        metadata = {
            "created": datetime.now().isoformat(),
            "createdBy": "HNF1B-DB Direct Migration",
            "resources": [
                {
                    "id": "hp",
                    "name": "Human Phenotype Ontology",
                    "url": "http://purl.obolibrary.org/obo/hp.owl",
                    "version": "2024-01-16",
                    "namespacePrefix": "HP",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_"
                },
                {
                    "id": "mondo",
                    "name": "Mondo Disease Ontology",
                    "url": "http://purl.obolibrary.org/obo/mondo.owl",
                    "version": "2024-01-03",
                    "namespacePrefix": "MONDO",
                    "iriPrefix": "http://purl.obolibrary.org/obo/MONDO_"
                }
            ],
            "phenopacketSchemaVersion": "2.0.0"
        }

        # Add publication references if available
        pub_col = next((col for col in first_row.index if 'publication' in col.lower()), None)
        if pub_col:
            pub_val = self._safe_value(first_row[pub_col])
            if pub_val:
                metadata["externalReferences"] = [{
                    "id": f"PUB:{pub_val}",
                    "description": f"Publication reference: {pub_val}"
                }]

        # Build complete phenopacket
        phenopacket = {
            "id": phenopacket_id,
            "subject": subject,
            "phenotypicFeatures": all_phenotypes,
            "diseases": diseases,
            "metaData": metadata
        }

        # Add interpretations if present
        if all_interpretations:
            phenopacket["interpretations"] = all_interpretations

        return self._clean_empty_fields(phenopacket)

    def _clean_empty_fields(self, obj: Any) -> Any:
        """Recursively remove empty fields from object."""
        if isinstance(obj, dict):
            return {k: self._clean_empty_fields(v) for k, v in obj.items()
                   if v is not None and (not isinstance(v, (list, dict)) or v)}
        elif isinstance(obj, list):
            cleaned = [self._clean_empty_fields(item) for item in obj]
            return [item for item in cleaned if item is not None]
        else:
            return obj

    async def migrate(self, limit: Optional[int] = None, test_mode: bool = False, dry_run: bool = False) -> None:
        """Execute the complete migration."""
        try:
            # Load all data from Google Sheets
            await self.load_google_sheets()

            # Normalize column names
            self.individuals_df.columns = [col.strip() for col in self.individuals_df.columns]

            # Group rows by individual_id (correct column name from logs)
            individual_groups = self.individuals_df.groupby('individual_id', dropna=False)

            phenopackets = []
            individual_count = 0

            logger.info(f"Processing {len(individual_groups)} individuals...")

            for individual_id, group_df in tqdm(individual_groups, desc="Building phenopackets"):
                if pd.isna(individual_id) or str(individual_id).strip() == "":
                    continue

                if limit and individual_count >= limit:
                    break

                try:
                    # Build phenopacket for this individual
                    phenopacket = self.build_phenopacket(str(individual_id), group_df)
                    phenopackets.append(phenopacket)
                    individual_count += 1

                except Exception as e:
                    logger.error(f"Error processing individual {individual_id}: {e}")
                    continue

            logger.info(f"Built {len(phenopackets)} phenopackets")

            if dry_run:
                # Save to JSON file for inspection
                output_file = f"phenopackets_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, 'w') as f:
                    json.dump(phenopackets, f, indent=2)
                logger.info(f"Dry run complete. Phenopackets saved to {output_file}")
            else:
                # Store phenopackets in database
                await self.store_phenopackets(phenopackets)

            # Generate summary report
            self.generate_summary(phenopackets)

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

    async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]) -> None:
        """Store phenopackets in the database."""
        async with self.target_session() as session:
            stored_count = 0

            for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
                try:
                    # Extract individual ID for generated columns
                    subject_id = phenopacket.get("subject", {}).get("id", "unknown")
                    subject_sex = phenopacket.get("subject", {}).get("sex", "UNKNOWN_SEX")

                    # Insert phenopacket
                    query = text("""
                        INSERT INTO phenopackets
                        (phenopacket_id, phenopacket, subject_id, subject_sex, created_by, schema_version)
                        VALUES (:phenopacket_id, :phenopacket, :subject_id, :subject_sex, :created_by, :schema_version)
                        ON CONFLICT (phenopacket_id) DO UPDATE
                        SET phenopacket = EXCLUDED.phenopacket,
                            subject_id = EXCLUDED.subject_id,
                            subject_sex = EXCLUDED.subject_sex,
                            updated_at = CURRENT_TIMESTAMP
                    """)

                    await session.execute(query, {
                        "phenopacket_id": phenopacket["id"],
                        "phenopacket": json.dumps(phenopacket),
                        "subject_id": subject_id,
                        "subject_sex": subject_sex,
                        "created_by": "direct_sheets_migration",
                        "schema_version": "2.0.0"
                    })

                    stored_count += 1

                except Exception as e:
                    logger.error(f"Error storing phenopacket {phenopacket.get('id')}: {e}")
                    continue

            await session.commit()
            logger.info(f"Successfully stored {stored_count} phenopackets")

    def generate_summary(self, phenopackets: List[Dict[str, Any]]) -> None:
        """Generate migration summary statistics."""
        total = len(phenopackets)
        with_phenotypes = sum(1 for p in phenopackets if p.get("phenotypicFeatures"))
        with_variants = sum(1 for p in phenopackets if p.get("interpretations"))
        with_diseases = sum(1 for p in phenopackets if p.get("diseases"))

        sex_distribution = {}
        for p in phenopackets:
            sex = p.get("subject", {}).get("sex", "UNKNOWN")
            sex_distribution[sex] = sex_distribution.get(sex, 0) + 1

        logger.info("\n" + "="*60)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total phenopackets created: {total}")
        logger.info(f"With phenotypic features: {with_phenotypes} ({with_phenotypes*100//total if total else 0}%)")
        logger.info(f"With genetic variants: {with_variants} ({with_variants*100//total if total else 0}%)")
        logger.info(f"With disease diagnoses: {with_diseases} ({with_diseases*100//total if total else 0}%)")
        logger.info(f"Sex distribution: {sex_distribution}")
        logger.info("="*60)


async def main():
    """Run the direct migration."""
    # Get database URL from environment
    target_db = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets"
    )

    # Parse command line arguments
    import sys
    test_mode = "--test" in sys.argv
    dry_run = "--dry-run" in sys.argv
    limit = None

    if test_mode:
        limit = 20
        logger.info("Running in TEST MODE - limiting to 20 individuals")

    if dry_run:
        logger.info("Running in DRY RUN MODE - will output to JSON file")

    # Run migration
    migration = DirectSheetsToPhenopackets(target_db)
    await migration.migrate(limit=limit, test_mode=test_mode, dry_run=dry_run)


if __name__ == "__main__":
    asyncio.run(main())