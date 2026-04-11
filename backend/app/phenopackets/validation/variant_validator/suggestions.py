"""Notation suggestion helper for the variant validator.

When a user hands us an invalid variant notation, we try to produce
three kinds of suggestion:

1. Exact-fix patches (missing transcript prefix, missing dot,
   coordinate-to-VCF conversion).
2. Fuzzy matches against a small library of known-valid examples.
3. A generic "here are the valid formats" fallback if nothing else
   applies.

Extracted during Wave 4 from ``variant_validator.py``.
"""

from __future__ import annotations

import re
from difflib import get_close_matches
from typing import List

COMMON_PATTERNS = [
    "NM_000458.4:c.544+1G>A",
    "NM_000458.4:c.1234A>T",
    "NM_000458.4:c.123del",
    "NM_000458.4:c.123_456dup",
    "chr17:g.36459258A>G",
    "17:36459258-37832869:DEL",
]


def get_notation_suggestions(invalid_notation: str) -> List[str]:
    """Generate suggestions for fixing an invalid variant notation."""
    suggestions: List[str] = []

    if "c." in invalid_notation or "p." in invalid_notation:
        if not invalid_notation.startswith("NM_"):
            suggestions.append(
                "Did you mean to include a transcript? Try: NM_000458.4:"
                + invalid_notation
            )

        if re.match(r"^c\d+", invalid_notation) or re.match(
            r"^p[A-Z]", invalid_notation
        ):
            suggestions.append(
                f"Missing dot notation. Did you mean: "
                f"{invalid_notation[0]}.{invalid_notation[1:]}?"
            )

    if re.match(r"^\d+[-:]\d+[-:][ATCG]+[-:][ATCG]+$", invalid_notation):
        parts = re.split(r"[-:]", invalid_notation)
        # parts = [chromosome, position, ref, alt]
        if len(parts) >= 4:
            chrom, position, ref, alt = parts[0], parts[1], parts[2], parts[3]
            suggestions.append(
                f"For VCF format, use: chr{chrom}-{position}-{ref}-{alt}"
            )
            # Genomic HGVS currently only suggests the chr17 RefSeq accession
            # because HNF1B variants always map to chr17; a chromosome→NC
            # lookup would be needed to generalise.
            if chrom == "17":
                suggestions.append(
                    f"For HGVS genomic, use: NC_000017.11:g.{position}{ref}>{alt}"
                )

    notation_lower = invalid_notation.lower()
    if re.search(r"\b(del|dup|deletion|duplication)\b", notation_lower):
        if ":" not in invalid_notation:
            suggestions.append(
                "For CNVs, use format: 17:start-end:DEL or 17:start-end:DUP"
            )

    close_matches = get_close_matches(
        invalid_notation, COMMON_PATTERNS, n=3, cutoff=0.6
    )
    if close_matches:
        suggestions.append(f"Similar valid formats: {', '.join(close_matches)}")

    if not suggestions:
        suggestions.append(
            "Valid formats: NM_000458.4:c.123A>G, chr17:g.36459258A>G, "
            "17:start-end:DEL"
        )

    return suggestions
