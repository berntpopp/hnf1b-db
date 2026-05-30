from __future__ import annotations

import json
from pathlib import Path

from app.publications.fulltext.fulltext_client import (
    parse_bioc,
    parse_europepmc_core,
    parse_idconv,
    parse_jats,
)
from app.publications.fulltext.types import SECTION_ORDER

FIX = Path(__file__).parent / "fixtures" / "publications"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_parse_idconv_maps_pmids_to_pmcids_with_error_as_none():
    data = _load("idconv_batch.json")
    result = parse_idconv(data)
    assert result["32574212"] == "PMC7310724"
    assert result["30791938"] == "PMC6385394"
    # status == "error" record resolves to None
    assert result["10484768"] is None
    # keys are bare digit strings
    assert all(k.isdigit() for k in result)


def test_parse_bioc_pmid_pmcid_and_sections():
    data = _load("pubtator_bioc_32574212.json")
    result = parse_bioc(data)
    assert result.pmid == "PMID:32574212"
    assert result.pmcid == "PMC7310724"
    assert result.source == "pubtator_full_bioc"
    # license/OA are NOT filled by this parser (caller does it)
    assert result.license is None
    assert result.is_open_access is False
    assert len(result.sections) > 0


def test_parse_bioc_only_canonical_sections_in_order():
    data = _load("pubtator_bioc_32574212.json")
    result = parse_bioc(data)
    labels = {s.section for s in result.sections}
    # No section outside the canonical taxonomy (REF/SUPPL/FIG dropped)
    assert labels.issubset(set(SECTION_ORDER))
    # The expected canonical sections are present
    assert "title" in labels
    assert "abstract" in labels
    assert "methods" in labels
    assert "results" in labels
    assert "discussion" in labels
    assert "table" in labels
    # order is a dense 0-based sequence over kept passages
    orders = [s.order for s in result.sections]
    assert orders == list(range(len(result.sections)))
    # no empty-text section survived
    assert all(s.text for s in result.sections)


def test_parse_europepmc_core_open_access_and_raw_license():
    data = _load("europepmc_core_32574212.json")
    is_oa, raw_license = parse_europepmc_core(data)
    assert is_oa is True
    assert raw_license == "cc by"


def test_parse_europepmc_core_empty_result_list():
    is_oa, raw_license = parse_europepmc_core({"resultList": {"result": []}})
    assert is_oa is False
    assert raw_license is None


def test_parse_jats_intro_section():
    xml = (
        "<article><body>"
        "<sec sec-type='intro'><title>Introduction</title>"
        "<p>HNF1B is a transcription factor.</p>"
        "<p>It causes renal cysts and diabetes.</p>"
        "</sec>"
        "<ref-list><ref><p>should be ignored</p></ref></ref-list>"
        "</body></article>"
    )
    sections = parse_jats(xml)
    assert len(sections) == 1
    assert sections[0].section == "intro"
    assert "transcription factor" in sections[0].text
    assert sections[0].order == 0


def test_parse_jats_title_heuristic_when_no_sec_type():
    xml = (
        "<article><body>"
        "<sec><title>Materials and Methods</title>"
        "<p>We sequenced 31 patients.</p></sec>"
        "<sec><title>Acknowledgements</title>"
        "<p>Thanks to everyone.</p></sec>"
        "</body></article>"
    )
    sections = parse_jats(xml)
    assert [s.section for s in sections] == ["methods"]


def test_parse_jats_table_wrap_emits_table_section():
    xml = (
        "<article><body>"
        "<table-wrap><label>Table 1</label>"
        "<caption><p>Variant summary.</p></caption></table-wrap>"
        "</body></article>"
    )
    sections = parse_jats(xml)
    assert len(sections) == 1
    assert sections[0].section == "table"
    assert "Table 1" in sections[0].text


def test_parse_jats_unparseable_returns_empty_tuple():
    assert parse_jats("not xml at all <<<") == ()
    assert parse_jats("<article><front>no body</front></article>") == ()
