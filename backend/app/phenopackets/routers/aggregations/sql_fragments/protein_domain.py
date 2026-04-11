"""HNF1B protein-domain classification SQL helpers.

Extracted during Wave 4 from ``aggregations/sql_fragments.py``. Used
by the protein-domain survival analysis handler to bucket missense
variants into the three functional domains of HNF1B (POU-S, POU-H,
TAD) based on amino-acid position parsed from the HGVS.p notation.

Reference: UniProt P35680, doi:10.3390/ijms251910609.
"""

from __future__ import annotations

from .paths import VD_ID

# =============================================================================
# Protein Domain Constants (HNF1B)
# =============================================================================

# HNF1B protein domain boundaries (amino acid positions).
# Based on UniProt P35680 and published literature.
HNF1B_PROTEIN_DOMAINS: dict[str, dict[str, int | str]] = {
    "POU-S": {
        "start": 90,
        "end": 173,
        "label": "POU-S (DNA Binding 1)",
        "description": "POU-specific domain for DNA binding",
    },
    "POU-H": {
        "start": 232,
        "end": 305,
        "label": "POU-H (DNA Binding 2)",
        "description": "POU-homeodomain for DNA binding",
    },
    "TAD": {
        "start": 314,
        "end": 557,
        "label": "TAD (Transactivation)",
        "description": "C-terminal transactivation domain for coactivator recruitment",
    },
}

# Regex pattern for missense variants in HGVS.p notation.
# Matches: p.Arg177Cys, p.Met1Val, p.Gly400Ser, etc.
# Excludes: p.Arg177Ter (nonsense), p.Arg177fs (frameshift), p.Arg177* (stop).
# Note: uses a negative lookahead ``(?!Ter)`` to exclude termination codons.
MISSENSE_HGVS_P_PATTERN = r"^p\.[A-Z][a-z]{2}\d+(?!Ter)[A-Z][a-z]{2}$"

# Regex pattern for extracting amino acid position from HGVS.p.
# Captures the numeric position: p.Arg177Cys -> 177.
AMINO_ACID_POSITION_PATTERN = r"p\.[A-Z][a-z]{2}(\d+)"


def get_missense_filter_sql(vd_path: str = "vd") -> str:
    r"""Generate a SQL filter matching missense variants only.

    Filters to variants with HGVS.p notation matching the missense
    pattern, excluding truncating variants (nonsense, frameshift,
    stop-gained).

    PostgreSQL regex does not support lookahead, so we use ``AND NOT``
    to exclude nonsense variants ending in ``Ter``. The pattern does
    not anchor at the start so the ``NP_xxx:p.Xxx123Yyy`` form is
    accepted.
    """
    return f"""EXISTS (
        SELECT 1
        FROM jsonb_array_elements({vd_path}->'expressions') elem
        WHERE elem->>'syntax' = 'hgvs.p'
        AND elem->>'value' ~ 'p\\.[A-Z][a-z]{{2}}\\d+[A-Z][a-z]{{2}}$'
        AND elem->>'value' !~ 'Ter$'
    )"""


def get_amino_acid_position_sql(vd_path: str = "vd") -> str:
    r"""Generate SQL that extracts the amino-acid position from HGVS.p.

    Extracts the numeric position from patterns like ``p.Arg177Cys``
    → ``177``.
    """
    return f"""(regexp_match(
        (SELECT elem->>'value'
         FROM jsonb_array_elements({vd_path}->'expressions') elem
         WHERE elem->>'syntax' = 'hgvs.p'
         LIMIT 1),
        'p\\.[A-Z][a-z]{{2}}(\\d+)'
    ))[1]::int"""


def get_protein_domain_classification_sql(vd_path: str = "vd") -> str:
    """Generate a CASE expression bucketing missense variants by domain.

    Classifies missense variants into HNF1B protein domains based on
    the amino-acid position extracted from HGVS.p notation:

    - **POU-S**: aa 90-173 (DNA binding domain 1)
    - **POU-H**: aa 232-305 (DNA binding domain 2)
    - **TAD**:   aa 314-557 (Transactivation domain)
    - **Other**: outside defined domains, or position extraction failed
    """
    pos_sql = get_amino_acid_position_sql(vd_path)
    pou_s = HNF1B_PROTEIN_DOMAINS["POU-S"]
    pou_h = HNF1B_PROTEIN_DOMAINS["POU-H"]
    tad = HNF1B_PROTEIN_DOMAINS["TAD"]

    return f"""CASE
    WHEN {pos_sql} BETWEEN {pou_s["start"]} AND {pou_s["end"]} THEN 'POU-S'
    WHEN {pos_sql} BETWEEN {pou_h["start"]} AND {pou_h["end"]} THEN 'POU-H'
    WHEN {pos_sql} BETWEEN {tad["start"]} AND {tad["end"]} THEN 'TAD'
    ELSE 'Other'
END"""


def get_cnv_exclusion_filter() -> str:
    """Generate a SQL filter that excludes CNV/large-deletion variants.

    CNVs and large deletions have no amino-acid position and must be
    excluded from the protein-domain analysis upstream of the
    classification CASE.
    """
    return f"NOT {VD_ID} ~ ':(DEL|DUP)'"


def get_vcf_id_extraction_sql(
    vd_path: str = "gi->'variantInterpretation'->'variationDescriptor'",
) -> str:
    """Generate SQL extracting a normalised VCF id for the annotations JOIN.

    Pulls the first VCF expression value from a variationDescriptor
    and normalises it to the format stored in ``variant_annotations``:

    - strip ``chr`` prefix (case-insensitive)
    - convert ``:`` separators to ``-``
    - uppercase
    """
    return f"""UPPER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(
                (SELECT expr->>'value'
                 FROM jsonb_array_elements({vd_path}->'expressions') expr
                 WHERE expr->>'syntax' = 'vcf'
                 LIMIT 1),
                '^chr', '', 'i'
            ),
            ':',
            '-',
            'g'
        )
    )"""
