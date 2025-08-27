# app/models.py
"""SQLAlchemy models for PostgreSQL database."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ------------------------------------------------------------------------------
# User model - System users/reviewers
class User(Base):
    """System users/reviewers model."""
    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core user fields
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    user_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_role: Mapped[str] = mapped_column(String(50))
    first_name: Mapped[str] = mapped_column(String(100))
    family_name: Mapped[str] = mapped_column(String(100))
    orcid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    reviewed_reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="reviewer"
    )
    assigned_publications: Mapped[List["Publication"]] = relationship(
        "Publication", back_populates="assignee"
    )


# ------------------------------------------------------------------------------
# Individual model - Patient demographics
class Individual(Base):
    """Patient demographics model."""
    __tablename__ = "individuals"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core individual fields
    individual_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    sex: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    individual_doi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dup_check: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    individual_identifier: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    problematic: Mapped[str] = mapped_column(String(500), default="")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="individual", cascade="all, delete-orphan"
    )
    variants: Mapped[List["Variant"]] = relationship(
        "Variant", secondary="individual_variants", back_populates="individuals"
    )


# ------------------------------------------------------------------------------
# Report model - Clinical presentations (separated from Individual for normalization)
class Report(Base):
    """Clinical presentations model."""
    __tablename__ = "reports"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign keys
    individual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("individuals.id", ondelete="CASCADE")
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    publication_ref: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("publications.id"), nullable=True
    )

    # Core report fields
    report_id: Mapped[str] = mapped_column(String(20), index=True)
    phenotypes: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict
    )  # Store phenotypes as JSONB
    review_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    report_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    family_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    age_reported: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    age_onset: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cohort: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    individual: Mapped["Individual"] = relationship(
        "Individual", back_populates="reports"
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User", back_populates="reviewed_reports"
    )
    publication: Mapped[Optional["Publication"]] = relationship("Publication")


# ------------------------------------------------------------------------------
# Individual-Variant association table (many-to-many)
class IndividualVariant(Base):
    """Individual-Variant association model."""
    __tablename__ = "individual_variants"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign keys
    individual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("individuals.id", ondelete="CASCADE")
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE")
    )

    # Association-specific fields
    detection_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    segregation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # For variant versioning

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ------------------------------------------------------------------------------
# Variant model - Genetic variants
class Variant(Base):
    """Genetic variants model."""
    __tablename__ = "variants"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core variant fields
    variant_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True
    )  # For versioning

    # Genomic coordinates and variant info
    variant_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hg19: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hg38: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hg19_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hg38_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    individuals: Mapped[List["Individual"]] = relationship(
        "Individual", secondary="individual_variants", back_populates="variants"
    )
    classifications: Mapped[List["VariantClassification"]] = relationship(
        "VariantClassification", back_populates="variant", cascade="all, delete-orphan"
    )
    annotations: Mapped[List["VariantAnnotation"]] = relationship(
        "VariantAnnotation", back_populates="variant", cascade="all, delete-orphan"
    )
    reported_entries: Mapped[List["ReportedEntry"]] = relationship(
        "ReportedEntry", back_populates="variant", cascade="all, delete-orphan"
    )


# ------------------------------------------------------------------------------
# VariantClassification model - Variant classifications
class VariantClassification(Base):
    """Variant classifications model."""
    __tablename__ = "variant_classifications"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE")
    )

    # Classification fields
    verdict: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    classification_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    variant: Mapped["Variant"] = relationship(
        "Variant", back_populates="classifications"
    )


# ------------------------------------------------------------------------------
# VariantAnnotation model - Variant annotations
class VariantAnnotation(Base):
    """Variant annotations model."""
    __tablename__ = "variant_annotations"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE")
    )

    # Annotation fields
    transcript: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    c_dot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    p_dot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    effect: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variant_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    annotation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    variant: Mapped["Variant"] = relationship("Variant", back_populates="annotations")


# ------------------------------------------------------------------------------
# ReportedEntry model - Reported variant entries
class ReportedEntry(Base):
    """Reported variant entries model."""
    __tablename__ = "reported_entries"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign keys
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE")
    )
    publication_ref: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("publications.id"), nullable=True
    )

    # Reported entry fields
    variant_reported: Mapped[str] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    variant: Mapped["Variant"] = relationship(
        "Variant", back_populates="reported_entries"
    )
    publication: Mapped[Optional["Publication"]] = relationship("Publication")


# ------------------------------------------------------------------------------
# Publication model - Research papers
class Publication(Base):
    """Research papers model."""
    __tablename__ = "publications"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Core publication fields
    publication_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    publication_alias: Mapped[str] = mapped_column(String(100))
    publication_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    publication_entry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime(2021, 11, 1)
    )

    # External identifiers
    pmid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    doi: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pdf: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Publication metadata
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    journal_abbreviation: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    journal: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    keywords: Mapped[List[str]] = mapped_column(JSONB, default=list)
    medical_specialty: Mapped[List[str]] = mapped_column(JSONB, default=list)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    assignee: Mapped[Optional["User"]] = relationship(
        "User", back_populates="assigned_publications"
    )
    authors: Mapped[List["Author"]] = relationship(
        "Author", back_populates="publication", cascade="all, delete-orphan"
    )


# ------------------------------------------------------------------------------
# Author model - Publication authors
class Author(Base):
    """Publication authors model."""
    __tablename__ = "authors"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE")
    )

    # Author fields
    lastname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    firstname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    initials: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    affiliations: Mapped[List[str]] = mapped_column(JSONB, default=list)
    author_order: Mapped[int] = mapped_column(
        Integer, default=0
    )  # For maintaining author order

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    publication: Mapped["Publication"] = relationship(
        "Publication", back_populates="authors"
    )


# ------------------------------------------------------------------------------
# Protein model - Protein structure data
class Protein(Base):
    """Protein structure and domains model."""
    __tablename__ = "proteins"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core protein fields
    gene: Mapped[str] = mapped_column(String(50), index=True)
    transcript: Mapped[str] = mapped_column(String(50))
    protein: Mapped[str] = mapped_column(String(50), index=True)
    features: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict
    )  # Store complex feature data as JSONB

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ------------------------------------------------------------------------------
# Gene model - Gene structure data
class Gene(Base):
    """Gene structure model."""
    __tablename__ = "genes"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Core gene fields
    gene_symbol: Mapped[str] = mapped_column(String(50), index=True)
    ensembl_gene_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    transcript: Mapped[str] = mapped_column(String(50))
    exons: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, default=list
    )  # Store exon data as JSONB
    hg38: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict
    )  # Genomic coordinates
    hg19: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict
    )  # Legacy coordinates

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
