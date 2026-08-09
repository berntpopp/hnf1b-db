"""Fail-closed unit-aware parser for source age fields."""

from __future__ import annotations

import re

from app.phenopackets.curation.models import OntologyTerm, TemporalValue


class AgeParseError(ValueError):
    """A source age has no unambiguous, allowed interpretation."""


_DURATION = re.compile(
    r"^(?P<value>\d+)\s*(?P<unit>y|yr|yrs|year|years|m|mo|mos|month|months|d|day|days)$",
    re.IGNORECASE,
)
_WEEKS = re.compile(r"^(?P<value>\d+)\s*(?:w|wk|wks|week|weeks)$", re.IGNORECASE)


def parse_source_age(raw: str, *, context: str | None = None) -> TemporalValue:
    """Parse only explicit source age syntax; never default a bare number to years."""
    value = raw.strip()
    lowered = value.casefold()
    if lowered == "prenatal":
        return TemporalValue(
            kind="ontologyClass",
            term=OntologyTerm(id="HP:0030674", label="Antenatal onset"),
        )
    if lowered == "postnatal":
        return TemporalValue(kind="unprojected")
    week_match = _WEEKS.fullmatch(value)
    if week_match:
        if (context or "").casefold() not in {"prenatal", "fetal", "fetus"}:
            raise AgeParseError("gestational week syntax requires prenatal/fetal context")
        return TemporalValue(
            kind="gestationalAge",
            iso8601_duration=f"P{week_match.group('value')}W",
        )
    duration_match = _DURATION.fullmatch(value)
    if duration_match:
        unit = duration_match.group("unit").casefold()
        designator = (
            "Y" if unit.startswith("y") else "M" if unit.startswith("m") else "D"
        )
        return TemporalValue(
            kind="age",
            iso8601_duration=f"P{duration_match.group('value')}{designator}",
        )
    raise AgeParseError(f"ambiguous or unsupported source age: {raw!r}")
