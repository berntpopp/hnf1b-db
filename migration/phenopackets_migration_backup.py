"""Fixed migration from normalized PostgreSQL to Phenopackets v2."""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PhenopacketsMigrationFixed:
    """Fixed migration from normalized PostgreSQL to Phenopackets."""

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

        # Mapping dictionaries for ontology terms
        self.phenotype_mappings = self._load_phenotype_mappings()
        self.disease_mappings = self._load_disease_mappings()
        
        # Storage for Varsome data loaded from Google Sheets
        self.varsome_data = {}

    def _load_phenotype_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load comprehensive phenotype to HPO term mappings."""
        return {
            # Kidney-related phenotypes
            "HP:0012622": {"id": "HP:0012622", "label": "Chronic kidney disease"},
            "HP:0100611": {"id": "HP:0100611", "label": "Multiple glomerular cysts"},
            "ORPHA:2260": {"id": "HP:0004719", "label": "Oligomeganephronia"},
            "RenalCysts": {"id": "HP:0000107", "label": "Renal cysts"},
            "RenalHypoplasia": {"id": "HP:0000089", "label": "Renal hypoplasia"},
            "SolitaryKidney": {"id": "HP:0004729", "label": "Solitary kidney"},
            "MulticysticDysplasticKidney": {"id": "HP:0000003", "label": "Multicystic kidney dysplasia"},
            "Hyperechogenicity": {"id": "HP:0010935", "label": "Increased echogenicity of kidneys"},
            "UrinaryTractMalformation": {"id": "HP:0000079", "label": "Abnormality of the urinary system"},
            "AntenatalRenalAbnormalities": {"id": "HP:0010945", "label": "Fetal renal anomaly"},
            
            # Metabolic phenotypes
            "Hypomagnesemia": {"id": "HP:0002917", "label": "Hypomagnesemia"},
            "Hyperuricemia": {"id": "HP:0002149", "label": "Hyperuricemia"},
            "Gout": {"id": "HP:0001997", "label": "Gout"},
            "Hypokalemia": {"id": "HP:0002900", "label": "Hypokalemia"},
            "Hyperparathyroidism": {"id": "HP:0000843", "label": "Hyperparathyroidism"},
            
            # Pancreatic/Liver phenotypes
            "PancreaticHypoplasia": {"id": "HP:0100575", "label": "Pancreatic hypoplasia"},
            "ExocrinePancreaticInsufficiency": {"id": "HP:0001738", "label": "Exocrine pancreatic insufficiency"},
            "AbnormalLiverPhysiology": {"id": "HP:0001410", "label": "Decreased liver function"},
            "ElevatedHepaticTransaminase": {"id": "HP:0002910", "label": "Elevated hepatic transaminase"},
            
            # Genital phenotypes
            "GenitalTractAbnormality": {"id": "HP:0000078", "label": "Genital abnormality"},
            
            # Developmental phenotypes
            "NeurodevelopmentalDisorder": {"id": "HP:0012759", "label": "Neurodevelopmental disorder"},
            "MentalDisease": {"id": "HP:0100753", "label": "Mental disorder"},
            "DysmorphicFeatures": {"id": "HP:0001999", "label": "Dysmorphic facial features"},
            "ShortStature": {"id": "HP:0004322", "label": "Short stature"},
            "PrematureBirth": {"id": "HP:0001622", "label": "Premature birth"},
            
            # Neurological phenotypes
            "BrainAbnormality": {"id": "HP:0002060", "label": "Abnormality of the brain"},
            "Seizures": {"id": "HP:0001250", "label": "Seizures"},
            
            # Other organ systems
            "EyeAbnormality": {"id": "HP:0000478", "label": "Abnormality of the eye"},
            "CongenitalCardiacAnomalies": {"id": "HP:0001627", "label": "Congenital heart defect"},
            "MusculoskeletalFeatures": {"id": "HP:0033127", "label": "Abnormality of the musculoskeletal system"},
            
            # Additional phenotypes from Google Sheets
            "RenalInsufficancy": {"id": "HP:0000083", "label": "Renal insufficiency"},
            "KidneyBiopsy": {"id": "HP:0100820", "label": "Kidney biopsy showing abnormalities"},
            
            # Diabetes-related (Note: MODY will be handled as disease, not phenotype)
            "MODY": None,  # Handled in diseases section
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
            "mody": {
                "id": "MONDO:0015967",
                "label": "Maturity-onset diabetes of the young type 5",
            },
        }

    def _parse_varsome_notation(self, varsome_str: str) -> Dict[str, Optional[str]]:
        """Parse Varsome notation to extract HGVS components.
        
        Format: HNF1B(NM_000458.4):c.182T>G (p.Val61Gly)
        """
        if not varsome_str or pd.isna(varsome_str):
            return {"gene": None, "transcript": None, "c_dot": None, "p_dot": None}
        
        pattern = r'([^(]+)\(([^)]+)\):([^ ]+)(?:\s*\(p\.([^)]+)\))?'
        match = re.match(pattern, str(varsome_str))
        
        if match:
            return {
                "gene": match.group(1).strip(),  # HNF1B
                "transcript": match.group(2),  # NM_000458.4
                "c_dot": match.group(3),  # c.182T>G
                "p_dot": f"p.{match.group(4)}" if match.group(4) else None  # p.Val61Gly
            }
        
        return {"gene": None, "transcript": None, "c_dot": None, "p_dot": None}

    async def load_varsome_from_sheets(self):
        """Load Varsome data directly from Google Sheets."""
        logger.info("Loading Varsome data from Google Sheets...")
        
        # Google Sheets export URL
        spreadsheet_id = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
        gid = "0"  # Main individuals sheet
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
        
        try:
            # Read the Google Sheets data
            df = pd.read_csv(url)
            
            # Process each row to extract Varsome data
            for _, row in df.iterrows():
                individual_id = row.get('individual_id')
                varsome = row.get('Varsome')
                
                if individual_id and varsome and not pd.isna(varsome):
                    # Format individual_id properly
                    if pd.notna(individual_id):
                        ind_id = str(individual_id).strip()
                        if ind_id and not ind_id.startswith('ind'):
                            ind_id = f"ind{int(float(ind_id)):04d}"
                        
                        # Parse Varsome notation
                        parsed = self._parse_varsome_notation(varsome)
                        
                        # Store the parsed data
                        if ind_id not in self.varsome_data:
                            self.varsome_data[ind_id] = []
                        
                        # Add variant info with additional fields from sheet
                        variant_info = {
                            **parsed,
                            "variant_type": row.get('VariantType'),
                            "hg38": row.get('hg38'),
                            "hg19": row.get('hg19'),
                            "verdict": row.get('verdict_classification'),
                            "detection_method": row.get('DetecionMethod') or row.get('DetectionMethod'),
                            "segregation": row.get('Segregation'),
                        }
                        
                        self.varsome_data[ind_id].append(variant_info)
            
            logger.info(f"Loaded Varsome data for {len(self.varsome_data)} individuals")
            
        except Exception as e:
            logger.error(f"Error loading Varsome data from Google Sheets: {e}")

    async def migrate_all_data(self):
        """Complete migration from old structure to phenopackets."""
        logger.info("Starting complete migration to phenopackets...")

        try:
            # Load Varsome data from Google Sheets first
            await self.load_varsome_from_sheets()
            
            # Step 1: Extract all data using SQL queries
            data = await self.extract_all_data_sql()
            logger.info(f"Extracted {len(data['individuals'])} individuals")

            # Step 2: Transform to phenopackets
            phenopackets = await self.transform_to_phenopackets(data)
            logger.info(f"Transformed {len(phenopackets)} phenopackets")

            # Step 3: Store in new structure
            await self.store_phenopackets(phenopackets)
            logger.info("Stored phenopackets in database")

            logger.info("Migration complete!")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            await self.source_engine.dispose()
            await self.target_engine.dispose()

    async def extract_all_data_sql(self) -> Dict[str, List[Dict]]:
        """Extract all data using direct SQL queries."""
        data = {
            "individuals": [],
            "reports": [],
            "variants": [],
            "publications": [],
        }

        async with self.source_session() as session:
            # Extract individuals
            query = """
                SELECT 
                    id::text as id,
                    individual_id,
                    sex,
                    dup_check,
                    individual_identifier,
                    created_at,
                    updated_at
                FROM individuals
            """
            result = await session.execute(text(query))
            data["individuals"] = [dict(row._mapping) for row in result]

            # Extract reports with phenotypes, publication references, and reviewer info
            query = """
                SELECT 
                    r.id::text as id,
                    r.report_id,
                    r.individual_id::text as individual_id,
                    r.phenotypes,
                    r.age_reported,
                    r.age_onset,
                    r.report_date,
                    r.publication_ref::text as publication_id,
                    p.publication_alias,
                    p.doi,
                    p.pmid,
                    p.title,
                    r.comment,
                    r.reviewed_by::text as reviewer_id,
                    u.email as reviewer_email,
                    r.created_at,
                    r.updated_at
                FROM reports r
                LEFT JOIN publications p ON r.publication_ref = p.id
                LEFT JOIN users u ON r.reviewed_by = u.id
            """
            result = await session.execute(text(query))
            data["reports"] = [dict(row._mapping) for row in result]

            # Extract variants with annotations through junction table
            query = """
                SELECT DISTINCT
                    v.id::text as variant_id,
                    iv.individual_id::text as individual_id,
                    v.variant_id as variant_name,
                    v.variant_type,
                    v.hg38,
                    v.hg38_info,
                    va.c_dot,
                    va.p_dot,
                    va.impact,
                    va.effect,
                    va.variant_class,
                    vc.verdict as acmg_classification,
                    iv.detection_method,
                    iv.segregation
                FROM variants v
                LEFT JOIN individual_variants iv ON v.id = iv.variant_id
                LEFT JOIN variant_annotations va ON v.id = va.variant_id
                LEFT JOIN variant_classifications vc ON v.id = vc.variant_id
                WHERE v.is_current = true
                  AND (iv.is_current = true OR iv.is_current IS NULL)
            """
            result = await session.execute(text(query))
            data["variants"] = [dict(row._mapping) for row in result]

        return data

    async def transform_to_phenopackets(
        self, data: Dict[str, List[Dict]]
    ) -> List[Dict[str, Any]]:
        """Transform normalized data to phenopackets format."""
        phenopackets = []

        for individual in tqdm(data["individuals"], desc="Transforming to phenopackets"):
            # Get related data
            ind_id = individual["id"]
            individual_id = individual["individual_id"]  # e.g., "ind0001"
            
            reports = [
                r for r in data["reports"] if r["individual_id"] == ind_id
            ]
            
            # Get Varsome variants for this individual (prioritize these)
            varsome_variants = self.varsome_data.get(individual_id, [])
            
            # Also get variants from database (fallback)
            db_variants = [
                v for v in data["variants"] if v["individual_id"] == ind_id
            ]
            
            # Use Varsome variants if available, otherwise use database variants
            variants = varsome_variants if varsome_variants else db_variants

            # Build phenopacket
            phenopacket = {
                "id": f"phenopacket:HNF1B:{individual['individual_id']}",
                "subject": self._build_subject(individual, reports),
                "phenotypicFeatures": self._build_phenotypic_features(reports),
                "measurements": self._build_measurements(reports),
                "diseases": self._build_diseases(reports),
                "interpretations": self._build_interpretations(variants),
                "files": self._build_files(reports),  # Add publication references here
                "metaData": self._build_metadata(individual, reports),
            }

            # Clean up empty arrays
            phenopacket = self._clean_phenopacket(phenopacket)
            phenopackets.append(phenopacket)

        return phenopackets

    def _build_subject(
        self, individual: Dict[str, Any], reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build subject section of phenopacket."""
        subject = {
            "id": individual["individual_id"],
            "sex": self._map_sex(individual.get("sex")),
        }

        # Add alternate IDs if available
        if individual.get("dup_check"):
            alternate_ids = [individual["dup_check"]]
            if individual.get("individual_identifier"):
                alternate_ids.append(individual["individual_identifier"])
            subject["alternateIds"] = alternate_ids

        # Add age at last encounter from most recent report
        if reports:
            latest_report = max(reports, key=lambda r: r.get("report_date") or datetime.min)
            if latest_report.get("age_reported"):
                subject["timeAtLastEncounter"] = {
                    "age": self._parse_age_to_iso8601(latest_report["age_reported"])
                }

        return subject

    def _build_phenotypic_features(
        self, reports: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build phenotypic features from the actual phenotypes JSONB structure."""
        features = []
        
        for report in reports:
            phenotypes = report.get("phenotypes", {})
            if not phenotypes:
                continue
            
            # Process each phenotype in the flat structure
            for phenotype_key, phenotype_data in phenotypes.items():
                if not isinstance(phenotype_data, dict):
                    continue
                    
                # Skip if not described or not reported
                described = phenotype_data.get("described", "")
                if described in ["not reported", None]:
                    continue
                
                # Skip MODY as it will be handled in diseases
                if phenotype_key == "MODY":
                    continue
                
                # Get mapping for this phenotype
                mapping = self.phenotype_mappings.get(phenotype_key)
                if not mapping:
                    # Try using the phenotype_id field if it's an HPO term
                    phenotype_id = phenotype_data.get("phenotype_id", "")
                    if phenotype_id.startswith("HP:"):
                        mapping = {
                            "id": phenotype_id,
                            "label": phenotype_data.get("name", phenotype_key)
                        }
                    elif phenotype_id == phenotype_key:
                        # Use the key itself as a fallback for unmapped phenotypes
                        # Log these for future mapping improvements
                        logger.debug(f"Unmapped phenotype: {phenotype_key}")
                        continue
                    else:
                        continue
                
                # Create feature
                feature = {
                    "type": {
                        "id": mapping["id"],
                        "label": mapping["label"]
                    }
                }
                
                # Handle excluded features (described as "no")
                if described == "no":
                    feature["excluded"] = True
                elif described == "yes":
                    feature["excluded"] = False
                else:
                    # Described contains specific information
                    feature["excluded"] = False
                    
                    # Parse stage information for CKD
                    if phenotype_key == "HP:0012622" and "stage" in str(described).lower():
                        try:
                            import re
                            match = re.search(r"stage\s*(\d)", str(described).lower())
                            if match:
                                stage_num = int(match.group(1))
                                feature["modifiers"] = [{
                                    "id": f"HP:0012{622 + stage_num}",
                                    "label": f"Stage {stage_num} chronic kidney disease"
                                }]
                        except:
                            pass
                
                # Add onset if available
                age_onset = phenotype_data.get("age_onset")
                if age_onset and age_onset != "not reported":
                    feature["onset"] = {
                        "age": self._parse_age_to_iso8601(age_onset)
                    }
                
                features.append(feature)
        
        return features

    def _build_diseases(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build disease entries from reports."""
        diseases = []

        # Add primary HNF1B disease
        diseases.append({
            "term": self.disease_mappings["hnf1b"]
        })

        # Check for MODY and other diabetes types in phenotypes
        for report in reports:
            phenotypes = report.get("phenotypes", {})
            if not phenotypes:
                continue
                
            # Check for MODY
            if "MODY" in phenotypes:
                mody = phenotypes["MODY"]
                if mody.get("described") not in ["no", "not reported", None]:
                    disease_entry = {"term": self.disease_mappings["mody"]}
                    
                    # Add onset if available
                    age_onset = mody.get("age_onset")
                    if age_onset and age_onset != "not reported":
                        disease_entry["onset"] = {
                            "age": self._parse_age_to_iso8601(age_onset)
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

        # Currently no measurements available in the reports table
        # This would be populated if measurement data was available
        
        return measurements

    def _build_interpretations(
        self, variants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build interpretations from variants with HGVS expressions."""
        interpretations = []

        for idx, variant in enumerate(variants):
            # Skip if no HGVS data
            if not variant.get("c_dot"):
                continue

            # Build HGVS expressions
            expressions = []
            if variant.get("transcript") and variant.get("c_dot"):
                expressions.append({
                    "syntax": "hgvs.c",
                    "value": f"{variant['transcript']}:{variant['c_dot']}"
                })
            elif variant.get("c_dot"):
                expressions.append({
                    "syntax": "hgvs.c",
                    "value": variant["c_dot"]
                })
            
            if variant.get("p_dot"):
                expressions.append({
                    "syntax": "hgvs.p",
                    "value": variant["p_dot"]
                })
            
            if variant.get("hg38"):
                expressions.append({
                    "syntax": "hgvs.g",
                    "value": variant["hg38"]
                })

            interpretation = {
                "id": f"interpretation-{idx+1:03d}",
                "progressStatus": "COMPLETED",
                "diagnosis": {
                    "disease": self.disease_mappings["hnf1b"],
                    "genomicInterpretations": [
                        {
                            "interpretationStatus": self._map_pathogenicity(
                                variant.get("verdict") or variant.get("acmg_classification", "")
                            ),
                            "variantInterpretation": {
                                "acmgPathogenicityClassification": self._map_pathogenicity(
                                    variant.get("verdict") or variant.get("acmg_classification", "")
                                ),
                                "variationDescriptor": {
                                    "id": f"var:HNF1B:{variant.get('c_dot', 'unknown')}",
                                    "label": self._build_variant_label(variant),
                                    "geneContext": {
                                        "valueId": "HGNC:5024",
                                        "symbol": "HNF1B",
                                    },
                                    "expressions": expressions if expressions else None,
                                    "moleculeContext": "genomic",
                                    "allelicState": {
                                        "id": "GENO:0000135",
                                        "label": "heterozygous"
                                    } if variant.get("segregation") == "De novo" else None
                                },
                            },
                        }
                    ],
                },
            }

            interpretations.append(interpretation)

        return interpretations

    def _build_files(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build files section with publication references."""
        files = []
        seen_dois = set()
        
        for report in reports:
            doi = report.get("doi")
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                file_entry = {
                    "uri": f"https://doi.org/{doi}",
                    "description": report.get("title", "Publication reference")[:200] if report.get("title") else "Publication reference",
                    "fileAttributes": {
                        "fileFormat": "application/pdf",
                        "publicationType": "journal_article",
                        "doi": doi
                    }
                }
                
                # Add PMID if available
                if report.get("pmid"):
                    file_entry["fileAttributes"]["pmid"] = str(report["pmid"])
                
                # Add publication alias as individual identifier
                if report.get("publication_alias"):
                    file_entry["individualToFileIdentifiers"] = {
                        report.get("publication_alias"): "PUBLICATION_REFERENCE"
                    }
                
                files.append(file_entry)
        
        return files
    
    def _build_metadata(
        self, individual: Dict[str, Any], reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build metadata section with reviewer and contributor information."""
        created_date = datetime.now().isoformat()
        if individual.get("created_at"):
            created_date = individual["created_at"].isoformat()
        
        # Get reviewer information from reports
        reviewers = set()
        for report in reports:
            if report.get("reviewer_email"):
                reviewers.add(report["reviewer_email"])
        
        # Build createdBy field with reviewer info
        created_by = "HNF1B-API Migration"
        if reviewers:
            # Use the first reviewer as the primary contributor
            created_by = list(reviewers)[0]

        metadata = {
            "created": created_date,
            "createdBy": created_by,
            "resources": [
                {
                    "id": "hpo",
                    "name": "Human Phenotype Ontology",
                    "namespacePrefix": "HP",
                    "url": "https://hpo.jax.org",
                    "version": "2024-01-01",
                },
                {
                    "id": "mondo",
                    "name": "Mondo Disease Ontology",
                    "namespacePrefix": "MONDO",
                    "url": "https://mondo.monarchinitiative.org",
                    "version": "2024-01-01",
                },
            ],
            "phenopacketSchemaVersion": "2.0.0",
        }
        
        # Add submittedBy if we have reviewer information
        if reviewers:
            metadata["submittedBy"] = list(reviewers)[:3]  # Include up to 3 reviewers
        
        # Add comments as a custom field
        comments = []
        for report in reports:
            if report.get("comment"):
                comments.append(report["comment"])
        
        if comments:
            # Combine all comments into a single notes field
            metadata["comments"] = comments[:5]  # Limit to first 5 comments to avoid bloat
        
        # Add external references (publications) if available
        external_refs = []
        for report in reports:
            if report.get("doi"):
                external_refs.append({
                    "id": f"DOI:{report['doi']}",
                    "description": f"Publication: {report.get('publication_alias', 'Unknown')}"
                })
        
        if external_refs:
            metadata["externalReferences"] = external_refs[:5]  # Limit to 5 refs
        
        return metadata

    def _map_sex(self, sex: Optional[str]) -> str:
        """Map sex to phenopacket format."""
        if not sex:
            return "UNKNOWN_SEX"
        sex_lower = sex.lower()
        if sex_lower in ["f", "female"]:
            return "FEMALE"
        elif sex_lower in ["m", "male"]:
            return "MALE"
        elif sex_lower in ["unspecified", "unknown"]:
            return "UNKNOWN_SEX"
        else:
            return "OTHER_SEX"

    def _parse_age_to_iso8601(self, age: Any) -> Dict[str, str]:
        """Parse age to ISO8601 duration format."""
        try:
            if isinstance(age, (int, float)):
                return {"iso8601duration": f"P{int(age)}Y"}
            elif isinstance(age, str):
                import re
                match = re.search(r"\d+", age)
                if match:
                    return {"iso8601duration": f"P{match.group()}Y"}
        except:
            pass
        return {"iso8601duration": "P0Y"}

    def _map_pathogenicity(self, acmg_class: str) -> str:
        """Map ACMG classification to interpretation status."""
        if not acmg_class:
            return "UNCERTAIN_SIGNIFICANCE"
        
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

    def _clean_phenopacket(self, phenopacket: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty arrays and null values."""
        cleaned = {}
        for key, value in phenopacket.items():
            if isinstance(value, list) and len(value) == 0:
                continue
            if value is None:
                continue
            cleaned[key] = value
        return cleaned

    async def store_phenopackets(self, phenopackets: List[Dict[str, Any]]):
        """Store phenopackets in the new database structure."""
        async with self.target_session() as session:
            for phenopacket in tqdm(phenopackets, desc="Storing phenopackets"):
                # Insert using raw SQL to avoid model dependencies
                query = text("""
                    INSERT INTO phenopackets 
                    (phenopacket_id, phenopacket, created_by, schema_version)
                    VALUES (:phenopacket_id, :phenopacket, :created_by, :schema_version)
                    ON CONFLICT (phenopacket_id) DO UPDATE 
                    SET phenopacket = EXCLUDED.phenopacket,
                        updated_at = NOW()
                """)
                
                await session.execute(query, {
                    "phenopacket_id": phenopacket["id"],
                    "phenopacket": json.dumps(phenopacket),
                    "created_by": "Migration System",
                    "schema_version": "2.0.0"
                })

            await session.commit()
            logger.info(f"Stored {len(phenopackets)} phenopackets")


async def main():
    """Run the migration."""
    import os

    source_db = os.getenv(
        "OLD_DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_db",
    )
    target_db = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
    )

    migration = PhenopacketsMigrationFixed(source_db, target_db)
    await migration.migrate_all_data()


if __name__ == "__main__":
    asyncio.run(main())