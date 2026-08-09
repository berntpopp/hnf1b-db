"""Strict source age parsing regression tests."""

import pytest

from migration.phenopackets.strict_age_parser import AgeParseError, parse_source_age


@pytest.mark.parametrize("raw", ["28w", "35wks", "12 weeks"])
def test_week_tokens_are_gestational_ages(raw):
    parsed = parse_source_age(raw, context="prenatal")
    assert parsed.kind == "gestationalAge"
    assert parsed.iso8601_duration == "P" + raw.split("w")[0].strip() + "W"


def test_prenatal_maps_to_antenatal_onset_and_postnatal_stays_unprojected():
    assert parse_source_age("prenatal").term.id == "HP:0030674"
    assert parse_source_age("postnatal").kind == "unprojected"


@pytest.mark.parametrize("raw", ["28", "ten", "3fortnights"])
def test_ambiguous_or_unknown_age_units_fail_closed(raw):
    with pytest.raises(AgeParseError):
        parse_source_age(raw)
