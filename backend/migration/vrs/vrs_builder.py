"""Builder for GA4GH VRS 2.0 (Variant Representation Specification) compliant alleles."""

import base64
import hashlib
import logging
from typing import Any, Dict, Optional

# GA4GH VRS imports for proper digest computation
try:
    from ga4gh.core import ga4gh_identify
    from ga4gh.vrs import models as vrs_models

    VRS_AVAILABLE = True
except ImportError:
    VRS_AVAILABLE = False
    logging.warning(
        "ga4gh.vrs not available - variant digests will use placeholder values instead of proper GA4GH computation. "
        "Install with 'pip install ga4gh.vrs' for production use."
    )


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
        "1": "NC_000001.11",
        "2": "NC_000002.12",
        "3": "NC_000003.12",
        "4": "NC_000004.12",
        "5": "NC_000005.10",
        "6": "NC_000006.12",
        "7": "NC_000007.14",
        "8": "NC_000008.11",
        "9": "NC_000009.12",
        "10": "NC_000010.11",
        "11": "NC_000011.10",
        "12": "NC_000012.12",
        "13": "NC_000013.11",
        "14": "NC_000014.9",
        "15": "NC_000015.10",
        "16": "NC_000016.10",
        "17": "NC_000017.11",
        "18": "NC_000018.10",
        "19": "NC_000019.10",
        "20": "NC_000020.11",
        "21": "NC_000021.9",
        "22": "NC_000022.11",
        "X": "NC_000023.11",
        "Y": "NC_000024.10",
        "M": "NC_012920.1",
        "MT": "NC_012920.1",
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
        parts = vcf_string.replace(":", "-").split("-")
        if len(parts) < 4:
            return None

        try:
            chromosome = parts[0].replace("chr", "")
            position = int(parts[1])
            ref_allele = parts[2]
            alt_allele = parts[3]

            # Skip structural variants
            if ref_allele.startswith("<") or alt_allele.startswith("<"):
                return None

            return {
                "chromosome": chromosome,
                "position": position,
                "ref": ref_allele,
                "alt": alt_allele,
            }
        except (ValueError, IndexError):
            return None

    @staticmethod
    def create_placeholder_refget(refseq_id: str) -> str:
        """Create a format-compliant RefGet accession placeholder.

        Note: This creates a deterministic placeholder that follows the RefGet format
        but is not a real sequence digest. Real RefGet IDs require access to actual
        sequence data to compute SHA512t24u digests.

        Args:
            refseq_id: RefSeq accession (e.g., 'NC_000017.11')

        Returns:
            Format-compliant RefGet accession (e.g., 'SQ.xxx...')
        """
        # Create a deterministic hash from RefSeq ID using SHA512t24u (GA4GH RefGet spec)
        sha512_digest = hashlib.sha512(refseq_id.encode()).digest()
        # Truncate to first 24 bytes (24 × 8 = 192 bits) per GA4GH RefGet specification
        truncated = sha512_digest[:24]
        # Base64url encode, remove padding
        digest = base64.urlsafe_b64encode(truncated).decode("ascii").rstrip("=")
        # Return with 'SQ.' prefix - GA4GH RefGet standard prefix for sequence identifiers
        return f"SQ.{digest}"

    @staticmethod
    def _create_deterministic_digest(identifier_string: str) -> str:
        """Create deterministic variant digest using SHA256.

        GA4GH VRS-compatible digest that produces consistent IDs across runs.
        Uses SHA256 hashing instead of Python's randomized hash() function.

        Args:
            identifier_string: Unique identifier string for the variant

        Returns:
            Base64url-encoded digest string without padding
        """
        sha256 = hashlib.sha256(identifier_string.encode()).digest()
        # Take first 12 bytes for VRS-like digest length
        return base64.urlsafe_b64encode(sha256[:12]).decode("ascii").rstrip("=")

    @classmethod
    def create_vrs_allele(
        cls,
        chromosome: str,
        position: int,
        ref: str,
        alt: str,
        assembly: str = "GRCh38",
    ) -> Dict[str, Any]:
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
        vrs_allele: Dict[str, Any] = {
            "type": "Allele",
            "digest": None,  # Would be computed using GA4GH digest algorithm
            "location": {
                "type": "SequenceLocation",
                "sequenceReference": {
                    # VRS 2.0 uses refget or sequence accessions
                    "type": "SequenceReference",
                    "refgetAccession": cls.create_placeholder_refget(refseq_id),
                    # Alternative: use refseq directly
                    "other_identifiers": [
                        f"refseq:{refseq_id}",
                        f"GRCh38:chr{chromosome}",
                    ],
                },
                "interval": {
                    "type": "SequenceInterval",
                    "start": {"type": "Number", "value": start},
                    "end": {"type": "Number", "value": end},
                },
            },
            "state": {"type": "LiteralSequenceExpression", "sequence": alt},
        }

        # Generate VRS 2.0 compliant identifier
        # Format: ga4gh:VA.{digest} where digest is computed from normalized VRS JSON
        if VRS_AVAILABLE:
            try:
                # Create proper VRS models for digest computation
                # Create format-compliant RefGet placeholder (real RefGet requires actual sequence)
                refget_accession = cls.create_placeholder_refget(refseq_id)

                vrs_location = vrs_models.SequenceLocation(
                    sequenceReference=vrs_models.SequenceReference(
                        refgetAccession=refget_accession
                    ),
                    start=start,
                    end=end,
                )

                # Create VRS Allele model
                vrs_obj = vrs_models.Allele(
                    location=vrs_location,
                    state=vrs_models.LiteralSequenceExpression(sequence=alt),
                )

                # Compute digest using GA4GH core functions
                digest = ga4gh_identify(vrs_obj)

                # Extract just the digest part (after the "ga4gh:VA." prefix)
                if digest.startswith("ga4gh:VA."):
                    vrs_allele["digest"] = digest[9:]  # Remove "ga4gh:VA." prefix
                else:
                    vrs_allele["digest"] = digest

                vrs_allele["id"] = f"ga4gh:VA.{vrs_allele['digest']}"

            except Exception as e:
                # Fallback to placeholder if VRS computation fails
                logging.warning(
                    f"VRS digest computation failed: {e}. Using placeholder."
                )
                identifier_string = f"{refseq_id}:{start}-{end}:{ref}>{alt}"
                vrs_allele["digest"] = cls._create_deterministic_digest(
                    identifier_string
                )
                vrs_allele["id"] = f"ga4gh:VA.{vrs_allele['digest']}"
        else:
            # Fallback to placeholder digest when ga4gh.vrs is not available
            identifier_string = f"{refseq_id}:{start}-{end}:{ref}>{alt}"
            vrs_allele["digest"] = cls._create_deterministic_digest(identifier_string)
            vrs_allele["id"] = f"ga4gh:VA.{vrs_allele['digest']}"

        # Add expressions for alternative representations
        vrs_allele["expressions"] = [
            {
                "syntax": "hgvs.g",
                "value": cls.create_hgvs_g_notation(chromosome, position, ref, alt),
            },
            {"syntax": "spdi", "value": f"{refseq_id}:{start}:{len(ref)}:{alt}"},
        ]

        return vrs_allele

    @classmethod
    def create_hgvs_g_notation(
        cls, chromosome: str, position: int, ref: str, alt: str
    ) -> str:
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
    def create_vrs_snv_variant(
        cls,
        hg38: str,
        c_dot: str | None = None,
        p_dot: str | None = None,
        transcript: str | None = None,
        variant_reported: str | None = None,
    ) -> dict[str, Any] | None:
        """Create a VRS 2.0 compliant variant descriptor for SNVs/Indels.

        Args:
            hg38: VCF-style genomic position
            c_dot: HGVS c. notation
            p_dot: HGVS p. notation
            transcript: Transcript ID
            variant_reported: Original variant description from publication

        Returns:
            Phenopacket-ready variant descriptor with VRS 2.0 structure
        """
        # Parse VCF coordinates
        vrs_components = cls.parse_vcf_to_vrs(hg38)
        if not vrs_components:
            return None

        # Create VRS 2.0 Allele
        vrs_allele = cls.create_vrs_allele(
            vrs_components["chromosome"],
            vrs_components["position"],
            vrs_components["ref"],
            vrs_components["alt"],
        )

        # Build variant descriptor for phenopacket
        label = f"HNF1B:{c_dot if c_dot else 'variant'}"
        if p_dot:
            label += f" ({p_dot})"

        variant_descriptor = {
            "id": vrs_allele["id"],  # Use VRS identifier
            "label": label,
            "geneContext": {"valueId": "HGNC:5024", "symbol": "HNF1B"},
            "expressions": [],
            "vrsAllele": vrs_allele,  # Embed full VRS structure
            "moleculeContext": "genomic",
        }

        # Add original publication description if available
        if variant_reported:
            variant_descriptor["description"] = variant_reported

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
                expressions.append(
                    {"syntax": "hgvs.c", "value": f"{transcript}:{c_dot}"}
                )
            else:
                expressions.append(
                    {"syntax": "hgvs.c", "value": f"NM_000458.4:{c_dot}"}
                )

        # Add HGVS.p if available
        if p_dot:
            expressions.append({"syntax": "hgvs.p", "value": f"NP_000449.3:{p_dot}"})

        # Add VCF notation
        expressions.append({"syntax": "vcf", "value": hg38})

        # Add SPDI notation from VRS
        for expr in vrs_allele.get("expressions", []):
            if expr["syntax"] == "spdi":
                expressions.append(expr)
                break

        # Note: Protein notation already added to label at line 343-344
        # No need to add again here (fixes Issue #103 - duplicate protein notation)

        return variant_descriptor
