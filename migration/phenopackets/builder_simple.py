"""Simplified phenopacket builder using extractors."""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from migration.phenopackets.age_parser import AgeParser
from migration.phenopackets.extractors import PhenotypeExtractor, VariantExtractor
from migration.phenopackets.hpo_mapper import HPOMapper
from migration.phenopackets.publication_mapper import PublicationMapper


class PhenopacketBuilder:
    """Builder for GA4GH Phenopackets v2 from spreadsheet data."""

    def __init__(
        self,
        hpo_mapper: HPOMapper,
        publication_mapper: Optional[PublicationMapper] = None,
    ):
        """Initialize phenopacket builder.

        Args:
            hpo_mapper: HPO term mapper
            publication_mapper: Publication reference mapper
        """
        self.hpo_mapper = hpo_mapper
        self.publication_mapper = publication_mapper
        self.age_parser = AgeParser()
        self.mondo_mappings = self._init_mondo_mappings()

        # Initialize extractors
        self.phenotype_extractor = PhenotypeExtractor(hpo_mapper, publication_mapper)
        self.variant_extractor = VariantExtractor(self.mondo_mappings)

    def _init_mondo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize MONDO disease mappings."""
        return {
            "hnf1b": {"id": "MONDO:0018874", "label": "HNF1B-related disorder"},
            "mody5": {
                "id": "MONDO:0010953",
                "label": "Maturity-onset diabetes of the young type 5",
            },
            "rcad": {"id": "ORPHA:93111", "label": "Renal cysts and diabetes syndrome"},
        }

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

    def build_phenopacket(
        self, individual_id: str, rows: pd.DataFrame
    ) -> Dict[str, Any]:
        """Build a complete phenopacket from individual data rows.

        Args:
            individual_id: Individual identifier
            rows: DataFrame rows for this individual

        Returns:
            Complete phenopacket dictionary
        """
        first_row = rows.iloc[0]

        # Build subject
        subject = self._build_subject(individual_id, first_row)

        # Extract and merge phenotypes
        all_phenotypes = self._merge_phenotypes(rows)

        # Extract and merge variants
        all_interpretations = self._merge_variants(rows)

        # Build diseases
        age_onset = self.age_parser.parse_age(first_row.get("AgeOnset"))
        diseases = self._build_diseases(first_row, age_onset)

        # Build metadata
        metadata = self._build_metadata(rows)

        # Assemble phenopacket
        phenopacket = {
            "id": f"phenopacket-{individual_id}",
            "subject": subject,
            "phenotypicFeatures": all_phenotypes,
            "diseases": diseases,
            "metaData": metadata,
        }

        if all_interpretations:
            phenopacket["interpretations"] = all_interpretations

        return self._clean_empty_fields(phenopacket)

    def _build_subject(self, individual_id: str, first_row: pd.Series) -> Dict[str, Any]:
        """Build subject section."""
        individual_identifier = self._safe_value(first_row.get("IndividualIdentifier"))

        subject = {
            "id": individual_id,
            "sex": self._map_sex(self._safe_value(first_row.get("Sex"))),
        }

        if individual_identifier:
            subject["alternateIds"] = [individual_identifier]

        # Add age if available
        age_reported = self.age_parser.parse_age(first_row.get("AgeReported"))
        if age_reported:
            subject["timeAtLastEncounter"] = age_reported

        return subject

    def _merge_phenotypes(self, rows: pd.DataFrame) -> List[Dict[str, Any]]:
        """Merge phenotypes from multiple rows."""
        phenotype_dict = {}

        for _, row in rows.iterrows():
            phenotypes = self.phenotype_extractor.extract(row)
            for pheno in phenotypes:
                pheno_id = pheno["type"]["id"]

                if pheno_id not in phenotype_dict:
                    phenotype_dict[pheno_id] = pheno
                else:
                    # Merge evidence from different publications
                    existing_pheno = phenotype_dict[pheno_id]
                    new_evidence = pheno.get("evidence", [])
                    if new_evidence:
                        if "evidence" not in existing_pheno:
                            existing_pheno["evidence"] = []

                        for new_ev in new_evidence:
                            is_duplicate = any(
                                existing_ev.get("reference", {}).get("id")
                                == new_ev.get("reference", {}).get("id")
                                and existing_ev.get("reference", {}).get("recordedAt")
                                == new_ev.get("reference", {}).get("recordedAt")
                                for existing_ev in existing_pheno["evidence"]
                            )

                            if not is_duplicate:
                                existing_pheno["evidence"].append(new_ev)

        return list(phenotype_dict.values())

    def _merge_variants(self, rows: pd.DataFrame) -> List[Dict[str, Any]]:
        """Merge variants from multiple rows."""
        variant_dict = {}

        for _, row in rows.iterrows():
            interpretations = self.variant_extractor.extract(row)
            for interp in interpretations:
                genomic_interps = interp.get("diagnosis", {}).get(
                    "genomicInterpretations", []
                )
                if not genomic_interps:
                    continue

                variant_desc = (
                    genomic_interps[0]
                    .get("variantInterpretation", {})
                    .get("variationDescriptor", {})
                )
                variant_id = variant_desc.get("id")

                if not variant_id:
                    variant_dict[f"unique_{len(variant_dict)}"] = interp
                    continue

                if variant_id not in variant_dict:
                    variant_dict[variant_id] = interp
                else:
                    # Merge publication sources
                    existing_interp = variant_dict[variant_id]
                    existing_genomic = existing_interp["diagnosis"][
                        "genomicInterpretations"
                    ][0]
                    new_genomic = genomic_interps[0]

                    existing_subject = existing_genomic.get("subjectOrBiosampleId", "")
                    new_subject = new_genomic.get("subjectOrBiosampleId", "")

                    if new_subject and new_subject != existing_subject:
                        subjects = []
                        if existing_subject:
                            subjects.append(existing_subject)
                        if new_subject not in subjects:
                            subjects.append(new_subject)

                        existing_genomic["subjectOrBiosampleId"] = " | ".join(subjects)

        return list(variant_dict.values())

    def _build_diseases(
        self, first_row: pd.Series, age_onset: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build diseases list for phenopacket."""
        disease_onset = None
        if age_onset:
            if "ontologyClass" in age_onset:
                disease_onset = age_onset
            else:
                disease_onset = {"age": age_onset}
        else:
            disease_onset = {
                "ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}
            }

        diseases = [{"term": self.mondo_mappings["hnf1b"], "onset": disease_onset}]

        # Check for MODY
        mody_col = next(
            (col for col in first_row.index if "mody" in col.lower()), None
        )
        if mody_col:
            mody_val = self._safe_value(first_row[mody_col])
            if mody_val and mody_val.lower() not in ["no", "not reported", ""]:
                diseases.append(
                    {
                        "term": self.mondo_mappings["mody5"],
                        "onset": {
                            "ontologyClass": {
                                "id": "HP:0003577",
                                "label": "Congenital onset",
                            }
                        },
                    }
                )

        return diseases

    def _build_metadata(self, rows: pd.DataFrame) -> Dict[str, Any]:
        """Build metadata for phenopacket."""
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
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                },
                {
                    "id": "mondo",
                    "name": "Mondo Disease Ontology",
                    "url": "http://purl.obolibrary.org/obo/mondo.owl",
                    "version": "2024-01-03",
                    "namespacePrefix": "MONDO",
                    "iriPrefix": "http://purl.obolibrary.org/obo/MONDO_",
                },
            ],
            "phenopacketSchemaVersion": "2.0.0",
        }

        # Add update history
        if len(rows) > 1:
            updates = []
            for _, row in rows.iterrows():
                timestamp = self.age_parser.parse_review_date(row.get("ReviewDate"))
                if timestamp:
                    updates.append(
                        {
                            "timestamp": timestamp,
                            "updatedBy": f"Publication: {row.get('Publication', 'Unknown')}",
                            "comment": f"Data from {row.get('Publication', 'Unknown source')}",
                        }
                    )
            if updates:
                updates.sort(key=lambda x: x["timestamp"])
                metadata["updates"] = updates

        # Add publication references
        if self.publication_mapper:
            external_refs = []
            pub_ids = set()

            for _, row in rows.iterrows():
                pub_val = row.get("Publication")
                if pub_val and pd.notna(pub_val):
                    pub_ids.add(str(pub_val))

            for pub_id in sorted(pub_ids):
                pub_ref = self.publication_mapper.create_publication_reference(pub_id)
                if pub_ref:
                    external_refs.append(pub_ref)

            if external_refs:
                metadata["externalReferences"] = external_refs

        return metadata

    def _clean_empty_fields(self, obj: Any) -> Any:
        """Recursively remove empty fields from object."""
        if isinstance(obj, dict):
            return {
                k: self._clean_empty_fields(v)
                for k, v in obj.items()
                if v is not None and (not isinstance(v, (list, dict)) or v)
            }
        elif isinstance(obj, list):
            cleaned = [self._clean_empty_fields(item) for item in obj]
            return [item for item in cleaned if item is not None]
        else:
            return obj