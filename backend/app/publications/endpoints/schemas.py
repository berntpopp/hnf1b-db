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
    phenopacket_count: int = Field(
        ..., description="Number of associated phenopackets"
    )
    first_added: Optional[str] = Field(
        None, description="When first added to database"
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
            }
        }
    )


class SyncResponse(BaseModel):
    """Response for sync operation."""

    status: str = Field(..., description="Status of the operation")
    message: str = Field(..., description="Human-readable message")
    total_pmids: Optional[int] = Field(None, description="Total PMIDs to sync")
    already_stored: Optional[int] = Field(None, description="PMIDs already stored")
    to_fetch: Optional[int] = Field(None, description="PMIDs to fetch from PubMed")
