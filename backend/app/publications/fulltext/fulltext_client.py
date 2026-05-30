"""PMCID resolution and open-access full-text fetching for publications.

This module pairs pure, fixture-tested parsers for the external services we
rely on (the NCBI PMC ID converter, PubTator3 BioC, EuropePMC search core, and
EuropePMC JATS ``fullTextXML``) with thin asynchronous I/O wrappers that drive
those parsers over an injected :class:`aiohttp.ClientSession`.

License normalization is intentionally *not* handled here: the parsers return
raw license strings exactly as the upstream service reports them, and the
caller (``coverage.py``) maps them onto the canonical taxonomy.
"""

from __future__ import annotations

from collections.abc import Iterable

from lxml import etree  # type: ignore[import-untyped]

from app.publications.fulltext.types import (
    BIOC_SECTION_MAP,
    FullTextResult,
    RawSection,
)

# --- JATS section heuristics ----------------------------------------------

#: Ordered substring heuristics mapping a JATS section title (lower-cased) or
#: ``sec-type`` onto a canonical section label. The first match wins, so more
#: specific markers should precede broader ones.
_JATS_TITLE_HEURISTICS: tuple[tuple[str, str], ...] = (
    ("introduc", "intro"),
    ("method", "methods"),
    ("result", "results"),
    ("discus", "discussion"),
    ("conclus", "conclusion"),
)


# --- Pure parsers ----------------------------------------------------------


def parse_idconv(data: dict) -> dict[str, str | None]:
    """Parse an NCBI PMC ID-converter JSON payload into a PMID -> PMCID map.

    Args:
        data: Decoded JSON from the PMC ID converter. The ``"records"`` list
            holds one record per requested id, each carrying a ``"pmid"``
            (int or str) and, when resolvable, a ``"pmcid"``. Records flagged
            with ``"status": "error"`` (or missing a ``pmcid``) are unresolved.

    Returns:
        A mapping from bare digit PMID string to the resolved PMCID, or
        ``None`` when the PMID has no open-access PMC record.
    """
    out: dict[str, str | None] = {}
    for record in data.get("records", []):
        pmid = record.get("pmid")
        if pmid is None:
            continue
        bare = str(pmid)
        if record.get("status") == "error":
            out[bare] = None
            continue
        out[bare] = record.get("pmcid") or None
    return out


def parse_bioc(data: dict) -> FullTextResult:
    """Parse a PubTator3 BioC JSON payload into a :class:`FullTextResult`.

    Passages whose ``infons.section_type`` is absent from
    :data:`~app.publications.fulltext.types.BIOC_SECTION_MAP` are dropped
    (this removes references, supplements, and figure passages). The
    ``license`` and ``is_open_access`` fields are left unset here and are
    filled in by the caller from the EuropePMC core record.

    Args:
        data: Decoded BioC JSON. The single document lives at
            ``data["PubTator3"][0]``.

    Returns:
        A :class:`FullTextResult` whose ``sections`` preserve document order,
        with a 0-based ``order`` assigned over the *kept* passages only.
    """
    doc = data["PubTator3"][0]
    pmid_raw, pmcid = _bioc_ids(doc)

    sections: list[RawSection] = []
    order = 0
    for passage in doc.get("passages", []):
        infons = passage.get("infons") or {}
        section_type = (infons.get("section_type") or "").upper()
        canonical = BIOC_SECTION_MAP.get(section_type)
        if canonical is None:
            continue
        text = passage.get("text") or ""
        if not text:
            continue
        sections.append(RawSection(section=canonical, text=text, order=order))
        order += 1

    return FullTextResult(
        pmid=f"PMID:{pmid_raw}",
        pmcid=pmcid,
        license=None,
        is_open_access=False,
        sections=tuple(sections),
        source="pubtator_full_bioc",
    )


def _bioc_ids(doc: dict) -> tuple[str, str | None]:
    """Derive the bare PMID and PMCID from a BioC document.

    Prefers the explicit ``pmid``/``pmcid`` fields and falls back to splitting
    the composite ``_id`` (formatted like ``"32574212|PMC7310724"``).

    Args:
        doc: The BioC document object.

    Returns:
        A ``(bare_pmid, pmcid_or_none)`` tuple.
    """
    pmid = doc.get("pmid")
    pmcid = doc.get("pmcid")
    composite = doc.get("_id") or ""
    parts = composite.split("|")
    if pmid is None and parts and parts[0]:
        pmid = parts[0]
    if not pmcid and len(parts) > 1 and parts[1]:
        pmcid = parts[1]
    bare = str(pmid) if pmid is not None else ""
    return bare, (pmcid or None)


def parse_europepmc_core(data: dict) -> tuple[bool, str | None]:
    """Parse an EuropePMC search ``core`` result into OA + raw license.

    Args:
        data: Decoded EuropePMC search JSON. The first hit (if any) is at
            ``data["resultList"]["result"][0]``.

    Returns:
        A ``(is_open_access, raw_license)`` tuple. ``is_open_access`` is
        ``True`` only when the record's ``isOpenAccess`` equals ``"Y"``.
        ``raw_license`` is the upstream string verbatim (e.g. ``"cc by"``) or
        ``None``. An empty result list yields ``(False, None)``.
    """
    results = data.get("resultList", {}).get("result", [])
    if not results:
        return (False, None)
    result = results[0]
    is_open_access = result.get("isOpenAccess") == "Y"
    raw_license = result.get("license")
    return (is_open_access, raw_license)


def parse_jats(xml: bytes | str) -> tuple[RawSection, ...]:
    """Best-effort parse of EuropePMC JATS ``fullTextXML`` into sections.

    This is a rarely-used fallback path, so it never raises on malformed or
    incomplete documents: anything unparseable yields an empty tuple. Body
    ``<sec>`` nodes are mapped onto canonical labels via their ``sec-type`` or
    ``<title>`` text, and ``<table-wrap>`` captions are emitted as ``"table"``
    sections. Reference lists and back matter are skipped.

    Args:
        xml: The raw JATS document as bytes or text.

    Returns:
        Ordered :class:`RawSection` objects in document order, or an empty
        tuple when nothing parseable is found.
    """
    root = _parse_xml(xml)
    if root is None:
        return ()

    sections: list[RawSection] = []
    order = 0
    body = root.find(".//body")
    if body is None:
        return ()

    for node in body.iter():
        tag = etree.QName(node).localname if node.tag is not etree.Comment else ""
        if tag == "sec":
            canonical = _jats_section_label(node)
            if canonical is None:
                continue
            text = _jats_sec_text(node)
            if not text:
                continue
            sections.append(RawSection(section=canonical, text=text, order=order))
            order += 1
        elif tag == "table-wrap":
            text = _jats_table_text(node)
            if not text:
                continue
            sections.append(RawSection(section="table", text=text, order=order))
            order += 1

    return tuple(sections)


def _parse_xml(xml: bytes | str) -> etree._Element | None:
    """Parse XML defensively, returning ``None`` on any failure.

    Args:
        xml: The raw document as bytes or text.

    Returns:
        The root element, or ``None`` if parsing failed or produced no tree.
    """
    try:
        if isinstance(xml, str):
            xml = xml.encode("utf-8")
        parser = etree.XMLParser(recover=True, resolve_entities=False)
        root = etree.fromstring(xml, parser=parser)
    except (etree.XMLSyntaxError, ValueError):
        return None
    return root


def _jats_section_label(sec: etree._Element) -> str | None:
    """Map a JATS ``<sec>`` onto a canonical section label.

    Args:
        sec: The ``<sec>`` element.

    Returns:
        A canonical section label, or ``None`` if the section is unrecognized.
    """
    candidates = []
    sec_type = sec.get("sec-type")
    if sec_type:
        candidates.append(sec_type.lower())
    title = sec.find("title")
    if title is not None and title.text:
        candidates.append(title.text.lower())
    for candidate in candidates:
        for marker, label in _JATS_TITLE_HEURISTICS:
            if marker in candidate:
                return label
    return None


def _jats_sec_text(sec: etree._Element) -> str:
    """Join the paragraph text directly under a JATS ``<sec>``.

    Args:
        sec: The ``<sec>`` element.

    Returns:
        The concatenated ``<p>`` text, stripped; empty when no paragraphs.
    """
    parts = []
    for para in sec.findall("p"):
        parts.append("".join(para.itertext()))
    return " ".join(part.strip() for part in parts if part.strip()).strip()


def _jats_table_text(table_wrap: etree._Element) -> str:
    """Collect label and caption text from a JATS ``<table-wrap>``.

    Args:
        table_wrap: The ``<table-wrap>`` element.

    Returns:
        The joined label/caption text, stripped; empty when neither exists.
    """
    parts = []
    label = table_wrap.find("label")
    if label is not None:
        parts.append("".join(label.itertext()))
    caption = table_wrap.find("caption")
    if caption is not None:
        parts.append("".join(caption.itertext()))
    return " ".join(part.strip() for part in parts if part.strip()).strip()


# --- Async I/O wrappers ----------------------------------------------------


async def resolve_pmcids(
    pmids: Iterable[str],
    *,
    session,
    base_url: str,
    tool: str,
    email: str,
    batch_size: int = 200,
    timeout: float = 30.0,
) -> dict[str, str | None]:
    """Resolve bare PMIDs to PMCIDs via the NCBI PMC ID converter.

    PMIDs are requested in batches and the per-batch results are merged.

    Args:
        pmids: Bare digit PMID strings to resolve.
        session: An injected :class:`aiohttp.ClientSession`.
        base_url: The ID-converter endpoint URL.
        tool: The ``tool`` query parameter (NCBI etiquette).
        email: The ``email`` query parameter (NCBI etiquette).
        batch_size: Maximum number of ids per request.
        timeout: Per-request timeout in seconds.

    Returns:
        A merged mapping from bare PMID to PMCID (or ``None`` when unresolved).
    """
    ids = [str(pmid) for pmid in pmids]
    out: dict[str, str | None] = {}
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        params = {
            "ids": ",".join(batch),
            "format": "json",
            "tool": tool,
            "email": email,
        }
        async with session.get(base_url, params=params, timeout=timeout) as resp:
            data = await resp.json()
        out.update(parse_idconv(data))
    return out


async def fetch_bioc(
    pmid: str,
    *,
    session,
    base_url: str,
    timeout: float = 60.0,
) -> FullTextResult | None:
    """Fetch and parse full-text BioC for a single PMID.

    Args:
        pmid: PMID in either ``"PMID:NNNNN"`` or bare digit form.
        session: An injected :class:`aiohttp.ClientSession`.
        base_url: The PubTator3 BioC endpoint URL.
        timeout: Request timeout in seconds.

    Returns:
        A :class:`FullTextResult`, or ``None`` when the response is unusable or
        yields no body sections.
    """
    digits = str(pmid).replace("PMID:", "")
    params = {"pmids": digits, "full": "true"}
    async with session.get(base_url, params=params, timeout=timeout) as resp:
        if resp.status != 200:
            return None
        data = await resp.json()
    try:
        result = parse_bioc(data)
    except (KeyError, IndexError, TypeError):
        return None
    if not result.sections:
        return None
    return result


async def fetch_europepmc_core(
    pmid: str,
    *,
    session,
    base_url: str,
    timeout: float = 30.0,
) -> tuple[bool, str | None]:
    """Fetch the EuropePMC ``core`` record for a PMID and parse OA + license.

    Args:
        pmid: PMID in either ``"PMID:NNNNN"`` or bare digit form.
        session: An injected :class:`aiohttp.ClientSession`.
        base_url: The EuropePMC REST base URL (``/search`` is appended).
        timeout: Request timeout in seconds.

    Returns:
        A ``(is_open_access, raw_license)`` tuple; ``(False, None)`` on misses.
    """
    digits = str(pmid).replace("PMID:", "")
    params = {
        "query": f"ext_id:{digits} AND src:MED",
        "resultType": "core",
        "format": "json",
    }
    url = f"{base_url}/search"
    async with session.get(url, params=params, timeout=timeout) as resp:
        if resp.status != 200:
            return (False, None)
        data = await resp.json()
    return parse_europepmc_core(data)


async def fetch_jats(
    pmcid_or_id: str,
    source: str,
    *,
    session,
    base_url: str,
    timeout: float = 30.0,
) -> tuple[RawSection, ...]:
    """Fetch and parse EuropePMC JATS ``fullTextXML`` for a record.

    Args:
        pmcid_or_id: The record id used in the URL path (e.g. a PMCID).
        source: The EuropePMC source segment (e.g. ``"PMC"`` or ``"MED"``).
        session: An injected :class:`aiohttp.ClientSession`.
        base_url: The EuropePMC REST base URL.
        timeout: Request timeout in seconds.

    Returns:
        Ordered :class:`RawSection` objects, or an empty tuple on any failure.
    """
    url = f"{base_url}/{source}/{pmcid_or_id}/fullTextXML"
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                return ()
            xml = await resp.read()
    except Exception:
        return ()
    return parse_jats(xml)
