from __future__ import annotations

from pathlib import Path

import pytest

from app.publications.fulltext.abstract_client import (
    fetch_abstracts,
    parse_efetch_xml,
)
from app.publications.fulltext.types import AbstractResult

FIX = Path(__file__).parent / "fixtures" / "publications"


def _read(name: str) -> bytes:
    return (FIX / name).read_bytes()


def test_parse_batch_returns_three_entries():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    assert set(results) == {"PMID:30791938", "PMID:10484768", "PMID:11085914"}
    assert len(results) == 3


def test_parse_batch_structured_abstract_labels():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    text = results["PMID:30791938"].text
    assert text is not None
    assert "BACKGROUND:" in text
    assert "CASE PRESENTATION:" in text
    assert "CONCLUSIONS:" in text
    # Structured blocks are separated by a blank line.
    assert "\n\n" in text


def test_parse_batch_simple_abstract_is_nonempty_str():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    text = results["PMID:10484768"].text
    assert isinstance(text, str)
    assert text.strip() != ""
    # A simple unlabeled abstract has no label prefix.
    assert "BACKGROUND:" not in text


def test_parse_batch_all_entries_are_abstractresult():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    for pmid, entry in results.items():
        assert isinstance(entry, AbstractResult)
        assert entry.pmid == pmid


def test_parse_batch_publication_types():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    types = results["PMID:30791938"].publication_types
    assert isinstance(types, tuple)
    assert "Review" in types
    assert "Case Reports" in types


def test_parse_single_32574212_has_abstract():
    results = parse_efetch_xml(_read("efetch_32574212.xml"))
    assert "PMID:32574212" in results
    text = results["PMID:32574212"].text
    assert isinstance(text, str)
    assert text.strip() != ""


def test_parse_no_abstract_yields_none():
    results = parse_efetch_xml(_read("efetch_no_abstract.xml"))
    assert "PMID:9876543" in results
    assert results["PMID:9876543"].text is None


def test_parse_accepts_str_input():
    raw = (FIX / "efetch_batch.xml").read_text(encoding="utf-8")
    results = parse_efetch_xml(raw)
    assert len(results) == 3


def test_parse_keys_are_normalized():
    results = parse_efetch_xml(_read("efetch_batch.xml"))
    for key in results:
        assert key.startswith("PMID:")
        assert key.replace("PMID:", "").isdigit()


def test_parse_empty_set_returns_empty_dict():
    xml = b"<?xml version='1.0'?><PubmedArticleSet></PubmedArticleSet>"
    assert parse_efetch_xml(xml) == {}


class _FakeResponse:
    def __init__(self, text: str):
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def text(self) -> str:
        return self._text


class _FakeSession:
    def __init__(self, text: str):
        self._text = text
        self.calls: list[dict] = []

    def post(self, url, *, data, timeout):
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        return _FakeResponse(self._text)


@pytest.mark.asyncio
async def test_fetch_abstracts_single_batch():
    session = _FakeSession((FIX / "efetch_batch.xml").read_text(encoding="utf-8"))
    results = await fetch_abstracts(
        ["PMID:30791938", "10484768", "PMID:11085914"],
        session=session,
        base_url="https://example.test/efetch.fcgi",
    )
    assert set(results) == {"PMID:30791938", "PMID:10484768", "PMID:11085914"}
    assert len(session.calls) == 1
    sent = session.calls[0]["data"]
    assert sent["db"] == "pubmed"
    assert sent["retmode"] == "xml"
    assert sent["rettype"] == "abstract"
    # Prefix stripped before sending.
    assert sent["id"] == "30791938,10484768,11085914"
    assert "api_key" not in sent


@pytest.mark.asyncio
async def test_fetch_abstracts_passes_api_key():
    session = _FakeSession((FIX / "efetch_32574212.xml").read_text(encoding="utf-8"))
    await fetch_abstracts(
        ["32574212"],
        session=session,
        base_url="https://example.test/efetch.fcgi",
        api_key="secret",
    )
    assert session.calls[0]["data"]["api_key"] == "secret"


@pytest.mark.asyncio
async def test_fetch_abstracts_batches_by_size():
    session = _FakeSession((FIX / "efetch_batch.xml").read_text(encoding="utf-8"))
    await fetch_abstracts(
        ["1", "2", "3", "4", "5"],
        session=session,
        base_url="https://example.test/efetch.fcgi",
        batch_size=2,
    )
    # 5 ids, batch_size 2 -> 3 requests.
    assert len(session.calls) == 3
    assert session.calls[0]["data"]["id"] == "1,2"
    assert session.calls[2]["data"]["id"] == "5"


@pytest.mark.asyncio
async def test_fetch_abstracts_empty_input_skips_io():
    session = _FakeSession("")
    results = await fetch_abstracts(
        [],
        session=session,
        base_url="https://example.test/efetch.fcgi",
    )
    assert results == {}
    assert session.calls == []
