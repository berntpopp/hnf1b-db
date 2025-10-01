# app/schemas.py
"""Pydantic schemas for API request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Base schemas
class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }


# User schemas
class UserBase(BaseSchema):
    """Base schema for user data."""

    user_id: int
    user_name: str
    email: str
    user_role: str
    first_name: str
    family_name: str
    orcid: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user creation."""

    password: str


class UserResponse(UserBase):
    """Schema for user response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# Individual schemas
class IndividualBase(BaseSchema):
    """Base schema for individual data."""

    individual_id: str
    sex: Optional[str] = Field(None, alias="Sex")
    individual_doi: Optional[str] = Field(None, alias="individual_DOI")
    dup_check: Optional[str] = Field(None, alias="DupCheck")
    individual_identifier: Optional[str] = Field(None, alias="IndividualIdentifier")
    problematic: str = Field("", alias="Problematic")


class IndividualCreate(IndividualBase):
    """Schema for individual creation."""

    pass


class IndividualResponse(IndividualBase):
    """Schema for individual response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Optional relationship data
    reports: List["ReportResponse"] = []
    variants: List["VariantResponse"] = []


# Report schemas
class ReportBase(BaseSchema):
    """Base schema for report data."""

    report_id: str
    phenotypes: Dict[str, Any] = Field(default_factory=dict)
    review_date: Optional[datetime] = None
    report_date: Optional[datetime] = None
    comment: Optional[str] = None
    family_history: Optional[str] = None
    age_reported: Optional[str] = None
    age_onset: Optional[str] = None
    cohort: Optional[str] = None


class ReportCreate(ReportBase):
    """Schema for report creation."""

    individual_id: uuid.UUID
    reviewed_by: Optional[uuid.UUID] = None
    publication_ref: Optional[uuid.UUID] = None


class ReportResponse(ReportBase):
    """Schema for report response."""

    id: uuid.UUID
    individual_id: uuid.UUID
    reviewed_by: Optional[uuid.UUID] = None
    publication_ref: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    # Optional relationship data
    individual: Optional["IndividualResponse"] = None
    reviewer: Optional["UserResponse"] = None
    publication: Optional["PublicationResponse"] = None


# Variant schemas
class VariantClassificationSchema(BaseSchema):
    """Schema for variant classification data."""

    id: uuid.UUID
    verdict: Optional[str] = None
    criteria: Optional[str] = None
    comment: Optional[str] = None
    system: Optional[str] = None
    classification_date: Optional[datetime] = None


class VariantAnnotationSchema(BaseSchema):
    """Schema for variant annotation data."""

    id: uuid.UUID
    transcript: Optional[str] = None
    c_dot: Optional[str] = None
    p_dot: Optional[str] = None
    source: Optional[str] = None
    annotation_date: Optional[datetime] = None


class ReportedEntrySchema(BaseSchema):
    id: uuid.UUID
    variant_reported: str
    publication_ref: Optional[uuid.UUID] = None


class VariantBase(BaseSchema):
    """Base schema for variant data."""

    variant_id: str
    is_current: bool = True


class VariantCreate(VariantBase):
    """Schema for variant creation."""

    pass


class VariantResponse(VariantBase):
    """Schema for variant response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Embedded relationship data
    classifications: List[VariantClassificationSchema] = []
    annotations: List[VariantAnnotationSchema] = []
    reported_entries: List[ReportedEntrySchema] = Field([], alias="reported")

    # Optional relationship data
    individuals: List["IndividualResponse"] = []


# Publication schemas
class AuthorSchema(BaseSchema):
    lastname: Optional[str] = None
    firstname: Optional[str] = None
    initials: Optional[str] = None
    affiliations: List[str] = []
    author_order: int = 0


class PublicationBase(BaseSchema):
    """Base schema for publication data."""

    publication_id: str
    publication_alias: str
    publication_type: Optional[str] = None
    publication_entry_date: datetime = Field(
        default_factory=lambda: datetime(2021, 11, 1)
    )
    pmid: Optional[int] = Field(None, alias="PMID")
    doi: Optional[str] = Field(None, alias="DOI")
    pdf: Optional[str] = Field(None, alias="PDF")
    title: Optional[str] = None
    abstract: Optional[str] = None
    publication_date: Optional[datetime] = None
    journal_abbreviation: Optional[str] = None
    journal: Optional[str] = None
    keywords: List[str] = []
    medical_specialty: List[str] = []
    comment: Optional[str] = None


class PublicationCreate(PublicationBase):
    """Schema for publication creation."""

    assignee_id: Optional[uuid.UUID] = None
    authors: List[AuthorSchema] = []


class PublicationResponse(PublicationBase):
    """Schema for publication response."""

    id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = Field(None, alias="assignee")
    created_at: datetime
    updated_at: datetime

    # Embedded relationship data
    authors: List[AuthorSchema] = []

    # Optional relationship data
    assignee_user: Optional["UserResponse"] = None


# Protein schemas
class ProteinBase(BaseSchema):
    """Base schema for protein data."""

    gene: str
    transcript: str
    protein: str
    features: Dict[str, Any] = Field(default_factory=dict)


class ProteinCreate(ProteinBase):
    """Schema for protein creation."""

    pass


class ProteinResponse(ProteinBase):
    """Schema for protein response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# Gene schemas
class GeneBase(BaseSchema):
    """Base schema for gene data."""

    gene_symbol: str
    ensembl_gene_id: str
    transcript: str
    exons: List[Dict[str, Any]] = []
    hg38: Dict[str, Any] = {}
    hg19: Dict[str, Any] = {}


class GeneCreate(GeneBase):
    """Schema for gene creation."""

    pass


class GeneResponse(GeneBase):
    """Schema for gene response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# API Response schemas
class PaginationMeta(BaseSchema):
    total: int
    page: int
    page_size: int
    total_pages: int
    links: Dict[str, str] = {}
    execution_time_ms: Optional[float] = None


class PaginatedResponse(BaseSchema):
    data: List[Any]
    meta: PaginationMeta


# Forward references for circular imports
IndividualResponse.model_rebuild()
ReportResponse.model_rebuild()
VariantResponse.model_rebuild()
PublicationResponse.model_rebuild()
