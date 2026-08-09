"""Explicit, one-to-one ownership map for the 60 Individuals source columns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from migration.source_manifest import INDIVIDUALS_HEADERS


@dataclass(frozen=True)
class SourceColumn:
    """One source header and the observation path that retains it."""

    header: str
    observation_path: str


_PATHS = (
    "identifiers.individualId",
    "identifiers.reportId",
    "identifiers.individualIdentifier",
    "publication.sourceKey",
    "publication.publicationType",
    "case.duplicateCheck",
    "case.problematic",
    "case.cohort",
    "identifiers.sex",
    "case.familyHistory",
    "ages.onset",
    "ages.reported",
    "variant.variantType",
    "variant.reported",
    "variant.sourceId",
    "variant.hg19Info",
    "variant.hg19",
    "variant.hg38Info",
    "variant.hg38",
    "variant.varsome",
    "variant.detectionMethod",
    "variant.segregation",
    "classification.verdict",
    "classification.criteria",
    "classification.comment",
    "classification.system",
    "classification.date",
    *(f"phenotypes.{header}" for header in INDIVIDUALS_HEADERS[27:57]),
    "notes.comment",
    "sourceReview.reviewerReference",
    "sourceReview.reviewedOn",
)

SOURCE_COLUMNS = tuple(
    SourceColumn(header=header, observation_path=path)
    for header, path in zip(INDIVIDUALS_HEADERS, _PATHS)
)


class SourceColumnError(ValueError):
    """A row does not have the closed 60-column source contract."""


def validate_source_headers(headers: Sequence[str]) -> None:
    """Reject missing, duplicate, or unowned Individuals columns."""
    normalized = [str(header).strip() for header in headers]
    expected = {entry.header for entry in SOURCE_COLUMNS}
    actual = set(normalized)
    duplicates = sorted({name for name in normalized if normalized.count(name) > 1})
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if duplicates or missing or unknown:
        parts: list[str] = []
        if duplicates:
            parts.append("duplicate=" + ", ".join(duplicates))
        if missing:
            parts.append("missing=" + ", ".join(missing))
        if unknown:
            parts.append("unknown=" + ", ".join(unknown))
        raise SourceColumnError("invalid Individuals headers: " + "; ".join(parts))
