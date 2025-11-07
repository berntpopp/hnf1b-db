"""Extractors for phenotypes and variants from spreadsheet data.

Follows Dependency Inversion Principle by depending on OntologyMapper abstraction.
"""

import re
from typing import Any, Dict, List, Optional, cast

import pandas as pd

from migration.phenopackets.age_parser import AgeParser
from migration.phenopackets.evidence_builder import EvidenceBuilder
from migration.phenopackets.ontology_mapper import OntologyMapper
from migration.phenopackets.publication_mapper import PublicationMapper
from migration.vrs.cnv_parser import CNVParser
from migration.vrs.vrs_builder import VRSBuilder


class PhenotypeExtractor:
    """Extracts phenotypic features from spreadsheet rows.

    Depends on OntologyMapper abstraction following Dependency Inversion Principle.
    This allows for easy testing with mock mappers and flexibility to swap
    implementations.
    """

    def __init__(
        self,
        ontology_mapper: OntologyMapper,
        publication_mapper: Optional[PublicationMapper] = None,
    ):
        """Initialize phenotype extractor.

        Args:
            ontology_mapper: Ontology term mapper (abstraction, not concrete class)
            publication_mapper: Publication reference mapper
        """
        self.ontology_mapper = ontology_mapper
        self.publication_mapper = publication_mapper
        self.age_parser = AgeParser()
        self.evidence_builder = EvidenceBuilder(publication_mapper)

    def _normalize_column_name(self, name: str) -> str:
        """Normalize column names to lowercase without spaces."""
        return self.ontology_mapper.normalize_key(name)

    def _safe_value(self, value: Any) -> Optional[str]:
        """Safely convert value to string, handling NaN."""
        if pd.isna(value) or value == "" or value == "NaN":
            return None
        return str(value).strip()

    def extract(self, row: pd.Series) -> List[Dict[str, Any]]:
        """Extract phenotypic features from a row with temporal information."""
        phenotypes: List[Dict[str, Any]] = []

        # Get timestamp from ReviewDate for this observation
        review_timestamp = self.age_parser.parse_review_date(row.get("ReviewDate"))

        # Get age at onset if available (e.g., "prenatal", "postnatal")
        age_onset_class = self.age_parser.parse_age(row.get("AgeOnset"))

        # Get reported age (e.g., "2y", "1y4m", "P2Y", "P1Y4M")
        age_reported = self.age_parser.parse_age(row.get("AgeReported"))

        # Normalize column names
        normalized_cols = {self._normalize_column_name(col): col for col in row.index}

        # Process each phenotype column
        for pheno_key, hpo_info in self.ontology_mapper.get_all_mappings().items():
            if pheno_key in normalized_cols:
                original_col = normalized_cols[pheno_key]
                value = self._safe_value(row[original_col])

                if value and value.lower() not in ["no", "not reported", "unknown", ""]:
                    # Special handling for KidneyBiopsy with specific diagnoses
                    if pheno_key == "kidneybiopsy":
                        self._handle_kidney_biopsy(
                            value, row, review_timestamp, phenotypes
                        )
                        continue

                    # Determine if phenotype is present
                    excluded = False
                    if value.lower() in ["absent", "negative", "none"]:
                        excluded = True

                    phenotype = {
                        "type": {"id": hpo_info["id"], "label": hpo_info["label"]},
                        "excluded": excluded,
                    }

                    # Add onset information - prenatal/postnatal takes priority
                    if not excluded:
                        if age_onset_class:
                            # Use prenatal/postnatal as primary onset
                            phenotype["onset"] = age_onset_class
                            # If we also have a specific age, add it alongside
                            if age_reported and "ontologyClass" in age_onset_class:
                                # Combine ontologyClass (prenatal/postnatal) + age
                                onset_dict = cast(Dict[str, Any], phenotype["onset"])
                                onset_dict["age"] = (
                                    age_reported.get("iso8601duration")
                                    if isinstance(age_reported, dict)
                                    and "iso8601duration" in age_reported
                                    else age_reported
                                )
                        elif age_reported:
                            # Only specific age available, use it
                            phenotype["onset"] = age_reported

                    # Add evidence (using EvidenceBuilder to eliminate duplication)
                    evidence = self.evidence_builder.build_evidence(
                        publication_id=row.get("Publication"),
                        review_timestamp=review_timestamp,
                    )
                    if evidence:
                        phenotype["evidence"] = evidence

                    # Add modifier if applicable (for bilateral/unilateral features)
                    if value.lower() in ["bilateral", "unilateral", "left", "right"]:
                        modifier_map = {
                            "bilateral": {"id": "HP:0012832", "label": "Bilateral"},
                            "unilateral": {"id": "HP:0012833", "label": "Unilateral"},
                            "left": {"id": "HP:0012835", "label": "Left"},
                            "right": {"id": "HP:0012834", "label": "Right"},
                        }
                        if value.lower() in modifier_map:
                            phenotype["modifiers"] = [modifier_map[value.lower()]]

                    phenotypes.append(phenotype)

        return phenotypes

    def _handle_kidney_biopsy(
        self,
        value: str,
        row: pd.Series,
        review_timestamp: Optional[str],
        phenotypes: List[Dict[str, Any]],
    ) -> None:
        """Handle special kidney biopsy findings."""
        value_lower = value.lower()

        # Map specific kidney biopsy findings to their HPO/ORPHA terms
        if "oligomeganephronia" in value_lower:
            phenotype = {
                "type": {"id": "ORPHA:2260", "label": "Oligomeganephronia"},
                "excluded": False,
            }
            evidence = self.evidence_builder.build_evidence(
                publication_id=row.get("Publication"),
                review_timestamp=review_timestamp,
            )
            if evidence:
                phenotype["evidence"] = evidence
            phenotypes.append(phenotype)

        if (
            "multiple glomerular cysts" in value_lower
            or "glomerular cyst" in value_lower
        ):
            phenotype = {
                "type": {"id": "HP:0100611", "label": "Multiple glomerular cysts"},
                "excluded": False,
            }
            evidence = self.evidence_builder.build_evidence(
                publication_id=row.get("Publication"),
                review_timestamp=review_timestamp,
            )
            if evidence:
                phenotype["evidence"] = evidence
            phenotypes.append(phenotype)


class VariantExtractor:
    """Extracts variants from spreadsheet rows."""

    def __init__(self, mondo_mappings: Dict[str, Dict[str, str]]):
        """Initialize variant extractor.

        Args:
            mondo_mappings: MONDO disease mappings
        """
        self.mondo_mappings = mondo_mappings

    def _safe_value(self, value: Any) -> Optional[str]:
        """Safely convert value to string, handling NaN."""
        if pd.isna(value) or value == "" or value == "NaN":
            return None
        return str(value).strip()

    def extract(self, row: pd.Series) -> List[Dict[str, Any]]:
        """Extract variant information from row."""
        interpretations = []

        # Get all variant-related columns
        varsome = self._safe_value(row.get("Varsome"))
        variant_reported = self._safe_value(row.get("VariantReported"))
        hg38 = self._safe_value(row.get("hg38"))
        hg38_info = self._safe_value(row.get("hg38_INFO"))
        verdict = self._safe_value(row.get("verdict_classification"))
        variant_type = self._safe_value(row.get("VariantType"))
        segregation = self._safe_value(row.get("Segregation"))
        criteria = self._safe_value(row.get("criteria_classification"))
        publication = self._safe_value(row.get("Publication"))

        # Check if this is a CNV
        is_cnv = self._is_cnv(variant_type)

        # Handle CNVs
        if is_cnv and hg38 and hg38_info:
            cnv_interp = self._handle_cnv(
                row, hg38, hg38_info, variant_type, variant_reported, publication
            )
            if cnv_interp:
                self._add_classification_info(
                    cnv_interp, verdict, criteria, segregation
                )
                interpretations.append(cnv_interp)
                # Skip SNV processing for CNVs - already handled
                return interpretations

        # Handle SNVs and other variants (only if not a CNV)
        c_dot, p_dot, transcript = self._parse_variant_notation(
            varsome, variant_reported
        )

        if c_dot or hg38 or varsome:
            variant_descriptor = self._create_snv_descriptor(
                hg38, c_dot, p_dot, transcript, variant_reported, variant_type
            )

            if variant_descriptor:
                interpretation = self._create_interpretation(
                    row, variant_descriptor, publication, len(interpretations)
                )
                self._add_classification_info(
                    interpretation, verdict, criteria, segregation
                )
                interpretations.append(interpretation)

        return interpretations

    def _is_cnv(self, variant_type: Optional[str]) -> bool:
        """Check if variant is a CNV."""
        if not variant_type:
            return False
        type_lower = variant_type.lower()
        return any(term in type_lower for term in ["delet", "dup", "cnv", "copy"])

    def _handle_cnv(
        self,
        row: pd.Series,
        hg38: str,
        hg38_info: str,
        variant_type: Optional[str],
        variant_reported: Optional[str],
        publication: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Handle CNV variant extraction."""
        cnv_interpretation = CNVParser.parse_variant_for_phenopacket(
            {
                "hg38": hg38,
                "hg38_INFO": hg38_info,
                "VariantType": variant_type,
                "VariantReported": variant_reported,
                "IndividualIdentifier": row.get(
                    "IndividualIdentifier", row.get("individual_id", "unknown")
                ),
            }
        )

        if cnv_interpretation:
            individual_id = row.get(
                "IndividualIdentifier", row.get("individual_id", "unknown")
            )
            subject_id = (
                f"{individual_id}_{publication}" if publication else individual_id
            )
            cnv_interpretation["diagnosis"]["genomicInterpretations"][0][
                "subjectOrBiosampleId"
            ] = subject_id

        return cnv_interpretation

    def _parse_variant_notation(
        self, varsome: Optional[str], variant_reported: Optional[str]
    ) -> tuple:
        """Parse variant notation from Varsome and VariantReported."""
        c_dot = None
        p_dot = None
        transcript = None

        # Parse Varsome (GA4GH compliant format)
        if varsome:
            transcript_match = re.search(r"NM_\d+\.\d+", varsome)
            if transcript_match:
                transcript = transcript_match.group()

            c_dot_match = re.search(r"c\.[^\s\)]+", varsome)
            if c_dot_match:
                c_dot = c_dot_match.group()

            p_dot_match = re.search(r"p\.[^\)]+", varsome)
            if p_dot_match:
                p_dot = p_dot_match.group()

        # Parse VariantReported if Varsome didn't provide everything
        if variant_reported and (not c_dot or not p_dot):
            if "," in variant_reported:
                parts = variant_reported.split(",")
                for part in parts:
                    part = part.strip()
                    if not c_dot and part.startswith("c."):
                        c_dot = part
                    elif not p_dot and part.startswith("p."):
                        p_dot = part
            elif not c_dot and variant_reported.startswith("c."):
                c_dot = variant_reported

        return c_dot, p_dot, transcript

    def _create_snv_descriptor(
        self,
        hg38: Optional[str],
        c_dot: Optional[str],
        p_dot: Optional[str],
        transcript: Optional[str],
        variant_reported: Optional[str],
        variant_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Create SNV/Indel variant descriptor."""
        # Try VRS 2.0 format
        variant_descriptor = None
        if hg38 and not (hg38.startswith("<") or "<" in hg38):
            variant_descriptor = VRSBuilder.create_vrs_snv_variant(
                hg38, c_dot, p_dot, transcript, variant_reported
            )

        # Fallback format
        if not variant_descriptor:
            variant_label = f"HNF1B:{c_dot if c_dot else 'variant'}"
            if p_dot:
                variant_label += f" ({p_dot})"

            variant_descriptor = {
                "id": f"var:HNF1B:{c_dot if c_dot else hg38 if hg38 else 'unknown'}",
                "label": variant_label,
                "geneContext": {"valueId": "HGNC:5024", "symbol": "HNF1B"},
                "expressions": [],
                "moleculeContext": "genomic",
            }

            if variant_reported:
                variant_descriptor["description"] = variant_reported

            expressions = variant_descriptor["expressions"]
            if c_dot:
                transcript_id = transcript if transcript else "NM_000458.4"
                expressions.append(
                    {"syntax": "hgvs.c", "value": f"{transcript_id}:{c_dot}"}
                )
            if p_dot:
                expressions.append(
                    {"syntax": "hgvs.p", "value": f"NP_000449.3:{p_dot}"}
                )
            if hg38:
                expressions.append({"syntax": "vcf", "value": hg38})

        # Add molecular consequence
        self._add_molecular_consequence(variant_descriptor, variant_type, hg38, c_dot)

        return variant_descriptor

    def _add_molecular_consequence(
        self,
        variant_descriptor: Dict[str, Any],
        variant_type: Optional[str],
        hg38: Optional[str],
        c_dot: Optional[str],
    ) -> None:
        """Add molecular consequence to variant descriptor."""
        molecular_consequence = None

        if variant_type:
            type_lower = variant_type.lower()
            if "snv" in type_lower or "snp" in type_lower:
                molecular_consequence = {"id": "SO:0001483", "label": "SNV"}
            elif "delet" in type_lower:
                molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
            elif "dup" in type_lower:
                molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
            elif "indel" in type_lower:
                molecular_consequence = {"id": "SO:1000032", "label": "indel"}
        elif hg38:
            if "<DEL>" in hg38:
                molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
            elif "<DUP>" in hg38:
                molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
        elif c_dot:
            # Check for complex indels (delins) first before simple del/ins
            if "delins" in c_dot:
                molecular_consequence = {"id": "SO:1000032", "label": "indel"}
            elif "del" in c_dot:
                molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
            elif "dup" in c_dot:
                molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
            elif "ins" in c_dot:
                molecular_consequence = {"id": "SO:0000667", "label": "insertion"}
            elif ">" in c_dot:
                molecular_consequence = {"id": "SO:0001483", "label": "SNV"}

        if molecular_consequence:
            variant_descriptor["molecularConsequences"] = [molecular_consequence]

    def _create_interpretation(
        self,
        row: pd.Series,
        variant_descriptor: Dict[str, Any],
        publication: Optional[str],
        interp_count: int,
    ) -> Dict[str, Any]:
        """Create variant interpretation."""
        individual_id = row.get(
            "IndividualIdentifier", row.get("individual_id", "unknown")
        )
        subject_biosample_id = (
            f"{individual_id}_{publication}" if publication else individual_id
        )

        return {
            "id": f"interpretation-{interp_count + 1:03d}",
            "progressStatus": "COMPLETED",
            "diagnosis": {
                # Disease term assignment strategy:
                # - For SNVs/indels: Empty disease field (assigned at phenopacket level)
                # - For CNVs: Disease assigned by CNVParser (MONDO:0011593)
                # - Rationale: HNF1B SNVs don't always correlate to a single disease;
                #   diagnosis depends on full phenotypic evidence reviewed at
                #   phenopacket level (see builder_simple.py _build_diseases method)
                "disease": {},  # Explicitly empty for SNVs/indels
                "genomicInterpretations": [
                    {
                        "subjectOrBiosampleId": subject_biosample_id,
                        "interpretationStatus": "UNCERTAIN_SIGNIFICANCE",
                        "variantInterpretation": {
                            "variationDescriptor": variant_descriptor
                        },
                    }
                ],
            },
        }

    def _add_classification_info(
        self,
        interpretation: Dict[str, Any],
        verdict: Optional[str],
        criteria: Optional[str],
        segregation: Optional[str],
    ) -> None:
        """Add classification information to interpretation."""
        genomic_interp = interpretation["diagnosis"]["genomicInterpretations"][0]

        # Add allelicState based on segregation
        if segregation:
            seg_lower = segregation.lower()
            if "de novo" in seg_lower or "inherited" in seg_lower:
                genomic_interp["variantInterpretation"]["variationDescriptor"][
                    "allelicState"
                ] = {"id": "GENO:0000135", "label": "heterozygous"}

        # Map pathogenicity
        # IMPORTANT: Check more specific patterns first to avoid substring matches
        # e.g., "likely pathogenic" must be checked before "pathogenic"
        if verdict:
            verdict_lower = verdict.lower()

            # Check specific patterns first (longer strings before shorter)
            if "likely pathogenic" in verdict_lower:
                genomic_interp["interpretationStatus"] = "LIKELY_PATHOGENIC"
            elif "likely benign" in verdict_lower:
                genomic_interp["interpretationStatus"] = "LIKELY_BENIGN"
            elif "pathogenic" in verdict_lower:
                genomic_interp["interpretationStatus"] = "PATHOGENIC"
            elif "uncertain significance" in verdict_lower or "vus" in verdict_lower:
                genomic_interp["interpretationStatus"] = "UNCERTAIN_SIGNIFICANCE"
            elif "benign" in verdict_lower:
                genomic_interp["interpretationStatus"] = "BENIGN"

        # Add classification criteria
        if criteria:
            guidelines = (
                "ClinGen CNV"
                if any(char.isdigit() and char in "1234" for char in criteria[:2])
                else "ACMG"
            )

            var_interp = genomic_interp["variantInterpretation"]
            if "extensions" not in var_interp:
                var_interp["extensions"] = []

            var_interp["extensions"].append(
                {
                    "name": "classification_criteria",
                    "value": {"guidelines": guidelines, "criteria": criteria},
                }
            )
