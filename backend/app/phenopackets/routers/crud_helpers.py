"""Pure helper functions used by the phenopacket CRUD router layer.

Extracted during Wave 4 from ``crud.py`` so the router file can stay
focused on HTTP plumbing. None of these functions touch the database
or SQLAlchemy sessions directly — they produce SQL expressions and
parse strings.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Integer, case, func

from app.phenopackets.models import Phenopacket

ALLOWED_SORT_FIELDS = {
    "created_at": Phenopacket.created_at,
    "subject_id": Phenopacket.subject_id,
    "subject_sex": Phenopacket.subject_sex,
    "features_count": Phenopacket.features_count,
    "has_variant": Phenopacket.has_variant,
}


def get_natural_sort_clauses(column, descending: bool = False) -> list:
    """Generate SQLAlchemy order clauses for natural sorting.

    Natural sorting ensures ``Var2`` comes before ``Var10`` by:

    1. Sorting by the text prefix (e.g., ``Var``)
    2. Sorting by the numeric suffix as an integer (e.g., 2, 10)
    """
    text_prefix = func.regexp_replace(column, r"[0-9]+$", "", "g")
    numeric_suffix = func.coalesce(
        func.cast(
            func.substring(column, r"([0-9]+)$"),
            Integer,
        ),
        0,
    )
    if descending:
        return [text_prefix.desc(), numeric_suffix.desc()]
    return [text_prefix.asc(), numeric_suffix.asc()]


def parse_sort_parameter(sort: str, *, content: Any = None) -> list:
    """Parse a JSON:API sort parameter into SQLAlchemy order clauses.

    ``sort`` is a comma-separated list of field names; prefix a field
    with ``-`` for descending order. Only fields in
    :data:`ALLOWED_SORT_FIELDS` are accepted — unknown fields produce
    a 400 with the full allow-list in the error detail.
    """
    # The generated columns are derived from the mutable working copy. Public
    # callers instead sort on the joined published-head JSON snapshot.
    sort_fields: dict[str, Any] = dict(ALLOWED_SORT_FIELDS)
    if content is not None:
        sort_fields = {
            "created_at": Phenopacket.created_at,
            "subject_id": content["subject"]["id"].astext,
            "subject_sex": content["subject"]["sex"].astext,
            "features_count": func.coalesce(
                func.jsonb_array_length(content["phenotypicFeatures"]), 0
            ),
            "has_variant": case(
                (
                    func.coalesce(
                        func.jsonb_array_length(content["interpretations"]), 0
                    )
                    > 0,
                    True,
                ),
                else_=False,
            ),
        }

    order_clauses: list = []
    for raw in sort.split(","):
        field = raw.strip()
        descending = field.startswith("-")
        field_name = field[1:] if descending else field

        if field_name not in sort_fields:
            allowed = ", ".join(sort_fields.keys())
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field: {field_name}. Allowed: {allowed}",
            )

        sort_column = sort_fields[field_name]

        # Apply natural sorting for subject_id to handle IDs like
        # "Var1", "Var2", "Var10" — extracts numeric suffix and sorts
        # numerically.
        if field_name == "subject_id":
            order_clauses.extend(get_natural_sort_clauses(sort_column, descending))
        else:
            if descending:
                order_clauses.append(sort_column.desc())
            else:
                order_clauses.append(sort_column.asc())
    return order_clauses


_PMID_PATTERN = re.compile(r"^PMID:\d{1,8}$")


def validate_pmid(pmid: str) -> str:
    """Validate and normalise a PMID string.

    Accepts ``"PMID:12345678"`` or just ``"12345678"``; returns the
    canonical ``PMID:N`` form. Raises ``ValueError`` on malformed input
    — the router catches it and returns ``HTTPException(400)``.
    """
    if not pmid.startswith("PMID:"):
        pmid = f"PMID:{pmid}"
    if not _PMID_PATTERN.match(pmid):
        raise ValueError(f"Invalid PMID format: {pmid}. Expected PMID:12345678")
    return pmid
