"""Pydantic models for the publications endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuthorModel(BaseModel):
    """Author information."""

    name: str
    affiliation: Optional[str] = None


class PublicationMetadataResponse(BaseModel):
    """Publication metadata response model."""

    pmid: str = Field(..., description="PubMed ID in format PMID:12345678")
    title: str = Field(..., description="Publication title")
    authors: list[AuthorModel] = Field(
        ..., description="List of authors with affiliations"
    )
    journal: Optional[str] = Field(None, description="Journal name")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI identifier")
    abstract: Optional[str] = Field(None, description="Abstract text (may be null)")
    data_source: str = Field(default="PubMed", description="Data source")
    fetched_at: str = Field(..., description="Storage timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pmid": "PMID:30791938",
                "title": (
                    "HNF1B-related disorder: clinical characteristics and "
                    "genetic findings"
                ),
                "authors": [
                    {"name": "Smith J", "affiliation": "Department of Medicine"},
                    {"name": "Doe A", "affiliation": "Department of Genetics"},
                ],
                "journal": "Journal of Medical Genetics",
                "year": 2019,
                "doi": "10.1136/jmedgenet-2018-105729",
                "abstract": None,
                "data_source": "PubMed",
                "fetched_at": "2025-10-22T14:30:00",
            }
        }
    )


class PublicationListItem(BaseModel):
    """Publication item for list endpoint."""

    pmid: str = Field(..., description="PubMed ID (without PMID: prefix)")
    title: Optional[str] = Field(None, description="Publication title")
    authors: Optional[str] = Field(None, description="Formatted author string")
    journal: Optional[str] = Field(None, description="Journal name")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI identifier")
    phenopacket_count: int = Field(..., description="Number of associated phenopackets")
    first_added: Optional[str] = Field(None, description="When first added to database")
    abstract: Optional[str] = Field(None, description="Abstract text (may be null)")
    coverage: str = Field(
        "title_only",
        description="Retrieval tier: full_text | abstract_only | title_only",
    )
    pmcid: Optional[str] = Field(None, description="PMC accession (open access)")
    license: Optional[str] = Field(None, description="Normalized license token")
    has_full_text: bool = Field(
        False, description="Whether license-gated full-text passages are stored"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pmid": "30791938",
                "title": "HNF1B-related disorder: clinical characteristics",
                "authors": "Smith J et al.",
                "journal": "J Med Genet",
                "year": 2019,
                "doi": "10.1136/jmedgenet-2018-105729",
                "phenopacket_count": 42,
                "first_added": "2024-01-15T10:30:00",
                "abstract": "HNF1B variants cause a multisystem disorder...",
                "coverage": "full_text",
                "pmcid": "PMC6385394",
                "license": "CC-BY",
                "has_full_text": True,
            }
        }
    )


class PassageHit(BaseModel):
    """A single ranked passage returned by the passage-retrieval endpoint."""

    passage_id: str = Field(
        ..., description="Stable passage identifier / citation anchor"
    )
    pmid: str = Field(..., description="PubMed ID in PMID: form")
    section: str = Field(..., description="Canonical section label")
    seq: int = Field(..., description="Global passage order within the publication")
    score: float = Field(..., description="Fused relevance score (higher is better)")
    source: str = Field(..., description="Passage provenance")
    char_count: int = Field(..., description="Character length of the stored passage")
    token_count: int = Field(..., description="Token count of the stored passage")
    text: Optional[str] = Field(None, description="Full passage text (full mode)")
    snippet: Optional[str] = Field(None, description="Highlighted snippet (brief mode)")
    lexical_rank: Optional[int] = Field(None, description="1-based lexical-leg rank")
    dense_rank: Optional[int] = Field(None, description="1-based dense-leg rank")


class PassagesMeta(BaseModel):
    """Diagnostics for a passage-retrieval response."""

    query: str = Field(..., description="The query that was executed")
    mode: str = Field(..., description="Text mode: full | brief | ids_only")
    rerank_used: str = Field(..., description="Rerank strategy actually applied")
    total: int = Field(..., description="Number of passages returned")
    lexical_candidate_count: int = Field(..., description="Lexical-leg candidate count")
    dense_candidate_count: int = Field(..., description="Dense-leg candidate count")
    embedding_dim: Optional[int] = Field(
        default=None, description="Dense embedding dim, if used"
    )
    truncated: bool = Field(False, description="Whether results were budget-truncated")
    notes: list[str] = Field(default_factory=list, description="Diagnostic notes")


class PassagesResponse(BaseModel):
    """Ranked passages plus retrieval diagnostics."""

    passages: list[PassageHit] = Field(..., description="Ranked passages, best first")
    meta: PassagesMeta = Field(..., description="Retrieval diagnostics")


class SyncResponse(BaseModel):
    """Response for sync operation.

    The endpoint returns immediately with the pre-sync counts
    (``total_pmids``/``already_stored``/``to_fetch``); the per-publication
    fetch counts (abstracts/full text/license-skipped/errors) are produced by
    the background task and the backfill script and surface in logs / the
    script summary. They are included here as optional fields for synchronous
    callers (e.g. the backfill script's structured summary).
    """

    status: str = Field(..., description="Status of the operation")
    message: str = Field(..., description="Human-readable message")
    total_pmids: Optional[int] = Field(None, description="Total PMIDs to sync")
    already_stored: Optional[int] = Field(None, description="PMIDs already stored")
    to_fetch: Optional[int] = Field(None, description="PMIDs to fetch from PubMed")
    abstracts_fetched: Optional[int] = Field(
        default=None, description="Abstracts stored"
    )
    full_text_fetched: Optional[int] = Field(
        default=None, description="Full-text pubs stored"
    )
    license_skipped: Optional[int] = Field(
        default=None, description="Body dropped by license gate"
    )
    errors: Optional[int] = Field(default=None, description="Per-publication failures")
