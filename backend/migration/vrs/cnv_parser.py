"""Parser for converting CNV data to GA4GH compliant format."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CNVParser:
    """Parser for converting CNV data to GA4GH compliant format."""

    # Known dbVar IDs for HNF1B CNVs
    DBVAR_MAPPINGS = {
        "deletion": "dbVar:nssv1184554",  # Common HNF1B deletion
        "duplication": "dbVar:nssv1184555",  # Common HNF1B duplication
    }

    @staticmethod
    def parse_hg38_coordinates(
        hg38: str, hg38_info: str
    ) -> Optional[Tuple[str, int, int, str]]:
        """Parse hg38 coordinates from VCF-style notation.

        Args:
            hg38: VCF-style position string (e.g., 'chr17-36459258-T-<DEL>')
            hg38_info: INFO field containing END and SVLEN

        Returns:
            Tuple of (chromosome, start, end, variant_type) or None if parsing fails
        """
        if not hg38 or not hg38_info:
            return None

        try:
            # Parse chromosome and start position from hg38 field
            parts = hg38.replace(":", "-").split("-")
            if len(parts) < 4:
                return None

            chromosome = parts[0].replace("chr", "")  # Remove 'chr' prefix
            start = int(parts[1])

            # Parse END position and variant type from hg38_INFO
            end_match = re.search(r"END=(\d+)", hg38_info)
            if not end_match:
                return None
            end = int(end_match.group(1))

            # Determine variant type
            variant_type = None
            if "SVTYPE=DEL" in hg38_info or "<DEL>" in hg38:
                variant_type = "DEL"
            elif "SVTYPE=DUP" in hg38_info or "<DUP>" in hg38:
                variant_type = "DUP"
            elif "SVTYPE=INV" in hg38_info:
                variant_type = "INV"
            elif "SVTYPE=INS" in hg38_info:
                variant_type = "INS"

            return (chromosome, start, end, variant_type)

        except (ValueError, IndexError) as e:
            logger.warning(
                f"Failed to parse coordinates from hg38='{hg38}', "
                f"hg38_info='{hg38_info}': {e}"
            )
            return None

    @staticmethod
    def create_ga4gh_cnv_notation(
        chromosome: str, start: int, end: int, variant_type: str
    ) -> str:
        """Create GA4GH compliant CNV notation.

        Args:
            chromosome: Chromosome number (e.g., '17')
            start: Start position (1-based)
            end: End position (1-based)
            variant_type: Type of variant (DEL, DUP, INV, INS)

        Returns:
            GA4GH compliant string (e.g., '17:36459258-37832869:DEL')
        """
        return f"{chromosome}:{start}-{end}:{variant_type}"

    @staticmethod
    def create_iscn_notation(
        chromosome: str, start: int, end: int, variant_type: str
    ) -> Optional[str]:
        """Create ISCN notation.

        Args:
            chromosome: Chromosome number
            start: Start position
            end: End position
            variant_type: Type of variant

        Returns:
            ISCN notation string or None
        """
        # Simplified ISCN notation for common CNVs
        if variant_type == "DEL":
            return f"del({chromosome})(q12)"  # HNF1B is at 17q12
        elif variant_type == "DUP":
            return f"dup({chromosome})(q12)"
        return None

    @staticmethod
    def get_dbvar_id(variant_type: str) -> Optional[str]:
        """Get dbVar ID for common HNF1B CNVs.

        Args:
            variant_type: Type of variant (DEL, DUP)

        Returns:
            dbVar ID string or None
        """
        if variant_type == "DEL":
            return CNVParser.DBVAR_MAPPINGS.get("deletion")
        elif variant_type == "DUP":
            return CNVParser.DBVAR_MAPPINGS.get("duplication")
        return None

    @classmethod
    def create_phenopacket_cnv_variant(
        cls,
        hg38: str,
        hg38_info: str,
        variant_type_str: Optional[str] = None,
        variant_reported: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a complete phenopacket CNV variant representation.

        Args:
            hg38: VCF-style position string
            hg38_info: INFO field with END and SVLEN
            variant_type_str: Original variant type string from spreadsheet
            variant_reported: Human-readable variant description

        Returns:
            Dictionary containing the complete variant representation
        """
        # Parse coordinates
        coords = cls.parse_hg38_coordinates(hg38, hg38_info)
        if not coords:
            return None

        chromosome, start, end, variant_type = coords

        # Create various notations
        ga4gh_notation = cls.create_ga4gh_cnv_notation(
            chromosome, start, end, variant_type
        )
        iscn_notation = cls.create_iscn_notation(chromosome, start, end, variant_type)
        dbvar_id = cls.get_dbvar_id(variant_type)

        # Calculate size
        size = end - start + 1
        size_mb = round(size / 1_000_000, 2)

        # Extract literature-reported size from VariantReported (e.g., "1.5 Mb", "1.5-megabase")
        reported_size = None
        if variant_reported:
            size_match = re.search(
                r"(\d+\.?\d*)\s*-?\s*[Mm](?:ega)?[Bb](?:ase)?", variant_reported
            )
            if size_match:
                reported_size = size_match.group(1) + "Mb"

        # Build concise label: "1.5Mb deletion (dbVar:nssv1184554)"
        if reported_size:
            label = f"{reported_size} {variant_type.lower()}"
        else:
            label = f"{size_mb}Mb {variant_type.lower()}"

        # Add dbVar ID to label if available (helps with literature search)
        if dbvar_id:
            label += f" ({dbvar_id})"

        # Build variant descriptor
        variant_descriptor = {
            "id": f"var:HNF1B:{ga4gh_notation}",
            "label": label,
            "structuralType": {
                "id": (
                    "SO:0000159"
                    if variant_type == "DEL"
                    else "SO:1000035"
                    if variant_type == "DUP"
                    else "SO:0000667"
                ),
                "label": "deletion"
                if variant_type == "DEL"
                else "duplication"
                if variant_type == "DUP"
                else "insertion",
            },
            "geneContext": {"valueId": "HGNC:5024", "symbol": "HNF1B"},
            "expressions": [],
            "extensions": [],
        }

        # Description: Full literature text + calculated size
        if variant_reported:
            variant_descriptor["description"] = (
                f"{variant_reported} [calculated: {size_mb}Mb, chr{chromosome}:{start:,}-{end:,}]"
            )
        else:
            variant_descriptor["description"] = (
                f"HNF1B {variant_type} ({size_mb}Mb) - chr{chromosome}:{start:,}-{end:,}"
            )

        # Add expressions in various formats
        expressions = variant_descriptor["expressions"]

        # GA4GH CNV notation (primary)
        expressions.append({"syntax": "ga4gh", "value": ga4gh_notation})

        # Add VCF-style notation
        expressions.append({"syntax": "vcf", "value": hg38})

        # Add ISCN notation if available
        if iscn_notation:
            expressions.append({"syntax": "iscn", "value": iscn_notation})

        # Add human-readable description if provided
        if variant_reported:
            expressions.append({"syntax": "text", "value": variant_reported})

        # Add extensions with detailed information
        extensions = variant_descriptor["extensions"]

        # Add dbVar reference if available
        if dbvar_id:
            extensions.append(
                {
                    "name": "external_reference",
                    "value": {
                        "id": dbvar_id,
                        "reference": "dbVar",
                        "description": "Database of Genomic Structural Variation",
                    },
                }
            )

        # Add precise coordinates
        extensions.append(
            {
                "name": "coordinates",
                "value": {
                    "assembly": "GRCh38/hg38",
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "length": size,
                },
            }
        )

        # Check for explicit zygosity/copy number information in the variant description
        if variant_reported:
            reported_lower = variant_reported.lower()

            # Check for explicit zygosity mentions
            if "homozygous" in reported_lower:
                extensions.append({"name": "zygosity", "value": "homozygous"})
                # For homozygous deletion: 0 copies, homozygous duplication: 4 copies
                if variant_type == "DEL":
                    extensions.append(
                        {
                            "name": "copy_number",
                            "value": {
                                "absolute_copy_number": 0,
                                "relative_copy_number": -2,
                                "evidence": "Explicitly stated as homozygous",
                            },
                        }
                    )
            elif "heterozygous" in reported_lower:
                extensions.append({"name": "zygosity", "value": "heterozygous"})
                # For heterozygous deletion: 1 copy, heterozygous duplication: 3 copies
                if variant_type == "DEL":
                    extensions.append(
                        {
                            "name": "copy_number",
                            "value": {
                                "absolute_copy_number": 1,
                                "relative_copy_number": -1,
                                "evidence": "Explicitly stated as heterozygous",
                            },
                        }
                    )
                elif variant_type == "DUP":
                    extensions.append(
                        {
                            "name": "copy_number",
                            "value": {
                                "absolute_copy_number": 3,
                                "relative_copy_number": 1,
                                "evidence": "Explicitly stated as heterozygous",
                            },
                        }
                    )
            # Check for explicit copy number mentions
            # (e.g., "CN=0", "0 copies", "single copy")
            cn_match = re.search(r"CN[=:]?\s*(\d+)|(\d+)\s*cop(y|ies)", reported_lower)
            if cn_match:
                copy_num = int(cn_match.group(1) or cn_match.group(2))
                extensions.append(
                    {
                        "name": "copy_number",
                        "value": {
                            "absolute_copy_number": copy_num,
                            "relative_copy_number": copy_num - 2,  # Normal is 2 copies
                            "evidence": (
                                f"Extracted from description: {cn_match.group(0)}"
                            ),
                        },
                    }
                )

        return variant_descriptor

    @classmethod
    def parse_variant_for_phenopacket(
        cls, row_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse variant data from a spreadsheet row for phenopacket inclusion.

        Args:
            row_data: Dictionary containing row data from spreadsheet

        Returns:
            Phenopacket-ready variant interpretation or None
        """
        hg38 = row_data.get("hg38")
        hg38_info = row_data.get("hg38_INFO")
        variant_type = row_data.get("VariantType")
        variant_reported = row_data.get("VariantReported")

        # Check if this is a CNV
        if not variant_type:
            return None

        variant_type_lower = variant_type.lower()
        # Use regex to match canonical CNV terms as whole words, case-insensitive
        cnv_pattern = (
            r"\b(deletion|duplication|del|dup|cnv|copy number variation|"
            r"copy number change|copy number loss|copy number gain)\b"
        )
        is_cnv = bool(re.search(cnv_pattern, variant_type_lower))

        if not is_cnv or not hg38 or not hg38_info:
            return None

        # Create the CNV variant descriptor
        variant_descriptor = cls.create_phenopacket_cnv_variant(
            hg38, hg38_info, variant_type, variant_reported
        )

        if not variant_descriptor:
            return None

        # Wrap in interpretation structure
        interpretation = {
            "progressStatus": "COMPLETED",
            "diagnosis": {
                "disease": {
                    "id": "MONDO:0011593",
                    "label": "Renal cysts and diabetes syndrome",
                },
                "genomicInterpretations": [
                    {
                        "subjectOrBiosampleId": row_data.get(
                            "IndividualIdentifier", "unknown"
                        ),
                        # CNVs are usually pathogenic
                        "interpretationStatus": "PATHOGENIC",
                        "variantInterpretation": {
                            "variationDescriptor": variant_descriptor
                        },
                    }
                ],
            },
        }

        return interpretation
