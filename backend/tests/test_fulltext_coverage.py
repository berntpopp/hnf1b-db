from __future__ import annotations

import pytest

from app.publications.fulltext.coverage import (
    classify_coverage,
    is_license_allowed,
    normalize_license,
)
from app.publications.fulltext.types import FullTextResult, RawSection

ALLOWED = ("CC0", "CC-BY", "CC-BY-SA", "PMC-OA")


def _section(text="Body text here.", section="results", order=0):
    return RawSection(section=section, text=text, order=order)


def _fulltext(*, license="CC-BY", is_open_access=True, sections=None, pmcid="PMC123"):
    return FullTextResult(
        pmid="PMID:32574212",
        pmcid=pmcid,
        license=license,
        is_open_access=is_open_access,
        sections=tuple(sections) if sections is not None else (_section(),),
        source="pubtator_full_bioc",
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("cc by", "CC-BY"),
        ("CC BY 4.0", "CC-BY"),
        ("cc-by", "CC-BY"),
        ("ccby", "CC-BY"),
        ("cc by-nc", "CC-BY-NC"),
        ("cc by nc", "CC-BY-NC"),
        ("cc-by-nc", "CC-BY-NC"),
        ("cc by-sa", "CC-BY-SA"),
        ("cc by-nc-nd", "CC-BY-NC-ND"),
        ("cc by nc nd", "CC-BY-NC-ND"),
        ("cc by-nd", "CC-BY-ND"),
        ("cc by-nc-sa", "CC-BY-NC-SA"),
        ("cc0", "CC0"),
        ("cc 0", "CC0"),
        ("cc-0", "CC0"),
        ("public domain", "CC0"),
        ("  CC-BY  ", "CC-BY"),
        ("CC-BY-NC-ND 4.0", "CC-BY-NC-ND"),
        (None, None),
        ("", None),
        ("unknown", None),
        ("UNKNOWN", None),
        ("weird", None),
        ("license-not-real", None),
    ],
)
def test_normalize_license(raw, expected):
    assert normalize_license(raw) == expected


def test_is_license_allowed_token_in_allowed():
    assert is_license_allowed("CC-BY", is_open_access=False, allowed=ALLOWED) is True


def test_is_license_allowed_token_not_in_allowed():
    assert (
        is_license_allowed("CC-BY-NC-ND", is_open_access=False, allowed=ALLOWED)
        is False
    )


def test_is_license_allowed_none_token_but_open_access_pmc_oa():
    assert is_license_allowed(None, is_open_access=True, allowed=ALLOWED) is True


def test_is_license_allowed_none_token_not_open_access():
    assert is_license_allowed(None, is_open_access=False, allowed=ALLOWED) is False


def test_is_license_allowed_open_access_but_no_pmc_oa():
    assert is_license_allowed(None, is_open_access=True, allowed=("CC-BY",)) is False


def test_full_text_kept_when_oa_and_ccby():
    ft = _fulltext(license="CC-BY", is_open_access=True)
    decision = classify_coverage(
        abstract="Some abstract.", fulltext=ft, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "full_text"
    assert decision.license == "CC-BY"
    assert decision.pmcid == "PMC123"
    assert decision.sections == ft.sections
    assert decision.source == "pubtator_full_bioc"


def test_license_gate_drops_body_when_not_allowed_not_oa():
    # CC-BY-NC-ND is not in ALLOWED and the record is not open access:
    # body must be dropped and fall through to abstract_only.
    ft = _fulltext(license="CC-BY-NC-ND", is_open_access=False)
    decision = classify_coverage(
        abstract="An abstract.", fulltext=ft, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "abstract_only"
    assert decision.sections == ()
    assert decision.license == "CC-BY-NC-ND"
    assert decision.pmcid == "PMC123"
    assert decision.source is None


def test_license_gate_keeps_body_when_oa_and_pmc_oa_allowed():
    # Same disallowed token, but open access + PMC-OA in allowed -> full_text.
    ft = _fulltext(license="CC-BY-NC-ND", is_open_access=True)
    decision = classify_coverage(
        abstract="An abstract.", fulltext=ft, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "full_text"
    assert decision.sections == ft.sections
    assert decision.source == "pubtator_full_bioc"


def test_license_gate_drops_body_to_title_only_when_no_abstract():
    ft = _fulltext(license="CC-BY-NC-ND", is_open_access=False)
    decision = classify_coverage(abstract=None, fulltext=ft, allowed_licenses=ALLOWED)
    assert decision.coverage == "title_only"
    assert decision.sections == ()
    assert decision.license == "CC-BY-NC-ND"
    assert decision.pmcid == "PMC123"


def test_no_abstract_no_fulltext_title_only():
    decision = classify_coverage(abstract=None, fulltext=None, allowed_licenses=ALLOWED)
    assert decision.coverage == "title_only"
    assert decision.sections == ()
    assert decision.license is None
    assert decision.pmcid is None
    assert decision.source is None


def test_empty_abstract_no_fulltext_title_only():
    decision = classify_coverage(abstract="", fulltext=None, allowed_licenses=ALLOWED)
    assert decision.coverage == "title_only"


def test_abstract_present_fulltext_none_abstract_only():
    decision = classify_coverage(
        abstract="A real abstract.", fulltext=None, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "abstract_only"
    assert decision.sections == ()
    assert decision.license is None
    assert decision.pmcid is None
    assert decision.source is None


def test_empty_sections_falls_back_to_abstract_only():
    # Allowed license but no body sections -> cannot be full_text.
    ft = _fulltext(license="CC-BY", is_open_access=True, sections=[])
    decision = classify_coverage(
        abstract="Abstract present.", fulltext=ft, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "abstract_only"
    assert decision.sections == ()
    assert decision.license == "CC-BY"
    assert decision.pmcid == "PMC123"


def test_full_text_via_cc0_token():
    ft = _fulltext(license="cc0", is_open_access=False)
    decision = classify_coverage(
        abstract="Abstract.", fulltext=ft, allowed_licenses=ALLOWED
    )
    assert decision.coverage == "full_text"
    assert decision.license == "CC0"
