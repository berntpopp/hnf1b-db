"""NCBI efetch abstract fetching and parsing for the full-text RAG stack.

This module exposes a pure parser, :func:`parse_efetch_xml`, that turns an
NCBI ``efetch`` ``PubmedArticleSet`` document into mapped
:class:`~app.publications.fulltext.types.AbstractResult` records, plus a thin
async wrapper, :func:`fetch_abstracts`, that batches ``efetch`` POST requests
over an injected :class:`aiohttp.ClientSession`.

The parser is the main risk surface and is exercised against recorded fixtures.
The async wrapper performs I/O and is integration-tested by the orchestrator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from lxml import etree  # type: ignore[import-untyped]

from app.publications.fulltext.types import AbstractResult

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import aiohttp

#: Blank-line separator between abstract blocks (kept out of docstrings to
#: avoid a literal escape sequence triggering the pydocstyle D301 rule).
_BLOCK_SEPARATOR = "\n\n"


def _normalize_pmid(raw: str) -> str:
    """Normalize bare digits or a prefixed PMID to canonical form.

    Args:
        raw: A PMID as bare digits (``"32574212"``) or already prefixed
            (``"PMID:32574212"``); surrounding whitespace is ignored.

    Returns:
        The canonical ``"PMID:<digits>"`` form.
    """
    digits = raw.strip().replace("PMID:", "")
    return f"PMID:{digits}"


def _extract_abstract_text(article: etree._Element) -> Optional[str]:
    """Extract and join the abstract blocks of a single PubmedArticle.

    Reads every ``.//Abstract/AbstractText`` node, capturing nested markup via
    ``itertext``. Structured blocks carrying a ``Label`` attribute are prefixed
    as ``"LABEL: text"``; blocks are joined by a blank line. Whitespace is
    stripped, and an empty result yields ``None``.

    Args:
        article: A ``PubmedArticle`` element.

    Returns:
        The joined abstract text, or ``None`` when no non-empty text exists.
    """
    blocks: list[str] = []
    for node in article.iterfind(".//Abstract/AbstractText"):
        text = "".join(node.itertext()).strip()
        if not text:
            continue
        label = node.get("Label")
        if label:
            blocks.append(f"{label.strip()}: {text}")
        else:
            blocks.append(text)
    if not blocks:
        return None
    return _BLOCK_SEPARATOR.join(blocks)


def _extract_publication_types(article: etree._Element) -> tuple[str, ...]:
    """Extract the publication-type labels of a single PubmedArticle.

    Args:
        article: A ``PubmedArticle`` element.

    Returns:
        A tuple of publication-type strings in document order; empty when none
        are present.
    """
    types: list[str] = []
    for node in article.iterfind(".//PublicationTypeList/PublicationType"):
        text = "".join(node.itertext()).strip()
        if text:
            types.append(text)
    return tuple(types)


def parse_efetch_xml(xml: Union[bytes, str]) -> dict[str, AbstractResult]:
    """Parse an efetch ``PubmedArticleSet`` into PMID-keyed abstract results.

    Args:
        xml: The raw ``efetch`` response as bytes or a string. A string is
            encoded to UTF-8 before parsing so that lxml does not reject any
            embedded XML declaration.

    Returns:
        A mapping from normalized PMID (``"PMID:<digits>"``) to its
        :class:`~app.publications.fulltext.types.AbstractResult`. Articles
        without a parseable ``MedlineCitation/PMID`` are skipped.
    """
    payload = xml.encode("utf-8") if isinstance(xml, str) else xml
    root = etree.fromstring(payload)

    results: dict[str, AbstractResult] = {}
    for article in root.iterfind(".//PubmedArticle"):
        pmid_text = article.findtext(".//MedlineCitation/PMID")
        if pmid_text is None or not pmid_text.strip():
            continue
        pmid = _normalize_pmid(pmid_text)
        results[pmid] = AbstractResult(
            pmid=pmid,
            text=_extract_abstract_text(article),
            publication_types=_extract_publication_types(article),
        )
    return results


def _bare_pmids(pmids: Iterable[str]) -> list[str]:
    """Strip the ``PMID:`` prefix and drop blanks, preserving order.

    Args:
        pmids: PMIDs with or without the canonical prefix.

    Returns:
        The bare-digit PMIDs, with empty entries removed.
    """
    bare: list[str] = []
    for pmid in pmids:
        digits = pmid.strip().replace("PMID:", "")
        if digits:
            bare.append(digits)
    return bare


async def fetch_abstracts(
    pmids: Sequence[str],
    *,
    session: aiohttp.ClientSession,
    base_url: str,
    api_key: Optional[str] = None,
    batch_size: int = 100,
    timeout: float = 30.0,
) -> dict[str, AbstractResult]:
    """Fetch and parse PubMed abstracts in batched efetch POST requests.

    Args:
        pmids: PMIDs to fetch, with or without the ``PMID:`` prefix.
        session: An injected aiohttp client session used for the POST requests.
        base_url: The efetch endpoint URL.
        api_key: Optional NCBI API key added to the request parameters.
        batch_size: Maximum number of PMIDs sent per request.
        timeout: Per-request timeout in seconds.

    Returns:
        A mapping from normalized PMID to its
        :class:`~app.publications.fulltext.types.AbstractResult`, merged across
        all batches.
    """
    bare = _bare_pmids(pmids)
    if not bare:
        return {}

    step = batch_size if batch_size > 0 else len(bare)
    merged: dict[str, AbstractResult] = {}
    for start in range(0, len(bare), step):
        batch = bare[start : start + step]
        if not batch:
            continue
        params: dict[str, str] = {
            "db": "pubmed",
            "retmode": "xml",
            "rettype": "abstract",
            "id": ",".join(batch),
        }
        if api_key:
            params["api_key"] = api_key
        async with session.post(
            base_url,
            data=params,
            timeout=timeout,
        ) as response:
            xml = await response.text()
        merged.update(parse_efetch_xml(xml))
    return merged
