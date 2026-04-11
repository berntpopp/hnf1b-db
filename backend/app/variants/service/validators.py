"""Variant-id validation and VEP-format conversion helpers.

Pure regex functions extracted during Wave 4 from the monolithic
``variants/service.py``. None of these functions touches the network
or the database.

The two public entrypoints (``is_cnv_variant``, ``validate_variant_id``)
plus the private ``_format_variant_for_vep`` are re-exported at the
package level for the existing ``test_variant_service_cnv.py`` and
``test_cnv_annotation.py`` regression suites, which import them
directly from ``app.variants.service``.
"""

from __future__ import annotations

import re
from typing import Optional


def is_cnv_variant(variant_id: str) -> bool:
    """Check whether ``variant_id`` is a CNV / structural variant.

    CNV formats supported:

    - VCF-style symbolic allele: ``17-36459258-A-<DEL>``, ``17-36459258-A-<DUP>``
    - Region format: ``17-36459258-37832869-DEL``, ``17:36459258-37832869:DEL``
    """
    sv_types = r"(DEL|DUP|INS|INV|CNV)"
    cnv_pattern = rf"<{sv_types}>|-{sv_types}$|:{sv_types}$"
    return bool(re.search(cnv_pattern, variant_id, re.IGNORECASE))


def validate_variant_id(variant_id: str, allow_cnv: bool = True) -> str:
    """Validate and normalise a variant id.

    Security: prevents SQL injection by validating the format with a
    regex allow-list before the value is passed to any SQL query.

    Supports the following formats:

    1. SNV/indel: ``CHR-POS-REF-ALT`` (e.g., ``17-36459258-A-G``)
    2. CNV symbolic (4-part): ``CHR-POS-REF-<SV_TYPE>``
    3. CNV with END (5-part): ``CHR-POS-END-REF-<SV_TYPE>``
    4. CNV region: ``CHR-START-END-SV_TYPE``
    5. Internal CNV: ``var:GENE:CHROM:START-END:TYPE``

    Raises ``ValueError`` with an explanatory message if the format
    is not recognised. The router catches that and returns a 400.
    """
    # Pattern 5: Internal CNV format - var:GENE:CHROM:START-END:TYPE.
    # Checked first because it contains colons that would otherwise be
    # normalised out by the region branch below.
    internal_cnv_pattern = (
        r"^var:[A-Za-z0-9]+:[0-9XYM]+:\d+-\d+:(DEL|DUP|INS|INV|CNV)$"
    )
    if allow_cnv and re.match(internal_cnv_pattern, variant_id, re.IGNORECASE):
        return variant_id  # Keep as-is (case-sensitive gene names)

    normalized = re.sub(r"^chr", "", variant_id, flags=re.IGNORECASE)

    # Normalise colon separators to dashes for region format.
    # e.g., 17:36459258-37832869:DEL -> 17-36459258-37832869-DEL
    if ":" in normalized and "-" in normalized:
        normalized = normalized.replace(":", "-")

    snv_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-[ACGT]+$"
    cnv_symbolic_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    cnv_with_end_pattern = r"^[0-9XYM]+-\d+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    cnv_region_pattern = r"^[0-9XYM]+-\d+-\d+-(DEL|DUP|INS|INV|CNV)$"

    is_snv = bool(re.match(snv_pattern, normalized, re.IGNORECASE))
    is_cnv_symbolic = bool(re.match(cnv_symbolic_pattern, normalized, re.IGNORECASE))
    is_cnv_with_end = bool(re.match(cnv_with_end_pattern, normalized, re.IGNORECASE))
    is_cnv_region = bool(re.match(cnv_region_pattern, normalized, re.IGNORECASE))

    if is_snv:
        return normalized.upper()

    if allow_cnv and (is_cnv_symbolic or is_cnv_with_end or is_cnv_region):
        return normalized.upper()

    raise ValueError(
        f"Invalid variant format: {variant_id}. "
        "Expected: CHR-POS-REF-ALT (e.g., 17-36459258-A-G) or "
        "CHR-POS-END-REF-<TYPE> for CNVs (e.g., 17-36459258-37832869-C-<DEL>)"
    )


def _format_variant_for_vep(variant_id: str) -> Optional[str]:
    """Format a variant id for the Ensembl VEP POST API.

    Handles the same variant families as :func:`validate_variant_id`:

    - SNV/indel: converts ``CHR-POS-REF-ALT`` to VCF format
      ``CHROM POS ID REF ALT . . .``
    - CNV region: converts ``CHR-START-END-TYPE`` to VEP SV format
    - CNV symbolic (4-part): ``CHR-POS-REF-<TYPE>`` — uses ``POS`` for
      both start and end
    - CNV with END (5-part): ``CHR-POS-END-REF-<TYPE>`` — uses the
      declared coordinates
    - Internal CNV format: ``var:GENE:CHROM:START-END:TYPE``

    Returns ``None`` if the format is not recognised (the caller
    logs a warning and skips the variant).
    """
    internal_cnv_pattern = (
        r"^var:([A-Z0-9]+):([0-9XYM]+):(\d+)-(\d+):(DEL|DUP|INS|INV|CNV)$"
    )
    internal_match = re.match(internal_cnv_pattern, variant_id, re.IGNORECASE)
    if internal_match:
        _gene, chrom, start, end, sv_type = internal_match.groups()
        return f"{chrom} {start} {end} {sv_type.upper()} + {variant_id}"

    parts = variant_id.split("-")

    # 5-part CNV with END position: CHR-POS-END-REF-<TYPE>
    cnv_with_end_pattern = r"^[0-9XYM]+-\d+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    if re.match(cnv_with_end_pattern, variant_id, re.IGNORECASE):
        chrom, start, end, _ref, alt = parts
        sv_type = alt.strip("<>").upper()
        return f"{chrom} {start} {end} {sv_type} + {variant_id}"

    # CNV region format: CHR-START-END-TYPE
    cnv_region_pattern = r"^[0-9XYM]+-\d+-\d+-(DEL|DUP|INS|INV|CNV)$"
    if re.match(cnv_region_pattern, variant_id, re.IGNORECASE):
        chrom, start, end, sv_type = parts
        return f"{chrom} {start} {end} {sv_type.upper()} + {variant_id}"

    # 4-part CNV symbolic: CHR-POS-REF-<TYPE>
    cnv_symbolic_pattern = r"^[0-9XYM]+-\d+-[ACGT]+-<(DEL|DUP|INS|INV|CNV)>$"
    if re.match(cnv_symbolic_pattern, variant_id, re.IGNORECASE):
        chrom, pos, _ref, alt = parts
        sv_type = alt.strip("<>").upper()
        # For symbolic alleles without END, use the same start/end;
        # VEP interprets the SV type.
        return f"{chrom} {pos} {pos} {sv_type} + {variant_id}"

    # Standard SNV/indel format: CHR-POS-REF-ALT
    if len(parts) == 4:
        chrom, pos, ref, alt = parts
        return f"{chrom} {pos} {variant_id} {ref} {alt} . . ."

    return None
