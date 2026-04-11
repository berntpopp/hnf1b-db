"""Shared helpers for the variant validator endpoints."""

from __future__ import annotations

import re


def detect_notation_type(notation: str) -> str:
    """Detect the family of a variant notation string.

    Returns one of ``hgvs.c`` / ``hgvs.p`` / ``hgvs.g`` / ``vcf`` /
    ``cnv`` / ``unknown``. The router falls back to ``unknown`` when
    no pattern matches and then runs the full fallback validator.
    """
    if ":c." in notation:
        return "hgvs.c"
    if ":p." in notation:
        return "hgvs.p"
    if ":g." in notation:
        return "hgvs.g"
    if re.match(r"^(chr)?[\dXY]+-\d+-[ATCG]+-[ATCG]+", notation):
        return "vcf"
    if re.match(r"^[\dXY]+:\d+-\d+:(DEL|DUP|INS|INV)", notation):
        return "cnv"
    return "unknown"
