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

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VRSBuilder:
    """Builder for GA4GH VRS 2.0 (Variant Representation Specification) compliant alleles.

    VRS 2.0 uses:
    - IRI-based identifiers
    - SequenceLocation with SequenceInterval
    - LiteralSequenceExpression for allele state
    - Computed identifiers using GA4GH digest algorithm
    """

    # Reference sequence accessions for chromosomes (GRCh38/hg38)
    REFSEQ_ACCESSIONS = {
        "1": "NC_000001.11", "2": "NC_000002.12", "3": "NC_000003.12",
        "4": "NC_000004.12", "5": "NC_000005.10", "6": "NC_000006.12",
        "7": "NC_000007.14", "8": "NC_000008.11", "9": "NC_000009.12",
        "10": "NC_000010.11", "11": "NC_000011.10", "12": "NC_000012.12",
        "13": "NC_000013.11", "14": "NC_000014.9", "15": "NC_000015.10",
        "16": "NC_000016.10", "17": "NC_000017.11", "18": "NC_000018.10",
        "19": "NC_000019.10", "20": "NC_000020.11", "21": "NC_000021.9",
        "22": "NC_000022.11", "X": "NC_000023.11", "Y": "NC_000024.10",
        "M": "NC_012920.1", "MT": "NC_012920.1"
    }

    @staticmethod
    def parse_vcf_to_vrs(vcf_string: str) -> Optional[Dict[str, Any]]:
        """Parse VCF-style string to VRS components.

        Args:
            vcf_string: VCF-style string (e.g., 'chr17-37744882-C-T' or 'chr17:37744882:C:T')

        Returns:
            Dictionary with VRS components or None if parsing fails
        """
        if not vcf_string:
            return None

        # Parse VCF format: chr17-37744882-C-T or chr17:37744882:C:T
        parts = vcf_string.replace(':', '-').split('-')
        if len(parts) < 4:
            return None

        try:
            chromosome = parts[0].replace('chr', '')
            position = int(parts[1])
            ref_allele = parts[2]
            alt_allele = parts[3]

            # Skip structural variants
            if ref_allele.startswith('<') or alt_allele.startswith('<'):
                return None

            return {
                'chromosome': chromosome,
                'position': position,
                'ref': ref_allele,
                'alt': alt_allele
            }
        except (ValueError, IndexError):
            return None

    @classmethod
    def create_vrs_allele(cls, chromosome: str, position: int,
                         ref: str, alt: str, assembly: str = "GRCh38") -> Dict[str, Any]:
        """Create a GA4GH VRS 2.0 Allele structure.

        VRS 2.0 Allele structure includes:
        - type: "Allele"
        - location: SequenceLocation with sequence reference
        - state: sequence state (literal or reference)
        - Optional computed digest identifier

        Args:
            chromosome: Chromosome (e.g., '17')
            position: 1-based position
            ref: Reference allele
            alt: Alternate allele
            assembly: Reference assembly (default: GRCh38)

        Returns:
            VRS 2.0 Allele dictionary
        """
        # Get RefSeq accession for chromosome
        refseq_id = cls.REFSEQ_ACCESSIONS.get(chromosome)
        if not refseq_id:
            refseq_id = f"NC_0000{chromosome}.??"  # Fallback

        # VRS 2.0 uses 0-based interbase coordinates (same as VRS 1.3)
        start = position - 1  # Convert from 1-based to 0-based
        end = start + len(ref)

        # Build VRS 2.0 Allele structure
        vrs_allele = {
            "type": "Allele",
            "digest": None,  # Would be computed using GA4GH digest algorithm
            "location": {
                "type": "SequenceLocation",
                "sequenceReference": {
                    # VRS 2.0 uses refget or sequence accessions
                    "type": "SequenceReference",
                    "refgetAccession": f"SQ.{refseq_id}",
                    # Alternative: use refseq directly
                    "other_identifiers": [
                        f"refseq:{refseq_id}",
                        f"GRCh38:chr{chromosome}"
                    ]
                },
                "interval": {
                    "type": "SequenceInterval",
                    "start": {
                        "type": "Number",
                        "value": start
                    },
                    "end": {
                        "type": "Number",
                        "value": end
                    }
                }
            },
            "state": {
                "type": "LiteralSequenceExpression",
                "sequence": alt
            }
        }

        # Generate VRS 2.0 compliant identifier
        # Format: ga4gh:VA.{digest} where digest is computed from normalized VRS JSON
        # For now, using a placeholder computation
        identifier_string = f"{refseq_id}:{start}-{end}:{ref}>{alt}"
        vrs_allele["digest"] = f"{abs(hash(identifier_string)) % (10**12):012d}"
        vrs_allele["id"] = f"ga4gh:VA.{vrs_allele['digest']}"

        # Add expressions for alternative representations
        vrs_allele["expressions"] = [
            {
                "syntax": "hgvs.g",
                "value": cls.create_hgvs_g_notation(chromosome, position, ref, alt)
            },
            {
                "syntax": "spdi",
                "value": f"{refseq_id}:{start}:{len(ref)}:{alt}"
            }
        ]

        return vrs_allele

    @classmethod
    def create_hgvs_g_notation(cls, chromosome: str, position: int,
                               ref: str, alt: str) -> str:
        """Create proper HGVS.g notation.

        Args:
            chromosome: Chromosome
            position: 1-based position
            ref: Reference allele
            alt: Alternate allele

        Returns:
            HGVS.g notation string
        """
        refseq_id = cls.REFSEQ_ACCESSIONS.get(chromosome, f"NC_0000{chromosome}.??")

        # Handle different variant types
        if len(ref) == 1 and len(alt) == 1:
            # SNV
            return f"{refseq_id}:g.{position}{ref}>{alt}"
        elif len(ref) > len(alt):
            # Deletion
            if len(alt) == 0 or (len(alt) == 1 and ref[0] == alt[0]):
                # Pure deletion
                del_start = position + 1 if len(alt) == 1 else position
                del_end = position + len(ref) - 1
                if del_start == del_end:
                    return f"{refseq_id}:g.{del_start}del"
                else:
                    return f"{refseq_id}:g.{del_start}_{del_end}del"
            else:
                # Deletion with substitution (complex)
                return f"{refseq_id}:g.{position}_{position + len(ref) - 1}delins{alt}"
        elif len(ref) < len(alt):
            # Insertion
            if len(ref) == 0 or (len(ref) == 1 and ref[0] == alt[0]):
                # Pure insertion
                ins_seq = alt[1:] if len(ref) == 1 else alt
                return f"{refseq_id}:g.{position}_{position + 1}ins{ins_seq}"
            else:
                # Insertion with substitution (complex)
                return f"{refseq_id}:g.{position}_{position + len(ref) - 1}delins{alt}"
        else:
            # Complex substitution
            return f"{refseq_id}:g.{position}_{position + len(ref) - 1}delins{alt}"

    @classmethod
    def create_vrs_snv_variant(cls, hg38: str, c_dot: str = None,
                              p_dot: str = None, transcript: str = None) -> Dict[str, Any]:
        """Create a VRS 2.0 compliant variant descriptor for SNVs/Indels.

        Args:
            hg38: VCF-style genomic position
            c_dot: HGVS c. notation
            p_dot: HGVS p. notation
            transcript: Transcript ID

        Returns:
            Phenopacket-ready variant descriptor with VRS 2.0 structure
        """
        # Parse VCF coordinates
        vrs_components = cls.parse_vcf_to_vrs(hg38)
        if not vrs_components:
            return None

        # Create VRS 2.0 Allele
        vrs_allele = cls.create_vrs_allele(
            vrs_components['chromosome'],
            vrs_components['position'],
            vrs_components['ref'],
            vrs_components['alt']
        )

        # Build variant descriptor for phenopacket
        variant_descriptor = {
            "id": vrs_allele["id"],  # Use VRS identifier
            "label": f"HNF1B:{c_dot if c_dot else 'variant'}",
            "geneContext": {
                "valueId": "HGNC:5024",
                "symbol": "HNF1B"
            },
            "expressions": [],
            "vrsAllele": vrs_allele,  # Embed full VRS structure
            "moleculeContext": "genomic"
        }

        # Add HGVS expressions
        expressions = variant_descriptor["expressions"]

        # Add HGVS.g from VRS
        for expr in vrs_allele.get("expressions", []):
            if expr["syntax"] == "hgvs.g":
                expressions.append(expr)
                break

        # Add HGVS.c if available
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

        # Add HGVS.p if available
        if p_dot:
            expressions.append({
                "syntax": "hgvs.p",
                "value": f"NP_000449.3:{p_dot}"
            })

        # Add VCF notation
        expressions.append({
            "syntax": "vcf",
            "value": hg38
        })

        # Add SPDI notation from VRS
        for expr in vrs_allele.get("expressions", []):
            if expr["syntax"] == "spdi":
                expressions.append(expr)
                break

        # Add label with protein change if available
        if p_dot:
            variant_descriptor["label"] += f" ({p_dot})"

        return variant_descriptor


class CNVParser:
    """Parser for converting CNV data to GA4GH compliant format."""

    # Known dbVar IDs for HNF1B CNVs
    DBVAR_MAPPINGS = {
        "deletion": "dbVar:nssv1184554",  # Common HNF1B deletion
        "duplication": "dbVar:nssv1184555",  # Common HNF1B duplication
    }

    @staticmethod
    def parse_hg38_coordinates(hg38: str, hg38_info: str) -> Optional[Tuple[str, int, int, str]]:
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
            parts = hg38.replace(':', '-').split('-')
            if len(parts) < 4:
                return None

            chromosome = parts[0].replace('chr', '')  # Remove 'chr' prefix
            start = int(parts[1])

            # Parse END position and variant type from hg38_INFO
            end_match = re.search(r'END=(\d+)', hg38_info)
            if not end_match:
                return None
            end = int(end_match.group(1))

            # Determine variant type
            variant_type = None
            if 'SVTYPE=DEL' in hg38_info or '<DEL>' in hg38:
                variant_type = 'DEL'
            elif 'SVTYPE=DUP' in hg38_info or '<DUP>' in hg38:
                variant_type = 'DUP'
            elif 'SVTYPE=INV' in hg38_info:
                variant_type = 'INV'
            elif 'SVTYPE=INS' in hg38_info:
                variant_type = 'INS'

            return (chromosome, start, end, variant_type)

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse coordinates from hg38='{hg38}', hg38_info='{hg38_info}': {e}")
            return None

    @staticmethod
    def create_ga4gh_cnv_notation(chromosome: str, start: int, end: int, variant_type: str) -> str:
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
    def create_iscn_notation(chromosome: str, start: int, end: int, variant_type: str) -> Optional[str]:
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
        if variant_type == 'DEL':
            return f"del({chromosome})(q12)"  # HNF1B is at 17q12
        elif variant_type == 'DUP':
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
        if variant_type == 'DEL':
            return CNVParser.DBVAR_MAPPINGS.get("deletion")
        elif variant_type == 'DUP':
            return CNVParser.DBVAR_MAPPINGS.get("duplication")
        return None

    @classmethod
    def create_phenopacket_cnv_variant(cls, hg38: str, hg38_info: str,
                                      variant_type_str: str = None,
                                      variant_reported: str = None) -> Dict[str, Any]:
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
        ga4gh_notation = cls.create_ga4gh_cnv_notation(chromosome, start, end, variant_type)
        iscn_notation = cls.create_iscn_notation(chromosome, start, end, variant_type)
        dbvar_id = cls.get_dbvar_id(variant_type)

        # Calculate size
        size = end - start + 1
        size_mb = round(size / 1_000_000, 2)

        # Build variant descriptor
        variant_descriptor = {
            "id": f"var:HNF1B:{ga4gh_notation}",
            "label": f"HNF1B {variant_type} ({size_mb}Mb)",
            "structuralType": {
                "id": f"SO:{'0000159' if variant_type == 'DEL' else '1000035' if variant_type == 'DUP' else '0000667'}",
                "label": "deletion" if variant_type == "DEL" else "duplication" if variant_type == "DUP" else "insertion"
            },
            "geneContext": {
                "valueId": "HGNC:5024",
                "symbol": "HNF1B"
            },
            "expressions": [],
            "extensions": []
        }

        # Add expressions in various formats
        expressions = variant_descriptor["expressions"]

        # GA4GH CNV notation (primary)
        expressions.append({
            "syntax": "ga4gh",
            "value": ga4gh_notation
        })

        # Add VCF-style notation
        expressions.append({
            "syntax": "vcf",
            "value": hg38
        })

        # Add ISCN notation if available
        if iscn_notation:
            expressions.append({
                "syntax": "iscn",
                "value": iscn_notation
            })

        # Add human-readable description if provided
        if variant_reported:
            expressions.append({
                "syntax": "text",
                "value": variant_reported
            })

        # Add extensions with detailed information
        extensions = variant_descriptor["extensions"]

        # Add dbVar reference if available
        if dbvar_id:
            extensions.append({
                "name": "external_reference",
                "value": {
                    "id": dbvar_id,
                    "reference": "dbVar",
                    "description": "Database of Genomic Structural Variation"
                }
            })

        # Add precise coordinates
        extensions.append({
            "name": "coordinates",
            "value": {
                "assembly": "GRCh38/hg38",
                "chromosome": chromosome,
                "start": start,
                "end": end,
                "length": size
            }
        })

        # Check for explicit zygosity/copy number information in the variant description
        if variant_reported:
            reported_lower = variant_reported.lower()

            # Check for explicit zygosity mentions
            if "homozygous" in reported_lower:
                extensions.append({
                    "name": "zygosity",
                    "value": "homozygous"
                })
                # For homozygous deletion: 0 copies, homozygous duplication: 4 copies
                if variant_type == 'DEL':
                    extensions.append({
                        "name": "copy_number",
                        "value": {
                            "absolute_copy_number": 0,
                            "relative_copy_number": -2,
                            "evidence": "Explicitly stated as homozygous"
                        }
                    })
            elif "heterozygous" in reported_lower:
                extensions.append({
                    "name": "zygosity",
                    "value": "heterozygous"
                })
                # For heterozygous deletion: 1 copy, heterozygous duplication: 3 copies
                if variant_type == 'DEL':
                    extensions.append({
                        "name": "copy_number",
                        "value": {
                            "absolute_copy_number": 1,
                            "relative_copy_number": -1,
                            "evidence": "Explicitly stated as heterozygous"
                        }
                    })
                elif variant_type == 'DUP':
                    extensions.append({
                        "name": "copy_number",
                        "value": {
                            "absolute_copy_number": 3,
                            "relative_copy_number": 1,
                            "evidence": "Explicitly stated as heterozygous"
                        }
                    })
            # Check for explicit copy number mentions (e.g., "CN=0", "0 copies", "single copy")
            cn_match = re.search(r'CN[=:]?\s*(\d+)|(\d+)\s*cop(y|ies)', reported_lower)
            if cn_match:
                copy_num = int(cn_match.group(1) or cn_match.group(2))
                extensions.append({
                    "name": "copy_number",
                    "value": {
                        "absolute_copy_number": copy_num,
                        "relative_copy_number": copy_num - 2,  # Assuming normal is 2 copies
                        "evidence": f"Extracted from description: {cn_match.group(0)}"
                    }
                })

        return variant_descriptor

    @classmethod
    def parse_variant_for_phenopacket(cls, row_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse variant data from a spreadsheet row for phenopacket inclusion.

        Args:
            row_data: Dictionary containing row data from spreadsheet

        Returns:
            Phenopacket-ready variant interpretation or None
        """
        hg38 = row_data.get('hg38')
        hg38_info = row_data.get('hg38_INFO')
        variant_type = row_data.get('VariantType')
        variant_reported = row_data.get('VariantReported')

        # Check if this is a CNV
        if not variant_type:
            return None

        variant_type_lower = variant_type.lower()
        is_cnv = any(term in variant_type_lower for term in ['delet', 'dup', 'cnv', 'copy'])

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
                    "id": "MONDO:0018874",
                    "label": "HNF1B-related disorder"
                },
                "genomicInterpretations": [
                    {
                        "subjectOrBiosampleId": row_data.get('IndividualIdentifier', 'unknown'),
                        "interpretationStatus": "PATHOGENIC",  # CNVs are usually pathogenic
                        "variantInterpretation": {
                            "variationDescriptor": variant_descriptor
                        }
                    }
                ]
            }
        }

        return interpretation


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
            "chronic kidney disease": {
                "id": "HP:0012622",
                "label": "Chronic kidney disease",
            },
            "stage 1 chronic kidney disease": {
                "id": "HP:0012623",
                "label": "Stage 1 chronic kidney disease",
            },
            "stage 2 chronic kidney disease": {
                "id": "HP:0012624",
                "label": "Stage 2 chronic kidney disease",
            },
            "stage 3 chronic kidney disease": {
                "id": "HP:0012625",
                "label": "Stage 3 chronic kidney disease",
            },
            "stage 4 chronic kidney disease": {
                "id": "HP:0012626",
                "label": "Stage 4 chronic kidney disease",
            },
            "stage 5 chronic kidney disease": {
                "id": "HP:0003774",
                "label": "Stage 5 chronic kidney disease",
            },
            "renalcysts": {"id": "HP:0000107", "label": "Renal cyst"},
            "renalhypoplasia": {"id": "HP:0000089", "label": "Renal hypoplasia"},
            "solitarykidney": {
                "id": "HP:0004729",
                "label": "Solitary functioning kidney",
            },
            "multicysticdysplastickidney": {
                "id": "HP:0000003",
                "label": "Multicystic kidney dysplasia",
            },
            "hyperechogenicity": {
                "id": "HP:0010935",
                "label": "Increased echogenicity of kidneys",
            },
            "urinarytractmalformation": {
                "id": "HP:0000079",
                "label": "Abnormality of the urinary system",
            },
            "antenatalrenalabnormalities": {
                "id": "HP:0010945",
                "label": "Fetal renal anomaly",
            },
            "multiple glomerular cysts": {
                "id": "HP:0100611",
                "label": "Multiple glomerular cysts",
            },
            "oligomeganephronia": {"id": "HP:0004719", "label": "Oligomeganephronia"},
            # Metabolic phenotypes
            "hypomagnesemia": {"id": "HP:0002917", "label": "Hypomagnesemia"},
            "hyperuricemia": {"id": "HP:0002149", "label": "Hyperuricemia"},
            "gout": {"id": "HP:0001997", "label": "Gout"},
            "hypokalemia": {"id": "HP:0002900", "label": "Hypokalemia"},
            "hyperparathyroidism": {"id": "HP:0000843", "label": "Hyperparathyroidism"},
            # Diabetes/Pancreas
            "mody": {
                "id": "HP:0004904",
                "label": "Maturity-onset diabetes of the young",
            },
            "pancreatichypoplasia": {
                "id": "HP:0100575",
                "label": "Pancreatic hypoplasia",
            },
            "exocrinepancreaticinsufficiency": {
                "id": "HP:0001738",
                "label": "Exocrine pancreatic insufficiency",
            },
            # Liver
            "abnormalliverphysiology": {
                "id": "HP:0031865",
                "label": "Abnormal liver physiology",
            },  # More suitable term
            "elevatedhepatictransaminase": {
                "id": "HP:0002910",
                "label": "Elevated hepatic transaminase",
            },
            # Genital
            "genitaltractabnormality": {
                "id": "HP:0000078",
                "label": "Abnormality of the genital system",
            },
            # Developmental
            "neurodevelopmentaldisorder": {
                "id": "HP:0012759",
                "label": "Neurodevelopmental abnormality",
            },
            "mentaldisease": {
                "id": "HP:0000708",
                "label": "Behavioral abnormality",
            },  # More general term
            "dysmorphicfeatures": {
                "id": "HP:0001999",
                "label": "Abnormal facial shape",
            },
            "shortstature": {"id": "HP:0004322", "label": "Short stature"},
            "prematurebirth": {"id": "HP:0001622", "label": "Premature birth"},
            # Neurological
            "brainabnormality": {
                "id": "HP:0012443",
                "label": "Abnormality of brain morphology",
            },  # More inclusive term
            "seizures": {"id": "HP:0001250", "label": "Seizures"},
            # Other systems
            "eyeabnormality": {"id": "HP:0000478", "label": "Abnormality of the eye"},
            "congenitalcardiacanomalies": {
                "id": "HP:0001627",
                "label": "Abnormal heart morphology",
            },
            "musculoskeletalfeatures": {
                "id": "HP:0033127",
                "label": "Abnormality of the musculoskeletal system",
            },
        }

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

    def _csv_url(self, spreadsheet_id: str, gid: str) -> str:
        """Generate Google Sheets CSV export URL."""
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

    async def load_google_sheets(self) -> None:
        """Load all data from Google Sheets."""
        logger.info("Loading data from Google Sheets...")

        # Load individuals sheet (contains phenotypes and variants data)
        url = self._csv_url(SPREADSHEET_ID, GID_INDIVIDUALS)
        self.individuals_df = pd.read_csv(url)
        self.individuals_df = self.individuals_df.dropna(how="all")
        logger.info(f"Loaded {len(self.individuals_df)} rows from individuals sheet")
        logger.info(
            f"Columns: {list(self.individuals_df.columns)[:10]}..."
        )  # Log first 10 columns

        # Load publications (optional)
        try:
            url = self._csv_url(SPREADSHEET_ID, GID_PUBLICATIONS)
            self.publications_df = pd.read_csv(url)
            self.publications_df = self.publications_df.dropna(how="all")
            logger.info(
                f"Loaded {len(self.publications_df)} rows from publications sheet"
            )
        except Exception as e:
            logger.warning(f"Could not load publications sheet: {e}")
            self.publications_df = pd.DataFrame()

        # Load reviewers (optional)
        try:
            url = self._csv_url(SPREADSHEET_ID, GID_REVIEWERS)
            self.reviewers_df = pd.read_csv(url)
            self.reviewers_df = self.reviewers_df.dropna(how="all")
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
                match = re.search(r"(\d+)", str(age_str))
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
                        "type": {"id": hpo_info["id"], "label": hpo_info["label"]},
                        "excluded": excluded,
                    }

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

    def _extract_variants(self, row: pd.Series) -> List[Dict[str, Any]]:
        """Extract variant information from row, prioritizing Varsome data."""
        interpretations = []

        # Get all variant-related columns
        varsome = self._safe_value(row.get("Varsome"))
        variant_reported = self._safe_value(row.get("VariantReported"))
        hg38 = self._safe_value(row.get("hg38"))
        hg38_info = self._safe_value(row.get("hg38_INFO"))
        verdict = self._safe_value(row.get("verdict_classification"))
        variant_type = self._safe_value(row.get("VariantType"))
        segregation = self._safe_value(row.get("Segregation"))

        # Check if this is a CNV (deletion/duplication)
        is_cnv = False
        if variant_type:
            type_lower = variant_type.lower()
            is_cnv = any(term in type_lower for term in ['delet', 'dup', 'cnv', 'copy'])

        # Handle CNVs using the new parser
        if is_cnv and hg38 and hg38_info:
            cnv_interpretation = CNVParser.parse_variant_for_phenopacket({
                'hg38': hg38,
                'hg38_INFO': hg38_info,
                'VariantType': variant_type,
                'VariantReported': variant_reported,
                'IndividualIdentifier': row.get("IndividualIdentifier", row.get("individual_id", "unknown"))
            })

            if cnv_interpretation:
                # Add segregation information if available
                if segregation:
                    seg_lower = segregation.lower()
                    if "de novo" in seg_lower or "inherited" in seg_lower:
                        cnv_interpretation["diagnosis"]["genomicInterpretations"][0][
                            "variantInterpretation"
                        ]["variationDescriptor"]["allelicState"] = {
                            "id": "GENO:0000135",
                            "label": "heterozygous"
                        }

                # Add pathogenicity classification if available
                if verdict:
                    # Map verdict to interpretation status
                    verdict_lower = verdict.lower()
                    if "pathogenic" in verdict_lower:
                        if "likely" in verdict_lower:
                            status = "LIKELY_PATHOGENIC"
                        else:
                            status = "PATHOGENIC"
                    elif "benign" in verdict_lower:
                        if "likely" in verdict_lower:
                            status = "LIKELY_BENIGN"
                        else:
                            status = "BENIGN"
                    else:
                        status = "UNCERTAIN_SIGNIFICANCE"

                    cnv_interpretation["diagnosis"]["genomicInterpretations"][0][
                        "interpretationStatus"
                    ] = status

                interpretations.append(cnv_interpretation)
                return interpretations  # Return early for CNVs

        # Handle SNVs and other non-CNV variants (existing code)
        # Initialize variant components
        c_dot = None
        p_dot = None
        transcript = None

        # PRIORITY 1: Parse Varsome (GA4GH compliant format)
        if varsome:
            # Example: HNF1B(NM_000458.4):c.406C>G (p.Gln136Glu)
            import re

            # Extract transcript
            transcript_match = re.search(r"NM_\d+\.\d+", varsome)
            if transcript_match:
                transcript = transcript_match.group()

            # Extract c.dot notation
            c_dot_match = re.search(r"c\.[^\s\)]+", varsome)
            if c_dot_match:
                c_dot = c_dot_match.group()

            # Extract p.dot notation
            p_dot_match = re.search(r"p\.[^\)]+", varsome)
            if p_dot_match:
                p_dot = p_dot_match.group()

        # PRIORITY 2: Parse VariantReported if Varsome didn't provide everything
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

        # Only create interpretation if we have meaningful variant data
        if c_dot or hg38 or varsome:
            # Try to create VRS 2.0 compliant variant if we have genomic coordinates
            variant_descriptor = None
            if hg38 and not (hg38.startswith('<') or '<' in hg38):
                # Try VRS format for SNVs/Indels (not structural variants)
                variant_descriptor = VRSBuilder.create_vrs_snv_variant(
                    hg38, c_dot, p_dot, transcript
                )

            # Fallback to original format if VRS creation fails
            if not variant_descriptor:
                # Create variant label
                variant_label = f"HNF1B:{c_dot if c_dot else 'variant'}"
                if p_dot:
                    variant_label += f" ({p_dot})"

                variant_descriptor = {
                    "id": f"var:HNF1B:{c_dot if c_dot else hg38 if hg38 else 'unknown'}",
                    "label": variant_label,
                    "geneContext": {
                        "valueId": "HGNC:5024",
                        "symbol": "HNF1B",
                    },
                    "expressions": [],
                    "moleculeContext": "genomic",
                }

            # Determine variant type and add molecular consequence
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
            elif hg38 and "<DEL>" in hg38:
                molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
            elif hg38 and "<DUP>" in hg38:
                molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
            elif c_dot:
                if "del" in c_dot:
                    molecular_consequence = {"id": "SO:0000159", "label": "deletion"}
                elif "dup" in c_dot:
                    molecular_consequence = {"id": "SO:1000035", "label": "duplication"}
                elif "ins" in c_dot:
                    molecular_consequence = {"id": "SO:0000667", "label": "insertion"}
                elif ">" in c_dot:
                    molecular_consequence = {"id": "SO:0001483", "label": "SNV"}

            # Add molecular consequence to variant descriptor
            if molecular_consequence:
                variant_descriptor["molecularConsequences"] = [molecular_consequence]

            # Create unique interpretation ID
            interpretation_id = f"interpretation-{len(interpretations)+1:03d}"

            interpretation = {
                "id": interpretation_id,
                "progressStatus": "COMPLETED",
                "diagnosis": {
                    "disease": self.mondo_mappings["hnf1b"],
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": row.get(
                                "IndividualIdentifier",
                                row.get("individual_id", "unknown"),
                            ),
                            "interpretationStatus": "UNCERTAIN_SIGNIFICANCE",
                            "variantInterpretation": {
                                "variationDescriptor": variant_descriptor
                            },
                        }
                    ],
                },
            }

            # Add allelicState based on segregation
            if segregation:
                seg_lower = segregation.lower()
                if "de novo" in seg_lower or "inherited" in seg_lower:
                    interpretation["diagnosis"]["genomicInterpretations"][0][
                        "variantInterpretation"
                    ]["variationDescriptor"]["allelicState"] = {
                        "id": "GENO:0000135",
                        "label": "heterozygous",
                    }

            # Only add expressions if not already handled by VRS builder
            if not variant_descriptor.get("vrsAllele"):
                expressions = interpretation["diagnosis"]["genomicInterpretations"][0][
                    "variantInterpretation"
                ]["variationDescriptor"]["expressions"]

                # Add c. notation with proper transcript
                if c_dot:
                    if transcript:
                        expressions.append(
                            {"syntax": "hgvs.c", "value": f"{transcript}:{c_dot}"}
                        )
                    else:
                        expressions.append(
                            {"syntax": "hgvs.c", "value": f"NM_000458.4:{c_dot}"}
                        )

                # Add p. notation if available
                if p_dot:
                    expressions.append(
                        {"syntax": "hgvs.p", "value": f"NP_000449.3:{p_dot}"}
                    )

                # Add genomic position if available
                if hg38:
                    expressions.append({"syntax": "vcf", "value": hg38})

            # Map pathogenicity if available
            if verdict:
                path_map = {
                    "pathogenic": "PATHOGENIC",
                    "likely pathogenic": "LIKELY_PATHOGENIC",
                    "uncertain significance": "UNCERTAIN_SIGNIFICANCE",
                    "likely benign": "LIKELY_BENIGN",
                    "benign": "BENIGN",
                }
                verdict_lower = verdict.lower()
                for key, value in path_map.items():
                    if key in verdict_lower:
                        interpretation["diagnosis"]["genomicInterpretations"][0][
                            "interpretationStatus"
                        ] = value
                        break

            interpretations.append(interpretation)

        return interpretations

    def build_phenopacket(
        self, individual_id: str, rows: pd.DataFrame
    ) -> Dict[str, Any]:
        """Build a complete phenopacket from individual data rows."""
        # Get first row for basic demographics
        first_row = rows.iloc[0]

        # Extract IDs - use individual_id as primary, IndividualIdentifier as alternate
        individual_identifier = self._safe_value(first_row.get("IndividualIdentifier"))

        phenopacket_id = f"phenopacket-{individual_id}"

        # Build subject
        subject = {
            "id": individual_id,  # Use individual_id as primary ID
            "sex": self._map_sex(self._safe_value(first_row.get("Sex"))),
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
            disease_onset = {
                "ontologyClass": {"id": "HP:0003577", "label": "Congenital onset"}
            }

        diseases = [{"term": self.mondo_mappings["hnf1b"], "onset": disease_onset}]

        # Check for MODY in phenotypes
        mody_col = next((col for col in first_row.index if "mody" in col.lower()), None)
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

        # Add publication references if available
        pub_col = next(
            (col for col in first_row.index if "publication" in col.lower()), None
        )
        if pub_col:
            pub_val = self._safe_value(first_row[pub_col])
            if pub_val:
                metadata["externalReferences"] = [
                    {
                        "id": f"PUB:{pub_val}",
                        "description": f"Publication reference: {pub_val}",
                    }
                ]

        # Build complete phenopacket
        phenopacket = {
            "id": phenopacket_id,
            "subject": subject,
            "phenotypicFeatures": all_phenotypes,
            "diseases": diseases,
            "metaData": metadata,
        }

        # Add interpretations if present
        if all_interpretations:
            phenopacket["interpretations"] = all_interpretations

        return self._clean_empty_fields(phenopacket)

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

    async def migrate(
        self,
        limit: Optional[int] = None,
        test_mode: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Execute the complete migration."""
        try:
            # Load all data from Google Sheets
            await self.load_google_sheets()

            # Normalize column names
            self.individuals_df.columns = [
                col.strip() for col in self.individuals_df.columns
            ]

            # Group rows by individual_id (correct column name from logs)
            individual_groups = self.individuals_df.groupby(
                "individual_id", dropna=False
            )

            phenopackets = []
            individual_count = 0

            logger.info(f"Processing {len(individual_groups)} individuals...")

            for individual_id, group_df in tqdm(
                individual_groups, desc="Building phenopackets"
            ):
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
                with open(output_file, "w") as f:
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
                    subject_sex = phenopacket.get("subject", {}).get(
                        "sex", "UNKNOWN_SEX"
                    )

                    # Insert phenopacket (subject_id and subject_sex are generated columns)
                    query = text("""
                        INSERT INTO phenopackets
                        (phenopacket_id, phenopacket, created_by, schema_version)
                        VALUES (:phenopacket_id, :phenopacket, :created_by, :schema_version)
                        ON CONFLICT (phenopacket_id) DO UPDATE
                        SET phenopacket = EXCLUDED.phenopacket,
                            updated_at = CURRENT_TIMESTAMP
                    """)

                    await session.execute(
                        query,
                        {
                            "phenopacket_id": phenopacket["id"],
                            "phenopacket": json.dumps(phenopacket),
                            "created_by": "direct_sheets_migration",
                            "schema_version": "2.0.0",
                        },
                    )

                    stored_count += 1

                except Exception as e:
                    logger.error(
                        f"Error storing phenopacket {phenopacket.get('id')}: {e}"
                    )
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

        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total phenopackets created: {total}")
        logger.info(
            f"With phenotypic features: {with_phenotypes} ({with_phenotypes*100//total if total else 0}%)"
        )
        logger.info(
            f"With genetic variants: {with_variants} ({with_variants*100//total if total else 0}%)"
        )
        logger.info(
            f"With disease diagnoses: {with_diseases} ({with_diseases*100//total if total else 0}%)"
        )
        logger.info(f"Sex distribution: {sex_distribution}")
        logger.info("=" * 60)


async def main():
    """Run the direct migration."""
    # Get database URL from environment
    target_db = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
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
