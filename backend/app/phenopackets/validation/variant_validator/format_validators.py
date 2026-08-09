"""Pure-function format validators for variant notation.

Extracted during Wave 4 from the monolithic
``variant_validator.py``. Nothing in this module touches the
network, async, or I/O — these functions are pure regex checks.

All validators return ``True`` when the input matches the expected
format for that notation family. Callers compose them via
``fallback_validation``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------- HGVS

# A transcript-relative position, optionally offset into an intron
# (e.g. ``544``, ``544+3``, ``544-6``). Reused by the del/dup/ins/delins
# patterns below so a single position group covers both exonic and
# intronic variants — HGVS itself makes no distinction between the two
# for these operators.
_HGVS_C_POS = r"\d+[+\-]?\d*"

_HGVS_C_PATTERNS = [
    # Substitution: c.544+1G>A (allows +/- offset)
    r"^(NM_\d+\.\d+:)?c\.([+\-*]?\d+[+\-]?\d*)([ATCG]>[ATCG])$",
    rf"^(NM_\d+\.\d+:)?c\.{_HGVS_C_POS}(_{_HGVS_C_POS})?del([ATCG]+)?$",  # Deletion
    rf"^(NM_\d+\.\d+:)?c\.{_HGVS_C_POS}(_{_HGVS_C_POS})?dup([ATCG]+)?$",  # Duplication
    rf"^(NM_\d+\.\d+:)?c\.{_HGVS_C_POS}(_{_HGVS_C_POS})?ins([ATCG]+)$",  # Insertion
    r"^(NM_\d+\.\d+:)?c\.\d+[+\-]\d+[ATCG]>[ATCG]$",  # Intronic substitution
    # Deletion-insertion with literal deleted/inserted sequences, single
    # position or range (e.g. ``c.1149delAinsTGGCC``,
    # ``c.499_504delGCTCTGinsCCCCT`` — 2 corpus instances).
    rf"^(NM_\d+\.\d+:)?c\.{_HGVS_C_POS}(_{_HGVS_C_POS})?del([ATCG]*)ins([ATCG]+)$",
]


def validate_hgvs_c(value: str) -> bool:
    """Validate HGVS c. notation.

    Examples: ``NM_000458.4:c.544+1G>A``, ``c.1234A>T``, ``c.123_456del``,
    ``c.544+3_544+6del`` (intronic range), ``c.499_504delGCTCTGinsCCCCT``.
    """
    return any(bool(re.match(pattern, value)) for pattern in _HGVS_C_PATTERNS)


# A three-letter amino-acid code, e.g. ``Arg``, ``Leu``, or the
# syntactically-identical-looking ``Ter`` (stop).
_AA3 = r"[A-Z][a-z]{2}"

_HGVS_P_PATTERNS = [
    # Frameshift, with an optional ``Ter##`` new-stop-codon position
    # (e.g. ``p.Pro328LeufsTer48`` — 83 corpus instances) alongside the
    # bare ``fs`` form.
    rf"^(NP_\d+\.\d+:)?p\.{_AA3}\d+{_AA3}fs(Ter\d+)?$",
    rf"^(NP_\d+\.\d+:)?p\.{_AA3}\d+\*$",  # Nonsense
    rf"^(NP_\d+\.\d+:)?p\.{_AA3}\d+{_AA3}$",  # Missense
    r"^(NP_\d+\.\d+:)?p\.\?$",  # Unknown effect
    # In-frame deletion, single residue (e.g. ``p.Gly239del``) or a range,
    # the range form optionally a delins (e.g. ``p.Arg137_Lys161del``,
    # ``p.Ala373_Gln383delinsGlu``).
    rf"^(NP_\d+\.\d+:)?p\.{_AA3}\d+del$",
    rf"^(NP_\d+\.\d+:)?p\.{_AA3}\d+_{_AA3}\d+del(ins(?:{_AA3})+)?$",
]


def validate_hgvs_p(value: str) -> bool:
    """Validate HGVS p. notation.

    Examples: ``NP_000449.3:p.Arg181*``, ``p.Val123Phe``,
    ``p.Pro328LeufsTer48``, ``p.Arg137_Lys161del``.
    """
    return any(bool(re.match(pattern, value)) for pattern in _HGVS_P_PATTERNS)


_HGVS_G_PATTERNS = [
    r"^NC_\d+\.\d+:g\.\d+[ATCG]>[ATCG]$",  # Substitution
    r"^NC_\d+\.\d+:g\.\d+(_\d+)?del([ATCG]+)?$",  # Deletion
    r"^NC_\d+\.\d+:g\.\d+(_\d+)?dup([ATCG]+)?$",  # Duplication
    r"^NC_\d+\.\d+:g\.\d+(_\d+)?ins([ATCG]+)$",  # Insertion
    # Deletion-insertion, single position or range (e.g.
    # ``g.37710560_37710560delinsGGCCA``).
    r"^NC_\d+\.\d+:g\.\d+(_\d+)?del([ATCG]*)ins([ATCG]+)$",
]


def validate_hgvs_g(value: str) -> bool:
    """Validate HGVS g. notation.

    Examples: ``NC_000017.11:g.36459258A>G``,
    ``NC_000017.11:g.37731657del``,
    ``NC_000017.11:g.37739437_37739438insA``.
    """
    return any(bool(re.match(pattern, value)) for pattern in _HGVS_G_PATTERNS)


# ----------------------------------------------------------------------- VCF

_VCF_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-[ATCG]+-([ATCG]+|<[A-Z]+>)$"

# 5-field structural-variant form: chrom-start-END-ref-<SYMBOLIC ALT>. The
# extra numeric field is the CNV's end coordinate; the corpus only ever
# pairs it with a symbolic ALT (``<DEL>``/``<DUP>``), never a literal one.
_VCF_CNV_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M)-\d+-\d+-[ATCG]+-<[A-Z]+>$"


def validate_vcf(value: str) -> bool:
    """Validate VCF format.

    Examples: ``chr17-36459258-A-G``, ``17-36459258-A-G`` (4-field), and
    ``17-36459258-37832869-C-<DEL>`` (5-field CNV with an END coordinate
    and a symbolic ALT).
    """
    return bool(re.match(_VCF_PATTERN, value, re.IGNORECASE)) or bool(
        re.match(_VCF_CNV_PATTERN, value, re.IGNORECASE)
    )


_VCF_FORMAT_PATTERN = re.compile(r"^(chr)?[\dXYM]+-\d+-[ACGT]+-[ACGT]+$", re.IGNORECASE)


def is_vcf_format(variant: str) -> bool:
    """Check whether a variant is in VCF ``chr-pos-ref-alt`` format."""
    return bool(_VCF_FORMAT_PATTERN.match(variant))


def vcf_to_vep_format(vcf_variant: str) -> Optional[str]:
    """Convert a VCF variant to VEP POST format.

    Input:  ``17-36459258-A-G`` or ``chr17-36459258-A-G``
    Output: ``17 36459258 . A G . . .``
    """
    vcf_variant = vcf_variant.replace("chr", "").replace("Chr", "").replace("CHR", "")
    parts = vcf_variant.split("-")
    if len(parts) != 4:
        return None

    chrom, pos, ref, alt = parts
    if not pos.isdigit():
        return None

    return f"{chrom} {pos} . {ref} {alt} . . ."


# ---------------------------------------------------------------------- SPDI

# SPDI's third field ("Deleted") is defined by the spec as either the
# deleted *sequence* (``[ATCG]*``, empty for a pure insertion) or the
# deleted *length* as a non-negative integer — the corpus uses the numeric
# form exclusively (424 instances, e.g. ``NC_000017.11:37739585:1:C``).
_SPDI_PATTERN = r"^NC_\d+\.\d+:\d+:([ATCG]*|\d+):[ATCG]+$"


def validate_spdi(value: str) -> bool:
    """Validate SPDI notation.

    Examples: ``NC_000017.11:36459257:A:G`` (deleted sequence),
    ``NC_000017.11:37739585:1:C`` (deleted length).
    """
    return bool(re.match(_SPDI_PATTERN, value))


# ----------------------------------------------------------------- GA4GH CNV

_CNV_PATTERN = r"^([1-9]|1[0-9]|2[0-2]|X|Y):\d+-\d+:(DEL|DUP|INS|INV)$"


def is_ga4gh_cnv_notation(value: str) -> bool:
    """Check whether ``value`` matches GA4GH CNV notation.

    Examples: ``17:36459258-37832869:DEL``, ``17:36459258-37832869:DUP``.
    """
    return bool(re.match(_CNV_PATTERN, value))


# --------------------------------------------------------------- VRS allele


def validate_vrs_allele(vrs_allele: Dict[str, Any]) -> List[str]:
    """Validate VRS 2.0 allele structure.

    Returns a list of error strings; an empty list means the allele
    passes all structural checks.
    """
    errors: List[str] = []

    if vrs_allele.get("type") != "Allele":
        errors.append("VRS allele must have type 'Allele'")

    location = vrs_allele.get("location", {})
    if not location:
        errors.append("VRS allele missing 'location' field")
    elif location.get("type") != "SequenceLocation":
        errors.append("VRS location must have type 'SequenceLocation'")

    state = vrs_allele.get("state", {})
    if not state:
        errors.append("VRS allele missing 'state' field")
    elif state.get("type") not in [
        "LiteralSequenceExpression",
        "ReferenceLengthExpression",
    ]:
        errors.append(
            "VRS state must be LiteralSequenceExpression or ReferenceLengthExpression"
        )

    return errors


# ----------------------------------------------------------------- combined


def fallback_validation(notation: str) -> bool:
    """Fallback validation when VEP is unavailable.

    Accepts the notation if it matches any of the regex validators
    above. Deliberately permissive — the caller will follow up with
    a VEP round-trip when possible.
    """
    return (
        validate_hgvs_c(notation)
        or validate_hgvs_p(notation)
        or validate_hgvs_g(notation)
        or validate_vcf(notation)
        or is_ga4gh_cnv_notation(notation)
    )
