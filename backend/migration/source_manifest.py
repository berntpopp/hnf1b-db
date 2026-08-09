"""Fail-closed, content-addressed source manifest construction.

The migration pipeline never receives a partial collection of dataframes.  It
first receives an immutable manifest of every required raw sheet, validated
without logging source rows.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from io import StringIO
from typing import Mapping, Sequence

REQUIRED_SHEETS = frozenset(
    {"Individuals", "Phenotypes", "Phenotype_modifier", "Publications"}
)

PHENOTYPE_COLUMNS = (
    "RenalInsufficancy",
    "Hyperechogenicity",
    "RenalCysts",
    "MulticysticDysplasticKidney",
    "KidneyBiopsy",
    "RenalHypoplasia",
    "SolitaryKidney",
    "UrinaryTractMalformation",
    "GenitalTractAbnormality",
    "AntenatalRenalAbnormalities",
    "Hypomagnesemia",
    "Hypokalemia",
    "Hyperuricemia",
    "Gout",
    "MODY",
    "PancreaticHypoplasia",
    "ExocrinePancreaticInsufficiency",
    "Hyperparathyroidism",
    "NeurodevelopmentalDisorder",
    "MentalDisease",
    "Seizures",
    "BrainAbnormality",
    "PrematureBirth",
    "CongenitalCardiacAnomalies",
    "EyeAbnormality",
    "ShortStature",
    "MusculoskeletalFeatures",
    "DysmorphicFeatures",
    "ElevatedHepaticTransaminase",
    "AbnormalLiverPhysiology",
)

INDIVIDUALS_HEADERS = (
    "individual_id",
    "report_id",
    "IndividualIdentifier",
    "Publication",
    "PublicationType",
    "DupCheck",
    "Problematic",
    "Cohort",
    "Sex",
    "FamilyHistory",
    "AgeOnset",
    "AgeReported",
    "VariantType",
    "VariantReported",
    "ID",
    "hg19_INFO",
    "hg19",
    "hg38_INFO",
    "hg38",
    "Varsome",
    "DetecionMethod",
    "Segregation",
    "verdict_classification",
    "criteria_classification",
    "comment_classification",
    "system_classification",
    "date_classification",
    *PHENOTYPE_COLUMNS,
    "Comment",
    "ReviewBy",
    "ReviewDate",
)

EXPECTED_HEADERS: dict[str, tuple[str, ...]] = {
    "Individuals": INDIVIDUALS_HEADERS,
    "Phenotypes": ("category", "phenotype_id", "phenotype_name"),
    "Phenotype_modifier": ("modifier", "modifier_id"),
    "Publications": ("publication", "pmid", "doi"),
}

_FORBIDDEN_HEADER_PARTS = ("password", "passwd", "secret", "token", "credential")


class SourceManifestError(ValueError):
    """A source fails a structural or security precondition."""


@dataclass(frozen=True)
class SheetManifest:
    """Safe structural metadata for one raw source sheet."""

    name: str
    sha256: str
    headers: tuple[str, ...]
    row_count: int


@dataclass(frozen=True)
class SourceManifest:
    """Immutable source set that is safe to persist as operational metadata."""

    source_system: str
    dataset_key: str
    sha256: str
    sheets: Mapping[str, SheetManifest]


def _normalise_headers(headers: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(header).strip() for header in headers)


def validate_sheet_headers(
    sheet_name: str,
    headers: Sequence[str],
    *,
    expected_headers: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Validate headers without reading, retaining, or logging source values."""
    normalized = _normalise_headers(headers)
    lower_headers = tuple(header.casefold() for header in normalized)
    forbidden = [
        header
        for header, lowered in zip(normalized, lower_headers)
        if any(part in lowered for part in _FORBIDDEN_HEADER_PARTS)
    ]
    if forbidden:
        raise SourceManifestError(
            f"forbidden credential-like headers in {sheet_name}: {', '.join(forbidden)}"
        )
    if sheet_name.casefold() == "reviewers" and any(
        "email" in header for header in lower_headers
    ):
        raise SourceManifestError(
            "reviewer email headers are forbidden; use an approved pseudonymous mapping"
        )
    if not normalized or any(not header for header in normalized):
        raise SourceManifestError(f"missing header in {sheet_name}")
    duplicates = sorted(
        {header for header in normalized if normalized.count(header) > 1}
    )
    if duplicates:
        raise SourceManifestError(
            f"duplicate headers in {sheet_name}: {', '.join(duplicates)}"
        )
    if expected_headers is not None:
        expected = set(expected_headers)
        actual = set(normalized)
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        if missing:
            raise SourceManifestError(
                f"missing required headers in {sheet_name}: {', '.join(missing)}"
            )
        if unknown:
            raise SourceManifestError(
                f"unknown headers in {sheet_name}: {', '.join(unknown)}"
            )
    return normalized


def _read_csv_structure(name: str, raw: bytes) -> tuple[tuple[str, ...], int]:
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceManifestError(f"{name} is not UTF-8 CSV") from exc
    rows = list(csv.reader(StringIO(decoded)))
    if not rows:
        raise SourceManifestError(f"{name} is empty")
    headers = tuple(rows[0])
    row_count = sum(1 for row in rows[1:] if any(cell.strip() for cell in row))
    return headers, row_count


def build_source_manifest(
    *,
    source_system: str,
    dataset_key: str,
    sheets: Mapping[str, bytes],
    header_validation: bool = True,
) -> SourceManifest:
    """Validate and content-address a complete raw source set.

    The caller retains the bytes separately.  This manifest stores only hashes,
    headers, and counts so it is safe for operational tables and logs.
    """
    actual_names = set(sheets)
    missing = sorted(REQUIRED_SHEETS - actual_names)
    unknown = sorted(actual_names - REQUIRED_SHEETS)
    if missing:
        raise SourceManifestError(f"missing required sheets: {', '.join(missing)}")
    if unknown:
        raise SourceManifestError(f"unknown sheets: {', '.join(unknown)}")

    sheet_manifests: dict[str, SheetManifest] = {}
    digest = hashlib.sha256()
    for name in sorted(REQUIRED_SHEETS):
        raw = sheets[name]
        if not isinstance(raw, bytes):
            raise SourceManifestError(f"{name} source must be raw bytes")
        headers, row_count = _read_csv_structure(name, raw)
        normalized = validate_sheet_headers(
            name,
            headers,
            expected_headers=EXPECTED_HEADERS[name] if header_validation else None,
        )
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw)
        sheet_manifests[name] = SheetManifest(
            name=name,
            sha256=hashlib.sha256(raw).hexdigest(),
            headers=normalized,
            row_count=row_count,
        )
    return SourceManifest(
        source_system=source_system,
        dataset_key=dataset_key,
        sha256=digest.hexdigest(),
        sheets=sheet_manifests,
    )
