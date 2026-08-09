"""Strict, lossless mapping from validated Publications rows to references."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


class PublicationMappingError(ValueError):
    """The pinned Publications sheet is not an unambiguous reference ledger."""


_PMID = re.compile(r"^(?:pmid:\s*)?(\d+)$", re.IGNORECASE)
_DOI = re.compile(r"^(?:doi:\s*)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
_NOT_REPORTED = {"", "nr", "not reported", "na", "n/a", "not applicable"}


@dataclass(frozen=True)
class PublicationReference:
    """Canonical external identifiers resolved from one Publications row."""

    pmid: str | None
    doi: str | None


def _text(value: Any) -> str:
    """Normalize dataframe scalar values without accepting missing sentinels."""
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.casefold() == "nan" else value


def _reference(value: Any, *, kind: str) -> str | None:
    """Parse one supplied PMID or DOI into its canonical storage representation."""
    text = _text(value)
    if text.casefold() in _NOT_REPORTED:
        return None
    pattern = _PMID if kind == "PMID" else _DOI
    match = pattern.fullmatch(text)
    if match is None:
        raise PublicationMappingError(f"invalid {kind} in Publications sheet")
    return match.group(1).casefold() if kind == "DOI" else match.group(1)


def publication_mapping_from_rows(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, PublicationReference]:
    """Build an alias lookup and refuse unmappable or ambiguous source rows."""
    mapping: dict[str, PublicationReference] = {}
    for row in rows:
        publication_id = _text(row.get("publication_id"))
        publication_alias = _text(row.get("publication_alias"))
        supplied_references = (_text(row.get("PMID")), _text(row.get("DOI")))
        if all(
            value.casefold() in _NOT_REPORTED
            for value in (publication_id, publication_alias, *supplied_references)
        ):
            # A placeholder row from a complete, header-valid snapshot is not
            # a publication mapping and therefore cannot create an alias.
            continue
        if not publication_id and not publication_alias:
            raise PublicationMappingError("Publications row has no identifier or alias")
        reference = PublicationReference(
            pmid=_reference(row.get("PMID"), kind="PMID"),
            doi=_reference(row.get("DOI"), kind="DOI"),
        )
        if reference.pmid is None and reference.doi is None:
            raise PublicationMappingError("Publications row has no PMID or DOI")
        for alias in {publication_id, publication_alias} - {""}:
            previous = mapping.get(alias)
            if previous is not None and previous != reference:
                raise PublicationMappingError("ambiguous publication alias")
            mapping[alias] = reference
    return mapping


def resolve_publication(
    source_value: Any,
    *,
    mapping: Mapping[str, PublicationReference] | None,
) -> PublicationReference | None:
    """Resolve a raw source publication without permitting unknown aliases."""
    raw = _text(source_value)
    if raw.casefold() in _NOT_REPORTED:
        return None
    pmid = _PMID.fullmatch(raw)
    if pmid is not None:
        return PublicationReference(pmid=pmid.group(1), doi=None)
    doi = _DOI.fullmatch(raw)
    if doi is not None:
        return PublicationReference(pmid=None, doi=doi.group(1).casefold())
    if mapping is None or raw not in mapping:
        raise PublicationMappingError("source publication alias is not mapped")
    return mapping[raw]
