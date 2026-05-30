"""Shared dataclasses and constants for the publication full-text RAG stack.

Every other module in :mod:`app.publications.fulltext` imports its data
contracts from here so the pure (fixture-tested) parsers, the DB persistence
layer, and the retrieval/orchestration glue all agree on field names and types.

Nothing in this module performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

# --- Canonical taxonomy ----------------------------------------------------

#: Coverage tier for a publication, in descending richness.
Coverage = Literal["full_text", "abstract_only", "title_only"]

#: Canonical passage section labels. The ``references`` section is never stored;
#: tables are stored as ``"table"``. The order here is also the document order
#: used for global ``seq`` assignment and for section-rank boosts.
SECTION_ORDER: tuple[str, ...] = (
    "title",
    "abstract",
    "intro",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "table",
)

#: Mapping from PubTator BioC ``infons.section_type`` (upper-case) to our
#: canonical section label. Section types not present here are skipped
#: (e.g. ``REF``, ``SUPPL``, ``FIG``, ``APPENDIX``, ``COMP_INT``).
BIOC_SECTION_MAP: dict[str, str] = {
    "TITLE": "title",
    "ABSTRACT": "abstract",
    "INTRO": "intro",
    "METHODS": "methods",
    "RESULTS": "results",
    "DISCUSS": "discussion",
    "CONCL": "conclusion",
    "TABLE": "table",
}

#: Provenance label stored on each passage row (``publication_fulltext.source``).
PassageSource = Literal[
    "pubtator_full_bioc",
    "europe_pmc_jats",
    "pubmed_efetch_abstract",
]


# --- Fetch / parse results -------------------------------------------------


@dataclass
class AbstractResult:
    """Parsed abstract for a single publication.

    Attributes:
        pmid: Normalized PMID (``"PMID:NNNNN"``).
        text: Joined abstract text (structured labels prefixed and
            blank-line separated, e.g. ``"BACKGROUND: ..."`` then
            ``"METHODS: ..."``), or ``None`` when the publication has no
            abstract in PubMed.
        publication_types: PubMed publication types (e.g. ``("Review",)``);
            empty when not parsed.
    """

    pmid: str
    text: Optional[str]
    publication_types: tuple[str, ...] = ()


@dataclass
class RawSection:
    """A contiguous section block extracted from a full-text source (pre-chunking).

    Attributes:
        section: Canonical section label (a member of :data:`SECTION_ORDER`).
        text: The section's text (original capitalization/punctuation preserved).
        order: 0-based position of this block within the source document, used
            to assign a stable global ordering before chunking.
    """

    section: str
    text: str
    order: int


@dataclass
class FullTextResult:
    """Resolved full-text payload for a publication, before the license gate.

    Attributes:
        pmid: Normalized PMID.
        pmcid: PMC accession (``"PMC..."``) or ``None``.
        license: Normalized license token (e.g. ``"CC-BY"``) or ``None``.
        is_open_access: EuropePMC ``isOpenAccess == "Y"``.
        sections: Ordered body sections (references already excluded).
        source: Provenance of ``sections`` (a :data:`PassageSource` value).
    """

    pmid: str
    pmcid: Optional[str]
    license: Optional[str]
    is_open_access: bool
    sections: tuple[RawSection, ...] = ()
    source: str = "pubtator_full_bioc"


# --- Coverage decision -----------------------------------------------------


@dataclass
class CoverageDecision:
    """Outcome of the license gate + coverage tiering for one publication.

    Attributes:
        coverage: The assigned :data:`Coverage` tier.
        license: Normalized license token recorded on the publication.
        pmcid: PMC accession recorded on the publication, if any.
        sections: Body sections that survived the license gate (empty unless
            ``coverage == "full_text"``).
        source: Provenance of the kept sections.
    """

    coverage: Coverage
    license: Optional[str]
    pmcid: Optional[str]
    sections: tuple[RawSection, ...] = ()
    source: Optional[str] = None


# --- Chunking / persistence ------------------------------------------------


@dataclass
class Chunk:
    """A token-windowed chunk of a single section.

    Attributes:
        section: Canonical section label.
        idx: 0-based chunk index *within its section* (used in ``passage_id``).
        text: The exact original substring (offset-recovered, not re-detokenized).
        char_count: ``len(text)``.
        token_count: Number of tokens in the chunk per the active tokenizer.
    """

    section: str
    idx: int
    text: str
    char_count: int
    token_count: int


@dataclass
class PassageRow:
    """A persistence-ready passage row for ``publication_fulltext``.

    Attributes:
        pmid: Normalized PMID.
        passage_id: ``"<PMID:bare>:<section>:<idx>"`` (<= 120 chars).
        section: Canonical section label.
        seq: 0-based global ordering within the publication.
        text: Passage text.
        char_count: ``len(text)``.
        token_count: Token count for the passage.
        source: Provenance (a :data:`PassageSource` value).
    """

    pmid: str
    passage_id: str
    section: str
    seq: int
    text: str
    char_count: int
    token_count: int
    source: str


# --- Retrieval -------------------------------------------------------------


@dataclass
class RetrievedPassage:
    """A passage returned by hybrid retrieval, with fusion diagnostics.

    Attributes:
        pmid: Normalized PMID.
        passage_id: Stable passage identifier (citation anchor).
        section: Canonical section label.
        seq: Global ordering within the publication.
        text: Full passage text (``None`` in ``ids_only`` mode).
        snippet: ``ts_headline`` snippet (set in ``brief`` mode).
        char_count: ``len`` of the stored passage text.
        token_count: Token count of the stored passage.
        source: Provenance.
        score: Final fused score (RRF + boosts), higher is better.
        lexical_rank: 1-based rank in the lexical leg, or ``None`` if absent.
        dense_rank: 1-based rank in the dense leg, or ``None`` if absent.
    """

    pmid: str
    passage_id: str
    section: str
    seq: int
    char_count: int
    token_count: int
    source: str
    score: float
    text: Optional[str] = None
    snippet: Optional[str] = None
    lexical_rank: Optional[int] = None
    dense_rank: Optional[int] = None


@dataclass
class RetrievalResult:
    """Ranked passages plus diagnostics for the ``_meta`` block.

    Attributes:
        passages: Fused, ranked passages (best first).
        rerank_used: The rerank mode actually applied (``rrf|lexical|off``).
        lexical_candidate_count: Candidates pulled by the lexical leg.
        dense_candidate_count: Candidates pulled by the dense leg (0 if disabled).
        embedding_dim: Embedding dimension when dense was used, else ``None``.
        embeddings_available: Whether the dense (semantic) leg was actually
            operational for this query — ``True`` IFF an embedding provider was
            present AND embeddings are stored for the configured model. ``False``
            otherwise (no provider, no stored embeddings, or a non-``rrf``
            request), making a silent "hybrid"->lexical degradation explicit.
        truncated: Whether results were cut to satisfy ``max_chars``/``limit``.
        notes: Human-readable diagnostics (e.g. dense fallback reason).
    """

    passages: list[RetrievedPassage] = field(default_factory=list)
    rerank_used: str = "lexical"
    lexical_candidate_count: int = 0
    dense_candidate_count: int = 0
    embedding_dim: Optional[int] = None
    embeddings_available: bool = False
    truncated: bool = False
    notes: tuple[str, ...] = ()


def make_passage_id(pmid: str, section: str, idx: int) -> str:
    """Build the stable ``passage_id`` for a chunk.

    Args:
        pmid: Normalized PMID (``"PMID:NNNNN"``) or bare digits.
        section: Canonical section label.
        idx: 0-based chunk index within the section.

    Returns:
        ``"PMID:<bare>:<section>:<idx>"`` (<= 120 chars), e.g.
        ``"PMID:32574212:methods:3"``.
    """
    bare = pmid.replace("PMID:", "")
    return f"PMID:{bare}:{section}:{idx}"
