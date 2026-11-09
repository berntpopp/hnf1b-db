"""Tests for the medical_specialty suggester (issue #11)."""

from __future__ import annotations

import json
from pathlib import Path

import aiohttp
import pytest

from app.publications.specialty import (
    SpecialtyInputs,
    evaluate,
    fetch_specialty_suggestions,
    parse_journal_mesh,
    parse_pubmed_inputs,
    suggest_specialties,
)

FIX = Path(__file__).parent / "fixtures" / "publications"
PUBMED = (FIX / "efetch_specialty.xml").read_bytes()
CATALOG = (FIX / "nlmcatalog_specialty.xml").read_bytes()


# --- parsing (recorded real NCBI records) -----------------------------------


def test_parse_pubmed_inputs_extracts_journal_and_first_last_affiliations():
    inputs = parse_pubmed_inputs(PUBMED)
    assert set(inputs) == {"9398836", "16971658", "29927023"}
    art = inputs["29927023"]
    assert art.journal == "Pediatric diabetes"
    assert art.nlm_unique_id == "100939345"
    assert "Pediatric Endocrinology" in art.first_affiliation
    # Multiple affiliations of one author are all kept.
    assert "Department of Genetic Medicine" in art.first_affiliation
    assert art.last_affiliation.startswith("Department of Genetic Medicine")


def test_parse_pubmed_inputs_missing_affiliations_are_empty():
    art = parse_pubmed_inputs(PUBMED)["9398836"]
    assert art.journal == "Nature genetics"
    assert art.first_affiliation == ""
    assert art.last_affiliation == ""


def test_parse_single_author_is_not_double_counted():
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>"
        "<Article><Journal><Title>J</Title></Journal><AuthorList><Author>"
        "<AffiliationInfo><Affiliation>Dept of Nephrology</Affiliation>"
        "</AffiliationInfo></Author></AuthorList></Article></MedlineCitation>"
        "</PubmedArticle></PubmedArticleSet>"
    )
    art = parse_pubmed_inputs(xml)["1"]
    assert art.first_affiliation == "Dept of Nephrology"
    assert art.last_affiliation == ""
    assert suggest_specialties(art).scores == {"nephrology": 1}


def test_parse_recovers_from_undeclared_nlm_entity():
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>2</PMID>"
        "<Article><Journal><Title>Diabetes &amp; Metabolism</Title></Journal>"
        "<AuthorList><Author><AffiliationInfo><Affiliation>H&ocirc;pital, "
        "P&eacute;diatrie</Affiliation></AffiliationInfo></Author></AuthorList>"
        "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
    )
    art = parse_pubmed_inputs(xml)["2"]
    assert art.journal == "Diabetes & Metabolism"
    assert art.first_affiliation == "Hôpital, Pédiatrie"
    # Accented French department names still match.
    assert set(suggest_specialties(art).scores) == {"diabetology", "pediatrics"}


def test_parse_skips_articles_without_pmid_and_tolerates_garbage():
    assert (
        parse_pubmed_inputs("<PubmedArticleSet><PubmedArticle/></PubmedArticleSet>")
        == {}
    )
    assert parse_pubmed_inputs(b"not xml at all") == {}
    assert parse_journal_mesh(b"") == {}


def test_parse_journal_mesh():
    mesh = parse_journal_mesh(CATALOG)
    assert mesh["9013836"] == ["Kidney Diseases", "Nephrology"]
    assert mesh["100939345"] == ["Child", "Diabetes Mellitus"]


# --- scoring ------------------------------------------------------------------


def test_journal_outweighs_single_affiliation_and_evidence_is_reported():
    inputs = parse_pubmed_inputs(PUBMED)["16971658"]
    s = suggest_specialties(inputs, parse_journal_mesh(CATALOG)["9013836"])
    assert s.ranked == ["nephrology", "pediatrics"]
    assert s.scores == {"nephrology": 3, "pediatrics": 1}
    assert s.evidence == {
        "nephrology": ["journal", "first_author"],
        "pediatrics": ["first_author"],
    }


def test_journal_title_and_mesh_count_once():
    s = suggest_specialties(
        SpecialtyInputs("3", journal="Diabetes"), ["Diabetes Mellitus"]
    )
    assert s.scores == {"diabetology": 2}


def test_mesh_alone_classifies_journal_with_uninformative_title():
    s = suggest_specialties(
        SpecialtyInputs("4", journal="Clinical Medicine"), ["Kidney Diseases"]
    )
    assert s.ranked == ["nephrology"]


def test_first_and_last_author_add_up():
    inputs = SpecialtyInputs(
        "5",
        first_affiliation="Department of Medical Genetics",
        last_affiliation="Institute of Human Genetics",
    )
    assert suggest_specialties(inputs).scores == {"genetics": 2}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Department of Paediatrics", {"pediatrics"}),
        ("Klinik für Nephrologie", {"nephrology"}),
        ("Service de néphrologie pédiatrique", {"nephrology", "pediatrics"}),
        ("Dept. of Obstetrics and Gynaecology", {"obstetrics", "gynecology"}),
        ("Institute of Pathology", {"pathology"}),
        ("Department of Radiology", {"radiology"}),
        ("Endocrinology and Metabolism", {"diabetology"}),
        ("Department of Cardiology", set()),
    ],
)
def test_affiliation_keyword_vocabulary(text, expected):
    assert (
        set(suggest_specialties(SpecialtyInputs("6", first_affiliation=text)).scores)
        == expected
    )


def test_no_evidence_gives_empty_suggestion():
    s = suggest_specialties(SpecialtyInputs("7", journal="Medicine"), ["Medicine"])
    assert s.scores == {} and s.ranked == []


def test_ties_rank_in_vocabulary_order():
    s = suggest_specialties(SpecialtyInputs("8", journal="Pediatric Nephrology"))
    assert s.ranked == ["nephrology", "pediatrics"]


# --- agreement with curators (86 manually labelled papers) --------------------


def test_agreement_with_manual_curation_does_not_regress():
    """Floors sit just below measured values (P .76 / R .82 / top-1 .88).

    Rows are real PubMed + NLM Catalog metadata for the papers curators labelled
    in the Vasileiou et al. sheet. A rule change that lowers agreement fails here.
    """
    rows = json.loads((FIX / "specialty_gold.json").read_text(encoding="utf-8"))
    pairs = []
    for row in rows:
        gold = set(row.pop("gold"))
        mesh = row.pop("journal_mesh")
        pairs.append((suggest_specialties(SpecialtyInputs(**row), mesh), gold))
    metrics = evaluate(pairs)
    assert metrics["n"] == 86
    assert metrics["precision"] >= 0.75
    assert metrics["recall"] >= 0.80
    assert metrics["top1"] >= 0.85


def test_evaluate_counts():
    s = suggest_specialties(SpecialtyInputs("9", journal="Kidney International"))
    m = evaluate([(s, {"nephrology", "genetics"})])
    assert m == {"n": 1, "precision": 1.0, "recall": 0.5, "top1": 1.0, "exact": 0.0}
    assert evaluate([])["n"] == 0


# --- fetching -------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)  # type: ignore[arg-type]

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    def __init__(self, status: int = 200):
        self.status = status
        self.calls: list[dict] = []

    def post(self, url, *, data, timeout):
        self.calls.append(data)
        body = PUBMED if data["db"] == "pubmed" else CATALOG
        return _FakeResponse(body, self.status)


@pytest.mark.asyncio
async def test_fetch_queries_pubmed_then_catalog_and_scores():
    session = _FakeSession()
    out = await fetch_specialty_suggestions(
        ["PMID:29927023", "16971658", "9398836"],
        session=session,  # type: ignore[arg-type]
        base_url="https://example.test/efetch.fcgi",
        api_key="k",
    )
    assert [c["db"] for c in session.calls] == ["pubmed", "nlmcatalog"]
    assert session.calls[0]["id"] == "29927023,16971658,9398836"
    assert session.calls[1]["id"] == "100939345,9013836,9216904"
    assert all(c["api_key"] == "k" for c in session.calls)
    assert out["9398836"].ranked == ["genetics"]
    assert out["29927023"].ranked[:2] == ["diabetology", "pediatrics"]


@pytest.mark.asyncio
async def test_fetch_batches_and_skips_io_for_empty_input():
    session = _FakeSession()
    await fetch_specialty_suggestions(
        ["1", "2", "3"],
        session=session,
        base_url="u",
        batch_size=2,  # type: ignore[arg-type]
    )
    assert [c["id"] for c in session.calls if c["db"] == "pubmed"] == ["1,2", "3"]
    empty = _FakeSession()
    assert await fetch_specialty_suggestions([], session=empty, base_url="u") == {}  # type: ignore[arg-type]
    assert empty.calls == []


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error_instead_of_empty_suggestions():
    with pytest.raises(aiohttp.ClientResponseError):
        await fetch_specialty_suggestions(
            ["1"],
            session=_FakeSession(status=429),
            base_url="u",  # type: ignore[arg-type]
        )
