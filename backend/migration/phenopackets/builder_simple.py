"""Simplified phenopacket builder using extractors.

Follows Dependency Inversion Principle by depending on OntologyMapper abstraction.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from migration.phenopackets.age_parser import AgeParser
from migration.phenopackets.extractors import PhenotypeExtractor, VariantExtractor
from migration.phenopackets.ontology_mapper import OntologyMapper
from migration.phenopackets.publication_mapper import PublicationMapper
from migration.phenopackets.reviewer_mapper import ReviewerMapper


class PhenopacketBuilder:
    """Builder for GA4GH Phenopackets v2 from spreadsheet data.

    Depends on OntologyMapper abstraction following Dependency Inversion Principle.
    High-level module depends on abstraction, not concrete implementation.
    """

    def __init__(
        self,
        ontology_mapper: OntologyMapper,
        publication_mapper: Optional[PublicationMapper] = None,
        reviewer_mapper: Optional[ReviewerMapper] = None,
    ):
        """Initialize phenopacket builder.

        Args:
            ontology_mapper: Ontology term mapper (abstraction, not concrete class)
            publication_mapper: Publication reference mapper
            reviewer_mapper: Reviewer name mapper for resolving emails to full names
        """
        self.ontology_mapper = ontology_mapper
        self.publication_mapper = publication_mapper
        self.reviewer_mapper = reviewer_mapper
        self.age_parser = AgeParser()
        self.mondo_mappings = self._init_mondo_mappings()

        # Initialize extractors with injected dependencies
        self.phenotype_extractor = PhenotypeExtractor(
            ontology_mapper, publication_mapper
        )
        self.variant_extractor = VariantExtractor(self.mondo_mappings)

    def _init_mondo_mappings(self) -> Dict[str, Dict[str, str]]:
        """Initialize disease ontology mappings.

        All individuals in this database have HNF1B-related genetic findings.
        MONDO:0011593 (Renal cysts and diabetes syndrome) is the umbrella term
        for HNF1B-related disorder, also known as RCAD.
        """
        return {
            "hnf1b_disorder": {
                "id": "MONDO:0011593",
                "label": "Renal cysts and diabetes syndrome",
            },
            "mody5": {
                "id": "MONDO:0010953",
                "label": "Maturity-onset diabetes of the young type 5",
            },
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

        # Build subject (pass all rows to prioritize non-UNKNOWN sex)
        subject = self._build_subject(individual_id, rows)

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

        # Attach migration metadata for attribution
        # This will be used by storage layer, then removed before DB insert
        reviewer_email = first_row.get("ReviewBy") or first_row.get("review_by")
        if reviewer_email and not pd.isna(reviewer_email):
            phenopacket["_migration_metadata"] = {
                "reviewer_email": str(reviewer_email).strip(),
                "sheet_row_number": first_row.name
                if hasattr(first_row, "name")
                else None,
                "import_date": datetime.utcnow().isoformat(),
            }

        return self._clean_empty_fields(phenopacket)

    def _build_subject(self, individual_id: str, rows: pd.DataFrame) -> Dict[str, Any]:
        """Build subject section.

        When individual appears in multiple studies (multiple rows), this method:
        - Uses report_id from first row as primary subject ID (sequential IDs without gaps)
        - Stores individual_id, other report_ids, and IndividualIdentifier as alternateIds
        - Prioritizes non-UNKNOWN_SEX values across all rows
        - Uses latest reported age

        Example:
            If individual appears in 2 studies with report_id 1 and 940:
            - subject.id = "1" (first report_id)
            - alternateIds = ["1", "940", "IndividualIdentifier value"]
        """
        first_row = rows.iloc[0]

        # Use report_id as primary subject ID (gives sequential IDs: 1, 2, 3, 4...)
        # Falls back to individual_id if report_id not available
        primary_id = self._safe_value(first_row.get("report_id"))
        if not primary_id:
            primary_id = individual_id

        # Prioritize non-UNKNOWN sex from any row
        sex = "UNKNOWN_SEX"
        for _, row in rows.iterrows():
            mapped_sex = self._map_sex(self._safe_value(row.get("Sex")))
            if mapped_sex != "UNKNOWN_SEX":
                sex = mapped_sex
                break  # Use first non-UNKNOWN value found

        # Collect all unique alternate IDs:
        # 1. individual_id (for deduplication tracking)
        # 2. Other report_ids (if patient in multiple studies)
        # 3. IndividualIdentifier (original source identifier)
        alternate_ids = set()

        # Add individual_id as alternate (links duplicate reports)
        if individual_id != primary_id:
            alternate_ids.add(str(individual_id))

        # Add all report_ids from all rows (including first one for completeness)
        for _, row in rows.iterrows():
            report_id = self._safe_value(row.get("report_id"))
            if report_id:
                alternate_ids.add(str(report_id))

        # Add IndividualIdentifier values if present (important source metadata)
        for _, row in rows.iterrows():
            identifier = self._safe_value(row.get("IndividualIdentifier"))
            if identifier:
                alternate_ids.add(identifier)

        # Remove primary_id from alternates if it was added
        alternate_ids.discard(str(primary_id))

        subject: Dict[str, Any] = {
            "id": str(primary_id),
            "sex": sex,
        }

        if alternate_ids:
            subject["alternateIds"] = sorted(list(alternate_ids))

        # Use latest (maximum) reported age across all rows
        # This captures the most recent follow-up information for patients
        # who appear in multiple publications/studies
        latest_age_reported = None
        for _, row in rows.iterrows():
            age_reported = self.age_parser.parse_age(row.get("AgeReported"))
            if age_reported:
                # Compare ISO8601 durations by converting to months
                if latest_age_reported is None:
                    latest_age_reported = age_reported
                else:
                    # Extract duration strings for comparison
                    current_iso = age_reported.get("iso8601duration", "")
                    latest_iso = latest_age_reported.get("iso8601duration", "")
                    if current_iso and latest_iso:
                        if self._iso8601_to_months(current_iso) > self._iso8601_to_months(
                            latest_iso
                        ):
                            latest_age_reported = age_reported

        if latest_age_reported:
            subject["timeAtLastEncounter"] = latest_age_reported

        return subject

    def _merge_phenotypes(self, rows: pd.DataFrame) -> List[Dict[str, Any]]:
        """Merge phenotypes from multiple rows.

        When same phenotype appears in multiple studies:
        - Keeps earliest onset (most informative temporal data)
        - Merges evidence from all publications
        - Sorts phenotypes chronologically by onset age
        """
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

                    # Keep earliest onset when same phenotype reported at different ages
                    existing_onset = existing_pheno.get("onset")
                    new_onset = pheno.get("onset")

                    if new_onset and (
                        not existing_onset
                        or self._is_earlier_onset(new_onset, existing_onset)
                    ):
                        existing_pheno["onset"] = new_onset

        # Sort phenotypes chronologically (earliest onset first)
        phenotypes_list = list(phenotype_dict.values())
        phenotypes_list.sort(key=lambda p: self._onset_sort_key(p.get("onset")))

        return phenotypes_list

    def _merge_variants(self, rows: pd.DataFrame) -> List[Dict[str, Any]]:
        """Merge variants from multiple rows.

        For CNVs: Merges overlapping deletions/duplications from different studies
        into a single variant entry with multiple coordinate estimates.
        """
        variant_dict: Dict[str, Any] = {}

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

                # Check if this is a CNV and if we have overlapping CNVs
                is_cnv = "DEL" in variant_id or "DUP" in variant_id
                merged = False

                if is_cnv:
                    # Extract coordinates from this variant
                    coords = self._extract_cnv_coordinates(variant_desc)
                    if coords:
                        chrom, start, end, var_type = coords

                        # Check for overlapping CNVs in existing variants
                        for existing_id, existing_interp in variant_dict.items():
                            existing_desc = (
                                existing_interp["diagnosis"]["genomicInterpretations"][
                                    0
                                ]
                                .get("variantInterpretation", {})
                                .get("variationDescriptor", {})
                            )
                            existing_coords = self._extract_cnv_coordinates(
                                existing_desc
                            )

                            if existing_coords:
                                ex_chrom, ex_start, ex_end, ex_type = existing_coords

                                # Check if same type and overlapping (>80% reciprocal overlap)
                                if chrom == ex_chrom and var_type == ex_type:
                                    overlap = self._calculate_cnv_overlap(
                                        start, end, ex_start, ex_end
                                    )
                                    if (
                                        overlap > 0.8
                                    ):  # 80% reciprocal overlap threshold
                                        # Merge into existing variant
                                        self._merge_cnv_interpretations(
                                            existing_interp,
                                            interp,
                                            existing_desc,
                                            variant_desc,
                                        )
                                        merged = True
                                        break

                if not merged:
                    if variant_id not in variant_dict:
                        variant_dict[variant_id] = interp
                    else:
                        # Merge publication sources (for identical variants)
                        existing_interp = variant_dict[variant_id]
                        existing_genomic = existing_interp["diagnosis"][
                            "genomicInterpretations"
                        ][0]
                        new_genomic = genomic_interps[0]

                        existing_subject = existing_genomic.get(
                            "subjectOrBiosampleId", ""
                        )
                        new_subject = new_genomic.get("subjectOrBiosampleId", "")

                        if new_subject and new_subject != existing_subject:
                            subjects = []
                            if existing_subject:
                                subjects.append(existing_subject)
                            if new_subject not in subjects:
                                subjects.append(new_subject)

                            existing_genomic["subjectOrBiosampleId"] = " | ".join(
                                subjects
                            )

        return list(variant_dict.values())

    def _extract_cnv_coordinates(self, variant_desc: Dict[str, Any]) -> Optional[tuple]:
        """Extract coordinates from CNV variant descriptor."""
        extensions = variant_desc.get("extensions", [])
        for ext in extensions:
            if ext.get("name") == "coordinates":
                coords = ext.get("value", {})
                chrom = coords.get("chromosome")
                start = coords.get("start")
                end = coords.get("end")

                # Get variant type from structuralType
                struct_type = variant_desc.get("structuralType", {})
                var_type = struct_type.get("label", "").upper()

                if chrom and start and end and var_type:
                    return (chrom, start, end, var_type)
        return None

    def _calculate_cnv_overlap(
        self, start1: int, end1: int, start2: int, end2: int
    ) -> float:
        """Calculate reciprocal overlap between two CNVs."""
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_len = max(0, overlap_end - overlap_start)

        len1 = end1 - start1
        len2 = end2 - start2

        if len1 == 0 or len2 == 0:
            return 0.0

        # Reciprocal overlap: min of (overlap/len1, overlap/len2)
        return min(overlap_len / len1, overlap_len / len2)

    def _merge_cnv_interpretations(
        self,
        existing_interp: Dict[str, Any],
        new_interp: Dict[str, Any],
        existing_desc: Dict[str, Any],
        new_desc: Dict[str, Any],
    ) -> None:
        """Merge CNV interpretations from multiple studies."""
        # Merge subject IDs
        existing_genomic = existing_interp["diagnosis"]["genomicInterpretations"][0]
        new_genomic = new_interp["diagnosis"]["genomicInterpretations"][0]

        existing_subject = existing_genomic.get("subjectOrBiosampleId", "")
        new_subject = new_genomic.get("subjectOrBiosampleId", "")

        if new_subject and new_subject != existing_subject:
            subjects = []
            if existing_subject:
                subjects.append(existing_subject)
            if new_subject not in subjects:
                subjects.append(new_subject)
            existing_genomic["subjectOrBiosampleId"] = " | ".join(subjects)

        # Update description to include both coordinate estimates
        new_coords_ext = next(
            (
                ext
                for ext in new_desc.get("extensions", [])
                if ext.get("name") == "coordinates"
            ),
            None,
        )

        if new_coords_ext:
            new_coords = new_coords_ext.get("value", {})
            new_chrom = new_coords.get("chromosome")
            new_start = new_coords.get("start")
            new_end = new_coords.get("end")
            new_size_mb = round(new_coords.get("length", 0) / 1_000_000, 2)

            # Append alternate coordinates to description
            current_desc = existing_desc.get("description", "")
            if "Alternate coordinates:" not in current_desc:
                existing_desc["description"] = (
                    f"{current_desc}; "
                    f"Alternate coordinates: chr{new_chrom}:{new_start:,}-{new_end:,} ({new_size_mb}Mb)"
                )

        # Prefer dbVar ID if new variant has it and existing doesn't
        if not any("dbVar" in str(ext) for ext in existing_desc.get("extensions", [])):
            for ext in new_desc.get("extensions", []):
                if ext.get("name") == "external_reference":
                    dbvar_id = ext.get("value", {}).get("id", "")
                    if "dbVar" in dbvar_id:
                        # Add dbVar ID to label
                        current_label = existing_desc.get("label", "")
                        if dbvar_id not in current_label:
                            existing_desc["label"] = f"{current_label} ({dbvar_id})"
                        # Add extension
                        existing_desc.setdefault("extensions", []).append(ext)
                        break

    def _build_diseases(
        self, first_row: pd.Series, age_onset: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build diseases list for phenopacket.

        All individuals in this database have HNF1B-related genetic findings,
        so MONDO:0011593 (Renal cysts and diabetes syndrome / RCAD) is included
        for all phenopackets as the base disease. Additional specific disease
        terms are added based on phenotypic evidence.
        """
        diseases = []

        # Determine onset for disease terms
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

        # Add base HNF1B disorder for all individuals
        diseases.append(
            {
                "term": self.mondo_mappings["hnf1b_disorder"],
                "onset": disease_onset,
            }
        )

        # Check for MODY/diabetes - add specific MONDO term if explicitly present
        mody_col = next((col for col in first_row.index if "mody" in col.lower()), None)
        if mody_col:
            mody_val = self._safe_value(first_row[mody_col])
            if not pd.isna(mody_val) and str(mody_val).lower() not in [
                "no",
                "not reported",
                "nan",
                "",
            ]:
                # Individual has MODY - add specific MONDO term
                diseases.append(
                    {
                        "term": self.mondo_mappings["mody5"],
                        "onset": disease_onset,
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

        # Build update history with per-publication metadata
        # This preserves comments and reviewers from ALL publications
        updates = []
        for _, row in rows.iterrows():
            timestamp = self.age_parser.parse_review_date(row.get("ReviewDate"))
            if timestamp:
                pub_id = self._safe_value(row.get("Publication"))
                update_entry = {
                    "timestamp": timestamp,
                    "updatedBy": f"Publication: {pub_id or 'Unknown'}",
                }

                # Add publication-specific comment if available
                row_comment = self._safe_value(row.get("Comment"))
                if row_comment:
                    update_entry["comment"] = row_comment
                else:
                    update_entry["comment"] = f"Data from {pub_id or 'Unknown source'}"

                # Add publication-specific reviewer if available
                row_reviewer_email = self._safe_value(row.get("ReviewBy"))
                if row_reviewer_email:
                    if self.reviewer_mapper:
                        row_reviewer_name = self.reviewer_mapper.get_full_name(
                            row_reviewer_email
                        )
                        update_entry["reviewer"] = (
                            row_reviewer_name or row_reviewer_email
                        )
                    else:
                        update_entry["reviewer"] = row_reviewer_email

                # Add publication ID for easy reference
                if pub_id:
                    update_entry["publication"] = pub_id

                updates.append(update_entry)

        if updates:
            updates.sort(key=lambda x: x["timestamp"])
            metadata["updates"] = updates

            # Set top-level comment and reviewer from most recent publication
            most_recent_update = updates[-1]  # Last item after sorting
            if "comment" in most_recent_update:
                metadata["comment"] = most_recent_update["comment"]
            if "reviewer" in most_recent_update:
                metadata["reviewer"] = most_recent_update["reviewer"]
        else:
            # Fallback for single publication with no ReviewDate
            first_row = rows.iloc[0]
            comment = self._safe_value(first_row.get("Comment"))
            if comment:
                metadata["comment"] = comment

            reviewer_email = self._safe_value(first_row.get("ReviewBy"))
            if reviewer_email and self.reviewer_mapper:
                reviewer_name = self.reviewer_mapper.get_full_name(reviewer_email)
                metadata["reviewer"] = reviewer_name or reviewer_email
            elif reviewer_email:
                metadata["reviewer"] = reviewer_email

        # Add publication references with publication type
        if self.publication_mapper:
            external_refs = []
            pub_data = {}  # Map pub_id -> (pub_ref, publication_type)

            for _, row in rows.iterrows():
                pub_val = row.get("Publication")
                if pub_val and pd.notna(pub_val):
                    pub_id = str(pub_val)
                    if pub_id not in pub_data:
                        pub_ref = self.publication_mapper.create_publication_reference(
                            pub_id
                        )
                        if pub_ref:
                            # Get PublicationType from this row
                            pub_type = self._safe_value(row.get("PublicationType"))
                            pub_data[pub_id] = (pub_ref, pub_type)

            for pub_id in sorted(pub_data.keys()):
                pub_ref, pub_type = pub_data[pub_id]
                # Add publication type as 'reference' field if available
                if pub_type:
                    pub_ref["reference"] = pub_type
                external_refs.append(pub_ref)

            if external_refs:
                metadata["externalReferences"] = external_refs

        return metadata

    def _iso8601_to_months(self, iso8601: str) -> int:
        """Convert ISO8601 duration to total months for comparison.

        Args:
            iso8601: ISO8601 duration string (e.g., "P1Y4M")

        Returns:
            Total months
        """
        import re

        pattern = r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?"
        match = re.match(pattern, iso8601)

        if not match:
            return 0

        years = int(match.group(1)) if match.group(1) else 0
        months = int(match.group(2)) if match.group(2) else 0
        days = int(match.group(3)) if match.group(3) else 0

        # Convert to months (rough approximation: 30 days = 1 month)
        total_months = years * 12 + months + (days // 30)
        return total_months

    def _is_earlier_onset(self, onset1: Dict[str, Any], onset2: Dict[str, Any]) -> bool:
        """Compare two onset structures and return True if onset1 is earlier.

        Prenatal < Postnatal < specific ages (sorted by duration)

        Args:
            onset1: First onset dictionary
            onset2: Second onset dictionary

        Returns:
            True if onset1 is earlier than onset2
        """
        # Get sort keys for comparison
        key1 = self._onset_sort_key(onset1)
        key2 = self._onset_sort_key(onset2)

        return key1 < key2

    def _onset_sort_key(self, onset: Optional[Dict[str, Any]]) -> tuple:
        """Generate sort key for onset (earlier onsets have smaller keys).

        Sort priority:
        1. Prenatal (HP:0034199) - earliest
        2. Congenital/Birth (HP:0003577)
        3. Postnatal (HP:0003674)
        4. Infantile (HP:0003593)
        5. Childhood (HP:0011463)
        6. Adult (HP:0003581)
        7. Specific ages (sorted by duration in months)
        8. Unknown (no onset) - latest

        Args:
            onset: Onset dictionary from phenotype

        Returns:
            Tuple for sorting (priority, months)
        """
        if not onset:
            return (999, 0)  # Unknown - sort last

        # Check for ontology class (prenatal/postnatal/etc)
        ontology_class = onset.get("ontologyClass", {})
        hpo_id = ontology_class.get("id", "")

        # Define priority order
        hpo_priorities = {
            "HP:0034199": 1,  # Prenatal
            "HP:0003577": 2,  # Congenital
            "HP:0003674": 3,  # Postnatal
            "HP:0003593": 4,  # Infantile
            "HP:0011463": 5,  # Childhood
            "HP:0003581": 6,  # Adult
        }

        priority = hpo_priorities.get(hpo_id, 50)  # Default priority

        # Get specific age if available
        age_months = 0

        # Check for age field (combined with ontologyClass)
        age_value = onset.get("age")
        if age_value:
            if isinstance(age_value, str):
                age_months = self._iso8601_to_months(age_value)
            elif isinstance(age_value, dict) and "iso8601duration" in age_value:
                age_months = self._iso8601_to_months(age_value["iso8601duration"])

        # Check for iso8601duration field (age only)
        if not age_value and "iso8601duration" in onset:
            age_months = self._iso8601_to_months(onset["iso8601duration"])

        return (priority, age_months)

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
